"""Run destructive-but-recoverable Basic Pitch fault injection against local Compose.

The script creates isolated projects, archives them on exit, restores the original
audio-to-MIDI settings, and returns the Basic Pitch container to its initial state.
It intentionally restarts application containers and pauses/stops the sidecar.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import struct
import subprocess
import sys
import time
import wave
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import httpx

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
COMPOSE_PROFILES = ("--profile", "basic-pitch", "--profile", "ffmpeg")


@dataclass(frozen=True)
class RuntimeSettings:
    provider_name: str
    service_url: str
    provider_timeout_seconds: float
    task_timeout_seconds: int

    def environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.update(
            {
                "AUDIO_TO_MIDI_PROVIDER_NAME": self.provider_name,
                "BASIC_PITCH_SERVICE_URL": self.service_url,
                "BASIC_PITCH_TIMEOUT_SECONDS": str(self.provider_timeout_seconds),
                "TASK_TIMEOUT_SECONDS": str(self.task_timeout_seconds),
            }
        )
        return environment


class FaultMatrix:
    def __init__(self, api_base_url: str, workspace: Path, verbose: bool) -> None:
        self.api_base_url = api_base_url.rstrip("/")
        self.workspace = workspace
        self.verbose = verbose
        self.client = httpx.Client(base_url=self.api_base_url, timeout=15)
        self.project_ids: list[str] = []
        self.results: list[dict[str, Any]] = []

    def close(self) -> None:
        self.client.close()

    def compose(
        self,
        *arguments: str,
        environment: dict[str, str] | None = None,
        check: bool = True,
        timeout: int = 180,
    ) -> subprocess.CompletedProcess[str]:
        command = ["docker", "compose", *COMPOSE_PROFILES, *arguments]
        if self.verbose:
            print("+", " ".join(command), flush=True)
        return subprocess.run(
            command,
            cwd=self.workspace,
            env=environment,
            check=check,
            capture_output=not self.verbose,
            text=True,
            timeout=timeout,
        )

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = self.client.request(method, path, **kwargs)
        if response.is_error:
            raise RuntimeError(
                f"{method} {path} returned {response.status_code}: {response.text[:500]}"
            )
        return response

    def wait_api(self, timeout_seconds: float = 90) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                response = self.client.get("/health/ready")
                if response.status_code == 200 and response.json().get("status") == "ready":
                    return
            except Exception as error:  # noqa: BLE001 - retry boundary
                last_error = error
            time.sleep(1)
        raise RuntimeError(f"API did not become ready: {last_error}")

    def wait_basic_pitch(self, timeout_seconds: float = 180) -> None:
        deadline = time.monotonic() + timeout_seconds
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                response = httpx.get("http://127.0.0.1:8010/health/ready", timeout=3)
                if response.status_code == 200 and response.json().get("status") == "ready":
                    return
            except Exception as error:  # noqa: BLE001 - retry boundary
                last_error = error
            time.sleep(2)
        raise RuntimeError(f"Basic Pitch did not become ready: {last_error}")

    def configure(self, settings: RuntimeSettings) -> None:
        self.compose(
            "up",
            "-d",
            "--force-recreate",
            "api",
            "audio-midi-worker",
            environment=settings.environment(),
            timeout=240,
        )
        self.wait_api()

    def create_fixture(self, scenario: str) -> tuple[str, str, str]:
        project = self.request(
            "POST",
            "/api/v1/projects",
            json={
                "name": f"Basic Pitch fault {scenario} {uuid4()}",
                "description": "Automatically archived fault-injection fixture",
            },
        ).json()
        project_id = str(project["id"])
        self.project_ids.append(project_id)
        intake = self.request(
            "POST",
            f"/api/v1/projects/{project_id}/intake",
            json={
                "idea": (
                    "Chinese indie rock song about riding home late at night. "
                    "Verse restrained and lonely, chorus lifting and hopeful. "
                    "128 BPM, E major, 4/4, 3:30, standard structure."
                )
            },
        ).json()
        song_spec = self.request(
            "POST",
            f"/api/v1/projects/{project_id}/song-spec/generate",
            json={"intake_id": intake["intake_id"]},
        ).json()
        approved = self.request(
            "POST",
            f"/api/v1/projects/{project_id}/song-specs/{song_spec['id']}/approve",
        ).json()
        upload = self.request(
            "POST",
            f"/api/v1/projects/{project_id}/audio-uploads",
            data={"kind": "reference", "notes": f"fault scenario: {scenario}"},
            files={"file": ("a4.wav", build_a4_wav(), "audio/wav")},
        ).json()
        return project_id, str(approved["id"]), str(upload["id"])

    def enqueue(self, project_id: str, song_spec_id: str, upload_id: str) -> str:
        run = self.request(
            "POST",
            f"/api/v1/projects/{project_id}/audio-uploads/{upload_id}/extract-midi",
            json={"song_spec_id": song_spec_id},
        ).json()
        return str(run["id"])

    def task(self, run_id: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            self.request("GET", f"/api/v1/tasks/{run_id}").json(),
        )

    def wait_task(
        self,
        run_id: str,
        expected_statuses: set[str],
        timeout_seconds: float = 90,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        last = self.task(run_id)
        while time.monotonic() < deadline:
            last = self.task(run_id)
            status = str(last["status"])
            if status in expected_statuses:
                return last
            if status in TERMINAL_STATUSES:
                raise AssertionError(
                    f"run {run_id} reached unexpected terminal state {status}: {last}"
                )
            time.sleep(0.5)
        raise TimeoutError(f"run {run_id} did not reach {expected_statuses}: {last}")

    def assert_no_midi(self, project_id: str) -> None:
        assets = self.request("GET", f"/api/v1/projects/{project_id}/midi-assets").json()
        if assets:
            raise AssertionError(f"project {project_id} unexpectedly contains MIDI assets")

    def record(self, scenario: str, started_at: float, task: dict[str, Any]) -> None:
        self.results.append(
            {
                "scenario": scenario,
                "elapsed_seconds": round(time.monotonic() - started_at, 3),
                "run_id": task["id"],
                "status": task["status"],
                "error_code": task.get("error_code"),
            }
        )

    def archive_projects(self) -> None:
        for project_id in self.project_ids:
            with suppress(Exception):
                self.request(
                    "PATCH",
                    f"/api/v1/projects/{project_id}",
                    json={"status": "archived"},
                )


def capture_runtime(matrix: FaultMatrix) -> RuntimeSettings:
    script = (
        "import json; from abachiwave.core.config import get_settings; "
        "s=get_settings(); print(json.dumps({"
        "'provider_name':s.audio_to_midi_provider_name,"
        "'service_url':s.basic_pitch_service_url,"
        "'provider_timeout_seconds':s.basic_pitch_timeout_seconds,"
        "'task_timeout_seconds':s.task_timeout_seconds}))"
    )
    result = matrix.compose("exec", "-T", "api", "python", "-c", script)
    return RuntimeSettings(**json.loads(result.stdout.strip()))


def sidecar_is_running(matrix: FaultMatrix) -> bool:
    result = matrix.compose(
        "ps",
        "--status",
        "running",
        "-q",
        "basic-pitch",
        check=False,
    )
    return bool(result.stdout.strip())


@contextmanager
def paused_sidecar(matrix: FaultMatrix) -> Iterator[None]:
    matrix.compose("pause", "basic-pitch")
    try:
        yield
    finally:
        matrix.compose("unpause", "basic-pitch", check=False)


def expect_failure(task: dict[str, Any], error_code: str) -> None:
    if task["status"] != "failed" or task.get("error_code") != error_code:
        raise AssertionError(f"expected failed/{error_code}, got {task}")


def run_matrix(matrix: FaultMatrix) -> None:
    original = capture_runtime(matrix)
    sidecar_was_running = sidecar_is_running(matrix)
    spotify_fast = RuntimeSettings(
        provider_name="spotify_basic_pitch",
        service_url="http://basic-pitch:8080",
        provider_timeout_seconds=1,
        task_timeout_seconds=120,
    )
    spotify_interruptible = RuntimeSettings(
        provider_name="spotify_basic_pitch",
        service_url="http://basic-pitch:8080",
        provider_timeout_seconds=30,
        task_timeout_seconds=120,
    )

    try:
        matrix.configure(spotify_fast)

        project_id, song_spec_id, upload_id = matrix.create_fixture("disconnect-recovery")
        matrix.compose("stop", "basic-pitch")
        started = time.monotonic()
        run_id = matrix.enqueue(project_id, song_spec_id, upload_id)
        task = matrix.wait_task(run_id, {"failed"}, timeout_seconds=30)
        expect_failure(task, "audio_to_midi_provider_unavailable")
        matrix.assert_no_midi(project_id)
        matrix.record("sidecar_disconnect", started, task)

        matrix.compose("up", "-d", "basic-pitch", timeout=240)
        matrix.wait_basic_pitch()
        matrix.configure(spotify_interruptible)
        started = time.monotonic()
        run_id = matrix.enqueue(project_id, song_spec_id, upload_id)
        task = matrix.wait_task(run_id, {"succeeded"}, timeout_seconds=120)
        matrix.record("sidecar_recovery", started, task)

        matrix.configure(spotify_fast)
        matrix.wait_basic_pitch()
        project_id, song_spec_id, upload_id = matrix.create_fixture("timeout")
        with paused_sidecar(matrix):
            started = time.monotonic()
            run_id = matrix.enqueue(project_id, song_spec_id, upload_id)
            task = matrix.wait_task(run_id, {"failed"}, timeout_seconds=30)
        expect_failure(task, "audio_to_midi_provider_timeout")
        matrix.assert_no_midi(project_id)
        matrix.record("sidecar_timeout", started, task)

        matrix.configure(spotify_interruptible)
        matrix.wait_basic_pitch()

        project_id, song_spec_id, upload_id = matrix.create_fixture("cancel")
        with paused_sidecar(matrix):
            started = time.monotonic()
            run_id = matrix.enqueue(project_id, song_spec_id, upload_id)
            matrix.wait_task(run_id, {"running"}, timeout_seconds=20)
            task = matrix.request("POST", f"/api/v1/tasks/{run_id}/cancel").json()
        if task["status"] != "cancelled":
            raise AssertionError(f"expected cancelled task, got {task}")
        time.sleep(5)
        matrix.assert_no_midi(project_id)
        matrix.record("running_cancel", started, matrix.task(run_id))

        project_id, song_spec_id, upload_id = matrix.create_fixture("worker-restart")
        with paused_sidecar(matrix):
            started = time.monotonic()
            run_id = matrix.enqueue(project_id, song_spec_id, upload_id)
            matrix.wait_task(run_id, {"running"}, timeout_seconds=20)
            matrix.compose("restart", "-t", "20", "audio-midi-worker", timeout=60)
        task = matrix.wait_task(run_id, {"failed"}, timeout_seconds=30)
        expect_failure(task, "task_interrupted")
        matrix.assert_no_midi(project_id)
        matrix.record("worker_restart", started, task)
    finally:
        matrix.compose("unpause", "basic-pitch", check=False)
        with suppress(Exception):
            matrix.wait_api(15)
            matrix.archive_projects()
        matrix.configure(original)
        if sidecar_was_running:
            matrix.compose("up", "-d", "basic-pitch")
            matrix.wait_basic_pitch()
        else:
            matrix.compose("stop", "basic-pitch")


def build_a4_wav() -> bytes:
    sample_rate = 48_000
    duration_seconds = 2
    amplitude = 12_000
    buffer = BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        frames = bytearray()
        for index in range(sample_rate * duration_seconds):
            sample = round(amplitude * math.sin(2 * math.pi * 440 * index / sample_rate))
            frames.extend(struct.pack("<h", sample))
        writer.writeframes(frames)
    return buffer.getvalue()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(__file__).resolve().parents[1]
    matrix = FaultMatrix(args.api_base_url, workspace, args.verbose)
    try:
        run_matrix(matrix)
        print(json.dumps({"status": "passed", "scenarios": matrix.results}, indent=2))
        return 0
    except Exception as error:  # noqa: BLE001 - CLI error boundary
        print(f"fault matrix failed: {type(error).__name__}: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            if error.stdout:
                print(error.stdout, file=sys.stderr)
            if error.stderr:
                print(error.stderr, file=sys.stderr)
        if matrix.results:
            print(json.dumps({"completed_scenarios": matrix.results}, indent=2))
        return 1
    finally:
        matrix.close()


if __name__ == "__main__":
    raise SystemExit(main())

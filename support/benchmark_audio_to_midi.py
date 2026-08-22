"""Benchmark the isolated Basic Pitch service against a versioned WAV/MIDI dataset."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
import wave
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

from abachiwave.evaluations.audio_to_midi import (
    ResourceMetrics,
    SampleBenchmarkResult,
    aggregate_benchmark_results,
    compare_reference_candidates,
    evaluate_thresholds,
    parse_docker_memory_mib,
    parse_timed_midi_notes,
)
from abachiwave.evaluations.basic_pitch_sweep import (
    parse_basic_pitch_param_assignments,
    prepare_basic_pitch_benchmark_manifest,
)
from abachiwave.schemas.song_specs import SongSpecData
from abachiwave.services.audio_to_midi_provider import (
    AudioToMidiRequest,
    BasicPitchHttpAudioToMidiProvider,
)


class DockerResourceSampler:
    def __init__(self, container: str) -> None:
        self.container = container
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._peak_cpu_percent: float | None = None
        self._peak_memory_mib: float | None = None
        self._sampling_error: str | None = None

    def start(self) -> None:
        snapshot = subprocess.run(
            [
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{json .}}",
                self.container,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        for line in snapshot.stdout.splitlines():
            self._record(line, include_cpu=False)
        self._thread = threading.Thread(target=self._collect, daemon=True)
        self._thread.start()

    def stop(self) -> ResourceMetrics:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
        with self._lock:
            process = self._process
        if process is not None and process.poll() is None:
            process.terminate()
            if self._thread is not None:
                self._thread.join(timeout=5)
        if process is not None and process.poll() is None:
            process.kill()
        with self._lock:
            if self._sampling_error is not None:
                raise RuntimeError(f"Docker resource sampling failed: {self._sampling_error}")
            return ResourceMetrics(
                peak_cpu_percent=self._peak_cpu_percent,
                peak_memory_mib=self._peak_memory_mib,
            )

    def _collect(self) -> None:
        while True:
            process = subprocess.Popen(
                [
                    "docker",
                    "stats",
                    "--no-stream",
                    "--format",
                    "{{json .}}",
                    self.container,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            with self._lock:
                self._process = process
            try:
                stdout, stderr = process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                with self._lock:
                    self._sampling_error = "docker stats timed out"
                return
            finally:
                with self._lock:
                    if self._process is process:
                        self._process = None
            if process.returncode != 0:
                if self._stop.is_set() and process.returncode < 0:
                    return
                with self._lock:
                    self._sampling_error = stderr.strip() or f"exit code {process.returncode}"
                return
            for line in stdout.splitlines():
                self._record(line, include_cpu=True)
            if self._stop.is_set():
                return

    def _record(self, line: str, *, include_cpu: bool) -> None:
        try:
            payload = json.loads(line)
            cpu = _parse_percent(str(payload["CPUPerc"]))
            memory = parse_docker_memory_mib(
                str(payload["MemUsage"]).split("/", maxsplit=1)[0]
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return
        with self._lock:
            if include_cpu:
                self._peak_cpu_percent = max(self._peak_cpu_percent or 0, cpu)
            self._peak_memory_mib = max(self._peak_memory_mib or 0, memory)


def run_benchmark(args: argparse.Namespace) -> tuple[dict[str, object], bool]:
    manifest = prepare_basic_pitch_benchmark_manifest(
        args.manifest,
        provider_params=getattr(args, "provider_params", None),
        sample_ids=getattr(args, "sample_ids", None),
    )
    provider = BasicPitchHttpAudioToMidiProvider(
        args.service_url,
        timeout_seconds=args.timeout_seconds,
    )
    health = httpx.get(f"{args.service_url.rstrip('/')}/health/ready", timeout=10)
    health.raise_for_status()
    health_payload = health.json()
    if health_payload.get("status") != "ready":
        raise RuntimeError(f"Basic Pitch service is not ready: {health_payload}")

    sampler: DockerResourceSampler | None = None
    if not args.no_resource_sampling:
        container = args.container or _resolve_basic_pitch_container(args.workspace)
        sampler = DockerResourceSampler(container)
        sampler.start()

    results: list[SampleBenchmarkResult] = []
    resources = ResourceMetrics()
    try:
        for _ in range(args.warmup_runs):
            first = manifest.samples[0]
            _transcribe(provider, first.audio_path, manifest.provider_params)

        for sample in manifest.samples:
            audio_bytes = sample.audio_path.read_bytes()
            duration_seconds = _wav_duration_seconds(sample.audio_path)
            reference_candidates = [
                (
                    sample.reference_id,
                    parse_timed_midi_notes(sample.reference_midi_path.read_bytes()),
                ),
                *(
                    (
                        reference.id,
                        parse_timed_midi_notes(reference.midi_path.read_bytes()),
                    )
                    for reference in sample.alternative_references
                ),
            ]
            for reference_id, reference_notes in reference_candidates:
                if not reference_notes:
                    raise ValueError(
                        f"reference MIDI has no complete notes: {sample.id}/{reference_id}"
                    )
            started_at = time.perf_counter()
            midi_bytes = _transcribe_bytes(
                provider,
                audio_bytes,
                sample.audio_path.name,
                manifest.provider_params,
            )
            latency_seconds = time.perf_counter() - started_at
            predicted = parse_timed_midi_notes(midi_bytes)
            selected_reference_id, metrics = compare_reference_candidates(
                reference_candidates,
                predicted,
                selection_policy=manifest.reference_selection_policy,
                onset_tolerance_seconds=manifest.onset_tolerance_seconds,
                offset_tolerance_seconds=manifest.offset_tolerance_seconds,
                offset_tolerance_ratio=manifest.offset_tolerance_ratio,
            )
            results.append(
                SampleBenchmarkResult(
                    sample_id=sample.id,
                    category=sample.category,
                    audio_duration_seconds=duration_seconds,
                    latency_seconds=latency_seconds,
                    real_time_factor=latency_seconds / duration_seconds,
                    metrics=metrics,
                    reference_id=selected_reference_id,
                )
            )
    finally:
        if sampler is not None:
            resources = sampler.stop()

    benchmark = aggregate_benchmark_results(results, resources=resources)
    violations = evaluate_thresholds(benchmark, manifest.thresholds)
    report: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": manifest.dataset.model_dump(mode="json"),
        "provider": {
            "name": provider.name,
            "version": provider.version,
            "service_url": args.service_url,
            "params": {**provider.default_params(), **manifest.provider_params},
            "warmup_runs": args.warmup_runs,
        },
        "tolerances": {
            "onset_seconds": manifest.onset_tolerance_seconds,
            "offset_seconds": manifest.offset_tolerance_seconds,
            "offset_ratio": manifest.offset_tolerance_ratio,
        },
        "reference_selection_policy": manifest.reference_selection_policy,
        "inputs": [
            {
                "id": sample.id,
                "category": sample.category,
                "audio_sha256": sample.audio_sha256,
                "reference_midi_sha256": sample.reference_midi_sha256,
                "source_member": sample.source_member,
                "source_audio_sha256": sample.source_audio_sha256,
                "source_annotation_member": sample.source_annotation_member,
                "source_annotation_sha256": sample.source_annotation_sha256,
                "reference_id": sample.reference_id,
                "attributes": sample.attributes,
                "alternative_references": [
                    {
                        "id": reference.id,
                        "midi_sha256": reference.midi_sha256,
                        "source_annotation_member": reference.source_annotation_member,
                        "source_annotation_sha256": reference.source_annotation_sha256,
                    }
                    for reference in sample.alternative_references
                ],
            }
            for sample in manifest.samples
        ],
        "benchmark": benchmark,
        "threshold_violations": [asdict(violation) for violation in violations],
        "passed": not violations,
    }
    return report, not violations


def _transcribe(
    provider: BasicPitchHttpAudioToMidiProvider,
    audio_path: Path,
    provider_params: dict[str, bool | float],
) -> bytes:
    return _transcribe_bytes(
        provider,
        audio_path.read_bytes(),
        audio_path.name,
        provider_params,
    )


def _transcribe_bytes(
    provider: BasicPitchHttpAudioToMidiProvider,
    audio_bytes: bytes,
    filename: str,
    provider_params: dict[str, bool | float],
) -> bytes:
    generated = provider.extract_midi(
        AudioToMidiRequest(
            audio_bytes=audio_bytes,
            filename=filename,
            song_spec=_benchmark_song_spec(),
            provider_params=dict(provider_params),
        )
    )
    return generated.data


def _benchmark_song_spec() -> SongSpecData:
    return SongSpecData(
        title="Audio-to-MIDI benchmark",
        language="English",
        genre=["Benchmark"],
        mood="neutral",
        theme="evaluation",
        story_arc="controlled fixture",
        narrative_perspective="instrumental",
        target_duration_seconds=180,
        tempo_bpm=120,
        key="C major",
        time_signature="4/4",
        energy_curve="steady",
        vocal_style="neutral",
        instrumentation=["reference audio"],
        song_structure=["fixture"],
        structure_sections=[],
        constraints=[],
    )


def _wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as reader:
        frame_rate = reader.getframerate()
        if frame_rate <= 0:
            raise ValueError(f"WAV has invalid frame rate: {path}")
        duration = reader.getnframes() / frame_rate
    if duration <= 0:
        raise ValueError(f"WAV is empty: {path}")
    return duration


def _resolve_basic_pitch_container(workspace: Path) -> str:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "--profile",
            "basic-pitch",
            "ps",
            "--status",
            "running",
            "-q",
            "basic-pitch",
        ],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    container = result.stdout.strip()
    if not container:
        raise RuntimeError("Basic Pitch container is not running")
    return container


def _parse_percent(value: str) -> float:
    return float(value.strip().removesuffix("%"))


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--service-url", default="http://127.0.0.1:8010")
    parser.add_argument("--timeout-seconds", type=float, default=180)
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--container")
    parser.add_argument("--no-resource-sampling", action="store_true")
    parser.add_argument(
        "--provider-param",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="override one Basic Pitch parameter; may be repeated",
    )
    parser.add_argument(
        "--sample-id",
        action="append",
        dest="sample_ids",
        help="run only a named manifest sample; may be repeated",
    )
    parser.add_argument("--output", type=Path)
    parser.set_defaults(workspace=workspace)
    args = parser.parse_args()
    if args.warmup_runs < 0:
        parser.error("--warmup-runs must be non-negative")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    try:
        args.provider_params = parse_basic_pitch_param_assignments(args.provider_param)
    except ValueError as error:
        parser.error(str(error))
    del args.provider_param
    return args


def main() -> int:
    args = parse_args()
    try:
        report, passed = run_benchmark(args)
        rendered = json.dumps(report, indent=2, ensure_ascii=False)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0 if passed else 2
    except Exception as error:  # noqa: BLE001 - CLI error boundary
        print(f"benchmark failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

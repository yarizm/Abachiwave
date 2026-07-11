from __future__ import annotations

import json
import math
import os
import time
import uuid
import wave
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zipfile import ZipFile

from mido import MidiFile

BASE_URL = os.environ.get("ABACHIWAVE_API_BASE_URL", "http://localhost:8000").rstrip("/")


def main() -> None:
    wait_health()
    project = request_json(
        "POST",
        "/api/v1/projects",
        {"name": f"MVP Smoke {int(time.time())}", "description": "Automated smoke run"},
        expect=(201,),
    )
    project_id = project["id"]

    intake = request_json(
        "POST",
        f"/api/v1/projects/{project_id}/intake",
        {
            "idea": (
                "Chinese indie rock song about riding home late at night. "
                "Verse restrained and lonely, chorus lifting and hopeful. "
                "128 BPM, E major, 4/4, 3:30, standard structure."
            )
        },
        expect=(201,),
    )
    draft = request_json(
        "POST",
        f"/api/v1/projects/{project_id}/song-spec/generate",
        {"intake_id": intake["intake_id"]},
    )
    approved = request_json(
        "POST",
        f"/api/v1/projects/{project_id}/song-specs/{draft['id']}/approve",
    )

    lyrics = request_json(
        "POST",
        f"/api/v1/projects/{project_id}/lyrics/generate",
        {"song_spec_id": approved["id"]},
        expect=(201,),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        concurrent_edits = [
            executor.submit(
                request_json,
                "PATCH",
                f"/api/v1/projects/{project_id}/lyrics/{lyrics['id']}",
                {
                    "sections": lyrics["sections"],
                    "hook_candidates": lyrics["hook_candidates"],
                },
            )
            for _ in range(2)
        ]
    concurrent_lyrics = [future.result() for future in concurrent_edits]
    assert sorted(version["version_number"] for version in concurrent_lyrics) == [2, 3]
    chords = request_json(
        "POST",
        f"/api/v1/projects/{project_id}/chords/generate",
        {"song_spec_id": approved["id"], "lyrics_version_id": lyrics["id"]},
        expect=(201,),
    )
    midi_assets = request_json(
        "POST",
        f"/api/v1/projects/{project_id}/midi/generate",
        {
            "song_spec_id": approved["id"],
            "lyrics_version_id": lyrics["id"],
            "chord_version_id": chords["id"],
        },
        expect=(201,),
    )
    assert {asset["kind"] for asset in midi_assets} == {"chord", "melody", "hook"}

    arrangement = request_json(
        "POST",
        f"/api/v1/projects/{project_id}/arrangement/generate",
        {"song_spec_id": approved["id"]},
        expect=(201,),
    )
    comment = request_json(
        "POST",
        f"/api/v1/projects/{project_id}/comments",
        {
            "author_name": "Smoke reviewer",
            "body": "Confirm the chorus lift before handoff.",
            "target_type": "arrangement",
            "target_id": arrangement["id"],
        },
        expect=(201,),
    )
    handoff = request_json("GET", f"/api/v1/projects/{project_id}/handoff")
    assert handoff["open_comments"][0]["id"] == comment["id"]
    assert "Confirm the chorus lift" in handoff["handoff_markdown"]
    resolved_comment = request_json(
        "PATCH",
        f"/api/v1/projects/{project_id}/comments/{comment['id']}",
        {"status": "resolved"},
    )
    assert resolved_comment["status"] == "resolved"
    comments = request_json("GET", f"/api/v1/projects/{project_id}/comments")
    assert comments and comments[0]["status"] == "resolved"

    demo_run = request_json(
        "POST",
        f"/api/v1/projects/{project_id}/demo/generate",
        {"arrangement_plan_id": arrangement["id"]},
        expect=(202,),
    )
    finished_demo_run = wait_task(demo_run["id"])
    demo_id = finished_demo_run["demo_id"]
    assert demo_id
    demo_data = request_bytes("GET", f"/api/v1/projects/{project_id}/demos/{demo_id}/download")
    assert demo_data[:4] == b"RIFF" and demo_data[8:12] == b"WAVE"
    demos = request_json("GET", f"/api/v1/projects/{project_id}/demos")
    assert demos and len(demos[0]["waveform_peaks"]) == 80

    revision = request_json(
        "POST",
        f"/api/v1/projects/{project_id}/revisions",
        {"feedback": "Make the chorus lyric stronger."},
        expect=(201,),
    )
    applied = request_json(
        "POST",
        f"/api/v1/projects/{project_id}/revisions/{revision['id']}/apply",
        {"regenerate_demo": False},
    )
    assert applied["revision"]["status"] == "applied"
    lyrics_versions = request_json("GET", f"/api/v1/projects/{project_id}/lyrics")
    assert len(lyrics_versions) >= 2
    diff_query = urlencode(
        {
            "asset_type": "lyrics",
            "left_id": lyrics_versions[1]["id"],
            "right_id": lyrics_versions[0]["id"],
        }
    )
    diff = request_json("GET", f"/api/v1/projects/{project_id}/versions/diff?{diff_query}")
    assert diff["asset_type"] == "lyrics"

    upload = multipart_upload(
        f"/api/v1/projects/{project_id}/audio-uploads",
        fields={"kind": "humming", "notes": "smoke test humming"},
        file_name="humming.wav",
        file_bytes=build_wav_bytes(),
    )
    assert upload["sample_rate"] == 8000
    assert len(upload["waveform_peaks"]) == 80
    audio_run = request_json(
        "POST",
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/extract-midi",
        {"song_spec_id": approved["id"], "target_kind": "melody"},
        expect=(202,),
    )
    finished_audio_run = wait_task(audio_run["id"])
    extracted_midi_id = finished_audio_run["result_midi_asset_id"]
    assert extracted_midi_id
    midi_data = request_bytes(
        "GET",
        f"/api/v1/projects/{project_id}/midi-assets/{extracted_midi_id}/download",
    )
    assert midi_data[:4] == b"MThd"
    MidiFile(file=BytesIO(midi_data))

    export_bundle = request_json(
        "POST",
        f"/api/v1/projects/{project_id}/exports",
        {},
        expect=(201,),
    )
    export_data = request_bytes("GET", export_bundle["download_url"])
    with ZipFile(BytesIO(export_data)) as archive:
        names = set(archive.namelist())
        assert {
            "manifest.json",
            "song-spec.json",
            "lyrics.md",
            "chords.md",
            "comments.json",
            "comments.md",
            "events.json",
            "handoff.json",
            "handoff.md",
            "review.json",
            "demos.json",
            "audio-uploads.json",
        }.issubset(names)
        exported_comments = json.loads(archive.read("comments.json").decode("utf-8"))
        exported_handoff = json.loads(archive.read("handoff.json").decode("utf-8"))
        exported_handoff_markdown = archive.read("handoff.md").decode("utf-8")
        exported_demos = json.loads(archive.read("demos.json").decode("utf-8"))
        exported_uploads = json.loads(archive.read("audio-uploads.json").decode("utf-8"))
        assert exported_comments and exported_comments[0]["status"] == "resolved"
        assert exported_handoff["review"]["score"] >= 80
        assert "Handoff" in exported_handoff_markdown
        assert exported_demos
        assert archive.read(exported_demos[0]["archive_path"]).startswith(b"RIFF")
        assert exported_uploads
        assert archive.read(exported_uploads[0]["archive_path"]).startswith(b"RIFF")

    print(
        json.dumps(
            {
                "status": "ok",
                "project_id": project_id,
                "demo_id": demo_id,
                "comment_id": comment["id"],
                "handoff_score": handoff["review"]["score"],
                "audio_upload_id": upload["id"],
                "extracted_midi_id": extracted_midi_id,
            },
            indent=2,
        )
    )


def wait_health() -> None:
    for _ in range(60):
        try:
            health = request_json("GET", "/health")
            if health["status"] == "ok":
                return
        except Exception:
            time.sleep(1)
    raise RuntimeError(f"API did not become healthy at {BASE_URL}")


def wait_task(task_id: str, *, timeout_seconds: int = 90) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    last: dict[str, object] | None = None
    while time.time() < deadline:
        last = request_json("GET", f"/api/v1/tasks/{task_id}")
        if last["status"] == "succeeded":
            return last
        if last["status"] in {"failed", "cancelled"}:
            raise RuntimeError(f"Task {task_id} ended as {last['status']}: {last}")
        time.sleep(2)
    raise TimeoutError(f"Task {task_id} did not finish: {last}")


def request_json(
    method: str,
    path: str,
    payload: object | None = None,
    *,
    expect: tuple[int, ...] = (200,),
) -> dict[str, object]:
    body = request_bytes(method, path, payload, expect=expect)
    return json.loads(body.decode("utf-8"))


def request_bytes(
    method: str,
    path_or_url: str,
    payload: object | None = None,
    *,
    expect: tuple[int, ...] = (200,),
) -> bytes:
    body = None
    headers = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    url = path_or_url if path_or_url.startswith("http") else f"{BASE_URL}{path_or_url}"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=30) as response:
            data = response.read()
            status = response.status
    except HTTPError as error:
        data = error.read()
        status = error.code
    if status not in expect:
        raise RuntimeError(f"{method} {url} returned {status}: {data[:1000]!r}")
    return data


def multipart_upload(
    path: str,
    *,
    fields: dict[str, str],
    file_name: str,
    file_bytes: bytes,
) -> dict[str, object]:
    boundary = f"----abachiwave-{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode()
        )
    parts.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode()
    )
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    request = Request(
        f"{BASE_URL}{path}",
        data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            data = response.read()
            status = response.status
    except HTTPError as error:
        data = error.read()
        status = error.code
    if status != 201:
        raise RuntimeError(f"POST {path} returned {status}: {data[:1000]!r}")
    return json.loads(data.decode("utf-8"))


def build_wav_bytes() -> bytes:
    sample_rate = 8000
    frequency = 440.0
    amplitude = 12000
    buffer = BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        for index in range(sample_rate):
            sample = int(amplitude * math.sin(2 * math.pi * frequency * index / sample_rate))
            writer.writeframesraw(sample.to_bytes(2, "little", signed=True))
    return buffer.getvalue()


if __name__ == "__main__":
    main()

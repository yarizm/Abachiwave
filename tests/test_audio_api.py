import asyncio
import wave
from collections.abc import AsyncIterator
from io import BytesIO
from math import pi, sin
from threading import Event
from typing import Any, cast
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from mido import MidiFile
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.core.config import get_settings
from abachiwave.models import GenerationRun
from abachiwave.services.audio import execute_audio_to_midi
from abachiwave.services.audio_derivatives import (
    PcmWavData,
    execute_audio_derivative,
    inspect_pcm_wav,
)
from abachiwave.services.audio_to_midi_provider import (
    AudioToMidiProviderTimeoutError,
    AudioToMidiRequest,
    GeneratedMidi,
    LocalMonophonicWavToMidiProvider,
)
from abachiwave.services.reference_analysis import execute_reference_analysis
from abachiwave.services.storage import get_object_storage
from abachiwave.services.task_queue import (
    get_audio_derivative_task_queue,
    get_audio_to_midi_task_queue,
    get_reference_analysis_task_queue,
)


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data
        self.content_types[key] = content_type

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def delete_bytes(self, key: str) -> None:
        self.objects.pop(key, None)
        self.content_types.pop(key, None)


class FakeAudioQueue:
    def __init__(self) -> None:
        self.enqueued: list[UUID] = []
        self.derivative_enqueued: list[UUID] = []
        self.analysis_enqueued: list[UUID] = []

    async def enqueue_audio_to_midi(self, run_id: UUID) -> str:
        self.enqueued.append(run_id)
        return f"fake-audio-job-{run_id}"

    async def enqueue_audio_derivative(self, run_id: UUID) -> str:
        self.derivative_enqueued.append(run_id)
        return f"fake-derivative-job-{run_id}"

    async def enqueue_reference_analysis(self, run_id: UUID) -> str:
        self.analysis_enqueued.append(run_id)
        return f"fake-analysis-job-{run_id}"


class FakeAudioConverter:
    name = "fake-ffmpeg"
    version = "test"

    def default_params(self) -> dict[str, object]:
        return {"codec": "pcm_s16le"}

    def convert_to_pcm_wav(self, source: bytes) -> PcmWavData:
        return inspect_pcm_wav(_wav_bytes())


class FailingAudioConverter(FakeAudioConverter):
    def convert_to_pcm_wav(self, source: bytes) -> PcmWavData:
        raise RuntimeError("fixture decode failure")


class BlockingAudioProvider(LocalMonophonicWavToMidiProvider):
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    def extract_midi(self, request: AudioToMidiRequest) -> GeneratedMidi:
        self.started.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError("test provider was not released")
        return super().extract_midi(request)


class CapturingAudioProvider(LocalMonophonicWavToMidiProvider):
    def __init__(self) -> None:
        self.requests: list[AudioToMidiRequest] = []

    def extract_midi(self, request: AudioToMidiRequest) -> GeneratedMidi:
        self.requests.append(request)
        return super().extract_midi(request)


class TimeoutAudioProvider(LocalMonophonicWavToMidiProvider):
    def extract_midi(self, request: AudioToMidiRequest) -> GeneratedMidi:
        raise AudioToMidiProviderTimeoutError("fixture provider timed out")


class WriteThenFailMidiStorage(MemoryStorage):
    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        super().put_bytes(key, data, content_type)
        if "/midi/" in key:
            raise RuntimeError("midi storage failed after write")


@pytest_asyncio.fixture
async def client_with_audio_deps(
    app: FastAPI,
) -> AsyncIterator[tuple[AsyncClient, MemoryStorage, FakeAudioQueue]]:
    storage = MemoryStorage()
    queue = FakeAudioQueue()
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[get_audio_to_midi_task_queue] = lambda: queue
    app.dependency_overrides[get_audio_derivative_task_queue] = lambda: queue
    app.dependency_overrides[get_reference_analysis_task_queue] = lambda: queue
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client, storage, queue
    app.dependency_overrides.pop(get_object_storage, None)
    app.dependency_overrides.pop(get_audio_to_midi_task_queue, None)
    app.dependency_overrides.pop(get_audio_derivative_task_queue, None)
    app.dependency_overrides.pop(get_reference_analysis_task_queue, None)


async def _create_project(client: AsyncClient, name: str = "Audio Project") -> str:
    response = await client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201
    return str(UUID(response.json()["id"]))


async def _create_song_spec(
    client: AsyncClient,
    *,
    approved: bool,
) -> tuple[str, dict[str, Any]]:
    project_id = await _create_project(client)
    intake_response = await client.post(
        f"/api/v1/projects/{project_id}/intake",
        json={
            "idea": (
                "Chinese indie rock song about riding home late at night. "
                "Verse restrained and lonely, chorus lifting and hopeful. "
                "128 BPM, E major, 4/4, 3:30, standard structure."
            )
        },
    )
    assert intake_response.status_code == 201
    song_spec_response = await client.post(
        f"/api/v1/projects/{project_id}/song-spec/generate",
        json={"intake_id": intake_response.json()["intake_id"]},
    )
    assert song_spec_response.status_code == 200
    if not approved:
        return project_id, cast(dict[str, Any], song_spec_response.json())
    approve_response = await client.post(
        f"/api/v1/projects/{project_id}/song-specs/{song_spec_response.json()['id']}/approve"
    )
    assert approve_response.status_code == 200
    return project_id, cast(dict[str, Any], approve_response.json())


async def _upload_wav(client: AsyncClient, project_id: str) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads",
        data={"kind": "humming", "notes": "chorus sketch"},
        files={"file": ("humming.wav", _wav_bytes(), "audio/wav")},
    )
    assert response.status_code == 201
    return cast(dict[str, Any], response.json())


@pytest.mark.asyncio
async def test_audio_upload_metadata_update_and_download(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
) -> None:
    client, _storage, _queue = client_with_audio_deps
    project_id = await _create_project(client)

    upload = await _upload_wav(client, project_id)

    assert upload["kind"] == "humming"
    assert upload["status"] == "available"
    assert upload["content_type"] == "audio/wav"
    assert upload["format"] == "wav"
    assert upload["duration_seconds"] > 0
    assert upload["sample_rate"] == 8000
    assert upload["channels"] == 1
    assert len(upload["waveform_peaks"]) == 80
    assert max(upload["waveform_peaks"]) > 0

    list_response = await client.get(f"/api/v1/projects/{project_id}/audio-uploads")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [upload["id"]]

    patch_response = await client.patch(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}",
        json={"kind": "reference", "notes": "updated notes"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["kind"] == "reference"
    assert patch_response.json()["notes"] == "updated notes"

    clear_notes_response = await client.patch(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}",
        json={"status": "archived", "notes": ""},
    )
    assert clear_notes_response.status_code == 200
    assert clear_notes_response.json()["status"] == "archived"
    assert clear_notes_response.json()["notes"] is None

    restore_response = await client.patch(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}",
        json={"status": "available"},
    )
    assert restore_response.status_code == 200

    events_response = await client.get(f"/api/v1/projects/{project_id}/events")
    assert events_response.status_code == 200
    event_types = {event["event_type"] for event in events_response.json()}
    assert {"audio.updated", "audio.archived", "audio.restored"}.issubset(event_types)

    download_response = await client.get(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/download"
    )
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith("audio/wav")
    assert download_response.content.startswith(b"RIFF")


@pytest.mark.asyncio
async def test_audio_derivative_run_is_executed_and_listed(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, queue = client_with_audio_deps
    project_id = await _create_project(client, "Derivative Project")
    upload = await _upload_wav(client, project_id)
    endpoint = f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/derivatives"

    create_response = await client.post(endpoint, json={"kind": "pcm_wav"})
    assert create_response.status_code == 202
    run = create_response.json()
    assert run["run_type"] == "audio_derivative"
    assert run["provider_name"] == "ffmpeg"
    assert queue.derivative_enqueued == [UUID(run["id"])]

    executed = await execute_audio_derivative(
        UUID(run["id"]),
        storage=storage,
        converter=FakeAudioConverter(),
        session_factory=session_factory,
    )
    assert executed is not None
    assert executed.status == "succeeded"
    derivative_id = executed.provider_usage["audio_derivative_id"]

    response = await client.get(endpoint)
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == derivative_id
    assert payload[0]["kind"] == "pcm_wav"
    assert payload[0]["format"] == "wav"
    assert payload[0]["sample_rate"] == 8000
    assert payload[0]["channels"] == 1
    assert payload[0]["source_checksum"] == upload["checksum"]
    assert any(key.endswith(".wav") for key in storage.objects)

    duplicate_response = await client.post(endpoint, json={"kind": "pcm_wav"})
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "PCM WAV derivative already exists"


@pytest.mark.asyncio
async def test_multiformat_uploads_are_normalized_and_streamed_as_pcm_wav(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, queue = client_with_audio_deps
    project_id = await _create_project(client, "Multiformat Project")
    fixtures = [
        ("reference.mp3", b"ID3" + bytes(125), "audio/mpeg", "mp3", "audio/mpeg"),
        (
            "reference.m4a",
            (24).to_bytes(4, "big") + b"ftypM4A " + bytes(4) + b"M4A ",
            "audio/mp4",
            "m4a",
            "audio/mp4",
        ),
        ("reference.flac", b"fLaC" + bytes(124), "audio/flac", "flac", "audio/flac"),
        ("reference.ogg", b"OggS" + bytes(124), "audio/ogg", "ogg", "audio/ogg"),
    ]

    uploads: list[dict[str, Any]] = []
    for filename, data, content_type, format_name, canonical_content_type in fixtures:
        response = await client.post(
            f"/api/v1/projects/{project_id}/audio-uploads",
            data={"kind": "reference"},
            files={"file": (filename, data, content_type)},
        )
        assert response.status_code == 201
        upload = cast(dict[str, Any], response.json())
        assert upload["format"] == format_name
        assert upload["content_type"] == canonical_content_type
        assert upload["status"] == "processing"
        assert upload["duration_seconds"] is None
        assert upload["sample_rate"] is None
        assert upload["channels"] is None
        assert upload["waveform_peaks"] is None
        uploads.append(upload)

    assert len(queue.derivative_enqueued) == len(fixtures)
    for run_id, upload in zip(queue.derivative_enqueued, uploads, strict=True):
        executed = await execute_audio_derivative(
            run_id,
            storage=storage,
            converter=FakeAudioConverter(),
            session_factory=session_factory,
        )
        assert executed is not None
        assert executed.status == "succeeded"

        refreshed_response = await client.get(
            f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}"
        )
        assert refreshed_response.status_code == 200
        refreshed = refreshed_response.json()
        assert refreshed["status"] == "available"
        assert refreshed["duration_seconds"] > 0
        assert refreshed["sample_rate"] == 8000
        assert refreshed["channels"] == 1
        assert len(refreshed["waveform_peaks"]) == 80

        derivative_response = await client.get(
            f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/derivatives"
        )
        derivative = derivative_response.json()[0]
        download_response = await client.get(
            f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}"
            f"/derivatives/{derivative['id']}/download"
        )
        assert download_response.status_code == 200
        assert download_response.headers["content-type"].startswith("audio/wav")
        assert download_response.content.startswith(b"RIFF")


@pytest.mark.asyncio
async def test_audio_upload_rejects_mismatched_extension_media_type_and_signature(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
) -> None:
    client, _storage, queue = client_with_audio_deps
    project_id = await _create_project(client, "Mismatched Audio")

    response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads",
        data={"kind": "reference"},
        files={"file": ("reference.mp3", b"fLaC" + bytes(32), "audio/mpeg")},
    )

    assert response.status_code == 415
    assert response.headers["X-Error-Code"] == "unsupported_media_type"
    assert queue.derivative_enqueued == []


@pytest.mark.asyncio
async def test_multiformat_normalization_failure_retry_and_cancel_update_upload_status(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, queue = client_with_audio_deps
    project_id = await _create_project(client, "Normalization lifecycle")
    create_response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads",
        data={"kind": "reference"},
        files={"file": ("reference.mp3", b"ID3" + bytes(125), "audio/mpeg")},
    )
    assert create_response.status_code == 201
    upload = create_response.json()
    first_run_id = queue.derivative_enqueued[0]
    duplicate_response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/derivatives",
        json={"kind": "pcm_wav"},
    )
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == (
        "PCM WAV derivative normalization is already active"
    )

    failed_run = await execute_audio_derivative(
        first_run_id,
        storage=storage,
        converter=FailingAudioConverter(),
        session_factory=session_factory,
    )
    assert failed_run is not None
    assert failed_run.status == "failed"
    failed_upload = (
        await client.get(f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}")
    ).json()
    assert failed_upload["status"] == "failed"
    invalid_restore_response = await client.patch(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}",
        json={"status": "available"},
    )
    assert invalid_restore_response.status_code == 409

    retry_response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/derivatives",
        json={"kind": "pcm_wav"},
    )
    assert retry_response.status_code == 202
    retry_run = retry_response.json()
    processing_upload = (
        await client.get(f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}")
    ).json()
    assert processing_upload["status"] == "processing"

    cancel_response = await client.post(f"/api/v1/tasks/{retry_run['id']}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"
    cancelled_upload = (
        await client.get(f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}")
    ).json()
    assert cancelled_upload["status"] == "failed"


@pytest.mark.asyncio
async def test_audio_to_midi_uses_ready_pcm_derivative_for_compressed_upload(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, queue = client_with_audio_deps
    project_id, song_spec = await _create_song_spec(client, approved=True)
    upload_response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads",
        data={"kind": "humming"},
        files={"file": ("humming.mp3", b"ID3" + bytes(125), "audio/mpeg")},
    )
    upload = upload_response.json()
    blocked_extract_response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/extract-midi",
        json={"song_spec_id": song_spec["id"]},
    )
    assert blocked_extract_response.status_code == 409
    assert blocked_extract_response.json()["detail"] == "Audio upload must be available"
    derivative_run = await execute_audio_derivative(
        queue.derivative_enqueued[0],
        storage=storage,
        converter=FakeAudioConverter(),
        session_factory=session_factory,
    )
    assert derivative_run is not None
    assert derivative_run.status == "succeeded"

    extract_response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/extract-midi",
        json={"song_spec_id": song_spec["id"]},
    )
    assert extract_response.status_code == 202
    midi_run = await execute_audio_to_midi(
        UUID(extract_response.json()["id"]),
        storage=storage,
        session_factory=session_factory,
    )
    assert midi_run is not None
    assert midi_run.status == "succeeded"
    assert midi_run.result_midi_asset_id is not None


@pytest.mark.asyncio
async def test_multiformat_upload_survives_normalization_queue_failure(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, storage, queue = client_with_audio_deps
    project_id = await _create_project(client, "Queue failure upload")

    async def fail_enqueue(_run_id: UUID) -> str:
        raise RuntimeError("queue unavailable")

    monkeypatch.setattr(queue, "enqueue_audio_derivative", fail_enqueue)
    response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads",
        data={"kind": "reference"},
        files={"file": ("reference.flac", b"fLaC" + bytes(64), "audio/flac")},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert len(storage.objects) == 1


@pytest.mark.asyncio
async def test_audio_marker_lifecycle_validation_and_project_isolation(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
) -> None:
    client, _storage, _queue = client_with_audio_deps
    project_id = await _create_project(client, "Marker Project")
    upload = await _upload_wav(client, project_id)
    marker_url = f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/markers"

    chorus_response = await client.post(
        marker_url,
        json={
            "position_seconds": 0.75,
            "label": " Chorus cue ",
            "section_id": " chorus ",
            "notes": " lift here ",
        },
    )
    assert chorus_response.status_code == 201
    chorus = chorus_response.json()
    assert chorus["label"] == "Chorus cue"
    assert chorus["section_id"] == "chorus"
    assert chorus["notes"] == "lift here"

    verse_response = await client.post(
        marker_url,
        json={"position_seconds": 0.25, "label": "Verse cue"},
    )
    assert verse_response.status_code == 201
    verse = verse_response.json()

    list_response = await client.get(marker_url)
    assert list_response.status_code == 200
    assert [marker["id"] for marker in list_response.json()] == [verse["id"], chorus["id"]]

    update_response = await client.patch(
        f"/api/v1/projects/{project_id}/audio-markers/{chorus['id']}",
        json={
            "position_seconds": 0.1,
            "label": "Intro cue",
            "section_id": "",
            "notes": "",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["position_seconds"] == 0.1
    assert update_response.json()["label"] == "Intro cue"
    assert update_response.json()["section_id"] is None
    assert update_response.json()["notes"] is None

    out_of_range_response = await client.post(
        marker_url,
        json={
            "position_seconds": upload["duration_seconds"] + 1,
            "label": "Outside audio",
        },
    )
    assert out_of_range_response.status_code == 422
    assert out_of_range_response.headers["X-Error-Code"] == "validation_failed"
    assert "position_seconds" in out_of_range_response.json()["fields"]

    other_project_id = await _create_project(client, "Other Marker Project")
    cross_project_list = await client.get(
        f"/api/v1/projects/{other_project_id}/audio-uploads/{upload['id']}/markers"
    )
    assert cross_project_list.status_code == 404
    cross_project_update = await client.patch(
        f"/api/v1/projects/{other_project_id}/audio-markers/{chorus['id']}",
        json={"label": "Cross project edit"},
    )
    assert cross_project_update.status_code == 404

    delete_response = await client.delete(
        f"/api/v1/projects/{project_id}/audio-markers/{chorus['id']}"
    )
    assert delete_response.status_code == 204
    assert delete_response.content == b""

    remaining_response = await client.get(marker_url)
    assert [marker["id"] for marker in remaining_response.json()] == [verse["id"]]

    events_response = await client.get(f"/api/v1/projects/{project_id}/events")
    event_types = {event["event_type"] for event in events_response.json()}
    assert {
        "audio.marker.created",
        "audio.marker.updated",
        "audio.marker.deleted",
    }.issubset(event_types)

@pytest.mark.asyncio
async def test_audio_upload_rejects_invalid_type_and_size(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _storage, _queue = client_with_audio_deps
    project_id = await _create_project(client)

    invalid_type_response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads",
        data={"kind": "humming"},
        files={"file": ("humming.mp3", b"not wav", "audio/mpeg")},
    )
    assert invalid_type_response.status_code == 415
    assert invalid_type_response.headers["X-Error-Code"] == "unsupported_media_type"
    assert invalid_type_response.headers["X-Error-Hint"] == "check_format"

    monkeypatch.setattr("abachiwave.services.audio.MAX_AUDIO_UPLOAD_BYTES", 16)
    too_large_response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads",
        data={"kind": "humming"},
        files={"file": ("humming.wav", _wav_bytes(), "audio/wav")},
    )
    assert too_large_response.status_code == 413
    assert too_large_response.headers["X-Error-Code"] == "upload_too_large"
    assert too_large_response.headers["X-Error-Hint"] == "trim_audio_under_25mb"


@pytest.mark.asyncio
async def test_audio_upload_enforces_per_project_limit_before_storage_write(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, storage, _queue = client_with_audio_deps
    project_id = await _create_project(client)
    monkeypatch.setenv("MAX_PROJECT_UPLOADS", "1")
    get_settings.cache_clear()

    try:
        await _upload_wav(client, project_id)
        response = await client.post(
            f"/api/v1/projects/{project_id}/audio-uploads",
            data={"kind": "reference"},
            files={"file": ("second.wav", _wav_bytes(), "audio/wav")},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "Project audio upload limit reached (1)"
    assert len(storage.objects) == 1


@pytest.mark.asyncio
async def test_audio_to_midi_requires_approved_song_spec(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
) -> None:
    client, _storage, _queue = client_with_audio_deps
    project_id, song_spec = await _create_song_spec(client, approved=False)
    upload = await _upload_wav(client, project_id)

    response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/extract-midi",
        json={"song_spec_id": song_spec["id"]},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_audio_to_midi_worker_creates_melody_midi(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, queue = client_with_audio_deps
    project_id, song_spec = await _create_song_spec(client, approved=True)
    upload = await _upload_wav(client, project_id)

    response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/extract-midi",
        json={"song_spec_id": song_spec["id"]},
    )
    assert response.status_code == 202
    run = response.json()
    assert run["run_type"] == "audio_to_midi"
    assert run["status"] == "queued"
    assert run["input_manifest"]["analysis_range"] == {
        "mode": "full",
        "start_seconds": 0.0,
        "end_seconds": upload["duration_seconds"],
    }
    # Provider routing keys off the upload kind, so a finished run has to carry it.
    assert run["input_manifest"]["audio_upload_kind"] == "humming"
    assert queue.enqueued == [UUID(run["id"])]

    executed = await execute_audio_to_midi(
        UUID(run["id"]),
        storage=storage,
        session_factory=session_factory,
    )

    assert executed is not None
    task = (await client.get(f"/api/v1/tasks/{run['id']}")).json()
    assert task["status"] == "succeeded"
    assert task["result_midi_asset_id"]
    midi_assets_response = await client.get(f"/api/v1/projects/{project_id}/midi-assets")
    assert midi_assets_response.status_code == 200
    melody = midi_assets_response.json()[0]
    assert melody["kind"] == "melody"
    assert melody["source_audio_upload_id"] == upload["id"]

    download_response = await client.get(
        f"/api/v1/projects/{project_id}/midi-assets/{melody['id']}/download"
    )
    assert download_response.status_code == 200
    assert download_response.content.startswith(b"MThd")
    MidiFile(file=BytesIO(download_response.content))


@pytest.mark.asyncio
async def test_audio_to_midi_worker_accepts_pre_lineage_queued_run(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, _queue = client_with_audio_deps
    project_id, song_spec = await _create_song_spec(client, approved=True)
    upload = await _upload_wav(client, project_id)
    response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/extract-midi",
        json={"song_spec_id": song_spec["id"]},
    )
    assert response.status_code == 202
    run = response.json()

    async with session_factory() as session:
        queued_run = await session.get(GenerationRun, run["id"])
        assert queued_run is not None
        legacy_manifest = dict(queued_run.input_manifest)
        legacy_manifest.pop("source_checksum")
        legacy_manifest.pop("analyzed_checksum")
        queued_run.input_manifest = legacy_manifest
        await session.commit()

    executed = await execute_audio_to_midi(
        UUID(run["id"]),
        storage=storage,
        session_factory=session_factory,
    )

    assert executed is not None
    assert executed.status == "succeeded"
    midi_assets = (
        await client.get(f"/api/v1/projects/{project_id}/midi-assets")
    ).json()
    source_manifest = midi_assets[0]["source_provider_manifest"]
    assert source_manifest["source_checksum"] == upload["checksum"]
    assert source_manifest["analyzed_checksum"] == upload["checksum"]


@pytest.mark.asyncio
async def test_audio_to_midi_analysis_range_is_validated_persisted_and_applied(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, queue = client_with_audio_deps
    project_id, song_spec = await _create_song_spec(client, approved=True)
    upload = await _upload_wav(client, project_id)
    endpoint = f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/extract-midi"

    outside_response = await client.post(
        endpoint,
        json={
            "song_spec_id": song_spec["id"],
            "analysis_range": {"start_seconds": 0.5, "end_seconds": 1.5},
        },
    )
    assert outside_response.status_code == 422
    assert outside_response.headers["X-Error-Code"] == "validation_failed"
    assert "analysis_range" in outside_response.json()["fields"]

    reversed_response = await client.post(
        endpoint,
        json={
            "song_spec_id": song_spec["id"],
            "analysis_range": {"start_seconds": 0.8, "end_seconds": 0.2},
        },
    )
    assert reversed_response.status_code == 422
    assert queue.enqueued == []

    create_response = await client.post(
        endpoint,
        json={
            "song_spec_id": song_spec["id"],
            "analysis_range": {"start_seconds": 0.2, "end_seconds": 0.6},
        },
    )
    assert create_response.status_code == 202
    run = create_response.json()
    assert run["input_manifest"]["analysis_range"] == {
        "mode": "selection",
        "start_seconds": 0.2,
        "end_seconds": 0.6,
    }

    provider = CapturingAudioProvider()
    executed = await execute_audio_to_midi(
        UUID(run["id"]),
        storage=storage,
        provider=provider,
        session_factory=session_factory,
    )
    assert executed is not None
    assert executed.status == "succeeded"
    assert executed.provider_usage["analysis_range"] == run["input_manifest"]["analysis_range"]
    assert (
        cast(int, executed.provider_usage["analyzed_audio_bytes"])
        < cast(int, executed.provider_usage["source_audio_bytes"])
    )
    assert len(provider.requests) == 1
    with wave.open(BytesIO(provider.requests[0].audio_bytes), "rb") as reader:
        assert reader.getnframes() / reader.getframerate() == pytest.approx(0.4, abs=0.001)


@pytest.mark.asyncio
async def test_reference_analysis_range_creates_traceable_candidate_versions(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, queue = client_with_audio_deps
    project_id = await _create_project(client, "Reference analysis")
    upload = await _upload_wav(client, project_id)
    endpoint = f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/analyze"
    range_payload = {
        "analysis_range": {"start_seconds": 0.2, "end_seconds": 0.8},
    }

    outside_response = await client.post(
        endpoint,
        json={"analysis_range": {"start_seconds": 0.8, "end_seconds": 1.2}},
    )
    assert outside_response.status_code == 422
    assert outside_response.headers["X-Error-Code"] == "validation_failed"

    create_response = await client.post(endpoint, json=range_payload)
    assert create_response.status_code == 202
    run = create_response.json()
    assert run["run_type"] == "reference_analysis"
    assert run["provider_name"] == "local_deterministic_reference_analysis"
    assert run["input_manifest"]["audio_derivative_id"] is None
    assert run["input_manifest"]["source_checksum"] == upload["checksum"]
    assert run["input_manifest"]["analysis_range"] == {
        "mode": "selection",
        "start_seconds": 0.2,
        "end_seconds": 0.8,
    }
    assert queue.analysis_enqueued == [UUID(run["id"])]

    duplicate_response = await client.post(endpoint, json=range_payload)
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == (
        "Reference analysis is already active for this range"
    )

    executed = await execute_reference_analysis(
        UUID(run["id"]),
        storage=storage,
        session_factory=session_factory,
    )
    assert executed is not None
    assert executed.status == "succeeded"
    assert executed.provider_usage["analysis_range"] == run["input_manifest"]["analysis_range"]
    assert cast(int, executed.provider_usage["analyzed_audio_bytes"]) < cast(
        int,
        executed.provider_usage["source_audio_bytes"],
    )

    list_response = await client.get(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/analyses"
    )
    assert list_response.status_code == 200
    analyses = list_response.json()
    assert len(analyses) == 1
    analysis = analyses[0]
    assert analysis["version_number"] == 1
    assert analysis["source_checksum"] == upload["checksum"]
    assert analysis["analysis_range"] == run["input_manifest"]["analysis_range"]
    assert analysis["tempo_bpm"] == 120
    assert analysis["key_candidate"]["value"] == "A major"
    assert analysis["pitch_range"]["low_midi"] == pytest.approx(69, abs=1)
    assert analysis["confidence"]["overall"] > 0
    assert analysis["structure_sections"]
    assert analysis["chord_candidates"]
    assert analysis["instrument_tags"]
    assert analysis["energy_curve"]
    assert analysis["production_features"]

    detail_response = await client.get(
        f"/api/v1/projects/{project_id}/reference-analyses/{analysis['id']}"
    )
    assert detail_response.status_code == 200
    assert detail_response.json() == analysis

    second_create = await client.post(endpoint, json={})
    assert second_create.status_code == 202
    second_run = second_create.json()
    second_executed = await execute_reference_analysis(
        UUID(second_run["id"]),
        storage=storage,
        session_factory=session_factory,
    )
    assert second_executed is not None
    assert second_executed.status == "succeeded"
    version_list = (
        await client.get(
            f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/analyses"
        )
    ).json()
    assert [item["version_number"] for item in version_list] == [2, 1]


@pytest.mark.asyncio
async def test_audio_to_midi_preserves_reference_analysis_and_provider_lineage(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, queue = client_with_audio_deps
    project_id, song_spec = await _create_song_spec(client, approved=True)
    upload = await _upload_wav(client, project_id)
    selected_range = {"start_seconds": 0.2, "end_seconds": 0.8}
    analysis_run = (
        await client.post(
            f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/analyze",
            json={"analysis_range": selected_range},
        )
    ).json()
    analyzed = await execute_reference_analysis(
        UUID(analysis_run["id"]),
        storage=storage,
        session_factory=session_factory,
    )
    assert analyzed is not None
    analysis_id = cast(str, analyzed.provider_usage["reference_analysis_id"])
    endpoint = f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/extract-midi"

    mismatched_range = await client.post(
        endpoint,
        json={
            "song_spec_id": song_spec["id"],
            "reference_analysis_id": analysis_id,
        },
    )
    assert mismatched_range.status_code == 409
    assert mismatched_range.json()["detail"] == (
        "Reference analysis range must match the MIDI extraction range"
    )

    create_response = await client.post(
        endpoint,
        json={
            "song_spec_id": song_spec["id"],
            "reference_analysis_id": analysis_id,
            "analysis_range": selected_range,
        },
    )
    assert create_response.status_code == 202
    run = create_response.json()
    assert run["input_manifest"]["reference_analysis_id"] == analysis_id
    assert run["input_manifest"]["source_checksum"] == upload["checksum"]
    assert run["input_manifest"]["analyzed_checksum"] == upload["checksum"]
    assert run["input_manifest"]["audio_derivative_id"] is None
    assert run["provider_name"] == "local_monophonic_wav_to_midi"

    executed = await execute_audio_to_midi(
        UUID(run["id"]),
        storage=storage,
        session_factory=session_factory,
    )
    assert executed is not None
    assert executed.status == "succeeded"
    assert executed.provider_usage["reference_analysis_id"] == analysis_id
    assert cast(int, executed.provider_usage["note_count"]) > 0

    midi_assets = (await client.get(f"/api/v1/projects/{project_id}/midi-assets")).json()
    melody = midi_assets[0]
    assert melody["source_audio_upload_id"] == upload["id"]
    assert melody["source_reference_analysis_id"] == analysis_id
    assert melody["note_events"]
    assert all(note["duration_beats"] > 0 for note in melody["note_events"])
    assert all(1 <= note["velocity"] <= 127 for note in melody["note_events"])
    manifest = melody["source_provider_manifest"]
    assert manifest["generation_run_id"] == run["id"]
    assert manifest["provider_name"] == run["provider_name"]
    assert manifest["provider_version"] == run["provider_version"]
    assert manifest["reference_analysis_id"] == analysis_id
    assert manifest["analysis_range"] == run["input_manifest"]["analysis_range"]
    assert queue.enqueued == [UUID(run["id"])]

    events = (await client.get(f"/api/v1/projects/{project_id}/events")).json()
    event_types = {event["event_type"] for event in events}
    assert {
        "audio.reference_analysis.queued",
        "audio.reference_analysis.ready",
    }.issubset(event_types)


@pytest.mark.asyncio
async def test_compressed_reference_analysis_uses_recorded_pcm_derivative(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, queue = client_with_audio_deps
    project_id = await _create_project(client, "Compressed reference analysis")
    upload_response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads",
        data={"kind": "reference"},
        files={"file": ("reference.mp3", b"ID3" + bytes(125), "audio/mpeg")},
    )
    upload = upload_response.json()
    derivative_run = await execute_audio_derivative(
        queue.derivative_enqueued[0],
        storage=storage,
        converter=FakeAudioConverter(),
        session_factory=session_factory,
    )
    assert derivative_run is not None
    derivative_id = cast(str, derivative_run.provider_usage["audio_derivative_id"])

    create_response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/analyze",
        json={},
    )
    assert create_response.status_code == 202
    run = create_response.json()
    assert run["input_manifest"]["audio_derivative_id"] == derivative_id
    executed = await execute_reference_analysis(
        UUID(run["id"]),
        storage=storage,
        session_factory=session_factory,
    )
    assert executed is not None
    assert executed.status == "succeeded"

    analyses = (
        await client.get(
            f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/analyses"
        )
    ).json()
    assert analyses[0]["audio_derivative_id"] == derivative_id
    assert analyses[0]["source_checksum"] == upload["checksum"]


@pytest.mark.asyncio
async def test_reference_analysis_apply_previews_impact_then_creates_song_spec_draft(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, _queue = client_with_audio_deps
    project_id, song_spec = await _create_song_spec(client, approved=True)
    upload = await _upload_wav(client, project_id)
    run = (
        await client.post(
            f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/analyze",
            json={},
        )
    ).json()
    executed = await execute_reference_analysis(
        UUID(run["id"]),
        storage=storage,
        session_factory=session_factory,
    )
    assert executed is not None
    analysis_id = cast(str, executed.provider_usage["reference_analysis_id"])
    endpoint = f"/api/v1/projects/{project_id}/reference-analyses/{analysis_id}/apply"
    fields = ["tempo_bpm", "key", "time_signature"]

    preview_response = await client.post(
        endpoint,
        json={"song_spec_id": song_spec["id"], "fields": fields},
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["applied"] is False
    assert preview["requires_confirmation"] is True
    assert preview["new_song_spec_id"] is None
    assert preview["selected_fields"] == fields
    assert {change["field"] for change in preview["changes"]} == {"tempo_bpm", "key"}
    assert preview["affected_asset_counts"] == {
        "lyrics": 0,
        "chords": 0,
        "midi": 0,
        "arrangements": 0,
    }
    assert len(preview["warnings"]) == 2
    before_apply = await client.get(f"/api/v1/projects/{project_id}/song-specs")
    assert len(before_apply.json()) == 1

    apply_response = await client.post(
        endpoint,
        json={"song_spec_id": song_spec["id"], "fields": fields, "confirm": True},
    )
    assert apply_response.status_code == 200
    applied = apply_response.json()
    assert applied["applied"] is True
    assert applied["requires_confirmation"] is False
    assert applied["new_song_spec_version"] == 2

    versions = (await client.get(f"/api/v1/projects/{project_id}/song-specs")).json()
    assert len(versions) == 2
    draft = versions[0]
    assert draft["id"] == applied["new_song_spec_id"]
    assert draft["status"] == "draft"
    assert draft["parent_version_id"] == song_spec["id"]
    assert draft["song_spec"]["tempo_bpm"] == 120
    assert draft["song_spec"]["key"] == "A major"
    assert draft["song_spec"]["time_signature"] == "4/4"
    assert versions[1]["status"] == "approved"

    no_change_response = await client.post(
        endpoint,
        json={"song_spec_id": draft["id"], "fields": fields, "confirm": True},
    )
    assert no_change_response.status_code == 409

    events = (await client.get(f"/api/v1/projects/{project_id}/events")).json()
    assert "audio.reference_analysis.applied" in {event["event_type"] for event in events}


@pytest.mark.asyncio
async def test_audio_to_midi_cancel_and_not_found_cases(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, _queue = client_with_audio_deps
    project_id, song_spec = await _create_song_spec(client, approved=True)
    upload = await _upload_wav(client, project_id)

    missing_response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads/00000000-0000-0000-0000-000000000000/extract-midi",
        json={"song_spec_id": song_spec["id"]},
    )
    assert missing_response.status_code == 404

    run = (
        await client.post(
            f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/extract-midi",
            json={"song_spec_id": song_spec["id"]},
        )
    ).json()
    cancel_response = await client.post(f"/api/v1/tasks/{run['id']}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    executed = await execute_audio_to_midi(
        UUID(run["id"]),
        storage=storage,
        session_factory=session_factory,
    )
    assert executed is not None
    assert str(executed.status) == "cancelled"
    midi_assets_response = await client.get(f"/api/v1/projects/{project_id}/midi-assets")
    assert midi_assets_response.status_code == 200
    assert midi_assets_response.json() == []

    cancel_again_response = await client.post(f"/api/v1/tasks/{run['id']}/cancel")
    assert cancel_again_response.status_code == 409


@pytest.mark.asyncio
async def test_running_audio_to_midi_cancel_wins_without_creating_asset(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, _queue = client_with_audio_deps
    project_id, song_spec = await _create_song_spec(client, approved=True)
    upload = await _upload_wav(client, project_id)
    run = (
        await client.post(
            f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/extract-midi",
            json={"song_spec_id": song_spec["id"]},
        )
    ).json()
    provider = BlockingAudioProvider()
    worker_task = asyncio.create_task(
        execute_audio_to_midi(
            UUID(run["id"]),
            storage=storage,
            provider=provider,
            session_factory=session_factory,
        )
    )
    assert await asyncio.to_thread(provider.started.wait, 3)

    cancel_response = await client.post(f"/api/v1/tasks/{run['id']}/cancel")
    assert cancel_response.status_code == 200
    provider.release.set()
    executed = await worker_task

    assert executed is not None
    assert str(executed.status) == "cancelled"
    midi_response = await client.get(f"/api/v1/projects/{project_id}/midi-assets")
    assert midi_response.json() == []
    assert not any("/midi/" in key for key in storage.objects)


@pytest.mark.asyncio
async def test_audio_to_midi_preserves_provider_failure_code(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, _queue = client_with_audio_deps
    project_id, song_spec = await _create_song_spec(client, approved=True)
    upload = await _upload_wav(client, project_id)
    run = (
        await client.post(
            f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/extract-midi",
            json={"song_spec_id": song_spec["id"]},
        )
    ).json()

    executed = await execute_audio_to_midi(
        UUID(run["id"]),
        storage=storage,
        provider=TimeoutAudioProvider(),
        session_factory=session_factory,
    )

    assert executed is not None
    assert str(executed.status) == "failed"
    assert executed.error_code == "audio_to_midi_provider_timeout"
    assert executed.error_message == "fixture provider timed out"
    assert (await client.get(f"/api/v1/projects/{project_id}/midi-assets")).json() == []

    repeated = await execute_audio_to_midi(
        UUID(run["id"]),
        storage=storage,
        session_factory=session_factory,
    )
    assert repeated is not None
    assert str(repeated.status) == "failed"
    assert (await client.get(f"/api/v1/projects/{project_id}/midi-assets")).json() == []


@pytest.mark.asyncio
async def test_audio_to_midi_storage_failure_cleans_partial_object(
    client_with_audio_deps: tuple[AsyncClient, MemoryStorage, FakeAudioQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, base_storage, _queue = client_with_audio_deps
    project_id, song_spec = await _create_song_spec(client, approved=True)
    upload = await _upload_wav(client, project_id)
    run = (
        await client.post(
            f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/extract-midi",
            json={"song_spec_id": song_spec["id"]},
        )
    ).json()
    failing_storage = WriteThenFailMidiStorage()
    failing_storage.objects.update(base_storage.objects)
    failing_storage.content_types.update(base_storage.content_types)

    executed = await execute_audio_to_midi(
        UUID(run["id"]),
        storage=failing_storage,
        session_factory=session_factory,
    )

    assert executed is not None
    assert str(executed.status) == "failed"
    assert not any("/midi/" in key for key in failing_storage.objects)
    midi_response = await client.get(f"/api/v1/projects/{project_id}/midi-assets")
    assert midi_response.json() == []


def _wav_bytes() -> bytes:
    sample_rate = 8000
    duration_seconds = 1.0
    frequency = 440.0
    amplitude = 12000
    buffer = BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        for index in range(int(sample_rate * duration_seconds)):
            sample = int(amplitude * sin(2 * pi * frequency * index / sample_rate))
            writer.writeframesraw(sample.to_bytes(2, byteorder="little", signed=True))
    return buffer.getvalue()

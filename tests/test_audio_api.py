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
from abachiwave.services.audio import execute_audio_to_midi
from abachiwave.services.audio_to_midi_provider import (
    AudioToMidiRequest,
    GeneratedMidi,
    LocalMonophonicWavToMidiProvider,
)
from abachiwave.services.storage import get_object_storage
from abachiwave.services.task_queue import get_audio_to_midi_task_queue


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

    async def enqueue_audio_to_midi(self, run_id: UUID) -> str:
        self.enqueued.append(run_id)
        return f"fake-audio-job-{run_id}"


class BlockingAudioProvider(LocalMonophonicWavToMidiProvider):
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    def extract_midi(self, request: AudioToMidiRequest) -> GeneratedMidi:
        self.started.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError("test provider was not released")
        return super().extract_midi(request)


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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client, storage, queue
    app.dependency_overrides.pop(get_object_storage, None)
    app.dependency_overrides.pop(get_audio_to_midi_task_queue, None)


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

    download_response = await client.get(
        f"/api/v1/projects/{project_id}/audio-uploads/{upload['id']}/download"
    )
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith("audio/wav")
    assert download_response.content.startswith(b"RIFF")


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

    monkeypatch.setattr("abachiwave.services.audio.MAX_AUDIO_UPLOAD_BYTES", 16)
    too_large_response = await client.post(
        f"/api/v1/projects/{project_id}/audio-uploads",
        data={"kind": "humming"},
        files={"file": ("humming.wav", _wav_bytes(), "audio/wav")},
    )
    assert too_large_response.status_code == 413


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

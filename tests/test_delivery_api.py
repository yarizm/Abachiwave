import json
from collections.abc import AsyncIterator
from hashlib import sha256
from io import BytesIO
from uuid import UUID, uuid4
from zipfile import ZipFile

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.models.audio import AudioUpload, AudioUploadKind, AudioUploadStatus
from abachiwave.models.demo import AudioDemoVersion, GenerationRun, GenerationRunStatus
from abachiwave.services.storage import get_object_storage


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}
        self.fail_export_put = False

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        if self.fail_export_put and "/exports/" in key:
            raise RuntimeError("export storage failed")
        self.objects[key] = data
        self.content_types[key] = content_type

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def delete_bytes(self, key: str) -> None:
        self.objects.pop(key, None)
        self.content_types.pop(key, None)


@pytest_asyncio.fixture
async def client_with_storage(app: FastAPI) -> AsyncIterator[tuple[AsyncClient, MemoryStorage]]:
    storage = MemoryStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client, storage
    app.dependency_overrides.pop(get_object_storage, None)


async def _create_project(client: AsyncClient) -> str:
    response = await client.post("/api/v1/projects", json={"name": "Delivery Project"})
    assert response.status_code == 201
    return str(UUID(response.json()["id"]))


async def _create_approved_song_spec(client: AsyncClient) -> tuple[str, dict[str, object]]:
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
    approve_response = await client.post(
        f"/api/v1/projects/{project_id}/song-specs/{song_spec_response.json()['id']}/approve"
    )
    assert approve_response.status_code == 200
    return project_id, approve_response.json()


async def _create_full_asset_chain(
    client: AsyncClient,
) -> tuple[str, dict[str, object], dict[str, object], dict[str, object], list[dict[str, object]]]:
    project_id, song_spec = await _create_approved_song_spec(client)
    lyrics_response = await client.post(
        f"/api/v1/projects/{project_id}/lyrics/generate",
        json={"song_spec_id": song_spec["id"]},
    )
    assert lyrics_response.status_code == 201
    lyrics = lyrics_response.json()
    chords_response = await client.post(
        f"/api/v1/projects/{project_id}/chords/generate",
        json={"song_spec_id": song_spec["id"], "lyrics_version_id": lyrics["id"]},
    )
    assert chords_response.status_code == 201
    chords = chords_response.json()
    midi_response = await client.post(
        f"/api/v1/projects/{project_id}/midi/generate",
        json={
            "song_spec_id": song_spec["id"],
            "lyrics_version_id": lyrics["id"],
            "chord_version_id": chords["id"],
        },
    )
    assert midi_response.status_code == 201
    return project_id, song_spec, lyrics, chords, midi_response.json()


@pytest.mark.asyncio
async def test_arrangement_requires_complete_asset_chain(
    client_with_storage: tuple[AsyncClient, MemoryStorage],
) -> None:
    client, _storage = client_with_storage
    project_id, song_spec = await _create_approved_song_spec(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/arrangement/generate",
        json={"song_spec_id": song_spec["id"]},
    )

    assert response.status_code == 409
    assert set(response.json()["detail"]["missing"]) == {
        "lyrics",
        "chords",
        "midi_chord",
        "midi_melody",
        "midi_hook",
    }


@pytest.mark.asyncio
async def test_arrangement_asset_tree_and_export_zip(
    client_with_storage: tuple[AsyncClient, MemoryStorage],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage = client_with_storage
    project_id, song_spec, lyrics, chords, midi_assets = await _create_full_asset_chain(client)

    arrangement_response = await client.post(
        f"/api/v1/projects/{project_id}/arrangement/generate",
        json={"song_spec_id": song_spec["id"]},
    )
    assert arrangement_response.status_code == 201
    arrangement = arrangement_response.json()
    assert arrangement["version_number"] == 1
    assert arrangement["arrangement_plan"]["sections"]

    edited_payload = arrangement["arrangement_plan"]
    edited_payload["overview"] = "Updated deterministic arrangement overview."
    edited_response = await client.patch(
        f"/api/v1/projects/{project_id}/arrangements/{arrangement['id']}",
        json=edited_payload,
    )
    assert edited_response.status_code == 200
    edited = edited_response.json()
    assert edited["version_number"] == 2
    assert edited["parent_version_id"] == arrangement["id"]

    asset_tree_response = await client.get(f"/api/v1/projects/{project_id}/assets")
    assert asset_tree_response.status_code == 200
    asset_tree = asset_tree_response.json()
    assert asset_tree["missing_prerequisites"] == []
    assert asset_tree["current"]["arrangement"]["version_number"] == 2
    assert {"song_spec", "lyrics", "chords", "midi", "arrangement"}.issubset(
        {item["asset_type"] for item in asset_tree["timeline"]}
    )

    comment_response = await client.post(
        f"/api/v1/projects/{project_id}/comments",
        json={
            "author_name": "Export reviewer",
            "body": "Confirm the exported arrangement notes.",
            "target_type": "arrangement",
            "target_id": edited["id"],
        },
    )
    assert comment_response.status_code == 201
    await _add_export_audio_assets(
        session_factory=session_factory,
        storage=storage,
        project_id=project_id,
        song_spec=song_spec,
        lyrics=lyrics,
        chords=chords,
        midi_assets=midi_assets,
        arrangement=edited,
    )

    export_response = await client.post(f"/api/v1/projects/{project_id}/exports", json={})
    assert export_response.status_code == 201
    export = export_response.json()
    assert export["status"] == "ready"
    assert export["download_url"]
    assert export["checksum"]

    download_response = await client.get(export["download_url"])
    assert download_response.status_code == 200
    with ZipFile(BytesIO(download_response.content)) as archive:
        names = set(archive.namelist())
        assert {
            "README.md",
            "manifest.json",
            "song-spec.json",
            "lyrics.md",
            "lyrics.json",
            "chords.md",
            "chords.json",
            "arrangement.md",
            "arrangement.json",
            "comments.md",
            "comments.json",
            "events.json",
            "handoff.md",
            "handoff.json",
            "review.json",
            "demos.json",
            "audio-uploads.json",
        }.issubset(names)
        assert any(name.startswith("midi/") and name.endswith(".mid") for name in names)
        assert any(name.startswith("demos/") and name.endswith(".wav") for name in names)
        assert any(name.startswith("audio-uploads/") and name.endswith(".wav") for name in names)
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        comments = json.loads(archive.read("comments.json").decode("utf-8"))
        events = json.loads(archive.read("events.json").decode("utf-8"))
        handoff = json.loads(archive.read("handoff.json").decode("utf-8"))
        handoff_markdown = archive.read("handoff.md").decode("utf-8")
        review = json.loads(archive.read("review.json").decode("utf-8"))
        demos = json.loads(archive.read("demos.json").decode("utf-8"))
        uploads = json.loads(archive.read("audio-uploads.json").decode("utf-8"))
        assert manifest["handoff"]["review"]["score"] == handoff["review"]["score"]
        assert manifest["comments"][0]["body"] == "Confirm the exported arrangement notes."
        assert comments[0]["target_type"] == "arrangement"
        assert "comment.created" in {event["event_type"] for event in events}
        assert handoff["open_comments"][0]["body"] == "Confirm the exported arrangement notes."
        assert "# Delivery Project Handoff" in handoff_markdown
        assert demos[0]["filename"] == "demo-v1.wav"
        assert archive.read(demos[0]["archive_path"]).startswith(b"RIFF")
        assert uploads[0]["filename"] == "humming.wav"
        assert archive.read(uploads[0]["archive_path"]).startswith(b"RIFF")
        assert review["status"] in {"ready", "needs_work"}

    events_response = await client.get(f"/api/v1/projects/{project_id}/events")
    assert events_response.status_code == 200
    event_types = {event["event_type"] for event in events_response.json()}
    assert {"arrangement.generated", "arrangement.edited", "export.ready"}.issubset(
        event_types
    )

    bad_token_response = await client.get(
        f"/api/v1/exports/{export['id']}/download?token=not-the-token"
    )
    assert bad_token_response.status_code == 403


@pytest.mark.asyncio
async def test_export_storage_failure_creates_failed_bundle(
    client_with_storage: tuple[AsyncClient, MemoryStorage],
) -> None:
    client, storage = client_with_storage
    project_id, song_spec, _lyrics, _chords, _midi_assets = await _create_full_asset_chain(client)
    arrangement_response = await client.post(
        f"/api/v1/projects/{project_id}/arrangement/generate",
        json={"song_spec_id": song_spec["id"]},
    )
    assert arrangement_response.status_code == 201
    storage.fail_export_put = True

    export_response = await client.post(f"/api/v1/projects/{project_id}/exports", json={})

    assert export_response.status_code == 201
    export = export_response.json()
    assert export["status"] == "failed"
    assert export["download_url"] is None
    assert export["error_message"] == "export storage failed"

    events_response = await client.get(f"/api/v1/projects/{project_id}/events")
    assert events_response.status_code == 200
    assert "export.failed" in {event["event_type"] for event in events_response.json()}


@pytest.mark.asyncio
async def test_delivery_not_found_cases(
    client_with_storage: tuple[AsyncClient, MemoryStorage],
) -> None:
    client, _storage = client_with_storage
    project_id, song_spec, _lyrics, _chords, _midi_assets = await _create_full_asset_chain(client)

    arrangement_response = await client.post(
        f"/api/v1/projects/{project_id}/arrangement/generate",
        json={
            "song_spec_id": song_spec["id"],
            "midi_asset_ids": ["00000000-0000-0000-0000-000000000000"],
        },
    )
    assert arrangement_response.status_code == 404

    export_response = await client.post(
        f"/api/v1/projects/{project_id}/exports",
        json={"arrangement_plan_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert export_response.status_code == 404


async def _add_export_audio_assets(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    storage: MemoryStorage,
    project_id: str,
    song_spec: dict[str, object],
    lyrics: dict[str, object],
    chords: dict[str, object],
    midi_assets: list[dict[str, object]],
    arrangement: dict[str, object],
) -> None:
    demo_bytes = b"RIFF\x04\x00\x00\x00WAVE"
    upload_bytes = b"RIFF\x04\x00\x00\x00WAVE"
    demo_storage_key = f"projects/{project_id}/demos/test-demo/demo-v1.wav"
    upload_storage_key = f"projects/{project_id}/audio-uploads/test-upload/humming.wav"
    storage.put_bytes(demo_storage_key, demo_bytes, "audio/wav")
    storage.put_bytes(upload_storage_key, upload_bytes, "audio/wav")
    async with session_factory() as session:
        run = GenerationRun(
            project_id=project_id,
            status=GenerationRunStatus.succeeded,
            input_manifest={"arrangement_plan_id": arrangement["id"]},
            provider_name="test_provider",
            provider_version="0.0.0",
            provider_params={},
        )
        session.add(run)
        await session.flush()
        demo = AudioDemoVersion(
            id=str(uuid4()),
            project_id=project_id,
            run_id=run.id,
            song_spec_id=str(song_spec["id"]),
            lyrics_version_id=str(lyrics["id"]),
            chord_version_id=str(chords["id"]),
            arrangement_plan_id=str(arrangement["id"]),
            midi_asset_ids=[str(asset["id"]) for asset in midi_assets],
            version_number=1,
            storage_key=demo_storage_key,
            filename="demo-v1.wav",
            content_type="audio/wav",
            size_bytes=len(demo_bytes),
            checksum=sha256(demo_bytes).hexdigest(),
            duration_seconds=1,
            waveform_peaks=[0.4] * 80,
            provider_name="test_provider",
            provider_version="0.0.0",
            provider_params={},
        )
        upload = AudioUpload(
            id=str(uuid4()),
            project_id=project_id,
            kind=AudioUploadKind.humming,
            status=AudioUploadStatus.available,
            storage_key=upload_storage_key,
            filename="humming.wav",
            content_type="audio/wav",
            size_bytes=len(upload_bytes),
            checksum=sha256(upload_bytes).hexdigest(),
            duration_seconds=1.0,
            sample_rate=8000,
            channels=1,
            waveform_peaks=[0.5] * 80,
            notes="export fixture",
        )
        session.add_all([demo, upload])
        await session.commit()

from collections.abc import AsyncIterator
from io import BytesIO
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from mido import MidiFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.models.demo import GenerationRun, GenerationRunStatus
from abachiwave.models.revision import ProjectEvent
from abachiwave.services.demo import execute_demo_generation
from abachiwave.services.demo_provider import LocalDeterministicWavProvider
from abachiwave.services.storage import get_object_storage
from abachiwave.services.task_queue import get_demo_task_queue


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


class FakeQueue:
    def __init__(self) -> None:
        self.enqueued: list[UUID] = []

    async def enqueue_demo_generation(self, run_id: UUID) -> str:
        self.enqueued.append(run_id)
        return f"fake-job-{run_id}"


@pytest_asyncio.fixture
async def client_with_revision_deps(
    app: FastAPI,
) -> AsyncIterator[tuple[AsyncClient, MemoryStorage, FakeQueue]]:
    storage = MemoryStorage()
    queue = FakeQueue()
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[get_demo_task_queue] = lambda: queue
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client, storage, queue
    app.dependency_overrides.pop(get_object_storage, None)
    app.dependency_overrides.pop(get_demo_task_queue, None)


async def _create_project(client: AsyncClient, name: str = "Revision Project") -> str:
    response = await client.post("/api/v1/projects", json={"name": name})
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
    generate_response = await client.post(
        f"/api/v1/projects/{project_id}/song-spec/generate",
        json={"intake_id": intake_response.json()["intake_id"]},
    )
    assert generate_response.status_code == 200
    approve_response = await client.post(
        f"/api/v1/projects/{project_id}/song-specs/{generate_response.json()['id']}/approve"
    )
    assert approve_response.status_code == 200
    return project_id, approve_response.json()


async def _create_full_asset_chain(
    client: AsyncClient,
) -> tuple[str, dict[str, object], dict[str, object], list[dict[str, object]], dict[str, object]]:
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
    arrangement_response = await client.post(
        f"/api/v1/projects/{project_id}/arrangement/generate",
        json={"song_spec_id": song_spec["id"]},
    )
    assert arrangement_response.status_code == 201
    return project_id, lyrics, chords, midi_response.json(), arrangement_response.json()


@pytest.mark.asyncio
async def test_lyrics_revision_plans_then_applies_without_mutating_before_apply(
    client_with_revision_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, _storage, queue = client_with_revision_deps
    project_id, lyrics, _chords, _midi_assets, _arrangement = await _create_full_asset_chain(client)

    plan_response = await client.post(
        f"/api/v1/projects/{project_id}/revisions",
        json={"feedback": "副歌歌词更有力量"},
    )

    assert plan_response.status_code == 201
    revision = plan_response.json()
    assert revision["status"] == "planned"
    assert revision["tasks"][0]["target"] == "lyrics"
    assert revision["tasks"][0]["supported"] is True
    lyrics_before_apply = (await client.get(f"/api/v1/projects/{project_id}/lyrics")).json()
    assert [item["version_number"] for item in lyrics_before_apply] == [1]

    apply_response = await client.post(
        f"/api/v1/projects/{project_id}/revisions/{revision['id']}/apply",
        json={"regenerate_demo": True},
    )

    assert apply_response.status_code == 200
    applied = apply_response.json()
    assert applied["revision"]["status"] == "applied"
    assert applied["created_versions"][0]["asset_type"] == "lyrics"
    assert applied["created_versions"][0]["source_revision_request_id"] == revision["id"]
    assert applied["demo_run"]["status"] == "queued"
    assert queue.enqueued == [UUID(applied["demo_run"]["id"])]

    lyrics_after_apply = (await client.get(f"/api/v1/projects/{project_id}/lyrics")).json()
    assert [item["version_number"] for item in lyrics_after_apply] == [2, 1]
    assert lyrics_after_apply[0]["parent_version_id"] == lyrics["id"]
    assert lyrics_after_apply[0]["source_revision_request_id"] == revision["id"]
    assert any("Revision:" in section["text"] for section in lyrics_after_apply[0]["sections"])

    async with session_factory() as session:
        events = (
            await session.execute(
                select(ProjectEvent).where(ProjectEvent.project_id == project_id)
            )
        ).scalars().all()
    event_types = {event.event_type for event in events}
    assert {"revision.planned", "revision.applied", "revision.version_created"}.issubset(
        event_types
    )


@pytest.mark.asyncio
async def test_melody_revision_diff_and_restore(
    client_with_revision_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
) -> None:
    client, _storage, _queue = client_with_revision_deps
    project_id, _lyrics, _chords, midi_assets, _arrangement = await _create_full_asset_chain(client)
    melody = next(asset for asset in midi_assets if asset["kind"] == "melody")

    plan_response = await client.post(
        f"/api/v1/projects/{project_id}/revisions",
        json={"feedback": "副歌旋律再抬高一点"},
    )
    revision = plan_response.json()
    apply_response = await client.post(
        f"/api/v1/projects/{project_id}/revisions/{revision['id']}/apply",
        json={},
    )

    assert apply_response.status_code == 200
    created = apply_response.json()["created_versions"][0]
    assert created["asset_type"] == "midi_melody"
    midi_list = (await client.get(f"/api/v1/projects/{project_id}/midi-assets")).json()
    new_melody = next(asset for asset in midi_list if asset["id"] == created["id"])
    assert new_melody["source_revision_request_id"] == revision["id"]
    download = await client.get(
        f"/api/v1/projects/{project_id}/midi-assets/{new_melody['id']}/download"
    )
    assert download.status_code == 200
    MidiFile(file=BytesIO(download.content))

    diff_response = await client.get(
        f"/api/v1/projects/{project_id}/versions/diff",
        params={
            "asset_type": "midi_melody",
            "left_id": str(melody["id"]),
            "right_id": str(new_melody["id"]),
        },
    )
    assert diff_response.status_code == 200
    assert diff_response.json()["asset_type"] == "midi_melody"
    assert diff_response.json()["changes"]

    restore_response = await client.post(
        f"/api/v1/projects/{project_id}/versions/restore",
        json={"asset_type": "midi_melody", "version_id": melody["id"]},
    )
    assert restore_response.status_code == 200
    restored = restore_response.json()["version"]
    assert restored["version_number"] > new_melody["version_number"]
    asset_tree = (await client.get(f"/api/v1/projects/{project_id}/assets")).json()
    current_melody = next(
        asset for asset in asset_tree["current"]["midi_assets"] if asset["kind"] == "melody"
    )
    assert current_melody["id"] == restored["id"]


@pytest.mark.asyncio
async def test_arrangement_revision_reject_diff_and_restore(
    client_with_revision_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
) -> None:
    client, _storage, _queue = client_with_revision_deps
    project_id, _lyrics, _chords, _midi_assets, arrangement = await _create_full_asset_chain(client)

    rejected_response = await client.post(
        f"/api/v1/projects/{project_id}/revisions",
        json={"feedback": "桥段把鼓抽掉、前奏更空"},
    )
    rejected = rejected_response.json()
    reject_response = await client.post(
        f"/api/v1/projects/{project_id}/revisions/{rejected['id']}/reject"
    )
    apply_rejected_response = await client.post(
        f"/api/v1/projects/{project_id}/revisions/{rejected['id']}/apply",
        json={},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "rejected"
    assert apply_rejected_response.status_code == 409

    plan_response = await client.post(
        f"/api/v1/projects/{project_id}/revisions",
        json={"feedback": "桥段把鼓抽掉、前奏更空"},
    )
    revision = plan_response.json()
    apply_response = await client.post(
        f"/api/v1/projects/{project_id}/revisions/{revision['id']}/apply",
        json={},
    )
    assert apply_response.status_code == 200
    created = apply_response.json()["created_versions"][0]
    assert created["asset_type"] == "arrangement"

    diff_response = await client.get(
        f"/api/v1/projects/{project_id}/versions/diff",
        params={
            "asset_type": "arrangement",
            "left_id": str(arrangement["id"]),
            "right_id": str(created["id"]),
        },
    )
    assert diff_response.status_code == 200
    assert diff_response.json()["changes"]

    restore_response = await client.post(
        f"/api/v1/projects/{project_id}/versions/restore",
        json={"asset_type": "arrangement", "version_id": arrangement["id"]},
    )
    assert restore_response.status_code == 200
    restored = restore_response.json()["version"]
    assert restored["parent_version_id"] == arrangement["id"]
    asset_tree = (await client.get(f"/api/v1/projects/{project_id}/assets")).json()
    assert asset_tree["current"]["arrangement"]["id"] == restored["id"]


@pytest.mark.asyncio
async def test_demo_diff_and_task_cancel_states(
    client_with_revision_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, _queue = client_with_revision_deps
    project_id, _lyrics, _chords, _midi_assets, _arrangement = (
        await _create_full_asset_chain(client)
    )

    queued_run = (
        await client.post(f"/api/v1/projects/{project_id}/demo/generate", json={})
    ).json()
    cancel_response = await client.post(f"/api/v1/tasks/{queued_run['id']}/cancel")
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"
    executed = await execute_demo_generation(
        UUID(queued_run["id"]),
        storage=storage,
        provider=LocalDeterministicWavProvider(default_duration_seconds=1),
        session_factory=session_factory,
    )
    assert executed is not None
    assert executed.status == GenerationRunStatus.cancelled

    running_run = (
        await client.post(f"/api/v1/projects/{project_id}/demo/generate", json={})
    ).json()
    async with session_factory() as session:
        run = await session.get(GenerationRun, running_run["id"])
        assert run is not None
        run.status = GenerationRunStatus.running
        await session.commit()
    running_cancel_response = await client.post(f"/api/v1/tasks/{running_run['id']}/cancel")
    assert running_cancel_response.status_code == 200
    assert running_cancel_response.json()["status"] == "cancelled"

    first_run = (
        await client.post(f"/api/v1/projects/{project_id}/demo/generate", json={})
    ).json()
    await execute_demo_generation(
        UUID(first_run["id"]),
        storage=storage,
        provider=LocalDeterministicWavProvider(default_duration_seconds=1),
        session_factory=session_factory,
    )
    second_run = (
        await client.post(f"/api/v1/projects/{project_id}/demo/generate", json={})
    ).json()
    await execute_demo_generation(
        UUID(second_run["id"]),
        storage=storage,
        provider=LocalDeterministicWavProvider(default_duration_seconds=1),
        session_factory=session_factory,
    )
    demos = (await client.get(f"/api/v1/projects/{project_id}/demos")).json()
    diff_response = await client.get(
        f"/api/v1/projects/{project_id}/versions/diff",
        params={
            "asset_type": "demo",
            "left_id": demos[1]["id"],
            "right_id": demos[0]["id"],
        },
    )
    assert diff_response.status_code == 200
    assert diff_response.json()["asset_type"] == "demo"

    cancel_succeeded_response = await client.post(f"/api/v1/tasks/{first_run['id']}/cancel")
    assert cancel_succeeded_response.status_code == 409

    async with session_factory() as session:
        events = (
            await session.execute(
                select(ProjectEvent).where(ProjectEvent.project_id == project_id)
            )
        ).scalars().all()
    assert {"task.cancelled", "demo.generated"}.issubset({event.event_type for event in events})


@pytest.mark.asyncio
async def test_project_events_endpoint_lists_recorded_events(
    client_with_revision_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
) -> None:
    client, _storage, _queue = client_with_revision_deps
    project_id, _lyrics, _chords, _midi_assets, _arrangement = (
        await _create_full_asset_chain(client)
    )

    revision_response = await client.post(
        f"/api/v1/projects/{project_id}/revisions",
        json={"feedback": "Make the chorus lyric stronger."},
    )
    assert revision_response.status_code == 201

    events_response = await client.get(f"/api/v1/projects/{project_id}/events")

    assert events_response.status_code == 200
    events = events_response.json()
    assert events
    assert any(event["event_type"] == "revision.planned" for event in events)
    planned_event = next(event for event in events if event["event_type"] == "revision.planned")
    assert planned_event["project_id"] == project_id
    assert planned_event["revision_request_id"] == revision_response.json()["id"]
    assert planned_event["payload"]["task_count"] >= 1


@pytest.mark.asyncio
async def test_project_events_endpoint_returns_404_for_missing_project(
    client_with_revision_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
) -> None:
    client, _storage, _queue = client_with_revision_deps

    response = await client.get(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/events"
    )

    assert response.status_code == 404

import asyncio
from collections.abc import AsyncIterator
from threading import Event
from uuid import UUID

import pytest
import pytest_asyncio
import sqlalchemy as sa
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.core.config import Settings
from abachiwave.models.demo import GenerationRun
from abachiwave.services import demo as demo_service
from abachiwave.services.demo import execute_demo_generation
from abachiwave.services.demo_provider import (
    DemoGenerationRequest,
    GeneratedAudio,
    LocalDeterministicWavProvider,
)
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


class FailingProvider:
    name = "failing_provider"
    version = "0.0.0"

    def default_params(self) -> dict[str, object]:
        return {"duration_seconds": 1}

    def generate_demo(self, request: DemoGenerationRequest) -> GeneratedAudio:
        raise RuntimeError("provider exploded")


class BlockingProvider(LocalDeterministicWavProvider):
    def __init__(self) -> None:
        super().__init__(default_duration_seconds=1)
        self.started = Event()
        self.release = Event()

    def generate_demo(self, request: DemoGenerationRequest) -> GeneratedAudio:
        self.started.set()
        if not self.release.wait(timeout=5):
            raise TimeoutError("test provider was not released")
        return super().generate_demo(request)


class WriteThenFailDemoStorage(MemoryStorage):
    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        super().put_bytes(key, data, content_type)
        if "/demos/" in key:
            raise RuntimeError("demo storage failed after write")


@pytest_asyncio.fixture
async def client_with_demo_deps(
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


async def _create_project(client: AsyncClient, name: str = "Demo Project") -> str:
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


async def _create_demo_ready_chain(client: AsyncClient) -> tuple[str, dict[str, object]]:
    project_id, song_spec = await _create_approved_song_spec(client)
    lyrics = (
        await client.post(
            f"/api/v1/projects/{project_id}/lyrics/generate",
            json={"song_spec_id": song_spec["id"]},
        )
    ).json()
    chords = (
        await client.post(
            f"/api/v1/projects/{project_id}/chords/generate",
            json={"song_spec_id": song_spec["id"], "lyrics_version_id": lyrics["id"]},
        )
    ).json()
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
    return project_id, arrangement_response.json()


@pytest.mark.asyncio
async def test_demo_generation_requires_arrangement(
    client_with_demo_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
) -> None:
    client, _storage, _queue = client_with_demo_deps
    project_id = await _create_project(client)

    response = await client.post(f"/api/v1/projects/{project_id}/demo/generate", json={})

    assert response.status_code == 409
    assert response.json()["detail"]["missing"] == ["arrangement"]
    assert response.json()["detail"]["error_code"] == "prerequisites_missing"
    assert response.headers["X-Error-Code"] == "prerequisites_missing"


@pytest.mark.asyncio
async def test_demo_generation_returns_provider_unavailable(
    client_with_demo_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _storage, _queue = client_with_demo_deps
    project_id, _arrangement = await _create_demo_ready_chain(client)
    monkeypatch.setattr(
        demo_service,
        "get_settings",
        lambda: Settings(_env_file=None, DEMO_PROVIDER_NAME="ghost_provider"),
    )

    response = await client.post(f"/api/v1/projects/{project_id}/demo/generate", json={})

    assert response.status_code == 503
    assert response.json() == {"detail": "Demo provider is unavailable"}
    assert response.headers["X-Error-Code"] == "provider_unavailable"
    assert response.headers["X-Error-Hint"] == "contact_support"


@pytest.mark.asyncio
async def test_demo_generation_creates_queued_run(
    client_with_demo_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
) -> None:
    client, _storage, queue = client_with_demo_deps
    project_id, arrangement = await _create_demo_ready_chain(client)

    response = await client.post(f"/api/v1/projects/{project_id}/demo/generate", json={})

    assert response.status_code == 202
    run = response.json()
    assert run["status"] == "queued"
    assert run["arq_job_id"] == f"fake-job-{run['id']}"
    assert run["input_manifest"]["arrangement_plan_id"] == arrangement["id"]
    assert queue.enqueued == [UUID(run["id"])]

    task_response = await client.get(f"/api/v1/tasks/{run['id']}")
    runs_response = await client.get(f"/api/v1/projects/{project_id}/runs")
    assert task_response.status_code == 200
    assert task_response.json()["status"] == "queued"
    assert [item["id"] for item in runs_response.json()] == [run["id"]]


@pytest.mark.asyncio
async def test_worker_generates_demo_wav_and_download(
    client_with_demo_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, _queue = client_with_demo_deps
    project_id, _arrangement = await _create_demo_ready_chain(client)
    run = (
        await client.post(f"/api/v1/projects/{project_id}/demo/generate", json={})
    ).json()

    executed = await execute_demo_generation(
        UUID(run["id"]),
        storage=storage,
        provider=LocalDeterministicWavProvider(default_duration_seconds=1),
        session_factory=session_factory,
    )

    assert executed is not None
    task_response = await client.get(f"/api/v1/tasks/{run['id']}")
    assert task_response.status_code == 200
    task = task_response.json()
    assert task["status"] == "succeeded"
    assert task["demo_id"]

    demos_response = await client.get(f"/api/v1/projects/{project_id}/demos")
    assert demos_response.status_code == 200
    demos = demos_response.json()
    assert len(demos) == 1
    assert demos[0]["content_type"] == "audio/wav"
    assert demos[0]["size_bytes"] > 44
    assert len(demos[0]["waveform_peaks"]) == 80
    assert max(demos[0]["waveform_peaks"]) > 0

    download_response = await client.get(
        f"/api/v1/projects/{project_id}/demos/{demos[0]['id']}/download"
    )
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith("audio/wav")
    assert download_response.content.startswith(b"RIFF")
    assert download_response.content[8:12] == b"WAVE"


@pytest.mark.asyncio
async def test_worker_failure_and_retry(
    client_with_demo_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, queue = client_with_demo_deps
    project_id, _arrangement = await _create_demo_ready_chain(client)
    run = (
        await client.post(f"/api/v1/projects/{project_id}/demo/generate", json={})
    ).json()

    executed = await execute_demo_generation(
        UUID(run["id"]),
        storage=storage,
        provider=FailingProvider(),
        session_factory=session_factory,
    )

    assert executed is not None
    failed_task = (await client.get(f"/api/v1/tasks/{run['id']}")).json()
    assert failed_task["status"] == "failed"
    assert failed_task["error_message"] == "provider exploded"

    retry_response = await client.post(f"/api/v1/tasks/{run['id']}/retry")
    assert retry_response.status_code == 200
    retry = retry_response.json()
    assert retry["status"] == "queued"
    assert retry["retry_of_run_id"] == run["id"]
    assert queue.enqueued[-1] == UUID(retry["id"])

    succeeded_run = (
        await client.post(f"/api/v1/projects/{project_id}/demo/generate", json={})
    ).json()
    await execute_demo_generation(
        UUID(succeeded_run["id"]),
        storage=storage,
        provider=LocalDeterministicWavProvider(default_duration_seconds=1),
        session_factory=session_factory,
    )
    retry_succeeded_response = await client.post(f"/api/v1/tasks/{succeeded_run['id']}/retry")
    assert retry_succeeded_response.status_code == 409


@pytest.mark.asyncio
async def test_running_demo_cancel_wins_without_creating_asset(
    client_with_demo_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, _queue = client_with_demo_deps
    project_id, _arrangement = await _create_demo_ready_chain(client)
    run = (
        await client.post(f"/api/v1/projects/{project_id}/demo/generate", json={})
    ).json()
    provider = BlockingProvider()
    worker_task = asyncio.create_task(
        execute_demo_generation(
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
    demos_response = await client.get(f"/api/v1/projects/{project_id}/demos")
    assert demos_response.json() == []
    assert not any("/demos/" in key for key in storage.objects)


@pytest.mark.asyncio
async def test_demo_storage_failure_cleans_partial_object(
    client_with_demo_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, _storage, _queue = client_with_demo_deps
    project_id, _arrangement = await _create_demo_ready_chain(client)
    run = (
        await client.post(f"/api/v1/projects/{project_id}/demo/generate", json={})
    ).json()
    failing_storage = WriteThenFailDemoStorage()

    executed = await execute_demo_generation(
        UUID(run["id"]),
        storage=failing_storage,
        provider=LocalDeterministicWavProvider(default_duration_seconds=1),
        session_factory=session_factory,
    )

    assert executed is not None
    assert str(executed.status) == "failed"
    assert not any("/demos/" in key for key in failing_storage.objects)
    demos_response = await client.get(f"/api/v1/projects/{project_id}/demos")
    assert demos_response.json() == []


@pytest.mark.asyncio
async def test_demo_not_found_and_cross_project_cases(
    client_with_demo_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, _queue = client_with_demo_deps
    project_id, _arrangement = await _create_demo_ready_chain(client)
    other_project_id = await _create_project(client, name="Other Project")
    run = (
        await client.post(f"/api/v1/projects/{project_id}/demo/generate", json={})
    ).json()
    await execute_demo_generation(
        UUID(run["id"]),
        storage=storage,
        provider=LocalDeterministicWavProvider(default_duration_seconds=1),
        session_factory=session_factory,
    )
    demo = (await client.get(f"/api/v1/projects/{project_id}/demos")).json()[0]

    missing_task_response = await client.get(
        "/api/v1/tasks/00000000-0000-0000-0000-000000000000"
    )
    cross_project_demo_response = await client.get(
        f"/api/v1/projects/{other_project_id}/demos/{demo['id']}"
    )
    missing_download_response = await client.get(
        f"/api/v1/projects/{project_id}/demos/00000000-0000-0000-0000-000000000000/download"
    )

    assert missing_task_response.status_code == 404
    assert cross_project_demo_response.status_code == 404
    assert missing_download_response.status_code == 404


@pytest.mark.asyncio
async def test_worker_fails_for_unknown_run_provider(
    client_with_demo_deps: tuple[AsyncClient, MemoryStorage, FakeQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, storage, _queue = client_with_demo_deps
    project_id, _arrangement = await _create_demo_ready_chain(client)
    run = (
        await client.post(f"/api/v1/projects/{project_id}/demo/generate", json={})
    ).json()
    # Simulate a run recorded with a provider that no longer exists.
    # (In practice this happens after a config rollback; here we force it.)
    async with session_factory() as session:
        await session.execute(
            sa.update(GenerationRun)
            .where(GenerationRun.id == run["id"])
            .values(provider_name="ghost_provider")
        )
        await session.commit()

    executed = await execute_demo_generation(
        UUID(run["id"]),
        storage=storage,
        session_factory=session_factory,
    )

    assert executed is not None
    assert str(executed.status) == "failed"
    assert executed.error_code == "demo_generation_failed"
    assert "ghost_provider" in (executed.error_message or "")

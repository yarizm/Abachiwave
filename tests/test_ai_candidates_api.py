from collections.abc import AsyncIterator
from typing import cast
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.models.composition import MidiAssetKind, MidiAssetVersion
from abachiwave.services.ai_generation import (
    REVISION_AVAILABLE_TARGETS,
    execute_candidate_generation,
)
from abachiwave.services.task_queue import get_text_generation_task_queue


class FakeTextQueue:
    def __init__(self) -> None:
        self.enqueued: list[UUID] = []

    async def enqueue_text_generation(self, run_id: UUID) -> str:
        self.enqueued.append(run_id)
        return f"text-job-{run_id}"


def test_revision_available_targets_match_task_target_enum() -> None:
    """The revision workflow must advertise only valid RevisionTaskTarget
    values; 'revision' itself is not a valid task target and midi_melody
    must be offered."""
    assert set(REVISION_AVAILABLE_TARGETS) == {"lyrics", "midi_melody", "arrangement"}


@pytest_asyncio.fixture
async def candidate_client(app: FastAPI) -> AsyncIterator[tuple[AsyncClient, FakeTextQueue]]:
    queue = FakeTextQueue()
    app.dependency_overrides[get_text_generation_task_queue] = lambda: queue
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, queue
    app.dependency_overrides.pop(get_text_generation_task_queue, None)


async def _create_project(client: AsyncClient, name: str = "Candidate Project") -> str:
    response = await client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201
    return cast(str, response.json()["id"])


async def _create_intake(client: AsyncClient, project_id: str) -> dict[str, object]:
    response = await client.post(
        f"/api/v1/projects/{project_id}/intake",
        json={
            "idea": (
                "English indie rock song about riding home at night. "
                "128 BPM, E major, 4/4, 3:30. Verse restrained, chorus hopeful."
            ),
            "answers": {"song_structure": "verse, chorus, bridge, final chorus"},
        },
    )
    assert response.status_code == 201
    return cast(dict[str, object], response.json())


async def _generate_candidates(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    project_id: str,
    payload: dict[str, object],
    endpoint: str = "candidates/generate",
) -> tuple[dict[str, object], list[dict[str, object]]]:
    response = await client.post(
        f"/api/v1/projects/{project_id}/{endpoint}",
        json=payload,
    )
    assert response.status_code == 202
    run = cast(dict[str, object], response.json())
    completed = await execute_candidate_generation(
        UUID(cast(str, run["id"])),
        session_factory=session_factory,
    )
    assert completed is not None
    assert completed.status == "succeeded"
    listed = await client.get(f"/api/v1/projects/{project_id}/candidates")
    assert listed.status_code == 200
    candidates = cast(list[dict[str, object]], listed.json())
    return run, [item for item in candidates if item["run_id"] == run["id"]]


@pytest.mark.asyncio
async def test_song_spec_candidates_are_not_assets_until_selected(
    candidate_client: tuple[AsyncClient, FakeTextQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, queue = candidate_client
    capabilities = await client.get("/api/v1/providers/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()[0]["provider_name"] == "local_deterministic"
    assert "api_key" not in capabilities.text

    project_id = await _create_project(client)
    intake = await _create_intake(client, project_id)
    create_run = await client.post(
        f"/api/v1/projects/{project_id}/song-spec/generate",
        json={
            "candidate_count": 2,
            "intake_id": intake["intake_id"],
        },
    )
    assert create_run.status_code == 202
    run = create_run.json()
    assert run["status"] == "queued"
    assert run["run_type"] == "text_generation"
    assert queue.enqueued == [UUID(run["id"])]
    assert (await client.get(f"/api/v1/projects/{project_id}/song-specs")).json() == []
    assert (await client.get(f"/api/v1/projects/{project_id}/candidates")).json() == []

    completed = await execute_candidate_generation(
        UUID(run["id"]),
        session_factory=session_factory,
    )
    assert completed is not None
    assert completed.status == "succeeded"

    candidates_response = await client.get(f"/api/v1/projects/{project_id}/candidates")
    assert candidates_response.status_code == 200
    candidates = candidates_response.json()
    assert len(candidates) == 2
    assert {item["candidate_index"] for item in candidates} == {1, 2}
    assert all(item["status"] == "pending" for item in candidates)
    assert (await client.get(f"/api/v1/projects/{project_id}/song-specs")).json() == []

    selection = await client.post(
        f"/api/v1/projects/{project_id}/candidates/{candidates[0]['id']}/select"
    )
    assert selection.status_code == 200
    assert selection.json()["asset_type"] == "song_spec"
    versions = (await client.get(f"/api/v1/projects/{project_id}/song-specs")).json()
    assert len(versions) == 1
    assert versions[0]["id"] == selection.json()["asset_id"]

    second_selection = await client.post(
        f"/api/v1/projects/{project_id}/candidates/{candidates[1]['id']}/select"
    )
    assert second_selection.status_code == 409


@pytest.mark.asyncio
async def test_candidate_generation_validates_workflow_sources(
    candidate_client: tuple[AsyncClient, FakeTextQueue],
) -> None:
    client, _queue = candidate_client
    project_id = await _create_project(client, "Candidate validation")
    missing_intake = await client.post(
        f"/api/v1/projects/{project_id}/candidates/generate",
        json={"workflow": "song_spec"},
    )
    assert missing_intake.status_code == 422

    unapproved_song_spec_id = "00000000-0000-0000-0000-000000000001"
    missing_song_spec = await client.post(
        f"/api/v1/projects/{project_id}/candidates/generate",
        json={"workflow": "lyrics", "song_spec_id": unapproved_song_spec_id},
    )
    assert missing_song_spec.status_code == 404


@pytest.mark.asyncio
async def test_lyrics_arrangement_and_revision_candidates_materialize_on_selection(
    candidate_client: tuple[AsyncClient, FakeTextQueue],
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    client, _queue = candidate_client
    project_id = await _create_project(client, "All candidate workflows")
    intake = await _create_intake(client, project_id)
    direct_spec = await client.post(
        f"/api/v1/projects/{project_id}/song-spec/generate",
        json={"intake_id": intake["intake_id"]},
    )
    assert direct_spec.status_code == 200
    approve = await client.post(
        f"/api/v1/projects/{project_id}/song-specs/{direct_spec.json()['id']}/approve"
    )
    assert approve.status_code == 200
    song_spec = cast(dict[str, object], approve.json())

    _lyrics_run, lyrics_candidates = await _generate_candidates(
        client,
        session_factory,
        project_id,
        {"song_spec_id": song_spec["id"], "candidate_count": 1},
        endpoint="lyrics/generate",
    )
    assert len(lyrics_candidates) == 1
    assert (await client.get(f"/api/v1/projects/{project_id}/lyrics")).json() == []
    selected_lyrics = await client.post(
        f"/api/v1/projects/{project_id}/candidates/{lyrics_candidates[0]['id']}/select"
    )
    assert selected_lyrics.status_code == 200
    lyrics_id = selected_lyrics.json()["asset_id"]

    chords_response = await client.post(
        f"/api/v1/projects/{project_id}/chords/generate",
        json={"song_spec_id": song_spec["id"], "lyrics_version_id": lyrics_id},
    )
    assert chords_response.status_code == 201
    chords_id = chords_response.json()["id"]
    async with session_factory() as session:
        for kind in MidiAssetKind:
            session.add(
                MidiAssetVersion(
                    project_id=project_id,
                    song_spec_id=cast(str, song_spec["id"]),
                    lyrics_version_id=lyrics_id,
                    chord_version_id=chords_id,
                    version_number=1,
                    kind=kind,
                    storage_key=f"test/{kind.value}.mid",
                    filename=f"{kind.value}.mid",
                    content_type="audio/midi",
                    size_bytes=14,
                    checksum="0" * 64,
                )
            )
        await session.commit()

    _arrangement_run, arrangement_candidates = await _generate_candidates(
        client,
        session_factory,
        project_id,
        {
            "song_spec_id": song_spec["id"],
            "candidate_count": 1,
        },
        endpoint="arrangement/generate",
    )
    assert len(arrangement_candidates) == 1
    assert (await client.get(f"/api/v1/projects/{project_id}/arrangements")).json() == []
    selected_arrangement = await client.post(
        f"/api/v1/projects/{project_id}/candidates/{arrangement_candidates[0]['id']}/select"
    )
    assert selected_arrangement.status_code == 200
    assert selected_arrangement.json()["asset_type"] == "arrangement"

    _revision_run, revision_candidates = await _generate_candidates(
        client,
        session_factory,
        project_id,
        {
            "feedback": "Make the chorus lyrics stronger",
            "candidate_count": 1,
        },
        endpoint="revisions",
    )
    assert len(revision_candidates) == 1
    assert (await client.get(f"/api/v1/projects/{project_id}/revisions")).json() == []
    selected_revision = await client.post(
        f"/api/v1/projects/{project_id}/candidates/{revision_candidates[0]['id']}/select"
    )
    assert selected_revision.status_code == 200
    assert selected_revision.json()["asset_type"] == "revision"
    revisions = (await client.get(f"/api/v1/projects/{project_id}/revisions")).json()
    assert len(revisions) == 1
    assert revisions[0]["status"] == "planned"

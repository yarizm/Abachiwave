from collections.abc import AsyncIterator
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from abachiwave.services.storage import get_object_storage


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def delete_bytes(self, key: str) -> None:
        self.objects.pop(key, None)


@pytest_asyncio.fixture
async def client_with_storage(app: FastAPI) -> AsyncIterator[AsyncClient]:
    storage = MemoryStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client
    app.dependency_overrides.pop(get_object_storage, None)


async def _create_project(client: AsyncClient, name: str = "Review Project") -> str:
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


async def _create_export_ready_project(client: AsyncClient) -> str:
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
    export_response = await client.post(f"/api/v1/projects/{project_id}/exports", json={})
    assert export_response.status_code == 201
    return project_id


@pytest.mark.asyncio
async def test_empty_project_review_is_blocked(client_with_storage: AsyncClient) -> None:
    project_id = await _create_project(client_with_storage)

    response = await client_with_storage.get(f"/api/v1/projects/{project_id}/review")

    assert response.status_code == 200
    review = response.json()
    assert review["status"] == "blocked"
    assert review["score"] < 50
    item_statuses = {item["id"]: item["status"] for item in review["items"]}
    assert item_statuses["song_spec"] == "fail"
    assert item_statuses["midi"] == "fail"
    assert review["next_actions"]


@pytest.mark.asyncio
async def test_export_ready_project_review_is_ready(client_with_storage: AsyncClient) -> None:
    project_id = await _create_export_ready_project(client_with_storage)

    response = await client_with_storage.get(f"/api/v1/projects/{project_id}/review")

    assert response.status_code == 200
    review = response.json()
    assert review["status"] == "ready"
    assert review["score"] >= 85
    item_statuses = {item["id"]: item["status"] for item in review["items"]}
    assert item_statuses["song_spec"] == "pass"
    assert item_statuses["export"] == "pass"
    assert item_statuses["demo"] == "warning"


@pytest.mark.asyncio
async def test_project_handoff_summarizes_current_state(
    client_with_storage: AsyncClient,
) -> None:
    project_id = await _create_export_ready_project(client_with_storage)
    comment_response = await client_with_storage.post(
        f"/api/v1/projects/{project_id}/comments",
        json={
            "author_name": "Producer",
            "body": "Check the bridge density before final handoff.",
            "target_type": "project",
        },
    )
    assert comment_response.status_code == 201

    response = await client_with_storage.get(f"/api/v1/projects/{project_id}/handoff")

    assert response.status_code == 200
    handoff = response.json()
    assert handoff["project"]["id"] == project_id
    assert handoff["review"]["score"] >= 85
    assert handoff["current_assets"]["song_spec"] is not None
    assert handoff["open_comments"][0]["body"] == "Check the bridge density before final handoff."
    assert handoff["recent_events"]
    assert handoff["next_actions"][0] == "Resolve 1 open project comment(s)."
    assert "# Review Project Handoff" in handoff["handoff_markdown"]
    assert "## Current Assets" in handoff["handoff_markdown"]
    assert "Check the bridge density" in handoff["handoff_markdown"]


@pytest.mark.asyncio
async def test_project_handoff_returns_blocked_empty_state(
    client_with_storage: AsyncClient,
) -> None:
    project_id = await _create_project(client_with_storage, "Empty Handoff")

    response = await client_with_storage.get(f"/api/v1/projects/{project_id}/handoff")

    assert response.status_code == 200
    handoff = response.json()
    assert handoff["review"]["status"] == "blocked"
    assert handoff["current_assets"]["song_spec"] is None
    assert "Approve a complete SongSpec" in handoff["next_actions"][0]
    assert "- SongSpec: missing" in handoff["handoff_markdown"]


@pytest.mark.asyncio
async def test_project_review_returns_404_for_missing_project(
    client_with_storage: AsyncClient,
) -> None:
    response = await client_with_storage.get(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/review"
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_project_handoff_returns_404_for_missing_project(
    client_with_storage: AsyncClient,
) -> None:
    response = await client_with_storage.get(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/handoff"
    )

    assert response.status_code == 404

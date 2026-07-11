from uuid import UUID

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient) -> str:
    response = await client.post("/api/v1/projects", json={"name": "SongSpec Project"})
    assert response.status_code == 201
    return str(UUID(response.json()["id"]))


@pytest.mark.asyncio
async def test_incomplete_intake_returns_clarification_questions(client: AsyncClient) -> None:
    project_id = await _create_project(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/intake",
        json={"idea": "A lonely late-night song"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "needs_clarification"
    fields = {question["field"] for question in body["questions"]}
    assert "tempo_bpm" in fields
    assert "key" in fields


@pytest.mark.asyncio
async def test_song_spec_generate_edit_and_approve_lifecycle(client: AsyncClient) -> None:
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
    intake = intake_response.json()
    assert intake["status"] == "ready_for_generation"

    generate_response = await client.post(
        f"/api/v1/projects/{project_id}/song-spec/generate",
        json={"intake_id": intake["intake_id"]},
    )
    assert generate_response.status_code == 200
    generated = generate_response.json()
    assert generated["version_number"] == 1
    assert generated["status"] == "draft"
    assert generated["missing_required_fields"] == []

    edit_response = await client.patch(
        f"/api/v1/projects/{project_id}/song-specs/{generated['id']}",
        json={"key": "A major", "genre": ["indie rock", "j-pop influenced"]},
    )
    assert edit_response.status_code == 200
    edited = edit_response.json()
    assert edited["version_number"] == 2
    assert edited["parent_version_id"] == generated["id"]
    assert edited["song_spec"]["key"] == "A major"

    approve_response = await client.post(
        f"/api/v1/projects/{project_id}/song-specs/{edited['id']}/approve"
    )
    assert approve_response.status_code == 200
    approved = approve_response.json()
    assert approved["status"] == "approved"
    assert approved["approved_at"]

    approve_first_response = await client.post(
        f"/api/v1/projects/{project_id}/song-specs/{generated['id']}/approve"
    )
    assert approve_first_response.status_code == 200
    versions_response = await client.get(f"/api/v1/projects/{project_id}/song-specs")
    assert versions_response.status_code == 200
    statuses = {item["id"]: item["status"] for item in versions_response.json()}
    assert statuses[generated["id"]] == "approved"
    assert statuses[edited["id"]] == "superseded"

    events_response = await client.get(f"/api/v1/projects/{project_id}/events")
    assert events_response.status_code == 200
    event_types = {event["event_type"] for event in events_response.json()}
    assert {
        "intake.created",
        "song_spec.generated",
        "song_spec.edited",
        "song_spec.approved",
    }.issubset(event_types)


@pytest.mark.asyncio
async def test_incomplete_song_spec_cannot_be_approved(client: AsyncClient) -> None:
    project_id = await _create_project(client)
    intake_response = await client.post(
        f"/api/v1/projects/{project_id}/intake",
        json={"idea": "A lonely late-night song"},
    )
    generated_response = await client.post(
        f"/api/v1/projects/{project_id}/song-spec/generate",
        json={"intake_id": intake_response.json()["intake_id"]},
    )
    assert generated_response.status_code == 200

    approve_response = await client.post(
        f"/api/v1/projects/{project_id}/song-specs/{generated_response.json()['id']}/approve"
    )

    assert approve_response.status_code == 422
    assert "missing_required_fields" in approve_response.json()["detail"]


@pytest.mark.asyncio
async def test_song_spec_not_found_returns_404(client: AsyncClient) -> None:
    project_id = await _create_project(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/song-specs/00000000-0000-0000-0000-000000000000/approve"
    )

    assert response.status_code == 404

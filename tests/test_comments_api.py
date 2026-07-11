from uuid import UUID

import pytest
from httpx import AsyncClient


async def _create_project(client: AsyncClient) -> str:
    response = await client.post("/api/v1/projects", json={"name": "Comments Project"})
    assert response.status_code == 201
    return str(UUID(response.json()["id"]))


@pytest.mark.asyncio
async def test_project_comment_lifecycle_and_events(client: AsyncClient) -> None:
    project_id = await _create_project(client)

    create_response = await client.post(
        f"/api/v1/projects/{project_id}/comments",
        json={
            "author_name": "Local reviewer",
            "body": "  Tighten the chorus lift before export.  ",
            "target_type": "project",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["author_name"] == "Local reviewer"
    assert created["body"] == "Tighten the chorus lift before export."
    assert created["status"] == "open"

    list_response = await client.get(f"/api/v1/projects/{project_id}/comments")
    assert list_response.status_code == 200
    assert [comment["id"] for comment in list_response.json()] == [created["id"]]

    resolve_response = await client.patch(
        f"/api/v1/projects/{project_id}/comments/{created['id']}",
        json={"status": "resolved"},
    )
    assert resolve_response.status_code == 200
    resolved = resolve_response.json()
    assert resolved["status"] == "resolved"
    assert resolved["resolved_at"]

    open_filter_response = await client.get(
        f"/api/v1/projects/{project_id}/comments?status=open"
    )
    assert open_filter_response.status_code == 200
    assert open_filter_response.json() == []

    reopen_response = await client.patch(
        f"/api/v1/projects/{project_id}/comments/{created['id']}",
        json={"status": "open", "body": "Reopened: chorus still needs a stronger lift."},
    )
    assert reopen_response.status_code == 200
    reopened = reopen_response.json()
    assert reopened["status"] == "open"
    assert reopened["resolved_at"] is None
    assert reopened["body"].startswith("Reopened:")

    events_response = await client.get(f"/api/v1/projects/{project_id}/events")
    assert events_response.status_code == 200
    event_types = {event["event_type"] for event in events_response.json()}
    assert {"comment.created", "comment.resolved", "comment.reopened"}.issubset(
        event_types
    )


@pytest.mark.asyncio
async def test_comment_validation_and_not_found(client: AsyncClient) -> None:
    project_id = await _create_project(client)

    blank_response = await client.post(
        f"/api/v1/projects/{project_id}/comments",
        json={"body": "   "},
    )
    assert blank_response.status_code == 422

    missing_project_response = await client.post(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000/comments",
        json={"body": "Will not be saved."},
    )
    assert missing_project_response.status_code == 404

    missing_comment_response = await client.patch(
        f"/api/v1/projects/{project_id}/comments/00000000-0000-0000-0000-000000000000",
        json={"status": "resolved"},
    )
    assert missing_comment_response.status_code == 404

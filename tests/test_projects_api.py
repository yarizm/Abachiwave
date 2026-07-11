from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from abachiwave.core.request_context import request_path_context
from abachiwave.schemas.health import DependencyReadiness
from abachiwave.services.readiness import get_readiness_service


class StubReadinessService:
    def __init__(self, dependencies: DependencyReadiness) -> None:
        self._dependencies = dependencies

    async def check(self) -> DependencyReadiness:
        return self._dependencies


def test_request_path_context_extracts_business_identifiers() -> None:
    project_id = "11111111-1111-4111-8111-111111111111"
    run_id = "22222222-2222-4222-8222-222222222222"
    export_id = "33333333-3333-4333-8333-333333333333"

    assert request_path_context(f"/api/v1/projects/{project_id}/lyrics") == {
        "project_id": project_id
    }
    assert request_path_context(f"/api/v1/tasks/{run_id}/retry") == {
        "generation_run_id": run_id
    }
    assert request_path_context(f"/api/v1/exports/{export_id}/download") == {
        "export_id": export_id
    }
    assert request_path_context("/health/ready") == {}


@pytest.mark.asyncio
async def test_health(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    UUID(response.headers["X-Request-ID"])

    live_response = await client.get("/health/live", headers={"X-Request-ID": "health-check-1"})
    assert live_response.status_code == 200
    assert live_response.json() == {"status": "ok"}
    assert live_response.headers["X-Request-ID"] == "health-check-1"


@pytest.mark.asyncio
async def test_request_id_replaces_invalid_value(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "invalid request id"})

    assert response.status_code == 200
    UUID(response.headers["X-Request-ID"])


@pytest.mark.asyncio
async def test_unhandled_error_returns_safe_response_with_request_id(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    @app.get("/_test/unhandled-error")
    async def unhandled_error() -> None:
        raise RuntimeError("database password must not be exposed")

    response = await client.get(
        "/_test/unhandled-error",
        headers={"X-Request-ID": "failed-request-1"},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["X-Request-ID"] == "failed-request-1"
    assert "password" not in response.text


@pytest.mark.asyncio
async def test_readiness_reports_dependency_state(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    app.dependency_overrides[get_readiness_service] = lambda: StubReadinessService(
        DependencyReadiness(database="ok", redis="ok", storage="ok")
    )
    ready_response = await client.get("/health/ready")

    assert ready_response.status_code == 200
    assert ready_response.json() == {
        "status": "ready",
        "dependencies": {"database": "ok", "redis": "ok", "storage": "ok"},
    }

    app.dependency_overrides[get_readiness_service] = lambda: StubReadinessService(
        DependencyReadiness(database="ok", redis="unavailable", storage="ok")
    )
    unavailable_response = await client.get("/health/ready")

    assert unavailable_response.status_code == 503
    assert unavailable_response.json() == {
        "status": "not_ready",
        "dependencies": {"database": "ok", "redis": "unavailable", "storage": "ok"},
    }


@pytest.mark.asyncio
async def test_project_lifecycle(client: AsyncClient) -> None:
    create_response = await client.post(
        "/api/v1/projects",
        json={"name": "  Night Ride  ", "description": "First demo project"},
    )

    assert create_response.status_code == 201
    created = create_response.json()
    project_id = UUID(created["id"])
    assert created["name"] == "Night Ride"
    assert created["description"] == "First demo project"
    assert created["status"] == "active"
    assert created["created_at"]
    assert created["updated_at"]

    list_response = await client.get("/api/v1/projects")
    assert list_response.status_code == 200
    assert [project["id"] for project in list_response.json()] == [str(project_id)]

    get_response = await client.get(f"/api/v1/projects/{project_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == str(project_id)

    update_response = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"name": "Night Ride v2", "status": "archived", "description": ""},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Night Ride v2"
    assert updated["description"] is None
    assert updated["status"] == "archived"

    events_response = await client.get(f"/api/v1/projects/{project_id}/events")
    assert events_response.status_code == 200
    event_types = {event["event_type"] for event in events_response.json()}
    assert {"project.created", "project.updated"}.issubset(event_types)


@pytest.mark.asyncio
async def test_project_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


@pytest.mark.asyncio
async def test_project_name_validation(client: AsyncClient) -> None:
    response = await client.post("/api/v1/projects", json={"name": "   "})

    assert response.status_code == 422

"""Tests for the unified error response contract (Phase 0).

Covers the three global handlers in ``abachiwave.main``:
``ProblemError``, ``RequestValidationError`` and ``VersionWriteConflictError``,
plus the middleware 500 fallback header enrichment.
"""

from __future__ import annotations

import re

import pytest
from httpx import ASGITransport, AsyncClient

from abachiwave.api.errors import ErrorCode, ErrorHint, ProblemError
from abachiwave.main import create_app


@pytest.mark.asyncio
async def test_cors_exposes_error_headers() -> None:
    """Browser clients read the error contract from response headers; CORS
    must expose them or headerCode/headerHint are null cross-origin."""
    app = create_app()

    @app.get("/_test/hint-error")
    async def hint_error() -> None:
        raise ProblemError(
            status_code=409,
            error_code=ErrorCode.PREREQUISITES_MISSING,
            detail={"message": "missing"},
            hint=ErrorHint.CHECK_PREREQUISITES,
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/_test/hint-error", headers={"Origin": "http://localhost:3000"}
        )

    assert response.status_code == 409
    exposed = {
        item.strip()
        for item in response.headers.get("access-control-expose-headers", "").split(",")
    }
    assert {"X-Error-Code", "X-Error-Hint", "X-Request-ID"}.issubset(exposed)


@pytest.mark.asyncio
async def test_problem_error_string_detail_keeps_body_adds_header() -> None:
    app = create_app()

    @app.get("/_test/string-error")
    async def string_error() -> None:
        raise ProblemError(
            status_code=404,
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            detail="Project not found",
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/_test/string-error")

    assert response.status_code == 404
    # Body must stay exactly {"detail": str} -- no extra keys.
    assert response.json() == {"detail": "Project not found"}
    assert response.headers["X-Error-Code"] == "resource_not_found"
    assert "X-Error-Hint" not in response.headers


@pytest.mark.asyncio
async def test_problem_error_dict_detail_adds_siblings() -> None:
    app = create_app()

    @app.get("/_test/dict-error")
    async def dict_error() -> None:
        raise ProblemError(
            status_code=409,
            error_code=ErrorCode.PREREQUISITES_MISSING,
            detail={
                "message": "Arrangement prerequisites are missing",
                "missing": ["MIDI: chord", "MIDI: melody"],
            },
            hint=ErrorHint.CHECK_PREREQUISITES,
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/_test/dict-error")

    assert response.status_code == 409
    detail = response.json()["detail"]
    # Original keys preserved.
    assert detail["message"] == "Arrangement prerequisites are missing"
    assert detail["missing"] == ["MIDI: chord", "MIDI: melody"]
    # New siblings added.
    assert detail["error_code"] == "prerequisites_missing"
    assert detail["hint"] == "check_prerequisites"
    # Headers also carry the values.
    assert response.headers["X-Error-Code"] == "prerequisites_missing"
    assert response.headers["X-Error-Hint"] == "check_prerequisites"


@pytest.mark.asyncio
async def test_problem_error_no_hint_omits_header() -> None:
    app = create_app()

    @app.get("/_test/no-hint-error")
    async def no_hint_error() -> None:
        raise ProblemError(
            status_code=404,
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            detail="AudioUpload not found",
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/_test/no-hint-error")

    assert response.headers["X-Error-Code"] == "resource_not_found"
    assert "X-Error-Hint" not in response.headers


@pytest.mark.asyncio
async def test_problem_error_fields_in_body() -> None:
    app = create_app()

    @app.get("/_test/fields-error")
    async def fields_error() -> None:
        raise ProblemError(
            status_code=422,
            error_code=ErrorCode.SONG_SPEC_INCOMPLETE,
            detail={"message": "SongSpec is incomplete", "missing_required_fields": ["theme"]},
            hint=ErrorHint.CHECK_REQUIRED_FIELDS,
            fields={"theme": "theme is required"},
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/_test/fields-error")

    assert response.status_code == 422
    body = response.json()
    assert body["fields"] == {"theme": "theme is required"}
    assert body["detail"]["missing_required_fields"] == ["theme"]


@pytest.mark.asyncio
async def test_validation_error_produces_fields_map() -> None:
    app = create_app()

    @app.get("/_test/validate")
    async def validate_endpoint(limit: int) -> dict[str, int]:
        return {"limit": limit}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # "not-an-int" fails int parsing; loc is ["query", "limit"].
        response = await client.get("/_test/validate", params={"limit": "not-an-int"})

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "Validation failed"
    assert body["error_code"] == "validation_failed"
    # fields is a flat dict, not a loc array.
    assert isinstance(body["fields"], dict)
    assert "query.limit" in body["fields"]
    assert "loc" not in body
    assert response.headers["X-Error-Code"] == "validation_failed"


@pytest.mark.asyncio
async def test_validation_error_nested_paths_use_dot_notation() -> None:
    """Exercise the handler with a fabricated nested loc without relying on a
    bespoke Pydantic route model (which FastAPI may interpret as query params).
    """
    from fastapi.exceptions import RequestValidationError

    app = create_app()

    @app.get("/_test/fabricated")
    async def fabricated() -> None:
        raise RequestValidationError(
            [
                {
                    "type": "int_parsing",
                    "loc": ("body", "sections", 0, "chords", 0),
                    "msg": "Input should be a valid integer",
                    "input": "bad",
                    "url": "https://example.com",  # pydantic v2 requires url key
                }
            ]
        )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/_test/fabricated")

    assert response.status_code == 422
    fields = response.json()["fields"]
    # Nested body path uses dot notation without the "body" prefix.
    assert "sections.0.chords.0" in fields


@pytest.mark.asyncio
async def test_validation_error_same_field_concatenated() -> None:
    app = create_app()

    @app.get("/_test/multi")
    async def multi(value: int) -> dict[str, int]:
        return {"value": value}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/_test/multi", params={"value": "not-an-int"})

    assert response.status_code == 422
    # Query param loc is ["query", "value"].
    assert "query.value" in response.json()["fields"]


@pytest.mark.asyncio
async def test_500_has_error_code_header() -> None:
    app = create_app()

    @app.get("/_test/crash")
    async def crash() -> None:
        raise RuntimeError("boom")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/_test/crash")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["X-Error-Code"] == "internal_error"


@pytest.mark.asyncio
async def test_version_conflict_has_headers() -> None:
    """Directly exercise the VersionWriteConflictError handler via a test route."""
    from abachiwave.services.versioning import VersionWriteConflictError

    app = create_app()

    @app.get("/_test/conflict")
    async def conflict() -> None:
        raise VersionWriteConflictError("Asset version changed concurrently; retry the request")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/_test/conflict")

    assert response.status_code == 409
    assert response.json() == {"detail": "Asset version changed concurrently; retry the request"}
    assert response.headers["X-Error-Code"] == "asset_version_conflict"
    assert response.headers["X-Error-Hint"] == "retry"


def test_error_code_values_stable_snake_case() -> None:
    pattern = re.compile(r"^[a-z][a-z0-9_]*$")
    for member in ErrorCode:
        assert pattern.fullmatch(member.value), f"{member} value is not snake_case: {member.value}"
        assert member.value != ""


def test_error_hint_values_stable_snake_case() -> None:
    pattern = re.compile(r"^[a-z][a-z0-9_]*$")
    for member in ErrorHint:
        assert pattern.fullmatch(member.value), f"{member} value is not snake_case: {member.value}"
        assert member.value != ""

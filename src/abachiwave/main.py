from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from abachiwave.api.errors import ErrorCode, ErrorHint, ProblemError
from abachiwave.api.router import api_router
from abachiwave.core.config import get_settings
from abachiwave.core.database import AsyncSessionLocal, engine
from abachiwave.core.logging import configure_logging
from abachiwave.core.request_context import request_context_middleware
from abachiwave.services.ai_generation import ensure_ai_catalog
from abachiwave.services.storage import close_object_storage
from abachiwave.services.task_queue import close_task_queue
from abachiwave.services.versioning import (
    VERSION_CONFLICT_MESSAGE,
    VersionWriteConflictError,
)

_ERROR_CODE_HEADER = "X-Error-Code"
_ERROR_HINT_HEADER = "X-Error-Hint"


def _build_error_headers(error: ProblemError) -> dict[str, str]:
    headers = {_ERROR_CODE_HEADER: error.error_code.value}
    if error.hint is not None:
        headers[_ERROR_HINT_HEADER] = error.hint.value
    return headers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    logger = structlog.get_logger(__name__)
    logger.info("api_starting", app_env=settings.app_env)
    try:
        async with AsyncSessionLocal() as session:
            await ensure_ai_catalog(session, settings=settings)
        yield
    finally:
        await close_task_queue()
        close_object_storage()
        await engine.dispose()
        logger.info("api_stopping")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Abachiwave API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.middleware("http")(request_context_middleware)

    @app.exception_handler(ProblemError)
    async def handle_problem_error(
        _request: Request,
        error: ProblemError,
    ) -> JSONResponse:
        headers = _build_error_headers(error)
        if isinstance(error.detail, dict):
            nested: dict[str, Any] = {
                **error.detail,
                "error_code": error.error_code.value,
            }
            if error.hint is not None:
                nested["hint"] = error.hint.value
            body: dict[str, Any] = {"detail": nested}
        else:
            # String detail: body stays exactly {"detail": str} (no new keys)
            # so exact-match assertions on the body remain valid.
            body = {"detail": error.detail}
        if error.fields:
            body["fields"] = error.fields
        return JSONResponse(
            status_code=error.status_code,
            content=body,
            headers={**headers, **error.headers},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        fields: dict[str, str] = {}
        for entry in error.errors():
            # Drop the "body" prefix FastAPI adds for body params; keep the
            # rest as dot-notation path (e.g. sections.0.chords.0).
            key = ".".join(str(part) for part in entry["loc"] if part != "body")
            if not key:
                key = "__root__"
            message = entry["msg"]
            fields[key] = f"{fields[key]}; {message}" if key in fields else message
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Validation failed",
                "error_code": ErrorCode.VALIDATION_FAILED.value,
                "fields": fields,
            },
            headers={_ERROR_CODE_HEADER: ErrorCode.VALIDATION_FAILED.value},
        )

    @app.exception_handler(VersionWriteConflictError)
    async def handle_version_write_conflict(
        _request: Request,
        _error: VersionWriteConflictError,
    ) -> JSONResponse:
        # Body unchanged (exact-match assertion depends on it); add headers.
        return JSONResponse(
            status_code=409,
            content={"detail": VERSION_CONFLICT_MESSAGE},
            headers={
                _ERROR_CODE_HEADER: ErrorCode.ASSET_VERSION_CONFLICT.value,
                _ERROR_HINT_HEADER: ErrorHint.RETRY.value,
            },
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", settings.request_id_header],
        expose_headers=[_ERROR_CODE_HEADER, _ERROR_HINT_HEADER, settings.request_id_header],
    )
    app.include_router(api_router)
    return app


app = create_app()

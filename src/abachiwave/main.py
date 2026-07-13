from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from abachiwave.api.router import api_router
from abachiwave.core.config import get_settings
from abachiwave.core.database import engine
from abachiwave.core.logging import configure_logging
from abachiwave.core.request_context import request_context_middleware
from abachiwave.services.storage import close_object_storage
from abachiwave.services.task_queue import close_task_queue
from abachiwave.services.versioning import (
    VERSION_CONFLICT_MESSAGE,
    VersionWriteConflictError,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    logger = structlog.get_logger(__name__)
    logger.info("api_starting", app_env=settings.app_env)
    try:
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

    @app.exception_handler(VersionWriteConflictError)
    async def handle_version_write_conflict(
        _request: Request,
        _error: VersionWriteConflictError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"detail": VERSION_CONFLICT_MESSAGE},
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", settings.request_id_header],
    )
    app.include_router(api_router)
    return app


app = create_app()

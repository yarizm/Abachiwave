from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
RequestHandler = Callable[[Request], Awaitable[Response]]


def normalize_request_id(value: str | None) -> str:
    if value and _REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return str(uuid4())


async def request_context_middleware(
    request: Request,
    call_next: RequestHandler,
) -> Response:
    settings = request.app.state.settings
    request_id = normalize_request_id(request.headers.get(settings.request_id_header))
    request.state.request_id = request_id
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        http_method=request.method,
        http_path=request.url.path,
    )
    logger = structlog.get_logger("abachiwave.request")

    try:
        response = await call_next(request)
    except Exception as error:
        logger.error("request_failed", error_type=type(error).__name__)
        response = JSONResponse(status_code=500, content={"detail": "Internal server error"})

    response.headers[settings.request_id_header] = request_id
    logger.info("request_completed", status_code=response.status_code)
    structlog.contextvars.clear_contextvars()
    return response

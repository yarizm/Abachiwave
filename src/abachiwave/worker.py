from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.core.config import get_settings
from abachiwave.core.database import AsyncSessionLocal
from abachiwave.models.demo import GenerationRun
from abachiwave.services.audio import execute_audio_to_midi
from abachiwave.services.demo import execute_demo_generation
from abachiwave.services.generation_runs import run_generation_with_timeout
from abachiwave.services.task_queue import build_redis_settings

__all__ = [
    "WorkerSettings",
    "build_redis_settings",
    "extract_midi_from_audio_job",
    "generate_demo_job",
    "health_check",
    "load_generation_log_context",
]

GenerationExecutor = Callable[[UUID], Awaitable[GenerationRun | None]]


async def health_check(ctx: dict[str, Any]) -> dict[str, str]:
    return {"status": "ok"}


async def generate_demo_job(ctx: dict[str, Any], run_id: str) -> dict[str, str]:
    return await _run_generation_job(run_id, execute_demo_generation, "demo_generation")


async def extract_midi_from_audio_job(ctx: dict[str, Any], run_id: str) -> dict[str, str]:
    return await _run_generation_job(run_id, execute_audio_to_midi, "audio_to_midi")


async def load_generation_log_context(
    run_id: UUID,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> dict[str, str]:
    selected_session_factory = session_factory or AsyncSessionLocal
    context = {"generation_run_id": str(run_id)}
    async with selected_session_factory() as session:
        run = await session.get(GenerationRun, str(run_id))
        if run is not None:
            context["project_id"] = run.project_id
            context["generation_run_type"] = str(run.run_type)
    return context


async def _run_generation_job(
    run_id: str,
    executor: GenerationExecutor,
    job_type: str,
) -> dict[str, str]:
    settings = get_settings()
    run_uuid = UUID(run_id)
    context = await load_generation_log_context(run_uuid)
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(**context)
    logger = structlog.get_logger("abachiwave.worker")
    logger.info("generation_job_started", job_type=job_type)
    try:
        run = await run_generation_with_timeout(
            run_uuid,
            executor,
            timeout_seconds=settings.task_timeout_seconds,
        )
        status = "not_found" if run is None else str(run.status)
        logger.info("generation_job_completed", job_type=job_type, status=status)
        return {"status": status}
    except Exception as error:
        logger.error(
            "generation_job_failed",
            job_type=job_type,
            error_type=type(error).__name__,
        )
        raise
    finally:
        structlog.contextvars.clear_contextvars()


class WorkerSettings:
    functions = [health_check, generate_demo_job, extract_midi_from_audio_job]
    redis_settings = build_redis_settings(get_settings().redis_url)
    job_timeout = get_settings().task_timeout_seconds + 30

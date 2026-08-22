import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.core.config import get_settings
from abachiwave.core.database import AsyncSessionLocal
from abachiwave.models.demo import GenerationRun
from abachiwave.services.ai_generation import ensure_ai_catalog, execute_candidate_generation
from abachiwave.services.audio import execute_audio_to_midi
from abachiwave.services.audio_derivatives import execute_audio_derivative
from abachiwave.services.audio_to_midi_provider import build_audio_to_midi_provider
from abachiwave.services.demo import execute_demo_generation
from abachiwave.services.demo_provider import build_demo_provider
from abachiwave.services.evaluations import (
    execute_text_evaluation,
    mark_text_evaluation_failed,
)
from abachiwave.services.generation_runs import (
    TASK_INTERRUPTED_ERROR,
    mark_generation_run_interrupted,
    run_generation_with_timeout,
)
from abachiwave.services.reference_analysis import execute_reference_analysis
from abachiwave.services.task_queue import (
    AUDIO_FFMPEG_QUEUE_NAME,
    AUDIO_TO_MIDI_QUEUE_NAME,
    build_redis_settings,
)

__all__ = [
    "FFmpegWorkerSettings",
    "AudioToMidiWorkerSettings",
    "WorkerSettings",
    "build_redis_settings",
    "analyze_reference_audio_job",
    "extract_midi_from_audio_job",
    "generate_demo_job",
    "generate_text_candidates_job",
    "normalize_audio_derivative_job",
    "health_check",
    "load_generation_log_context",
    "run_text_evaluation_job",
    "startup_worker",
    "startup_audio_to_midi_worker",
]

GenerationExecutor = Callable[[UUID], Awaitable[GenerationRun | None]]


async def health_check(ctx: dict[str, Any]) -> dict[str, str]:
    return {"status": "ok"}


async def startup_worker(ctx: dict[str, Any]) -> None:
    build_demo_provider(get_settings())
    async with AsyncSessionLocal() as session:
        await ensure_ai_catalog(session)


async def startup_audio_to_midi_worker(ctx: dict[str, Any]) -> None:
    build_audio_to_midi_provider(get_settings())


async def generate_demo_job(ctx: dict[str, Any], run_id: str) -> dict[str, str]:
    return await _run_generation_job(run_id, execute_demo_generation, "demo_generation")


async def extract_midi_from_audio_job(ctx: dict[str, Any], run_id: str) -> dict[str, str]:
    return await _run_generation_job(run_id, execute_audio_to_midi, "audio_to_midi")


async def normalize_audio_derivative_job(ctx: dict[str, Any], run_id: str) -> dict[str, str]:
    return await _run_generation_job(run_id, execute_audio_derivative, "audio_derivative")


async def analyze_reference_audio_job(ctx: dict[str, Any], run_id: str) -> dict[str, str]:
    return await _run_generation_job(run_id, execute_reference_analysis, "reference_analysis")


async def generate_text_candidates_job(ctx: dict[str, Any], run_id: str) -> dict[str, str]:
    return await _run_generation_job(run_id, execute_candidate_generation, "text_generation")


async def run_text_evaluation_job(ctx: dict[str, Any], run_id: str) -> dict[str, str]:
    settings = get_settings()
    run_uuid = UUID(run_id)
    logger = structlog.get_logger("abachiwave.worker")
    logger.info("text_evaluation_started", evaluation_run_id=run_id)
    try:
        async with asyncio.timeout(settings.text_evaluation_timeout_seconds):
            evaluation = await execute_text_evaluation(run_uuid)
        status = "not_found" if evaluation is None else str(evaluation.status)
        logger.info(
            "text_evaluation_completed",
            evaluation_run_id=run_id,
            status=status,
        )
        return {"status": status}
    except TimeoutError:
        await mark_text_evaluation_failed(
            run_uuid,
            "evaluation_timeout",
            "Text evaluation exceeded its configured timeout",
        )
        logger.error("text_evaluation_timed_out", evaluation_run_id=run_id)
        return {"status": "failed"}
    except Exception as error:
        # The run row was already committed as 'running' by the executor;
        # anything that escapes must be marked failed or the row stays
        # 'running' forever. Log the type only, never the error content.
        await mark_text_evaluation_failed(
            run_uuid,
            "evaluation_failed",
            f"Text evaluation failed: {type(error).__name__}",
        )
        logger.error(
            "text_evaluation_failed",
            evaluation_run_id=run_id,
            error_type=type(error).__name__,
        )
        return {"status": "failed"}


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
    except asyncio.CancelledError:
        await mark_generation_run_interrupted(run_uuid, TASK_INTERRUPTED_ERROR)
        logger.warning("generation_job_interrupted", job_type=job_type)
        raise
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
    functions = [
        health_check,
        generate_demo_job,
        analyze_reference_audio_job,
        generate_text_candidates_job,
        run_text_evaluation_job,
    ]
    redis_settings = build_redis_settings(get_settings().redis_url)
    on_startup = startup_worker
    job_timeout = (
        max(
            get_settings().task_timeout_seconds,
            get_settings().text_evaluation_timeout_seconds,
        )
        + 30
    )


class AudioToMidiWorkerSettings:
    functions = [
        health_check,
        extract_midi_from_audio_job,
    ]
    redis_settings = build_redis_settings(get_settings().redis_url)
    queue_name = AUDIO_TO_MIDI_QUEUE_NAME
    on_startup = startup_audio_to_midi_worker
    job_timeout = get_settings().task_timeout_seconds + 30


class FFmpegWorkerSettings:
    functions = [
        health_check,
        normalize_audio_derivative_job,
    ]
    redis_settings = build_redis_settings(get_settings().redis_url)
    queue_name = AUDIO_FFMPEG_QUEUE_NAME
    job_timeout = get_settings().task_timeout_seconds + 30

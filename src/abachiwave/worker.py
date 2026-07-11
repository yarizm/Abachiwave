from typing import Any
from uuid import UUID

from abachiwave.core.config import get_settings
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
]


async def health_check(ctx: dict[str, Any]) -> dict[str, str]:
    return {"status": "ok"}


async def generate_demo_job(ctx: dict[str, Any], run_id: str) -> dict[str, str]:
    settings = get_settings()
    run = await run_generation_with_timeout(
        UUID(run_id),
        execute_demo_generation,
        timeout_seconds=settings.task_timeout_seconds,
    )
    if run is None:
        return {"status": "not_found"}
    return {"status": str(run.status)}


async def extract_midi_from_audio_job(ctx: dict[str, Any], run_id: str) -> dict[str, str]:
    settings = get_settings()
    run = await run_generation_with_timeout(
        UUID(run_id),
        execute_audio_to_midi,
        timeout_seconds=settings.task_timeout_seconds,
    )
    if run is None:
        return {"status": "not_found"}
    return {"status": str(run.status)}


class WorkerSettings:
    functions = [health_check, generate_demo_job, extract_midi_from_audio_job]
    redis_settings = build_redis_settings(get_settings().redis_url)
    job_timeout = get_settings().task_timeout_seconds + 30

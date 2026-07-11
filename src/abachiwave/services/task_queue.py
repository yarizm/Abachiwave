from typing import Protocol
from urllib.parse import urlparse
from uuid import UUID

from arq import create_pool
from arq.connections import RedisSettings

from abachiwave.core.config import get_settings


class DemoTaskQueue(Protocol):
    async def enqueue_demo_generation(self, run_id: UUID) -> str: ...


class AudioToMidiTaskQueue(Protocol):
    async def enqueue_audio_to_midi(self, run_id: UUID) -> str: ...


class ArqTaskQueue:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url

    async def enqueue_demo_generation(self, run_id: UUID) -> str:
        pool = await create_pool(build_redis_settings(self._redis_url))
        try:
            job = await pool.enqueue_job("generate_demo_job", str(run_id))
            if job is None:
                raise RuntimeError("Demo generation job could not be enqueued")
            return str(job.job_id)
        finally:
            await pool.close()

    async def enqueue_audio_to_midi(self, run_id: UUID) -> str:
        pool = await create_pool(build_redis_settings(self._redis_url))
        try:
            job = await pool.enqueue_job("extract_midi_from_audio_job", str(run_id))
            if job is None:
                raise RuntimeError("Audio-to-MIDI job could not be enqueued")
            return str(job.job_id)
        finally:
            await pool.close()


def get_demo_task_queue() -> DemoTaskQueue:
    return ArqTaskQueue(get_settings().redis_url)


def get_audio_to_midi_task_queue() -> AudioToMidiTaskQueue:
    return ArqTaskQueue(get_settings().redis_url)


def build_redis_settings(redis_url: str) -> RedisSettings:
    parsed = urlparse(redis_url)
    if parsed.scheme != "redis":
        raise ValueError("Only redis:// URLs are supported for the worker")
    database = int(parsed.path.removeprefix("/") or "0")
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        database=database,
        username=parsed.username,
        password=parsed.password,
    )

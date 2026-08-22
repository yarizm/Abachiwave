import asyncio
from functools import lru_cache
from typing import Protocol
from urllib.parse import urlparse
from uuid import UUID

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from abachiwave.core.config import get_settings

AUDIO_FFMPEG_QUEUE_NAME = "arq:audio-ffmpeg"
AUDIO_TO_MIDI_QUEUE_NAME = "arq:audio-midi"


class DemoTaskQueue(Protocol):
    async def enqueue_demo_generation(self, run_id: UUID) -> str: ...


class AudioToMidiTaskQueue(Protocol):
    async def enqueue_audio_to_midi(self, run_id: UUID) -> str: ...


class AudioDerivativeTaskQueue(Protocol):
    async def enqueue_audio_derivative(self, run_id: UUID) -> str: ...


class ReferenceAnalysisTaskQueue(Protocol):
    async def enqueue_reference_analysis(self, run_id: UUID) -> str: ...


class TextGenerationTaskQueue(Protocol):
    async def enqueue_text_generation(self, run_id: UUID) -> str: ...


class TextEvaluationTaskQueue(Protocol):
    async def enqueue_text_evaluation(self, run_id: UUID) -> str: ...


class ArqTaskQueue:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._pool: ArqRedis | None = None
        self._pool_lock = asyncio.Lock()

    async def _get_pool(self) -> ArqRedis:
        if self._pool is not None:
            return self._pool
        async with self._pool_lock:
            if self._pool is None:
                self._pool = await create_pool(build_redis_settings(self._redis_url))
        return self._pool

    async def ping(self) -> None:
        pool = await self._get_pool()
        await pool.ping()

    async def close(self) -> None:
        if self._pool is None:
            return
        await self._pool.close()
        self._pool = None

    async def enqueue_demo_generation(self, run_id: UUID) -> str:
        pool = await self._get_pool()
        job = await pool.enqueue_job("generate_demo_job", str(run_id))
        if job is None:
            raise RuntimeError("Demo generation job could not be enqueued")
        return str(job.job_id)

    async def enqueue_audio_to_midi(self, run_id: UUID) -> str:
        pool = await self._get_pool()
        job = await pool.enqueue_job(
            "extract_midi_from_audio_job",
            str(run_id),
            _queue_name=AUDIO_TO_MIDI_QUEUE_NAME,
        )
        if job is None:
            raise RuntimeError("Audio-to-MIDI job could not be enqueued")
        return str(job.job_id)

    async def enqueue_audio_derivative(self, run_id: UUID) -> str:
        pool = await self._get_pool()
        job = await pool.enqueue_job(
            "normalize_audio_derivative_job",
            str(run_id),
            _queue_name=AUDIO_FFMPEG_QUEUE_NAME,
        )
        if job is None:
            raise RuntimeError("Audio derivative job could not be enqueued")
        return str(job.job_id)

    async def enqueue_reference_analysis(self, run_id: UUID) -> str:
        pool = await self._get_pool()
        job = await pool.enqueue_job("analyze_reference_audio_job", str(run_id))
        if job is None:
            raise RuntimeError("Reference analysis job could not be enqueued")
        return str(job.job_id)

    async def enqueue_text_generation(self, run_id: UUID) -> str:
        pool = await self._get_pool()
        job = await pool.enqueue_job("generate_text_candidates_job", str(run_id))
        if job is None:
            raise RuntimeError("Text candidate generation job could not be enqueued")
        return str(job.job_id)

    async def enqueue_text_evaluation(self, run_id: UUID) -> str:
        pool = await self._get_pool()
        job = await pool.enqueue_job("run_text_evaluation_job", str(run_id))
        if job is None:
            raise RuntimeError("Text evaluation job could not be enqueued")
        return str(job.job_id)


@lru_cache
def get_arq_task_queue() -> ArqTaskQueue:
    return ArqTaskQueue(get_settings().redis_url)


def get_demo_task_queue() -> DemoTaskQueue:
    return get_arq_task_queue()


def get_audio_to_midi_task_queue() -> AudioToMidiTaskQueue:
    return get_arq_task_queue()


def get_audio_derivative_task_queue() -> AudioDerivativeTaskQueue:
    return get_arq_task_queue()


def get_reference_analysis_task_queue() -> ReferenceAnalysisTaskQueue:
    return get_arq_task_queue()


def get_text_generation_task_queue() -> TextGenerationTaskQueue:
    return get_arq_task_queue()


def get_text_evaluation_task_queue() -> TextEvaluationTaskQueue:
    return get_arq_task_queue()


async def close_task_queue() -> None:
    queue = get_arq_task_queue()
    await queue.close()
    get_arq_task_queue.cache_clear()


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

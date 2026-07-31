import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.core.database import AsyncSessionLocal
from abachiwave.models.demo import GenerationRun, GenerationRunStatus

TASK_TIMEOUT_ERROR = "task execution timed out"
GenerationExecutor = Callable[[UUID], Awaitable[GenerationRun | None]]
FailureMarker = Callable[[UUID, str], Awaitable[GenerationRun | None]]


async def lock_generation_run(
    session: AsyncSession,
    run_id: UUID,
) -> GenerationRun | None:
    statement: Select[tuple[GenerationRun]] = (
        select(GenerationRun)
        .where(GenerationRun.id == str(run_id))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def mark_generation_run_failed(
    run_id: UUID,
    error_message: str,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> GenerationRun | None:
    selected_session_factory = session_factory or AsyncSessionLocal
    async with selected_session_factory() as session:
        run = await lock_generation_run(session, run_id)
        if run is None:
            return None
        if run.status not in {GenerationRunStatus.queued, GenerationRunStatus.running}:
            return run
        run.status = GenerationRunStatus.failed
        run.error_code = "task_timeout"
        run.error_message = error_message
        run.completed_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(run)
        return run


async def run_generation_with_timeout(
    run_id: UUID,
    executor: GenerationExecutor,
    *,
    timeout_seconds: float,
    failure_marker: FailureMarker = mark_generation_run_failed,
) -> GenerationRun | None:
    try:
        return await asyncio.wait_for(executor(run_id), timeout=timeout_seconds)
    except TimeoutError:
        return await failure_marker(run_id, TASK_TIMEOUT_ERROR)

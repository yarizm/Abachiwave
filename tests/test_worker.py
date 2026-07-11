import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.models.demo import (
    GenerationRun,
    GenerationRunStatus,
    GenerationRunType,
)
from abachiwave.models.project import Project
from abachiwave.services.generation_runs import TASK_TIMEOUT_ERROR, run_generation_with_timeout
from abachiwave.worker import build_redis_settings, health_check, load_generation_log_context


@pytest.mark.asyncio
async def test_worker_health_check() -> None:
    assert await health_check({}) == {"status": "ok"}


def test_build_redis_settings_from_url() -> None:
    settings = build_redis_settings("redis://user:pass@localhost:6380/2")

    assert settings.host == "localhost"
    assert settings.port == 6380
    assert settings.database == 2
    assert settings.username == "user"
    assert settings.password == "pass"


@pytest.mark.asyncio
async def test_load_generation_log_context_includes_run_and_project(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        project = Project(name="Worker context")
        session.add(project)
        await session.flush()
        run = GenerationRun(
            project_id=project.id,
            run_type=GenerationRunType.demo_generation,
            status=GenerationRunStatus.queued,
            input_manifest={},
            provider_name="test_provider",
            provider_version="1.0",
            provider_params={},
        )
        session.add(run)
        await session.commit()
        run_id = UUID(run.id)

    context = await load_generation_log_context(run_id, session_factory=session_factory)

    assert context == {
        "generation_run_id": str(run_id),
        "project_id": project.id,
        "generation_run_type": "demo_generation",
    }


@pytest.mark.asyncio
async def test_generation_timeout_marks_run_failed() -> None:
    run_id = uuid4()
    marked: list[tuple[UUID, str]] = []

    async def slow_executor(_run_id: UUID) -> GenerationRun | None:
        await asyncio.sleep(1)
        return None

    async def failure_marker(failed_run_id: UUID, message: str) -> GenerationRun | None:
        marked.append((failed_run_id, message))
        return GenerationRun(
            id=str(failed_run_id),
            project_id=str(uuid4()),
            status=GenerationRunStatus.failed,
            error_message=message,
        )

    run = await run_generation_with_timeout(
        run_id,
        slow_executor,
        timeout_seconds=0.01,
        failure_marker=failure_marker,
    )

    assert run is not None
    assert run.status == GenerationRunStatus.failed
    assert run.error_message == TASK_TIMEOUT_ERROR
    assert marked == [(run_id, TASK_TIMEOUT_ERROR)]

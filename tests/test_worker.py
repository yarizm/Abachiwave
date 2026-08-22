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
from abachiwave.services.generation_runs import (
    TASK_INTERRUPTED_ERROR,
    TASK_TIMEOUT_ERROR,
    mark_generation_run_interrupted,
    run_generation_with_timeout,
)
from abachiwave.services.task_queue import (
    AUDIO_FFMPEG_QUEUE_NAME,
    AUDIO_TO_MIDI_QUEUE_NAME,
    ArqTaskQueue,
)
from abachiwave.worker import (
    AudioToMidiWorkerSettings,
    WorkerSettings,
    build_redis_settings,
    extract_midi_from_audio_job,
    health_check,
    load_generation_log_context,
    run_text_evaluation_job,
)


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
async def test_task_queue_reuses_pool_until_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeJob:
        job_id = "job-1"

    class FakePool:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, str | None]] = []
            self.closed = False

        async def enqueue_job(
            self,
            function: str,
            run_id: str,
            *,
            _queue_name: str | None = None,
        ) -> FakeJob:
            self.calls.append((function, run_id, _queue_name))
            return FakeJob()

        async def close(self) -> None:
            self.closed = True

    pool = FakePool()
    create_calls = 0

    async def fake_create_pool(_settings: object) -> FakePool:
        nonlocal create_calls
        create_calls += 1
        return pool

    monkeypatch.setattr("abachiwave.services.task_queue.create_pool", fake_create_pool)
    queue = ArqTaskQueue("redis://localhost:6379/0")
    first_run = uuid4()
    second_run = uuid4()
    third_run = uuid4()
    fourth_run = uuid4()
    fifth_run = uuid4()
    sixth_run = uuid4()

    assert await queue.enqueue_demo_generation(first_run) == "job-1"
    assert await queue.enqueue_audio_to_midi(second_run) == "job-1"
    assert await queue.enqueue_audio_derivative(third_run) == "job-1"
    assert await queue.enqueue_reference_analysis(sixth_run) == "job-1"
    assert await queue.enqueue_text_generation(fourth_run) == "job-1"
    assert await queue.enqueue_text_evaluation(fifth_run) == "job-1"
    await queue.close()

    assert create_calls == 1
    assert pool.calls == [
        ("generate_demo_job", str(first_run), None),
        ("extract_midi_from_audio_job", str(second_run), AUDIO_TO_MIDI_QUEUE_NAME),
        ("normalize_audio_derivative_job", str(third_run), AUDIO_FFMPEG_QUEUE_NAME),
        ("analyze_reference_audio_job", str(sixth_run), None),
        ("generate_text_candidates_job", str(fourth_run), None),
        ("run_text_evaluation_job", str(fifth_run), None),
    ]
    assert pool.closed is True


def test_audio_to_midi_uses_dedicated_worker_queue() -> None:
    assert AudioToMidiWorkerSettings.queue_name == AUDIO_TO_MIDI_QUEUE_NAME
    assert any(
        function.__name__ == "extract_midi_from_audio_job"
        for function in AudioToMidiWorkerSettings.functions
    )
    assert all(
        function.__name__ != "extract_midi_from_audio_job"
        for function in WorkerSettings.functions
    )


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


@pytest.mark.asyncio
async def test_interrupted_marker_only_changes_active_generation_run(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        project = Project(name="Interrupted worker")
        session.add(project)
        await session.flush()
        run = GenerationRun(
            project_id=project.id,
            run_type=GenerationRunType.audio_to_midi,
            status=GenerationRunStatus.running,
            input_manifest={},
            provider_name="test_provider",
            provider_version="1.0",
            provider_params={},
        )
        session.add(run)
        await session.commit()
        run_id = UUID(run.id)

    interrupted = await mark_generation_run_interrupted(
        run_id,
        session_factory=session_factory,
    )
    assert interrupted is not None
    assert interrupted.status == GenerationRunStatus.failed
    assert interrupted.error_code == "task_interrupted"
    assert interrupted.error_message == TASK_INTERRUPTED_ERROR
    assert interrupted.completed_at is not None

    repeated = await mark_generation_run_interrupted(
        run_id,
        session_factory=session_factory,
    )
    assert repeated is not None
    assert repeated.error_code == "task_interrupted"


@pytest.mark.asyncio
async def test_worker_cancellation_marks_generation_run_interrupted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = uuid4()
    marked: list[tuple[UUID, str]] = []

    async def fake_context(_run_id: UUID) -> dict[str, str]:
        return {"generation_run_id": str(_run_id)}

    async def cancel_job(*args: object, **kwargs: object) -> None:
        raise asyncio.CancelledError

    async def mark_interrupted(marked_run_id: UUID, message: str) -> None:
        marked.append((marked_run_id, message))

    monkeypatch.setattr("abachiwave.worker.load_generation_log_context", fake_context)
    monkeypatch.setattr("abachiwave.worker.run_generation_with_timeout", cancel_job)
    monkeypatch.setattr(
        "abachiwave.worker.mark_generation_run_interrupted",
        mark_interrupted,
    )

    with pytest.raises(asyncio.CancelledError):
        await extract_midi_from_audio_job({}, str(run_id))

    assert marked == [(run_id, TASK_INTERRUPTED_ERROR)]


@pytest.mark.asyncio
async def test_evaluation_exception_marks_run_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Any non-timeout exception escaping execute_text_evaluation must mark the
    run failed, or the evaluation_runs row stays 'running' forever."""
    async def boom(_run_uuid: UUID) -> None:
        raise RuntimeError("provider exploded")

    monkeypatch.setattr("abachiwave.worker.execute_text_evaluation", boom)
    marked: list[tuple[UUID, str, str]] = []

    async def fake_mark(run_uuid: UUID, error_code: str, error_message: str) -> None:
        marked.append((run_uuid, error_code, error_message))

    monkeypatch.setattr("abachiwave.worker.mark_text_evaluation_failed", fake_mark)
    run_id = uuid4()

    result = await run_text_evaluation_job({}, str(run_id))

    assert result == {"status": "failed"}
    assert marked == [(run_id, "evaluation_failed", "Text evaluation failed: RuntimeError")]

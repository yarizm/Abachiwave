from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.models.project import Project
from abachiwave.models.song_spec import SongSpecVersion
from abachiwave.services.versioning import (
    ProjectVersionLockError,
    VersionWriteConflictError,
    create_version_with_retry,
    is_version_number_conflict,
    lock_project_for_version_write,
    project_version_lock_statement,
)


def test_project_version_lock_uses_postgresql_for_update() -> None:
    statement = project_version_lock_statement(uuid4())
    sql = str(statement)

    assert "FOR UPDATE" in sql


@pytest.mark.asyncio
async def test_project_version_lock_requires_existing_project(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        project = Project(name="Version lock")
        session.add(project)
        await session.commit()

        await lock_project_for_version_write(session, UUID(project.id))

        with pytest.raises(ProjectVersionLockError):
            await lock_project_for_version_write(session, uuid4())


@pytest.mark.asyncio
async def test_version_create_retries_inside_savepoint(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        project = Project(name="Retry version")
        session.add(project)
        await session.flush()
        session.add(
            SongSpecVersion(project_id=project.id, version_number=1)
        )
        await session.commit()

        numbers = iter([1, 2])

        async def load_next_version_number() -> int:
            return next(numbers)

        version = await create_version_with_retry(
            session=session,
            project_id=UUID(project.id),
            load_next_version_number=load_next_version_number,
            build_version=lambda number: SongSpecVersion(
                project_id=project.id,
                version_number=number,
            ),
            max_retries=1,
        )
        await session.commit()

        assert version.version_number == 2
        count = await session.scalar(select(func.count()).select_from(SongSpecVersion))
        assert count == 2


@pytest.mark.asyncio
async def test_version_create_raises_after_retry_limit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        project = Project(name="Exhaust version retry")
        session.add(project)
        await session.flush()
        session.add(SongSpecVersion(project_id=project.id, version_number=1))
        await session.commit()

        async def stale_version_number() -> int:
            return 1

        with pytest.raises(VersionWriteConflictError):
            await create_version_with_retry(
                session=session,
                project_id=UUID(project.id),
                load_next_version_number=stale_version_number,
                build_version=lambda number: SongSpecVersion(
                    project_id=project.id,
                    version_number=number,
                ),
                max_retries=1,
            )

        count = await session.scalar(select(func.count()).select_from(SongSpecVersion))
        assert count == 1


def test_non_version_integrity_error_is_not_retryable() -> None:
    error = IntegrityError("insert", {}, Exception("UNIQUE constraint failed: projects.id"))

    assert is_version_number_conflict(error) is False

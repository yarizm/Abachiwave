from datetime import UTC, datetime
from functools import partial
from uuid import UUID

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.agents.song_spec import build_clarification_questions, build_song_spec_from_input
from abachiwave.models.project import Project
from abachiwave.models.song_spec import (
    IdeaIntake,
    IdeaIntakeStatus,
    SongSpecStatus,
    SongSpecVersion,
)
from abachiwave.schemas.song_specs import (
    IdeaIntakeCreate,
    IdeaIntakeRead,
    SongSpecData,
    SongSpecUpdate,
    SongSpecVersionRead,
)
from abachiwave.services.events import add_project_event
from abachiwave.services.versioning import create_version_with_retry


def intake_to_read(intake: IdeaIntake) -> IdeaIntakeRead:
    return IdeaIntakeRead(
        intake_id=UUID(intake.id),
        idea=intake.idea,
        answers=intake.answers,
        status=intake.status,
        questions=intake.questions,
        generation_source=intake.generation_source,
        created_at=intake.created_at,
        updated_at=intake.updated_at,
    )


def song_spec_to_data(song_spec: SongSpecVersion) -> SongSpecData:
    return SongSpecData(
        theme=song_spec.theme,
        genre=song_spec.genre,
        language=song_spec.language,
        tempo_bpm=song_spec.tempo_bpm,
        key=song_spec.key,
        time_signature=song_spec.time_signature,
        target_duration_seconds=song_spec.target_duration_seconds,
        mood_curve=song_spec.mood_curve,
        song_structure=song_spec.song_structure,
    )


def song_spec_to_read(song_spec: SongSpecVersion) -> SongSpecVersionRead:
    data = song_spec_to_data(song_spec)
    return SongSpecVersionRead(
        id=UUID(song_spec.id),
        project_id=UUID(song_spec.project_id),
        intake_id=UUID(song_spec.intake_id) if song_spec.intake_id else None,
        version_number=song_spec.version_number,
        status=song_spec.status,
        parent_version_id=(
            UUID(song_spec.parent_version_id) if song_spec.parent_version_id else None
        ),
        approved_at=song_spec.approved_at,
        song_spec=data,
        missing_required_fields=data.missing_required_fields(),
        created_at=song_spec.created_at,
        updated_at=song_spec.updated_at,
    )


async def project_exists(session: AsyncSession, project_id: UUID) -> bool:
    return await session.get(Project, str(project_id)) is not None


async def create_idea_intake(
    session: AsyncSession,
    project_id: UUID,
    payload: IdeaIntakeCreate,
) -> IdeaIntake | None:
    if not await project_exists(session, project_id):
        return None
    questions = build_clarification_questions(payload.idea, payload.answers)
    status = (
        IdeaIntakeStatus.needs_clarification
        if questions
        else IdeaIntakeStatus.ready_for_generation
    )
    intake = IdeaIntake(
        project_id=str(project_id),
        idea=payload.idea,
        answers=payload.answers,
        questions=[question.model_dump() for question in questions],
        status=status,
    )
    session.add(intake)
    await session.flush()
    add_project_event(
        session,
        project_id=project_id,
        event_type="intake.created",
        payload={
            "intake_id": intake.id,
            "status": str(status),
            "question_count": len(questions),
        },
    )
    await session.commit()
    await session.refresh(intake)
    return intake


async def get_latest_idea_intake(session: AsyncSession, project_id: UUID) -> IdeaIntake | None:
    statement: Select[tuple[IdeaIntake]] = (
        select(IdeaIntake)
        .where(IdeaIntake.project_id == str(project_id))
        .order_by(IdeaIntake.created_at.desc())
        .limit(1)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_idea_intake(
    session: AsyncSession,
    project_id: UUID,
    intake_id: UUID,
) -> IdeaIntake | None:
    statement: Select[tuple[IdeaIntake]] = select(IdeaIntake).where(
        IdeaIntake.id == str(intake_id),
        IdeaIntake.project_id == str(project_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_song_spec_versions(
    session: AsyncSession,
    project_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[SongSpecVersion]:
    statement: Select[tuple[SongSpecVersion]] = (
        select(SongSpecVersion)
        .where(SongSpecVersion.project_id == str(project_id))
        .order_by(SongSpecVersion.version_number.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_song_spec_version(
    session: AsyncSession,
    project_id: UUID,
    song_spec_id: UUID,
) -> SongSpecVersion | None:
    statement: Select[tuple[SongSpecVersion]] = select(SongSpecVersion).where(
        SongSpecVersion.id == str(song_spec_id),
        SongSpecVersion.project_id == str(project_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def generate_song_spec_version(
    session: AsyncSession,
    project_id: UUID,
    intake_id: UUID,
) -> SongSpecVersion | None:
    intake = await get_idea_intake(session, project_id, intake_id)
    if intake is None:
        return None
    data = build_song_spec_from_input(intake.idea, intake.answers)
    version = await _create_song_spec_version(
        session=session,
        project_id=project_id,
        intake_id=intake_id,
        data=data,
        parent_version_id=None,
    )
    intake.status = IdeaIntakeStatus.generated
    await session.commit()
    await session.refresh(version)
    return version


async def edit_song_spec_version(
    session: AsyncSession,
    project_id: UUID,
    song_spec_id: UUID,
    payload: SongSpecUpdate,
) -> SongSpecVersion | None:
    current = await get_song_spec_version(session, project_id, song_spec_id)
    if current is None:
        return None
    current_data = song_spec_to_data(current).model_dump()
    updates = payload.model_dump(exclude_unset=True)
    merged = SongSpecData(**{**current_data, **updates})
    return await _create_song_spec_version(
        session=session,
        project_id=project_id,
        intake_id=UUID(current.intake_id) if current.intake_id else None,
        data=merged,
        parent_version_id=UUID(current.id),
    )


async def approve_song_spec_version(
    session: AsyncSession,
    project_id: UUID,
    song_spec_id: UUID,
) -> tuple[SongSpecVersion | None, list[str]]:
    song_spec = await get_song_spec_version(session, project_id, song_spec_id)
    if song_spec is None:
        return None, []
    data = song_spec_to_data(song_spec)
    missing = data.missing_required_fields()
    if missing:
        return song_spec, missing

    await session.execute(
        update(SongSpecVersion)
        .where(
            SongSpecVersion.project_id == str(project_id),
            SongSpecVersion.status == SongSpecStatus.approved,
            SongSpecVersion.id != str(song_spec_id),
        )
        .values(status=SongSpecStatus.superseded)
    )
    song_spec.status = SongSpecStatus.approved
    song_spec.approved_at = datetime.now(UTC)
    add_project_event(
        session,
        project_id=project_id,
        event_type="song_spec.approved",
        payload={
            "song_spec_id": song_spec.id,
            "version_number": song_spec.version_number,
        },
        artifact_version_id=UUID(song_spec.id),
    )
    await session.commit()
    await session.refresh(song_spec)
    return song_spec, []


async def _next_version_number(session: AsyncSession, project_id: UUID) -> int:
    statement = select(func.max(SongSpecVersion.version_number)).where(
        SongSpecVersion.project_id == str(project_id)
    )
    result = await session.execute(statement)
    current = result.scalar_one_or_none()
    return int(current or 0) + 1


async def _create_song_spec_version(
    *,
    session: AsyncSession,
    project_id: UUID,
    intake_id: UUID | None,
    data: SongSpecData,
    parent_version_id: UUID | None,
) -> SongSpecVersion:
    version = await create_version_with_retry(
        session=session,
        project_id=project_id,
        load_next_version_number=partial(_next_version_number, session, project_id),
        build_version=lambda version_number: SongSpecVersion(
            project_id=str(project_id),
            intake_id=str(intake_id) if intake_id else None,
            version_number=version_number,
            status=SongSpecStatus.draft,
            parent_version_id=str(parent_version_id) if parent_version_id else None,
            **data.to_model_values(),
        ),
    )
    add_project_event(
        session,
        project_id=project_id,
        event_type="song_spec.edited" if parent_version_id else "song_spec.generated",
        payload={
            "song_spec_id": version.id,
            "version_number": version.version_number,
            "missing_required_fields": data.missing_required_fields(),
        },
        artifact_version_id=UUID(version.id),
    )
    await session.commit()
    await session.refresh(version)
    return version

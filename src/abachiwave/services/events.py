from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.models.revision import ProjectEvent


def add_project_event(
    session: AsyncSession,
    *,
    project_id: UUID,
    event_type: str,
    payload: dict[str, object],
    revision_request_id: UUID | None = None,
    generation_run_id: UUID | None = None,
    artifact_version_id: UUID | None = None,
) -> ProjectEvent:
    event = ProjectEvent(
        project_id=str(project_id),
        event_type=event_type,
        payload=payload,
        revision_request_id=str(revision_request_id) if revision_request_id else None,
        generation_run_id=str(generation_run_id) if generation_run_id else None,
        artifact_version_id=str(artifact_version_id) if artifact_version_id else None,
    )
    session.add(event)
    return event


async def list_project_events(
    session: AsyncSession,
    *,
    project_id: UUID,
    limit: int = 50,
) -> list[ProjectEvent]:
    statement: Select[tuple[ProjectEvent]] = (
        select(ProjectEvent)
        .where(ProjectEvent.project_id == str(project_id))
        .order_by(ProjectEvent.created_at.desc(), ProjectEvent.id.desc())
        .limit(limit)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())

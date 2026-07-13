from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.models.comment import ProjectComment, ProjectCommentStatus
from abachiwave.models.project import Project
from abachiwave.schemas.comments import (
    ProjectCommentCreate,
    ProjectCommentRead,
    ProjectCommentUpdate,
)
from abachiwave.services.events import add_project_event


def comment_to_read(comment: ProjectComment) -> ProjectCommentRead:
    return ProjectCommentRead(
        id=UUID(comment.id),
        project_id=UUID(comment.project_id),
        author_name=comment.author_name,
        body=comment.body,
        status=comment.status,
        target_type=comment.target_type,
        target_id=UUID(comment.target_id) if comment.target_id else None,
        resolved_at=comment.resolved_at,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


async def create_project_comment(
    session: AsyncSession,
    project_id: UUID,
    payload: ProjectCommentCreate,
) -> ProjectComment | None:
    project = await session.get(Project, str(project_id))
    if project is None:
        return None
    comment = ProjectComment(
        project_id=str(project_id),
        author_name=payload.author_name,
        body=payload.body,
        target_type=payload.target_type,
        target_id=str(payload.target_id) if payload.target_id else None,
    )
    session.add(comment)
    await session.flush()
    add_project_event(
        session,
        project_id=project_id,
        event_type="comment.created",
        payload={
            "comment_id": comment.id,
            "target_type": str(comment.target_type),
            "target_id": comment.target_id,
        },
        artifact_version_id=UUID(comment.id),
    )
    await session.commit()
    await session.refresh(comment)
    return comment


async def list_project_comments(
    session: AsyncSession,
    project_id: UUID,
    status: ProjectCommentStatus | None = None,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[ProjectComment]:
    statement: Select[tuple[ProjectComment]] = (
        select(ProjectComment)
        .where(ProjectComment.project_id == str(project_id))
        .order_by(ProjectComment.created_at.desc(), ProjectComment.id.desc())
    )
    if status is not None:
        statement = statement.where(ProjectComment.status == status)
    statement = statement.limit(limit).offset(offset)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_project_comment(
    session: AsyncSession,
    project_id: UUID,
    comment_id: UUID,
) -> ProjectComment | None:
    statement: Select[tuple[ProjectComment]] = select(ProjectComment).where(
        ProjectComment.id == str(comment_id),
        ProjectComment.project_id == str(project_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def update_project_comment(
    session: AsyncSession,
    project_id: UUID,
    comment_id: UUID,
    payload: ProjectCommentUpdate,
) -> ProjectComment | None:
    comment = await get_project_comment(session, project_id, comment_id)
    if comment is None:
        return None

    updates = payload.model_dump(exclude_unset=True)
    event_type = "comment.updated"
    if "body" in updates:
        comment.body = payload.body or comment.body
    if payload.status is not None:
        comment.status = payload.status
        if payload.status == ProjectCommentStatus.resolved:
            comment.resolved_at = datetime.now(UTC)
            event_type = "comment.resolved"
        else:
            comment.resolved_at = None
            event_type = "comment.reopened"

    if updates:
        add_project_event(
            session,
            project_id=project_id,
            event_type=event_type,
            payload={
                "comment_id": comment.id,
                "status": str(comment.status),
                "updated_fields": sorted(updates),
            },
            artifact_version_id=UUID(comment.id),
        )
    await session.commit()
    await session.refresh(comment)
    return comment

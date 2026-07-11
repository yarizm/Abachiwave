from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.models.comment import ProjectCommentStatus
from abachiwave.models.project import Project
from abachiwave.schemas.handoff import ProjectHandoffRead
from abachiwave.schemas.projects import ProjectRead
from abachiwave.schemas.revisions import ProjectEventRead
from abachiwave.services.comments import comment_to_read, list_project_comments
from abachiwave.services.delivery import build_asset_tree
from abachiwave.services.events import list_project_events
from abachiwave.services.handoff_format import (
    build_handoff_markdown,
    build_handoff_next_actions,
)
from abachiwave.services.review import build_project_review


async def build_project_handoff(
    session: AsyncSession,
    project_id: UUID,
) -> ProjectHandoffRead | None:
    project = await session.get(Project, str(project_id))
    if project is None:
        return None

    asset_tree = await build_asset_tree(session, project_id)
    review = await build_project_review(session, project_id)
    if review is None:
        return None

    open_comments = [
        comment_to_read(comment)
        for comment in await list_project_comments(
            session,
            project_id,
            ProjectCommentStatus.open,
        )
    ]
    recent_events = [
        ProjectEventRead.model_validate(event)
        for event in await list_project_events(session, project_id=project_id, limit=12)
    ]
    generated_at = datetime.now(UTC)
    next_actions = build_handoff_next_actions(review, open_comments)
    project_read = ProjectRead.model_validate(project)

    return ProjectHandoffRead(
        project=project_read,
        review=review,
        current_assets=asset_tree.current,
        missing_prerequisites=asset_tree.missing_prerequisites,
        open_comments=open_comments,
        recent_events=recent_events,
        next_actions=next_actions,
        handoff_markdown=build_handoff_markdown(
            project=project_read,
            review=review,
            asset_tree=asset_tree,
            open_comments=open_comments,
            recent_events=recent_events,
            next_actions=next_actions,
            generated_at=generated_at,
        ),
        generated_at=generated_at,
    )

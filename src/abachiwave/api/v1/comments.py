from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.core.database import get_session
from abachiwave.models.comment import ProjectCommentStatus
from abachiwave.schemas.comments import (
    ProjectCommentCreate,
    ProjectCommentRead,
    ProjectCommentUpdate,
)
from abachiwave.services.comments import (
    comment_to_read,
    create_project_comment,
    list_project_comments,
    update_project_comment,
)
from abachiwave.services.song_specs import project_exists

router = APIRouter()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/{project_id}/comments",
    response_model=ProjectCommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_project_comment_endpoint(
    project_id: UUID,
    payload: ProjectCommentCreate,
    session: SessionDependency,
) -> ProjectCommentRead:
    comment = await create_project_comment(session, project_id, payload)
    if comment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return comment_to_read(comment)


@router.get("/{project_id}/comments", response_model=list[ProjectCommentRead])
async def list_project_comments_endpoint(
    project_id: UUID,
    session: SessionDependency,
    status_filter: Annotated[ProjectCommentStatus | None, Query(alias="status")] = None,
) -> list[ProjectCommentRead]:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    comments = await list_project_comments(session, project_id, status_filter)
    return [comment_to_read(comment) for comment in comments]


@router.patch("/{project_id}/comments/{comment_id}", response_model=ProjectCommentRead)
async def update_project_comment_endpoint(
    project_id: UUID,
    comment_id: UUID,
    payload: ProjectCommentUpdate,
    session: SessionDependency,
) -> ProjectCommentRead:
    comment = await update_project_comment(session, project_id, comment_id, payload)
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ProjectComment not found",
        )
    return comment_to_read(comment)

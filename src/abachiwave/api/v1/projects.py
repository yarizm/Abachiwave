from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.api.errors import ErrorCode, ErrorHint, ProblemError
from abachiwave.api.pagination import PageDependency
from abachiwave.api.v1.ai import enqueue_candidate_generation_or_raise
from abachiwave.core.database import get_session
from abachiwave.models.ai import TextWorkflow
from abachiwave.schemas.ai import CandidateGenerateRequest
from abachiwave.schemas.demo import GenerationRunRead
from abachiwave.schemas.handoff import ProjectHandoffRead
from abachiwave.schemas.projects import ProjectCreate, ProjectRead, ProjectUpdate
from abachiwave.schemas.review import ProjectReviewRead
from abachiwave.schemas.song_specs import (
    IdeaIntakeCreate,
    IdeaIntakeRead,
    SongSpecGenerateRequest,
    SongSpecUpdate,
    SongSpecVersionRead,
)
from abachiwave.services.handoff import build_project_handoff
from abachiwave.services.projects import (
    create_project,
    get_project,
    list_projects,
    update_project,
)
from abachiwave.services.review import build_project_review
from abachiwave.services.song_specs import (
    SongSpecStructureChangeRequiresPreviewError,
    approve_song_spec_version,
    create_idea_intake,
    edit_song_spec_version,
    generate_song_spec_version,
    get_latest_idea_intake,
    intake_to_read,
    list_song_spec_versions,
    project_exists,
    song_spec_to_read,
)
from abachiwave.services.task_queue import (
    TextGenerationTaskQueue,
    get_text_generation_task_queue,
)

router = APIRouter()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
TextQueueDependency = Annotated[
    TextGenerationTaskQueue,
    Depends(get_text_generation_task_queue),
]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project_endpoint(
    payload: ProjectCreate,
    session: SessionDependency,
) -> ProjectRead:
    project = await create_project(session, payload)
    return ProjectRead.model_validate(project)


@router.get("", response_model=list[ProjectRead])
async def list_projects_endpoint(
    session: SessionDependency,
    page: PageDependency,
) -> list[ProjectRead]:
    projects = await list_projects(session, limit=page.limit, offset=page.offset)
    return [ProjectRead.model_validate(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project_endpoint(
    project_id: UUID,
    session: SessionDependency,
) -> ProjectRead:
    project = await get_project(session, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectRead.model_validate(project)


@router.get("/{project_id}/review", response_model=ProjectReviewRead)
async def get_project_review_endpoint(
    project_id: UUID,
    session: SessionDependency,
) -> ProjectReviewRead:
    review = await build_project_review(session, project_id)
    if review is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return review


@router.get("/{project_id}/handoff", response_model=ProjectHandoffRead)
async def get_project_handoff_endpoint(
    project_id: UUID,
    session: SessionDependency,
) -> ProjectHandoffRead:
    handoff = await build_project_handoff(session, project_id)
    if handoff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return handoff


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project_endpoint(
    project_id: UUID,
    payload: ProjectUpdate,
    session: SessionDependency,
) -> ProjectRead:
    project = await update_project(session, project_id, payload)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectRead.model_validate(project)


@router.post(
    "/{project_id}/intake",
    response_model=IdeaIntakeRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_idea_intake_endpoint(
    project_id: UUID,
    payload: IdeaIntakeCreate,
    session: SessionDependency,
) -> IdeaIntakeRead:
    intake = await create_idea_intake(session, project_id, payload)
    if intake is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return intake_to_read(intake)


@router.get("/{project_id}/intake/latest", response_model=IdeaIntakeRead | None)
async def get_latest_idea_intake_endpoint(
    project_id: UUID,
    session: SessionDependency,
) -> IdeaIntakeRead | None:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    intake = await get_latest_idea_intake(session, project_id)
    return intake_to_read(intake) if intake else None


@router.post(
    "/{project_id}/song-spec/generate",
    response_model=SongSpecVersionRead | GenerationRunRead,
)
async def generate_song_spec_endpoint(
    project_id: UUID,
    payload: SongSpecGenerateRequest,
    session: SessionDependency,
    queue: TextQueueDependency,
    response: Response,
) -> SongSpecVersionRead | GenerationRunRead:
    if payload.provider_profile_id is not None or payload.candidate_count is not None:
        response.status_code = status.HTTP_202_ACCEPTED
        return await enqueue_candidate_generation_or_raise(
            session=session,
            project_id=project_id,
            payload=CandidateGenerateRequest(
                workflow=TextWorkflow.song_spec,
                provider_profile_id=payload.provider_profile_id,
                candidate_count=payload.candidate_count or 1,
                intake_id=payload.intake_id,
            ),
            queue=queue,
        )
    song_spec = await generate_song_spec_version(session, project_id, payload.intake_id)
    if song_spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project or intake not found",
        )
    return song_spec_to_read(song_spec)


@router.get("/{project_id}/song-specs", response_model=list[SongSpecVersionRead])
async def list_song_spec_versions_endpoint(
    project_id: UUID,
    session: SessionDependency,
    page: PageDependency,
) -> list[SongSpecVersionRead]:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    song_specs = await list_song_spec_versions(
        session,
        project_id,
        limit=page.limit,
        offset=page.offset,
    )
    return [song_spec_to_read(song_spec) for song_spec in song_specs]


@router.patch("/{project_id}/song-specs/{song_spec_id}", response_model=SongSpecVersionRead)
async def edit_song_spec_version_endpoint(
    project_id: UUID,
    song_spec_id: UUID,
    payload: SongSpecUpdate,
    session: SessionDependency,
) -> SongSpecVersionRead:
    try:
        song_spec = await edit_song_spec_version(session, project_id, song_spec_id, payload)
    except SongSpecStructureChangeRequiresPreviewError as error:
        raise ProblemError(
            status_code=status.HTTP_409_CONFLICT,
            error_code=ErrorCode.SONG_STRUCTURE_CHANGE_REQUIRES_PREVIEW,
            detail=str(error),
            hint=ErrorHint.USE_STRUCTURE_EDITOR,
        ) from error
    if song_spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SongSpec not found")
    return song_spec_to_read(song_spec)


@router.post("/{project_id}/song-specs/{song_spec_id}/approve", response_model=SongSpecVersionRead)
async def approve_song_spec_version_endpoint(
    project_id: UUID,
    song_spec_id: UUID,
    session: SessionDependency,
) -> SongSpecVersionRead:
    song_spec, missing = await approve_song_spec_version(session, project_id, song_spec_id)
    if song_spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SongSpec not found")
    if missing:
        raise ProblemError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_code=ErrorCode.SONG_SPEC_INCOMPLETE,
            detail={"message": "SongSpec is incomplete", "missing_required_fields": missing},
            hint=ErrorHint.CHECK_REQUIRED_FIELDS,
            fields={field: f"{field} is required" for field in missing},
        )
    return song_spec_to_read(song_spec)

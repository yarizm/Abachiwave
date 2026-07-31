from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.api.pagination import PageDependency
from abachiwave.api.v1.ai import enqueue_candidate_generation_or_raise
from abachiwave.core.database import get_session
from abachiwave.models.ai import TextWorkflow
from abachiwave.schemas.ai import CandidateGenerateRequest
from abachiwave.schemas.demo import GenerationRunRead
from abachiwave.schemas.revisions import (
    ProjectEventRead,
    RevisionApplyRead,
    RevisionApplyRequest,
    RevisionRequestCreate,
    RevisionRequestRead,
    VersionDiffRead,
    VersionRestoreRead,
    VersionRestoreRequest,
)
from abachiwave.services.demo import create_demo_generation_run, generation_run_to_read
from abachiwave.services.events import list_project_events
from abachiwave.services.revisions import (
    apply_revision_request,
    build_version_diff,
    create_revision_request,
    get_revision_request,
    list_revision_requests,
    reject_revision_request,
    restore_version,
    restored_version_to_read,
    revision_request_to_read,
)
from abachiwave.services.song_specs import project_exists
from abachiwave.services.storage import ObjectStorage, get_object_storage
from abachiwave.services.task_queue import (
    DemoTaskQueue,
    TextGenerationTaskQueue,
    get_demo_task_queue,
    get_text_generation_task_queue,
)

router = APIRouter()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
StorageDependency = Annotated[ObjectStorage, Depends(get_object_storage)]
QueueDependency = Annotated[DemoTaskQueue, Depends(get_demo_task_queue)]
TextQueueDependency = Annotated[
    TextGenerationTaskQueue,
    Depends(get_text_generation_task_queue),
]


@router.post(
    "/{project_id}/revisions",
    response_model=RevisionRequestRead | GenerationRunRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_revision_endpoint(
    project_id: UUID,
    payload: RevisionRequestCreate,
    session: SessionDependency,
    queue: TextQueueDependency,
    response: Response,
) -> RevisionRequestRead | GenerationRunRead:
    if payload.provider_profile_id is not None or payload.candidate_count is not None:
        response.status_code = status.HTTP_202_ACCEPTED
        return await enqueue_candidate_generation_or_raise(
            session=session,
            project_id=project_id,
            payload=CandidateGenerateRequest(
                workflow=TextWorkflow.revision,
                provider_profile_id=payload.provider_profile_id,
                candidate_count=payload.candidate_count or 1,
                feedback=payload.feedback,
            ),
            queue=queue,
        )
    revision = await create_revision_request(session, project_id, payload.feedback)
    if revision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return revision_request_to_read(revision)


@router.get("/{project_id}/revisions", response_model=list[RevisionRequestRead])
async def list_revisions_endpoint(
    project_id: UUID,
    session: SessionDependency,
    page: PageDependency,
) -> list[RevisionRequestRead]:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    revisions = await list_revision_requests(
        session,
        project_id,
        limit=page.limit,
        offset=page.offset,
    )
    return [revision_request_to_read(revision) for revision in revisions]


@router.get("/{project_id}/events", response_model=list[ProjectEventRead])
async def list_project_events_endpoint(
    project_id: UUID,
    session: SessionDependency,
    page: PageDependency,
) -> list[ProjectEventRead]:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    events = await list_project_events(
        session,
        project_id=project_id,
        limit=page.limit,
        offset=page.offset,
    )
    return [ProjectEventRead.model_validate(event) for event in events]


@router.get("/{project_id}/revisions/{revision_id}", response_model=RevisionRequestRead)
async def get_revision_endpoint(
    project_id: UUID,
    revision_id: UUID,
    session: SessionDependency,
) -> RevisionRequestRead:
    revision = await get_revision_request(session, project_id, revision_id)
    if revision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RevisionRequest not found",
        )
    return revision_request_to_read(revision)


@router.post("/{project_id}/revisions/{revision_id}/apply", response_model=RevisionApplyRead)
async def apply_revision_endpoint(
    project_id: UUID,
    revision_id: UUID,
    payload: RevisionApplyRequest,
    session: SessionDependency,
    storage: StorageDependency,
    queue: QueueDependency,
) -> RevisionApplyRead:
    result = await apply_revision_request(
        session=session,
        project_id=project_id,
        revision_id=revision_id,
        task_ids=payload.task_ids,
        storage=storage,
    )
    if result.not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.not_found)
    if result.conflict or result.revision is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.conflict or "RevisionRequest could not be applied",
        )

    demo_run: GenerationRunRead | None = None
    if payload.regenerate_demo:
        demo_result = await create_demo_generation_run(
            session=session,
            project_id=project_id,
            arrangement_plan_id=None,
            queue=queue,
        )
        if demo_result.not_found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=demo_result.not_found)
        if demo_result.missing or demo_result.run is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Demo prerequisites are missing",
                    "missing": demo_result.missing,
                },
            )
        demo_run = await generation_run_to_read(session, demo_result.run)

    return RevisionApplyRead(
        revision=revision_request_to_read(result.revision),
        created_versions=result.created_versions,
        demo_run=demo_run,
    )


@router.post("/{project_id}/revisions/{revision_id}/reject", response_model=RevisionRequestRead)
async def reject_revision_endpoint(
    project_id: UUID,
    revision_id: UUID,
    session: SessionDependency,
) -> RevisionRequestRead:
    revision, conflict = await reject_revision_request(session, project_id, revision_id)
    if conflict == "RevisionRequest not found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=conflict)
    if conflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict)
    if revision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RevisionRequest not found",
        )
    return revision_request_to_read(revision)


@router.get("/{project_id}/versions/diff", response_model=VersionDiffRead)
async def version_diff_endpoint(
    project_id: UUID,
    session: SessionDependency,
    asset_type: Annotated[str, Query()],
    left_id: Annotated[UUID, Query()],
    right_id: Annotated[UUID, Query()],
) -> VersionDiffRead:
    diff, not_found = await build_version_diff(
        session=session,
        project_id=project_id,
        asset_type=asset_type,
        left_id=left_id,
        right_id=right_id,
    )
    if not_found:
        status_code = (
            status.HTTP_409_CONFLICT
            if not_found == "Unsupported asset_type"
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=status_code, detail=not_found)
    if diff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    return diff


@router.post("/{project_id}/versions/restore", response_model=VersionRestoreRead)
async def restore_version_endpoint(
    project_id: UUID,
    payload: VersionRestoreRequest,
    session: SessionDependency,
    storage: StorageDependency,
) -> VersionRestoreRead:
    version, not_found = await restore_version(
        session=session,
        project_id=project_id,
        asset_type=payload.asset_type,
        version_id=payload.version_id,
        storage=storage,
    )
    if not_found:
        status_code = (
            status.HTTP_409_CONFLICT
            if not_found == "Unsupported asset_type"
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=status_code, detail=not_found)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    return restored_version_to_read(payload.asset_type, version)

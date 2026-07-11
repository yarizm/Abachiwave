from collections.abc import AsyncIterator
from io import BytesIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.core.database import get_session
from abachiwave.schemas.demo import AudioDemoVersionRead, DemoGenerateRequest, GenerationRunRead
from abachiwave.services.demo import (
    audio_demo_to_read,
    cancel_generation_run,
    create_demo_generation_run,
    generation_run_to_read,
    get_demo_version,
    get_generation_run,
    list_demo_versions,
    list_generation_runs,
    retry_generation_run,
)
from abachiwave.services.song_specs import project_exists
from abachiwave.services.storage import ObjectStorage, get_object_storage
from abachiwave.services.task_queue import DemoTaskQueue, get_demo_task_queue

router = APIRouter()
tasks_router = APIRouter()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
StorageDependency = Annotated[ObjectStorage, Depends(get_object_storage)]
QueueDependency = Annotated[DemoTaskQueue, Depends(get_demo_task_queue)]


@router.post(
    "/{project_id}/demo/generate",
    response_model=GenerationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_demo_endpoint(
    project_id: UUID,
    payload: DemoGenerateRequest,
    session: SessionDependency,
    queue: QueueDependency,
) -> GenerationRunRead:
    result = await create_demo_generation_run(
        session=session,
        project_id=project_id,
        arrangement_plan_id=payload.arrangement_plan_id,
        queue=queue,
    )
    if result.not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.not_found)
    if result.missing or result.run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Demo prerequisites are missing", "missing": result.missing},
        )
    return await generation_run_to_read(session, result.run)


@router.get("/{project_id}/demos", response_model=list[AudioDemoVersionRead])
async def list_demos_endpoint(
    project_id: UUID,
    session: SessionDependency,
) -> list[AudioDemoVersionRead]:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    demos = await list_demo_versions(session, project_id)
    return [audio_demo_to_read(demo) for demo in demos]


@router.get("/{project_id}/demos/{demo_id}", response_model=AudioDemoVersionRead)
async def get_demo_endpoint(
    project_id: UUID,
    demo_id: UUID,
    session: SessionDependency,
) -> AudioDemoVersionRead:
    demo = await get_demo_version(session, project_id, demo_id)
    if demo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AudioDemoVersion not found",
        )
    return audio_demo_to_read(demo)


@router.get("/{project_id}/demos/{demo_id}/download")
async def download_demo_endpoint(
    project_id: UUID,
    demo_id: UUID,
    session: SessionDependency,
    storage: StorageDependency,
) -> StreamingResponse:
    demo = await get_demo_version(session, project_id, demo_id)
    if demo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AudioDemoVersion not found",
        )
    try:
        data = storage.get_bytes(demo.storage_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo file not found",
        ) from exc
    return StreamingResponse(
        _byte_stream(data),
        media_type=demo.content_type,
        headers={"Content-Disposition": f'inline; filename="{demo.filename}"'},
    )


@router.get("/{project_id}/runs", response_model=list[GenerationRunRead])
async def list_project_runs_endpoint(
    project_id: UUID,
    session: SessionDependency,
) -> list[GenerationRunRead]:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    runs = await list_generation_runs(session, project_id)
    return [await generation_run_to_read(session, run) for run in runs]


@tasks_router.get("/{task_id}", response_model=GenerationRunRead)
async def get_task_endpoint(
    task_id: UUID,
    session: SessionDependency,
) -> GenerationRunRead:
    run = await get_generation_run(session, task_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GenerationRun not found")
    return await generation_run_to_read(session, run)


@tasks_router.post("/{task_id}/retry", response_model=GenerationRunRead)
async def retry_task_endpoint(
    task_id: UUID,
    session: SessionDependency,
    queue: QueueDependency,
) -> GenerationRunRead:
    run, not_found_or_conflict, missing = await retry_generation_run(
        session=session,
        task_id=task_id,
        queue=queue,
    )
    if not_found_or_conflict == "GenerationRun not found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_or_conflict)
    if not_found_or_conflict in {"GenerationRun is not failed", "GenerationRun is not retryable"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=not_found_or_conflict)
    if not_found_or_conflict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_or_conflict)
    if missing or run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Demo prerequisites are missing", "missing": missing},
        )
    return await generation_run_to_read(session, run)


@tasks_router.post("/{task_id}/cancel", response_model=GenerationRunRead)
async def cancel_task_endpoint(
    task_id: UUID,
    session: SessionDependency,
) -> GenerationRunRead:
    run, conflict = await cancel_generation_run(session, task_id)
    if conflict == "GenerationRun not found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=conflict)
    if conflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GenerationRun not found")
    return await generation_run_to_read(session, run)


async def _byte_stream(data: bytes) -> AsyncIterator[bytes]:
    buffer = BytesIO(data)
    yield buffer.read()

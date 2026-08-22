from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.api.errors import ErrorCode, ProblemError
from abachiwave.api.pagination import PageDependency
from abachiwave.core.database import get_session
from abachiwave.schemas.audio import AudioMarkerCreate, AudioMarkerRead, AudioMarkerUpdate
from abachiwave.services.audio_markers import (
    AudioMarkerPositionError,
    audio_marker_to_read,
    create_audio_marker,
    delete_audio_marker,
    list_audio_markers,
    update_audio_marker,
)

router = APIRouter()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "/{project_id}/audio-uploads/{audio_upload_id}/markers",
    response_model=AudioMarkerRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_audio_marker_endpoint(
    project_id: UUID,
    audio_upload_id: UUID,
    payload: AudioMarkerCreate,
    session: SessionDependency,
) -> AudioMarkerRead:
    try:
        marker = await create_audio_marker(session, project_id, audio_upload_id, payload)
    except AudioMarkerPositionError as exc:
        raise ProblemError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_code=ErrorCode.VALIDATION_FAILED,
            detail=str(exc),
            fields={"position_seconds": str(exc)},
        ) from exc
    if marker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AudioUpload not found")
    return audio_marker_to_read(marker)


@router.get(
    "/{project_id}/audio-uploads/{audio_upload_id}/markers",
    response_model=list[AudioMarkerRead],
)
async def list_audio_markers_endpoint(
    project_id: UUID,
    audio_upload_id: UUID,
    session: SessionDependency,
    page: PageDependency,
) -> list[AudioMarkerRead]:
    markers = await list_audio_markers(
        session,
        project_id,
        audio_upload_id,
        limit=page.limit,
        offset=page.offset,
    )
    if markers is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AudioUpload not found")
    return [audio_marker_to_read(marker) for marker in markers]


@router.patch(
    "/{project_id}/audio-markers/{marker_id}",
    response_model=AudioMarkerRead,
)
async def update_audio_marker_endpoint(
    project_id: UUID,
    marker_id: UUID,
    payload: AudioMarkerUpdate,
    session: SessionDependency,
) -> AudioMarkerRead:
    try:
        marker = await update_audio_marker(session, project_id, marker_id, payload)
    except AudioMarkerPositionError as exc:
        raise ProblemError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_code=ErrorCode.VALIDATION_FAILED,
            detail=str(exc),
            fields={"position_seconds": str(exc)},
        ) from exc
    if marker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AudioMarker not found")
    return audio_marker_to_read(marker)


@router.delete(
    "/{project_id}/audio-markers/{marker_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_audio_marker_endpoint(
    project_id: UUID,
    marker_id: UUID,
    session: SessionDependency,
) -> Response:
    deleted = await delete_audio_marker(session, project_id, marker_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AudioMarker not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

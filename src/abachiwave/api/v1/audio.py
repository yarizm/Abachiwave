from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.api.errors import ErrorCode, ErrorHint, ProblemError
from abachiwave.api.pagination import PageDependency
from abachiwave.core.database import get_session
from abachiwave.models.audio import AudioUploadKind
from abachiwave.schemas.audio import AudioExtractMidiRequest, AudioUploadRead, AudioUploadUpdate
from abachiwave.schemas.demo import GenerationRunRead
from abachiwave.services import audio as audio_service
from abachiwave.services.audio import (
    AudioUploadLimitError,
    AudioUploadTooLargeError,
    UnsupportedAudioTypeError,
    audio_upload_to_read,
    create_audio_to_midi_run,
    create_audio_upload,
    get_audio_upload,
    list_audio_uploads,
    update_audio_upload,
)
from abachiwave.services.demo import generation_run_to_read
from abachiwave.services.song_specs import project_exists
from abachiwave.services.storage import ObjectStorage, get_object_storage, iter_storage_bytes
from abachiwave.services.task_queue import (
    AudioToMidiTaskQueue,
    get_audio_to_midi_task_queue,
)

router = APIRouter()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
StorageDependency = Annotated[ObjectStorage, Depends(get_object_storage)]
QueueDependency = Annotated[AudioToMidiTaskQueue, Depends(get_audio_to_midi_task_queue)]


@router.post(
    "/{project_id}/audio-uploads",
    response_model=AudioUploadRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_audio_upload_endpoint(
    project_id: UUID,
    session: SessionDependency,
    storage: StorageDependency,
    file: Annotated[UploadFile, File()],
    kind: Annotated[AudioUploadKind, Form()],
    notes: Annotated[str | None, Form()] = None,
) -> AudioUploadRead:
    try:
        data = await _read_limited_upload(file)
        upload = await create_audio_upload(
            session=session,
            project_id=project_id,
            filename=file.filename or "audio.wav",
            content_type=file.content_type or "",
            data=data,
            kind=kind,
            notes=notes,
            storage=storage,
        )
    except AudioUploadTooLargeError as exc:
        raise ProblemError(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            error_code=ErrorCode.UPLOAD_TOO_LARGE,
            detail=str(exc),
            hint=ErrorHint.TRIM_AUDIO_UNDER_25MB,
        ) from exc
    except AudioUploadLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except UnsupportedAudioTypeError as exc:
        raise ProblemError(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            error_code=ErrorCode.UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
            hint=ErrorHint.CHECK_FORMAT,
        ) from exc
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return audio_upload_to_read(upload)


@router.get("/{project_id}/audio-uploads", response_model=list[AudioUploadRead])
async def list_audio_uploads_endpoint(
    project_id: UUID,
    session: SessionDependency,
    page: PageDependency,
) -> list[AudioUploadRead]:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    uploads = await list_audio_uploads(
        session,
        project_id,
        limit=page.limit,
        offset=page.offset,
    )
    return [audio_upload_to_read(upload) for upload in uploads]


@router.get("/{project_id}/audio-uploads/{audio_upload_id}", response_model=AudioUploadRead)
async def get_audio_upload_endpoint(
    project_id: UUID,
    audio_upload_id: UUID,
    session: SessionDependency,
) -> AudioUploadRead:
    upload = await get_audio_upload(session, project_id, audio_upload_id)
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AudioUpload not found")
    return audio_upload_to_read(upload)


@router.patch("/{project_id}/audio-uploads/{audio_upload_id}", response_model=AudioUploadRead)
async def update_audio_upload_endpoint(
    project_id: UUID,
    audio_upload_id: UUID,
    payload: AudioUploadUpdate,
    session: SessionDependency,
) -> AudioUploadRead:
    upload = await update_audio_upload(session, project_id, audio_upload_id, payload)
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AudioUpload not found")
    return audio_upload_to_read(upload)


@router.get("/{project_id}/audio-uploads/{audio_upload_id}/download")
async def download_audio_upload_endpoint(
    project_id: UUID,
    audio_upload_id: UUID,
    session: SessionDependency,
    storage: StorageDependency,
) -> StreamingResponse:
    upload = await get_audio_upload(session, project_id, audio_upload_id)
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AudioUpload not found")
    try:
        data = iter_storage_bytes(storage, upload.storage_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio file not found",
        ) from exc
    return StreamingResponse(
        data,
        media_type=upload.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{upload.filename}"',
            "Content-Length": str(upload.size_bytes),
        },
    )


@router.post(
    "/{project_id}/audio-uploads/{audio_upload_id}/extract-midi",
    response_model=GenerationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def extract_audio_midi_endpoint(
    project_id: UUID,
    audio_upload_id: UUID,
    payload: AudioExtractMidiRequest,
    session: SessionDependency,
    queue: QueueDependency,
) -> GenerationRunRead:
    result = await create_audio_to_midi_run(
        session=session,
        project_id=project_id,
        audio_upload_id=audio_upload_id,
        song_spec_id=payload.song_spec_id,
        target_kind=payload.target_kind,
        queue=queue,
    )
    if result.not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.not_found)
    if result.conflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.conflict)
    if result.run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GenerationRun not found")
    return await generation_run_to_read(session, result.run)


async def _read_limited_upload(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > audio_service.MAX_AUDIO_UPLOAD_BYTES:
            raise AudioUploadTooLargeError("Audio upload exceeds 25 MB")
        chunks.append(chunk)
    return b"".join(chunks)

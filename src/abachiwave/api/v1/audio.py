from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.api.errors import ErrorCode, ErrorHint, ProblemError
from abachiwave.api.pagination import PageDependency
from abachiwave.core.database import get_session
from abachiwave.models.audio import AudioDerivativeKind, AudioUploadKind
from abachiwave.schemas.audio import (
    AudioDerivativeCreateRequest,
    AudioDerivativeRead,
    AudioExtractMidiRequest,
    AudioUploadRead,
    AudioUploadUpdate,
    ReferenceAnalysisApplyRead,
    ReferenceAnalysisApplyRequest,
    ReferenceAnalysisCreateRequest,
    ReferenceAnalysisRead,
)
from abachiwave.schemas.demo import GenerationRunRead
from abachiwave.services import audio as audio_service
from abachiwave.services.audio import (
    AudioUploadLimitError,
    AudioUploadStateError,
    AudioUploadTooLargeError,
    UnsupportedAudioTypeError,
    audio_upload_requires_normalization,
    audio_upload_to_read,
    create_audio_to_midi_run,
    create_audio_upload,
    get_audio_upload,
    list_audio_uploads,
    mark_audio_upload_normalization_failed,
    update_audio_upload,
)
from abachiwave.services.audio_derivatives import (
    audio_derivative_to_read,
    create_audio_derivative_run,
    get_audio_derivative,
    list_audio_derivatives,
)
from abachiwave.services.demo import generation_run_to_read
from abachiwave.services.reference_analysis import (
    apply_reference_analysis,
    create_reference_analysis_run,
    get_reference_analysis,
    list_reference_analyses,
    reference_analysis_to_read,
)
from abachiwave.services.song_specs import project_exists
from abachiwave.services.storage import ObjectStorage, get_object_storage, iter_storage_bytes
from abachiwave.services.task_queue import (
    AudioDerivativeTaskQueue,
    AudioToMidiTaskQueue,
    ReferenceAnalysisTaskQueue,
    get_audio_derivative_task_queue,
    get_audio_to_midi_task_queue,
    get_reference_analysis_task_queue,
)

router = APIRouter()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
StorageDependency = Annotated[ObjectStorage, Depends(get_object_storage)]
QueueDependency = Annotated[AudioToMidiTaskQueue, Depends(get_audio_to_midi_task_queue)]
DerivativeQueueDependency = Annotated[
    AudioDerivativeTaskQueue,
    Depends(get_audio_derivative_task_queue),
]
ReferenceAnalysisQueueDependency = Annotated[
    ReferenceAnalysisTaskQueue,
    Depends(get_reference_analysis_task_queue),
]


@router.post(
    "/{project_id}/audio-uploads",
    response_model=AudioUploadRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_audio_upload_endpoint(
    project_id: UUID,
    session: SessionDependency,
    storage: StorageDependency,
    derivative_queue: DerivativeQueueDependency,
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
        if upload is not None and audio_upload_requires_normalization(upload):
            try:
                result = await create_audio_derivative_run(
                    session=session,
                    project_id=project_id,
                    audio_upload_id=UUID(upload.id),
                    kind=AudioDerivativeKind.pcm_wav,
                    queue=derivative_queue,
                )
                if result.run is None:
                    await mark_audio_upload_normalization_failed(
                        session,
                        project_id,
                        UUID(upload.id),
                    )
            except Exception:
                await mark_audio_upload_normalization_failed(
                    session,
                    project_id,
                    UUID(upload.id),
                )
            await session.refresh(upload)
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
    try:
        upload = await update_audio_upload(session, project_id, audio_upload_id, payload)
    except AudioUploadStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if upload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AudioUpload not found")
    return audio_upload_to_read(upload)


@router.post(
    "/{project_id}/audio-uploads/{audio_upload_id}/derivatives",
    response_model=GenerationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_audio_derivative_endpoint(
    project_id: UUID,
    audio_upload_id: UUID,
    payload: AudioDerivativeCreateRequest,
    session: SessionDependency,
    queue: DerivativeQueueDependency,
) -> GenerationRunRead:
    result = await create_audio_derivative_run(
        session=session,
        project_id=project_id,
        audio_upload_id=audio_upload_id,
        kind=payload.kind,
        queue=queue,
    )
    if result.not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.not_found)
    if result.conflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.conflict)
    if result.run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GenerationRun not found")
    return await generation_run_to_read(session, result.run)


@router.get(
    "/{project_id}/audio-uploads/{audio_upload_id}/derivatives",
    response_model=list[AudioDerivativeRead],
)
async def list_audio_derivatives_endpoint(
    project_id: UUID,
    audio_upload_id: UUID,
    session: SessionDependency,
    page: PageDependency,
) -> list[AudioDerivativeRead]:
    derivatives = await list_audio_derivatives(
        session,
        project_id,
        audio_upload_id,
        limit=page.limit,
        offset=page.offset,
    )
    if derivatives is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AudioUpload not found")
    return [audio_derivative_to_read(derivative) for derivative in derivatives]


@router.get(
    "/{project_id}/audio-uploads/{audio_upload_id}/derivatives/{derivative_id}/download"
)
async def download_audio_derivative_endpoint(
    project_id: UUID,
    audio_upload_id: UUID,
    derivative_id: UUID,
    session: SessionDependency,
    storage: StorageDependency,
) -> StreamingResponse:
    derivative = await get_audio_derivative(
        session,
        project_id,
        audio_upload_id,
        derivative_id,
    )
    if derivative is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AudioDerivative not found",
        )
    try:
        data = iter_storage_bytes(storage, derivative.storage_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audio derivative file not found",
        ) from exc
    return StreamingResponse(
        data,
        media_type=derivative.content_type,
        headers={
            "Content-Disposition": f'inline; filename="{derivative.filename}"',
            "Content-Length": str(derivative.size_bytes),
        },
    )


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
        analysis_range=payload.analysis_range,
        reference_analysis_id=payload.reference_analysis_id,
        queue=queue,
    )
    if result.not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.not_found)
    if result.conflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.conflict)
    if result.invalid_range:
        raise ProblemError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_code=ErrorCode.VALIDATION_FAILED,
            detail=result.invalid_range,
            fields={"analysis_range": result.invalid_range},
        )
    if result.run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GenerationRun not found")
    return await generation_run_to_read(session, result.run)


@router.post(
    "/{project_id}/audio-uploads/{audio_upload_id}/analyze",
    response_model=GenerationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def analyze_reference_audio_endpoint(
    project_id: UUID,
    audio_upload_id: UUID,
    payload: ReferenceAnalysisCreateRequest,
    session: SessionDependency,
    queue: ReferenceAnalysisQueueDependency,
) -> GenerationRunRead:
    result = await create_reference_analysis_run(
        session=session,
        project_id=project_id,
        audio_upload_id=audio_upload_id,
        analysis_range=payload.analysis_range,
        queue=queue,
    )
    if result.not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.not_found)
    if result.conflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.conflict)
    if result.invalid_range:
        raise ProblemError(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_code=ErrorCode.VALIDATION_FAILED,
            detail=result.invalid_range,
            fields={"analysis_range": result.invalid_range},
        )
    if result.run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="GenerationRun not found")
    return await generation_run_to_read(session, result.run)


@router.get(
    "/{project_id}/audio-uploads/{audio_upload_id}/analyses",
    response_model=list[ReferenceAnalysisRead],
)
async def list_reference_analyses_endpoint(
    project_id: UUID,
    audio_upload_id: UUID,
    session: SessionDependency,
    page: PageDependency,
) -> list[ReferenceAnalysisRead]:
    analyses = await list_reference_analyses(
        session,
        project_id,
        audio_upload_id,
        limit=page.limit,
        offset=page.offset,
    )
    if analyses is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AudioUpload not found")
    return [reference_analysis_to_read(analysis) for analysis in analyses]


@router.get(
    "/{project_id}/reference-analyses/{analysis_id}",
    response_model=ReferenceAnalysisRead,
)
async def get_reference_analysis_endpoint(
    project_id: UUID,
    analysis_id: UUID,
    session: SessionDependency,
) -> ReferenceAnalysisRead:
    analysis = await get_reference_analysis(session, project_id, analysis_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ReferenceAnalysisVersion not found",
        )
    return reference_analysis_to_read(analysis)


@router.post(
    "/{project_id}/reference-analyses/{analysis_id}/apply",
    response_model=ReferenceAnalysisApplyRead,
)
async def apply_reference_analysis_endpoint(
    project_id: UUID,
    analysis_id: UUID,
    payload: ReferenceAnalysisApplyRequest,
    session: SessionDependency,
) -> ReferenceAnalysisApplyRead:
    result = await apply_reference_analysis(
        session=session,
        project_id=project_id,
        analysis_id=analysis_id,
        request=payload,
    )
    if result.not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.not_found)
    if result.conflict:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.conflict)
    if result.response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ReferenceAnalysis apply result not found",
        )
    return result.response


async def _read_limited_upload(file: UploadFile) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > audio_service.MAX_AUDIO_UPLOAD_BYTES:
            raise AudioUploadTooLargeError("Audio upload exceeds 25 MB")
        chunks.append(chunk)
    return b"".join(chunks)

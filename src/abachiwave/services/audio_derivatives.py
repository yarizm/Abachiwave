import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Protocol
from uuid import UUID
from wave import Error as WaveError
from wave import open as wave_open

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.core.database import AsyncSessionLocal
from abachiwave.models.audio import (
    AudioDerivative,
    AudioDerivativeKind,
    AudioSourceFormat,
    AudioUpload,
    AudioUploadStatus,
)
from abachiwave.models.demo import GenerationRun, GenerationRunStatus, GenerationRunType
from abachiwave.models.project import Project
from abachiwave.schemas.audio import AudioDerivativeRead
from abachiwave.services.events import add_project_event
from abachiwave.services.generation_runs import lock_generation_run
from abachiwave.services.storage import ObjectStorage, get_object_storage
from abachiwave.services.task_queue import AudioDerivativeTaskQueue
from abachiwave.services.wav_analysis import WavAnalysisError, analyze_wav_bytes


class AudioDerivativeInputError(ValueError):
    pass


class AudioConverter(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    def default_params(self) -> dict[str, object]: ...

    def convert_to_pcm_wav(self, source: bytes) -> "PcmWavData": ...


@dataclass(frozen=True)
class PcmWavData:
    data: bytes
    sample_rate: int
    channels: int
    duration_seconds: float


@dataclass(frozen=True)
class AudioDerivativeCreateResult:
    run: GenerationRun | None
    not_found: str | None = None
    conflict: str | None = None


def audio_derivative_to_read(derivative: AudioDerivative) -> AudioDerivativeRead:
    return AudioDerivativeRead(
        id=UUID(derivative.id),
        project_id=UUID(derivative.project_id),
        audio_upload_id=UUID(derivative.audio_upload_id),
        kind=derivative.kind,
        filename=derivative.filename,
        content_type=derivative.content_type,
        format=derivative.format,
        sample_rate=derivative.sample_rate,
        channels=derivative.channels,
        duration_seconds=derivative.duration_seconds,
        size_bytes=derivative.size_bytes,
        checksum=derivative.checksum,
        source_checksum=derivative.source_checksum,
        created_at=derivative.created_at,
        updated_at=derivative.updated_at,
    )


async def list_audio_derivatives(
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[AudioDerivative] | None:
    if await _get_audio_upload(session, project_id, audio_upload_id) is None:
        return None
    statement: Select[tuple[AudioDerivative]] = (
        select(AudioDerivative)
        .where(
            AudioDerivative.project_id == str(project_id),
            AudioDerivative.audio_upload_id == str(audio_upload_id),
        )
        .order_by(AudioDerivative.created_at.desc(), AudioDerivative.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_audio_derivative(
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
    derivative_id: UUID | None = None,
    *,
    kind: AudioDerivativeKind | None = None,
) -> AudioDerivative | None:
    conditions = [
        AudioDerivative.project_id == str(project_id),
        AudioDerivative.audio_upload_id == str(audio_upload_id),
    ]
    if derivative_id is not None:
        conditions.append(AudioDerivative.id == str(derivative_id))
    if kind is not None:
        conditions.append(AudioDerivative.kind == kind)
    statement: Select[tuple[AudioDerivative]] = (
        select(AudioDerivative)
        .where(*conditions)
        .order_by(AudioDerivative.created_at.desc(), AudioDerivative.id.desc())
        .limit(1)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def create_audio_derivative_run(
    *,
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
    kind: AudioDerivativeKind,
    queue: AudioDerivativeTaskQueue,
    converter: AudioConverter | None = None,
) -> AudioDerivativeCreateResult:
    project = await session.get(Project, str(project_id))
    if project is None:
        return AudioDerivativeCreateResult(run=None, not_found="Project not found")
    upload = await _get_audio_upload(session, project_id, audio_upload_id)
    if upload is None:
        return AudioDerivativeCreateResult(run=None, not_found="AudioUpload not found")
    if kind is not AudioDerivativeKind.pcm_wav:
        return AudioDerivativeCreateResult(run=None, conflict="Unsupported audio derivative kind")

    existing_statement: Select[tuple[AudioDerivative]] = select(AudioDerivative).where(
        AudioDerivative.project_id == str(project_id),
        AudioDerivative.audio_upload_id == str(audio_upload_id),
        AudioDerivative.kind == kind,
        AudioDerivative.source_checksum == upload.checksum,
    )
    if (await session.execute(existing_statement)).scalar_one_or_none() is not None:
        return AudioDerivativeCreateResult(run=None, conflict="PCM WAV derivative already exists")

    active_statement: Select[tuple[GenerationRun]] = select(GenerationRun).where(
        GenerationRun.project_id == str(project_id),
        GenerationRun.run_type == GenerationRunType.audio_derivative,
        GenerationRun.status.in_(
            [GenerationRunStatus.queued, GenerationRunStatus.running]
        ),
    )
    active_runs = (await session.execute(active_statement)).scalars().all()
    if any(
        active.input_manifest.get("audio_upload_id") == upload.id
        and active.input_manifest.get("source_checksum") == upload.checksum
        for active in active_runs
    ):
        return AudioDerivativeCreateResult(
            run=None,
            conflict="PCM WAV derivative normalization is already active",
        )

    if converter is None:
        from abachiwave.services.audio_conversion import build_audio_converter

        selected_converter: AudioConverter = build_audio_converter()
    else:
        selected_converter = converter
    run = GenerationRun(
        project_id=str(project_id),
        run_type=GenerationRunType.audio_derivative,
        input_manifest={
            "audio_upload_id": upload.id,
            "derivative_kind": kind.value,
            "source_checksum": upload.checksum,
        },
        provider_name=selected_converter.name,
        provider_version=selected_converter.version,
        provider_params=selected_converter.default_params(),
    )
    session.add(run)
    if upload.format != AudioSourceFormat.wav:
        upload.status = AudioUploadStatus.processing
    await session.flush()
    add_project_event(
        session,
        project_id=project_id,
        event_type="audio.normalization.queued",
        payload={
            "audio_upload_id": upload.id,
            "run_id": run.id,
            "source_format": str(upload.format),
        },
        generation_run_id=UUID(run.id),
    )
    await session.commit()
    await session.refresh(run)
    try:
        run.arq_job_id = await queue.enqueue_audio_derivative(UUID(run.id))
    except Exception as exc:
        run.status = GenerationRunStatus.failed
        run.error_code = "queue_enqueue_failed"
        run.error_message = str(exc)
        run.completed_at = datetime.now(UTC)
        if upload.format != AudioSourceFormat.wav:
            upload.status = AudioUploadStatus.failed
        await session.commit()
        await session.refresh(run)
        raise
    await session.commit()
    await session.refresh(run)
    return AudioDerivativeCreateResult(run=run)


async def execute_audio_derivative(
    run_id: UUID,
    *,
    storage: ObjectStorage | None = None,
    converter: AudioConverter | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> GenerationRun | None:
    selected_storage = storage or get_object_storage()
    if converter is None:
        from abachiwave.services.audio_conversion import build_audio_converter

        selected_converter: AudioConverter = build_audio_converter()
    else:
        selected_converter = converter
    selected_session_factory = session_factory or AsyncSessionLocal
    async with selected_session_factory() as session:
        run = await session.get(GenerationRun, str(run_id))
        if run is None:
            return None
        if run.status == GenerationRunStatus.cancelled:
            return run
        try:
            if run.run_type != GenerationRunType.audio_derivative:
                raise ValueError("GenerationRun is not an audio derivative run")
            run.status = GenerationRunStatus.running
            run.started_at = datetime.now(UTC)
            run.error_code = None
            run.error_message = None
            await session.commit()
            await session.refresh(run)

            project_id = UUID(run.project_id)
            audio_upload_id = _manifest_uuid(run.input_manifest, "audio_upload_id")
            upload = await _get_audio_upload(session, project_id, audio_upload_id)
            if upload is None:
                raise ValueError("AudioUpload not found")
            source = await asyncio.to_thread(selected_storage.get_bytes, upload.storage_key)
            pcm_wav = await asyncio.to_thread(selected_converter.convert_to_pcm_wav, source)

            locked_run = await lock_generation_run(session, run_id)
            if locked_run is None:
                return None
            run = locked_run
            if run.status == GenerationRunStatus.cancelled:
                await session.commit()
                await session.refresh(run)
                return run
            await session.commit()

            derivative = await create_pcm_wav_derivative(
                session,
                selected_storage,
                project_id,
                audio_upload_id,
                pcm_wav=pcm_wav,
                generation_run_id=run_id,
            )
            if derivative is None:
                raise ValueError("AudioUpload not found")

            locked_run = await lock_generation_run(session, run_id)
            if locked_run is None:
                return None
            run = locked_run
            if run.status == GenerationRunStatus.cancelled:
                await session.commit()
                await session.refresh(run)
                return run
            run.status = GenerationRunStatus.succeeded
            run.provider_usage = {
                "source_bytes": upload.size_bytes,
                "derived_bytes": derivative.size_bytes,
                "audio_derivative_id": derivative.id,
            }
            run.completed_at = datetime.now(UTC)
            run.error_code = None
            run.error_message = None
            add_project_event(
                session,
                project_id=project_id,
                event_type="audio.derivative.ready",
                payload={
                    "audio_upload_id": upload.id,
                    "audio_derivative_id": derivative.id,
                    "run_id": run.id,
                },
                generation_run_id=run_id,
            )
            await session.commit()
            await session.refresh(run)
            return run
        except Exception as exc:
            await session.rollback()
            failed_run = await session.get(GenerationRun, str(run_id))
            if failed_run is None:
                return None
            if failed_run.status == GenerationRunStatus.cancelled:
                return failed_run
            failed_run.status = GenerationRunStatus.failed
            failed_run.error_code = "audio_derivative_failed"
            failed_run.error_message = str(exc)
            failed_run.completed_at = datetime.now(UTC)
            try:
                failed_project_id = UUID(failed_run.project_id)
                failed_upload_id = _manifest_uuid(
                    failed_run.input_manifest,
                    "audio_upload_id",
                )
                failed_upload = await _get_audio_upload(
                    session,
                    failed_project_id,
                    failed_upload_id,
                )
                if (
                    failed_upload is not None
                    and failed_upload.format != AudioSourceFormat.wav
                    and failed_upload.status == AudioUploadStatus.processing
                ):
                    failed_upload.status = AudioUploadStatus.failed
                    add_project_event(
                        session,
                        project_id=failed_project_id,
                        event_type="audio.normalization.failed",
                        payload={
                            "audio_upload_id": failed_upload.id,
                            "run_id": failed_run.id,
                        },
                        generation_run_id=run_id,
                    )
            except (TypeError, ValueError):
                pass
            await session.commit()
            await session.refresh(failed_run)
            return failed_run


async def create_pcm_wav_derivative(
    session: AsyncSession,
    storage: ObjectStorage,
    project_id: UUID,
    audio_upload_id: UUID,
    *,
    pcm_wav: PcmWavData,
    generation_run_id: UUID | None = None,
) -> AudioDerivative | None:
    upload = await _get_audio_upload(session, project_id, audio_upload_id)
    if upload is None:
        return None
    if not pcm_wav.data:
        raise AudioDerivativeInputError("PCM WAV derivative must not be empty")
    if pcm_wav.sample_rate <= 0 or pcm_wav.channels <= 0 or pcm_wav.duration_seconds < 0:
        raise AudioDerivativeInputError("PCM WAV metadata is invalid")
    try:
        waveform_metadata = analyze_wav_bytes(pcm_wav.data)
    except WavAnalysisError as exc:
        raise AudioDerivativeInputError("PCM WAV derivative is invalid") from exc

    if upload.format != AudioSourceFormat.wav:
        upload.duration_seconds = waveform_metadata.duration_seconds
        upload.sample_rate = waveform_metadata.sample_rate
        upload.channels = waveform_metadata.channels
        upload.waveform_peaks = waveform_metadata.waveform_peaks
        upload.status = AudioUploadStatus.available

    source_checksum = upload.checksum
    existing_statement: Select[tuple[AudioDerivative]] = select(AudioDerivative).where(
        AudioDerivative.project_id == str(project_id),
        AudioDerivative.audio_upload_id == str(audio_upload_id),
        AudioDerivative.kind == AudioDerivativeKind.pcm_wav,
        AudioDerivative.source_checksum == source_checksum,
    )
    existing = (await session.execute(existing_statement)).scalar_one_or_none()
    if existing is not None:
        return existing

    checksum = sha256(pcm_wav.data).hexdigest()
    safe_stem = Path(upload.filename).stem or "audio"
    filename = f"{safe_stem}.pcm.wav"
    storage_key = (
        f"projects/{project_id}/audio-derivatives/{audio_upload_id}/"
        f"{AudioDerivativeKind.pcm_wav.value}/{checksum}.wav"
    )
    storage.put_bytes(storage_key, pcm_wav.data, "audio/wav")
    derivative = AudioDerivative(
        project_id=str(project_id),
        audio_upload_id=str(audio_upload_id),
        kind=AudioDerivativeKind.pcm_wav,
        storage_key=storage_key,
        filename=filename,
        content_type="audio/wav",
        format="wav",
        sample_rate=pcm_wav.sample_rate,
        channels=pcm_wav.channels,
        duration_seconds=pcm_wav.duration_seconds,
        size_bytes=len(pcm_wav.data),
        checksum=checksum,
        source_checksum=source_checksum,
    )
    try:
        session.add(derivative)
        await session.flush()
        add_project_event(
            session,
            project_id=project_id,
            event_type="audio.derivative.created",
            payload={
                "audio_upload_id": str(audio_upload_id),
                "audio_derivative_id": derivative.id,
                "kind": AudioDerivativeKind.pcm_wav.value,
                "source_checksum": source_checksum,
                "checksum": checksum,
            },
            generation_run_id=generation_run_id,
        )
        await session.commit()
    except Exception:
        await session.rollback()
        storage.delete_bytes(storage_key)
        raise
    await session.refresh(derivative)
    return derivative


def inspect_pcm_wav(data: bytes) -> PcmWavData:
    try:
        with wave_open(BytesIO(data), "rb") as reader:
            channels = reader.getnchannels()
            sample_rate = reader.getframerate()
            sample_width = reader.getsampwidth()
            frame_count = reader.getnframes()
    except (EOFError, WaveError) as exc:
        raise AudioDerivativeInputError("Invalid WAV source") from exc
    if sample_width != 2:
        raise AudioDerivativeInputError("Only 16-bit PCM WAV derivatives are supported")
    if channels <= 0 or sample_rate <= 0:
        raise AudioDerivativeInputError("WAV metadata is invalid")
    duration_seconds = frame_count / sample_rate
    return PcmWavData(
        data=data,
        sample_rate=sample_rate,
        channels=channels,
        duration_seconds=duration_seconds,
    )


async def _get_audio_upload(
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
) -> AudioUpload | None:
    statement: Select[tuple[AudioUpload]] = select(AudioUpload).where(
        AudioUpload.id == str(audio_upload_id),
        AudioUpload.project_id == str(project_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


def _manifest_uuid(manifest: dict[str, object], key: str) -> UUID:
    value = manifest.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Generation run manifest is missing {key}")
    return UUID(value)

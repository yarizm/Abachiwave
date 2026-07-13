import asyncio
import re
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.core.config import get_settings
from abachiwave.core.database import AsyncSessionLocal
from abachiwave.models.audio import AudioUpload, AudioUploadKind, AudioUploadStatus
from abachiwave.models.composition import MidiAssetKind
from abachiwave.models.demo import GenerationRun, GenerationRunStatus, GenerationRunType
from abachiwave.models.project import Project
from abachiwave.models.song_spec import SongSpecStatus
from abachiwave.schemas.audio import AudioUploadRead, AudioUploadUpdate
from abachiwave.services.audio_to_midi_provider import (
    AudioToMidiRequest,
    LocalMonophonicWavToMidiProvider,
)
from abachiwave.services.composition import create_midi_asset_version_from_bytes
from abachiwave.services.events import add_project_event
from abachiwave.services.generation_runs import lock_generation_run
from abachiwave.services.song_specs import get_song_spec_version, song_spec_to_data
from abachiwave.services.storage import ObjectStorage, get_object_storage
from abachiwave.services.task_queue import AudioToMidiTaskQueue
from abachiwave.services.wav_analysis import WavAnalysisError, analyze_wav_bytes

SUPPORTED_WAV_CONTENT_TYPES = {"audio/wav", "audio/x-wav", "audio/wave"}
MAX_AUDIO_UPLOAD_BYTES = 25 * 1024 * 1024


class UnsupportedAudioTypeError(ValueError):
    pass


class AudioUploadTooLargeError(ValueError):
    pass


class AudioUploadLimitError(ValueError):
    pass


@dataclass(frozen=True)
class AudioToMidiCreateResult:
    run: GenerationRun | None
    not_found: str | None = None
    conflict: str | None = None


async def create_audio_upload(
    *,
    session: AsyncSession,
    project_id: UUID,
    filename: str,
    content_type: str,
    data: bytes,
    kind: AudioUploadKind,
    notes: str | None,
    storage: ObjectStorage,
    max_project_uploads: int | None = None,
) -> AudioUpload | None:
    project_result = await session.execute(
        select(Project).where(Project.id == str(project_id)).with_for_update()
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        return None
    upload_limit = (
        get_settings().max_project_uploads
        if max_project_uploads is None
        else max_project_uploads
    )
    upload_count = await session.scalar(
        select(func.count())
        .select_from(AudioUpload)
        .where(AudioUpload.project_id == str(project_id))
    )
    if (upload_count or 0) >= upload_limit:
        raise AudioUploadLimitError(
            f"Project audio upload limit reached ({upload_limit})"
        )
    _validate_upload(content_type, data)
    try:
        metadata = analyze_wav_bytes(data)
    except WavAnalysisError as exc:
        raise UnsupportedAudioTypeError(str(exc)) from exc
    upload_id = str(uuid4())
    safe_name = _safe_filename(filename)
    storage_key = f"projects/{project_id}/audio-uploads/{upload_id}/{safe_name}"
    await asyncio.to_thread(storage.put_bytes, storage_key, data, content_type)
    upload = AudioUpload(
        id=upload_id,
        project_id=str(project_id),
        kind=kind,
        status=AudioUploadStatus.available,
        storage_key=storage_key,
        filename=safe_name,
        content_type=content_type,
        size_bytes=len(data),
        checksum=sha256(data).hexdigest(),
        duration_seconds=metadata.duration_seconds,
        sample_rate=metadata.sample_rate,
        channels=metadata.channels,
        waveform_peaks=metadata.waveform_peaks,
        notes=_normalize_notes(notes),
    )
    try:
        session.add(upload)
        add_project_event(
            session,
            project_id=project_id,
            event_type="audio.uploaded",
            payload={"audio_upload_id": upload.id, "kind": str(kind)},
            artifact_version_id=UUID(upload.id),
        )
        await session.commit()
        await session.refresh(upload)
        return upload
    except Exception:
        await session.rollback()
        with suppress(Exception):
            await asyncio.to_thread(storage.delete_bytes, storage_key)
        raise


async def list_audio_uploads(
    session: AsyncSession,
    project_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[AudioUpload]:
    statement: Select[tuple[AudioUpload]] = (
        select(AudioUpload)
        .where(AudioUpload.project_id == str(project_id))
        .order_by(AudioUpload.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_audio_upload(
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


async def update_audio_upload(
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
    payload: AudioUploadUpdate,
) -> AudioUpload | None:
    upload = await get_audio_upload(session, project_id, audio_upload_id)
    if upload is None:
        return None
    previous_status = upload.status
    update_fields = payload.model_fields_set
    if "kind" in update_fields and payload.kind is not None:
        upload.kind = payload.kind
    if "status" in update_fields and payload.status is not None:
        upload.status = payload.status
    if "notes" in update_fields:
        upload.notes = payload.notes
    if update_fields:
        event_type = "audio.updated"
        if "status" in update_fields and upload.status != previous_status:
            event_type = (
                "audio.archived"
                if upload.status == AudioUploadStatus.archived
                else "audio.restored"
            )
        add_project_event(
            session,
            project_id=project_id,
            event_type=event_type,
            payload={
                "audio_upload_id": upload.id,
                "status": str(upload.status),
                "updated_fields": sorted(update_fields),
            },
            artifact_version_id=UUID(upload.id),
        )
    await session.commit()
    await session.refresh(upload)
    return upload


async def create_audio_to_midi_run(
    *,
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
    song_spec_id: UUID,
    target_kind: MidiAssetKind,
    queue: AudioToMidiTaskQueue,
    provider: LocalMonophonicWavToMidiProvider | None = None,
) -> AudioToMidiCreateResult:
    project = await session.get(Project, str(project_id))
    if project is None:
        return AudioToMidiCreateResult(run=None, not_found="Project not found")
    upload = await get_audio_upload(session, project_id, audio_upload_id)
    if upload is None:
        return AudioToMidiCreateResult(run=None, not_found="AudioUpload not found")
    song_spec = await get_song_spec_version(session, project_id, song_spec_id)
    if song_spec is None:
        return AudioToMidiCreateResult(run=None, not_found="SongSpec not found")
    if song_spec.status != SongSpecStatus.approved:
        return AudioToMidiCreateResult(run=None, conflict="SongSpec must be approved")
    if target_kind is not MidiAssetKind.melody:
        return AudioToMidiCreateResult(run=None, conflict="Only melody extraction is supported")

    selected_provider = provider or LocalMonophonicWavToMidiProvider()
    run = GenerationRun(
        project_id=str(project_id),
        run_type=GenerationRunType.audio_to_midi,
        input_manifest={
            "audio_upload_id": upload.id,
            "song_spec_id": song_spec.id,
            "target_kind": target_kind.value,
        },
        provider_name=selected_provider.name,
        provider_version=selected_provider.version,
        provider_params=selected_provider.default_params(),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    try:
        run.arq_job_id = await queue.enqueue_audio_to_midi(UUID(run.id))
    except Exception as exc:
        run.status = GenerationRunStatus.failed
        run.error_message = str(exc)
        run.completed_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(run)
        raise

    await session.commit()
    await session.refresh(run)
    return AudioToMidiCreateResult(run=run)


async def execute_audio_to_midi(
    run_id: UUID,
    *,
    storage: ObjectStorage | None = None,
    provider: LocalMonophonicWavToMidiProvider | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> GenerationRun | None:
    selected_storage = storage or get_object_storage()
    selected_provider = provider or LocalMonophonicWavToMidiProvider()
    selected_session_factory = session_factory or AsyncSessionLocal
    stored_key: str | None = None
    async with selected_session_factory() as session:
        run = await session.get(GenerationRun, str(run_id))
        if run is None:
            return None
        if run.status == GenerationRunStatus.cancelled:
            return run
        try:
            if run.run_type != GenerationRunType.audio_to_midi:
                raise ValueError("GenerationRun is not an audio-to-MIDI run")
            run.status = GenerationRunStatus.running
            run.started_at = datetime.now(UTC)
            run.error_message = None
            await session.commit()
            await session.refresh(run)

            project_id = UUID(run.project_id)
            audio_upload_id = _manifest_uuid(run.input_manifest, "audio_upload_id")
            song_spec_id = _manifest_uuid(run.input_manifest, "song_spec_id")
            upload = await get_audio_upload(session, project_id, audio_upload_id)
            if upload is None:
                raise ValueError("AudioUpload not found")
            song_spec = await get_song_spec_version(session, project_id, song_spec_id)
            if song_spec is None:
                raise ValueError("SongSpec not found")
            await session.refresh(run)
            if run.status == GenerationRunStatus.cancelled:
                return run
            await session.commit()
            audio_bytes = await asyncio.to_thread(selected_storage.get_bytes, upload.storage_key)
            midi = await asyncio.to_thread(
                selected_provider.extract_midi,
                AudioToMidiRequest(
                    audio_bytes=audio_bytes,
                    filename=upload.filename,
                    song_spec=song_spec_to_data(song_spec),
                    provider_params=run.provider_params,
                )
            )
            locked_run = await lock_generation_run(session, run_id)
            if locked_run is None:
                return None
            run = locked_run
            if run.status == GenerationRunStatus.cancelled:
                await session.commit()
                await session.refresh(run)
                return run
            midi_asset = await create_midi_asset_version_from_bytes(
                session=session,
                project_id=project_id,
                song_spec_id=UUID(song_spec.id),
                lyrics_version_id=None,
                chord_version_id=None,
                kind=MidiAssetKind.melody,
                midi_bytes=midi.data,
                filename=midi.filename,
                storage=selected_storage,
                source_audio_upload_id=audio_upload_id,
                commit=False,
            )
            stored_key = midi_asset.storage_key
            run.result_midi_asset_id = midi_asset.id
            run.status = GenerationRunStatus.succeeded
            run.completed_at = datetime.now(UTC)
            run.error_message = None
            add_project_event(
                session,
                project_id=project_id,
                event_type="audio.midi_extracted",
                payload={
                    "audio_upload_id": upload.id,
                    "midi_asset_id": midi_asset.id,
                    "run_id": run.id,
                },
                generation_run_id=UUID(run.id),
                artifact_version_id=UUID(midi_asset.id),
            )
            await session.commit()
            await session.refresh(run)
            return run
        except Exception as exc:
            await session.rollback()
            if stored_key is not None:
                with suppress(Exception):
                    await asyncio.to_thread(selected_storage.delete_bytes, stored_key)
            failed_run = await session.get(GenerationRun, str(run_id))
            if failed_run is None:
                return None
            if failed_run.status == GenerationRunStatus.cancelled:
                return failed_run
            failed_run.status = GenerationRunStatus.failed
            failed_run.error_message = str(exc)
            failed_run.completed_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(failed_run)
            return failed_run


def audio_upload_to_read(upload: AudioUpload) -> AudioUploadRead:
    return AudioUploadRead(
        id=UUID(upload.id),
        project_id=UUID(upload.project_id),
        kind=upload.kind,
        status=upload.status,
        filename=upload.filename,
        content_type=upload.content_type,
        size_bytes=upload.size_bytes,
        checksum=upload.checksum,
        duration_seconds=upload.duration_seconds,
        sample_rate=upload.sample_rate,
        channels=upload.channels,
        waveform_peaks=upload.waveform_peaks,
        notes=upload.notes,
        created_at=upload.created_at,
        updated_at=upload.updated_at,
    )


def _validate_upload(content_type: str, data: bytes) -> None:
    if content_type not in SUPPORTED_WAV_CONTENT_TYPES:
        raise UnsupportedAudioTypeError("Only WAV uploads are supported")
    if len(data) > MAX_AUDIO_UPLOAD_BYTES:
        raise AudioUploadTooLargeError("Audio upload exceeds 25 MB")


def _safe_filename(filename: str) -> str:
    name = Path(filename or "audio.wav").name
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip(".-")
    return stem or "audio.wav"


def _normalize_notes(notes: str | None) -> str | None:
    if notes is None:
        return None
    normalized = notes.strip()
    return normalized or None


def _manifest_uuid(manifest: dict[str, object], key: str) -> UUID:
    value = manifest.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Generation run manifest is missing {key}")
    return UUID(value)

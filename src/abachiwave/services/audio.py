import asyncio
import re
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal, TypedDict, cast
from uuid import UUID, uuid4

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.core.config import get_settings
from abachiwave.core.database import AsyncSessionLocal
from abachiwave.models.audio import (
    AudioDerivative,
    AudioDerivativeKind,
    AudioSourceFormat,
    AudioUpload,
    AudioUploadKind,
    AudioUploadStatus,
    ReferenceAnalysisVersion,
)
from abachiwave.models.composition import MidiAssetKind
from abachiwave.models.demo import GenerationRun, GenerationRunStatus, GenerationRunType
from abachiwave.models.project import Project
from abachiwave.models.song_spec import SongSpecStatus
from abachiwave.schemas.audio import (
    AudioAnalysisRange,
    AudioUploadRead,
    AudioUploadUpdate,
)
from abachiwave.services.audio_to_midi_provider import (
    AudioToMidiProvider,
    AudioToMidiProviderError,
    AudioToMidiRequest,
    build_audio_to_midi_provider,
    resolve_audio_to_midi_provider_name,
)
from abachiwave.services.composition import create_midi_asset_version_from_bytes
from abachiwave.services.events import add_project_event
from abachiwave.services.generation_runs import lock_generation_run
from abachiwave.services.song_specs import get_song_spec_version, song_spec_to_data
from abachiwave.services.storage import ObjectStorage, get_object_storage
from abachiwave.services.task_queue import AudioToMidiTaskQueue
from abachiwave.services.wav_analysis import (
    WavAnalysisError,
    analyze_wav_bytes,
    slice_wav_bytes,
)

MAX_AUDIO_UPLOAD_BYTES = 25 * 1024 * 1024
GENERIC_UPLOAD_CONTENT_TYPES = {"", "application/octet-stream"}


@dataclass(frozen=True)
class AudioFormatSpec:
    format: AudioSourceFormat
    extensions: frozenset[str]
    content_types: frozenset[str]
    canonical_content_type: str


AUDIO_FORMAT_SPECS = {
    AudioSourceFormat.wav: AudioFormatSpec(
        format=AudioSourceFormat.wav,
        extensions=frozenset({".wav"}),
        content_types=frozenset({"audio/wav", "audio/x-wav", "audio/wave"}),
        canonical_content_type="audio/wav",
    ),
    AudioSourceFormat.mp3: AudioFormatSpec(
        format=AudioSourceFormat.mp3,
        extensions=frozenset({".mp3"}),
        content_types=frozenset({"audio/mpeg", "audio/mp3"}),
        canonical_content_type="audio/mpeg",
    ),
    AudioSourceFormat.m4a: AudioFormatSpec(
        format=AudioSourceFormat.m4a,
        extensions=frozenset({".m4a"}),
        content_types=frozenset({"audio/mp4", "audio/x-m4a"}),
        canonical_content_type="audio/mp4",
    ),
    AudioSourceFormat.flac: AudioFormatSpec(
        format=AudioSourceFormat.flac,
        extensions=frozenset({".flac"}),
        content_types=frozenset({"audio/flac", "audio/x-flac"}),
        canonical_content_type="audio/flac",
    ),
    AudioSourceFormat.ogg: AudioFormatSpec(
        format=AudioSourceFormat.ogg,
        extensions=frozenset({".ogg", ".oga"}),
        content_types=frozenset({"audio/ogg", "application/ogg"}),
        canonical_content_type="audio/ogg",
    ),
}


class UnsupportedAudioTypeError(ValueError):
    pass


class AudioUploadTooLargeError(ValueError):
    pass


class AudioUploadLimitError(ValueError):
    pass


class AudioUploadStateError(ValueError):
    pass


@dataclass(frozen=True)
class AudioToMidiCreateResult:
    run: GenerationRun | None
    not_found: str | None = None
    conflict: str | None = None
    invalid_range: str | None = None


class AudioAnalysisRangeManifest(TypedDict):
    mode: Literal["full", "selection"]
    start_seconds: float
    end_seconds: float


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
        get_settings().max_project_uploads if max_project_uploads is None else max_project_uploads
    )
    upload_count = await session.scalar(
        select(func.count())
        .select_from(AudioUpload)
        .where(AudioUpload.project_id == str(project_id))
    )
    if (upload_count or 0) >= upload_limit:
        raise AudioUploadLimitError(f"Project audio upload limit reached ({upload_limit})")
    format_spec = _validate_upload(filename, content_type, data)
    metadata = None
    if format_spec.format is AudioSourceFormat.wav:
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
        status=(
            AudioUploadStatus.available
            if metadata is not None
            else AudioUploadStatus.processing
        ),
        storage_key=storage_key,
        filename=safe_name,
        content_type=format_spec.canonical_content_type,
        format=format_spec.format,
        size_bytes=len(data),
        checksum=sha256(data).hexdigest(),
        duration_seconds=metadata.duration_seconds if metadata is not None else None,
        sample_rate=metadata.sample_rate if metadata is not None else None,
        channels=metadata.channels if metadata is not None else None,
        waveform_peaks=metadata.waveform_peaks if metadata is not None else None,
        notes=_normalize_notes(notes),
    )
    try:
        session.add(upload)
        add_project_event(
            session,
            project_id=project_id,
            event_type="audio.uploaded",
            payload={
                "audio_upload_id": upload.id,
                "kind": str(kind),
                "format": format_spec.format.value,
                "status": str(upload.status),
            },
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
    if (
        "status" in update_fields
        and payload.status is not None
        and upload.status not in {AudioUploadStatus.available, AudioUploadStatus.archived}
    ):
        raise AudioUploadStateError(
            "Audio upload cannot be archived or restored while normalization is incomplete"
        )
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
    analysis_range: AudioAnalysisRange | None = None,
    reference_analysis_id: UUID | None = None,
    provider: AudioToMidiProvider | None = None,
) -> AudioToMidiCreateResult:
    project = await session.get(Project, str(project_id))
    if project is None:
        return AudioToMidiCreateResult(run=None, not_found="Project not found")
    upload = await get_audio_upload(session, project_id, audio_upload_id)
    if upload is None:
        return AudioToMidiCreateResult(run=None, not_found="AudioUpload not found")
    if upload.status != AudioUploadStatus.available:
        return AudioToMidiCreateResult(run=None, conflict="Audio upload must be available")
    song_spec = await get_song_spec_version(session, project_id, song_spec_id)
    if song_spec is None:
        return AudioToMidiCreateResult(run=None, not_found="SongSpec not found")
    if song_spec.status != SongSpecStatus.approved:
        return AudioToMidiCreateResult(run=None, conflict="SongSpec must be approved")
    if target_kind is not MidiAssetKind.melody:
        return AudioToMidiCreateResult(run=None, conflict="Only melody extraction is supported")
    resolved_range, range_error = resolve_audio_analysis_range(
        upload.duration_seconds,
        analysis_range,
    )
    if range_error is not None:
        return AudioToMidiCreateResult(run=None, invalid_range=range_error)
    if resolved_range is None:
        return AudioToMidiCreateResult(run=None, invalid_range="Audio duration is unavailable")

    derivative: AudioDerivative | None = None
    if upload.format != AudioSourceFormat.wav:
        derivative = await _ready_pcm_derivative(session, project_id, audio_upload_id)
        if derivative is None:
            return AudioToMidiCreateResult(run=None, conflict="PCM WAV derivative is not ready")
    reference_analysis: ReferenceAnalysisVersion | None = None
    if reference_analysis_id is not None:
        reference_analysis = await _reference_analysis_for_project(
            session,
            project_id,
            reference_analysis_id,
        )
        if reference_analysis is None:
            return AudioToMidiCreateResult(run=None, not_found="ReferenceAnalysis not found")
        analysis_conflict = _validate_reference_analysis_source(
            reference_analysis,
            upload=upload,
            derivative=derivative,
            analysis_range=resolved_range,
        )
        if analysis_conflict is not None:
            return AudioToMidiCreateResult(run=None, conflict=analysis_conflict)

    # Routed by upload kind: only hummed vocal input has held-out evidence for an
    # alternative provider, and that pipeline is unusable on polyphonic material.
    selected_provider = provider or build_audio_to_midi_provider(
        provider_name=resolve_audio_to_midi_provider_name(str(upload.kind))
    )
    run = GenerationRun(
        project_id=str(project_id),
        run_type=GenerationRunType.audio_to_midi,
        input_manifest={
            "audio_upload_id": upload.id,
            # The upload kind is what any provider routing keys off, so it belongs in the
            # run record: without it a finished run cannot explain why it used the
            # provider it used. str() rather than .value because the column is a plain
            # String, so a loaded row carries the raw value, not the StrEnum member.
            "audio_upload_kind": str(upload.kind),
            "song_spec_id": song_spec.id,
            "target_kind": target_kind.value,
            "audio_derivative_id": derivative.id if derivative is not None else None,
            "reference_analysis_id": (
                reference_analysis.id if reference_analysis is not None else None
            ),
            "source_checksum": upload.checksum,
            "analyzed_checksum": derivative.checksum if derivative is not None else upload.checksum,
            "analysis_range": resolved_range,
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
        run.error_code = "queue_enqueue_failed"
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
    provider: AudioToMidiProvider | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> GenerationRun | None:
    selected_storage = storage or get_object_storage()
    selected_session_factory = session_factory or AsyncSessionLocal
    stored_key: str | None = None
    async with selected_session_factory() as session:
        run = await session.get(GenerationRun, str(run_id))
        if run is None:
            return None
        if run.status not in {GenerationRunStatus.queued, GenerationRunStatus.running}:
            return run
        try:
            if run.run_type != GenerationRunType.audio_to_midi:
                raise ValueError("GenerationRun is not an audio-to-MIDI run")
            selected_provider = provider or build_audio_to_midi_provider(
                provider_name=run.provider_name
            )
            if (
                selected_provider.name != run.provider_name
                or selected_provider.version != run.provider_version
            ):
                raise ValueError("Audio-to-MIDI provider does not match the recorded run")
            run.status = GenerationRunStatus.running
            run.started_at = datetime.now(UTC)
            run.error_code = None
            run.error_message = None
            await session.commit()
            await session.refresh(run)

            project_id = UUID(run.project_id)
            audio_upload_id = _manifest_uuid(run.input_manifest, "audio_upload_id")
            song_spec_id = _manifest_uuid(run.input_manifest, "song_spec_id")
            upload = await get_audio_upload(session, project_id, audio_upload_id)
            if upload is None:
                raise ValueError("AudioUpload not found")
            source_checksum = (
                _manifest_optional_string(run.input_manifest, "source_checksum")
                or upload.checksum
            )
            if upload.checksum != source_checksum:
                raise ValueError("Audio-to-MIDI source checksum changed")
            song_spec = await get_song_spec_version(session, project_id, song_spec_id)
            if song_spec is None:
                raise ValueError("SongSpec not found")
            await session.refresh(run)
            if run.status == GenerationRunStatus.cancelled:
                return run
            await session.commit()
            derivative = await _manifest_pcm_derivative(
                session,
                project_id,
                audio_upload_id,
                run.input_manifest,
            )
            analyzed_checksum = (
                derivative.checksum if derivative is not None else upload.checksum
            )
            reference_analysis = await _manifest_reference_analysis(
                session,
                project_id,
                upload,
                derivative,
                run.input_manifest,
            )
            audio_storage_key = (
                derivative.storage_key if derivative is not None else upload.storage_key
            )
            audio_filename = derivative.filename if derivative is not None else upload.filename
            audio_bytes = await asyncio.to_thread(
                selected_storage.get_bytes,
                audio_storage_key,
            )
            analysis_range_manifest = manifest_audio_analysis_range(
                run.input_manifest,
                fallback_duration_seconds=upload.duration_seconds,
            )
            source_audio_bytes = len(audio_bytes)
            if analysis_range_manifest["mode"] == "selection":
                audio_bytes = await asyncio.to_thread(
                    slice_wav_bytes,
                    audio_bytes,
                    start_seconds=float(analysis_range_manifest["start_seconds"]),
                    end_seconds=float(analysis_range_manifest["end_seconds"]),
                )
            midi = await asyncio.to_thread(
                selected_provider.extract_midi,
                AudioToMidiRequest(
                    audio_bytes=audio_bytes,
                    filename=audio_filename,
                    song_spec=song_spec_to_data(song_spec),
                    provider_params=run.provider_params,
                ),
            )
            if (
                midi.provider_name != run.provider_name
                or midi.provider_version != run.provider_version
            ):
                raise ValueError("Audio-to-MIDI result provider does not match the recorded run")
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
                source_reference_analysis_id=(
                    UUID(reference_analysis.id) if reference_analysis is not None else None
                ),
                source_provider_manifest={
                    "generation_run_id": run.id,
                    "provider_name": run.provider_name,
                    "provider_version": run.provider_version,
                    "provider_params": run.provider_params,
                    "audio_upload_id": upload.id,
                    "audio_derivative_id": derivative.id if derivative is not None else None,
                    "reference_analysis_id": (
                        reference_analysis.id if reference_analysis is not None else None
                    ),
                    "source_checksum": source_checksum,
                    "analyzed_checksum": analyzed_checksum,
                    "analysis_range": analysis_range_manifest,
                },
                commit=False,
            )
            stored_key = midi_asset.storage_key
            run.result_midi_asset_id = midi_asset.id
            run.status = GenerationRunStatus.succeeded
            run.provider_usage = {
                **midi.provider_usage,
                "source_audio_bytes": source_audio_bytes,
                "analyzed_audio_bytes": len(audio_bytes),
                "analysis_range": analysis_range_manifest,
                "audio_derivative_id": derivative.id if derivative is not None else None,
                "reference_analysis_id": (
                    reference_analysis.id if reference_analysis is not None else None
                ),
                "note_count": len(midi_asset.note_events),
            }
            run.completed_at = datetime.now(UTC)
            run.error_code = None
            run.error_message = None
            add_project_event(
                session,
                project_id=project_id,
                event_type="audio.midi_extracted",
                payload={
                    "audio_upload_id": upload.id,
                    "midi_asset_id": midi_asset.id,
                    "run_id": run.id,
                    "analysis_range": analysis_range_manifest,
                    "reference_analysis_id": (
                        reference_analysis.id if reference_analysis is not None else None
                    ),
                    "provider_name": run.provider_name,
                    "provider_version": run.provider_version,
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
            failed_run.error_code = (
                exc.code
                if isinstance(exc, AudioToMidiProviderError)
                else "audio_to_midi_failed"
            )
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
        format=upload.format,
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


def audio_upload_requires_normalization(upload: AudioUpload) -> bool:
    return upload.format != AudioSourceFormat.wav


async def mark_audio_upload_normalization_failed(
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
) -> AudioUpload | None:
    upload = await get_audio_upload(session, project_id, audio_upload_id)
    if upload is None:
        return None
    if upload.status == AudioUploadStatus.processing:
        upload.status = AudioUploadStatus.failed
        add_project_event(
            session,
            project_id=project_id,
            event_type="audio.normalization.failed",
            payload={"audio_upload_id": upload.id, "format": str(upload.format)},
        )
        await session.commit()
        await session.refresh(upload)
    return upload


def _validate_upload(filename: str, content_type: str, data: bytes) -> AudioFormatSpec:
    if len(data) > MAX_AUDIO_UPLOAD_BYTES:
        raise AudioUploadTooLargeError("Audio upload exceeds 25 MB")
    detected_format = _detect_audio_format(data)
    if detected_format is None:
        raise UnsupportedAudioTypeError(
            "Unsupported audio format. Use WAV, MP3, M4A, FLAC, or OGG"
        )
    spec = AUDIO_FORMAT_SPECS[detected_format]
    extension = Path(filename).suffix.lower()
    normalized_content_type = content_type.partition(";")[0].strip().lower()
    content_type_matches = (
        normalized_content_type in spec.content_types
        or normalized_content_type in GENERIC_UPLOAD_CONTENT_TYPES
    )
    if extension not in spec.extensions or not content_type_matches:
        raise UnsupportedAudioTypeError(
            "Audio filename, media type, and file signature must describe the same format"
        )
    return spec


def _detect_audio_format(data: bytes) -> AudioSourceFormat | None:
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return AudioSourceFormat.wav
    if data.startswith(b"fLaC"):
        return AudioSourceFormat.flac
    if data.startswith(b"OggS"):
        return AudioSourceFormat.ogg
    if data.startswith(b"ID3") or (
        len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0
    ):
        return AudioSourceFormat.mp3
    if _looks_like_m4a(data):
        return AudioSourceFormat.m4a
    return None


def _looks_like_m4a(data: bytes) -> bool:
    if len(data) < 12 or data[4:8] != b"ftyp":
        return False
    box_size = int.from_bytes(data[:4], byteorder="big", signed=False)
    if box_size < 12:
        return False
    box_end = min(len(data), box_size)
    brands = {data[offset : offset + 4] for offset in range(8, box_end - 3, 4)}
    return bool(brands & {b"M4A ", b"M4B ", b"mp41", b"mp42", b"isom"})


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


def _manifest_optional_uuid(manifest: dict[str, object], key: str) -> UUID | None:
    value = manifest.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Generation run manifest has invalid {key}")
    return UUID(value)


def _manifest_string(manifest: dict[str, object], key: str) -> str:
    value = manifest.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Generation run manifest is missing {key}")
    return value


def _manifest_optional_string(manifest: dict[str, object], key: str) -> str | None:
    value = manifest.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"Generation run manifest has invalid {key}")
    return value


async def _ready_pcm_derivative(
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
) -> AudioDerivative | None:
    statement: Select[tuple[AudioDerivative]] = (
        select(AudioDerivative)
        .where(
            AudioDerivative.project_id == str(project_id),
            AudioDerivative.audio_upload_id == str(audio_upload_id),
            AudioDerivative.kind == AudioDerivativeKind.pcm_wav,
        )
        .order_by(AudioDerivative.created_at.desc(), AudioDerivative.id.desc())
        .limit(1)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def _reference_analysis_for_project(
    session: AsyncSession,
    project_id: UUID,
    reference_analysis_id: UUID,
) -> ReferenceAnalysisVersion | None:
    statement: Select[tuple[ReferenceAnalysisVersion]] = select(
        ReferenceAnalysisVersion
    ).where(
        ReferenceAnalysisVersion.id == str(reference_analysis_id),
        ReferenceAnalysisVersion.project_id == str(project_id),
    )
    return (await session.execute(statement)).scalar_one_or_none()


def _validate_reference_analysis_source(
    analysis: ReferenceAnalysisVersion,
    *,
    upload: AudioUpload,
    derivative: AudioDerivative | None,
    analysis_range: AudioAnalysisRangeManifest,
) -> str | None:
    if analysis.audio_upload_id != upload.id or analysis.source_checksum != upload.checksum:
        return "Reference analysis does not belong to this audio source"
    derivative_id = derivative.id if derivative is not None else None
    if analysis.audio_derivative_id != derivative_id:
        return "Reference analysis uses a different PCM derivative"
    if analysis.analysis_range != dict(analysis_range):
        return "Reference analysis range must match the MIDI extraction range"
    return None


async def _manifest_pcm_derivative(
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
    manifest: dict[str, object],
) -> AudioDerivative | None:
    derivative_id = _manifest_optional_uuid(manifest, "audio_derivative_id")
    analyzed_checksum = _manifest_optional_string(manifest, "analyzed_checksum")
    if derivative_id is None:
        upload = await get_audio_upload(session, project_id, audio_upload_id)
        if upload is None or upload.format != AudioSourceFormat.wav:
            raise ValueError("Generation run manifest is missing the PCM derivative")
        if analyzed_checksum is not None and analyzed_checksum != upload.checksum:
            raise ValueError("Audio-to-MIDI analyzed checksum changed")
        return None
    statement: Select[tuple[AudioDerivative]] = select(AudioDerivative).where(
        AudioDerivative.id == str(derivative_id),
        AudioDerivative.project_id == str(project_id),
        AudioDerivative.audio_upload_id == str(audio_upload_id),
        AudioDerivative.kind == AudioDerivativeKind.pcm_wav,
    )
    derivative = (await session.execute(statement)).scalar_one_or_none()
    if derivative is None:
        raise ValueError("Recorded PCM WAV derivative is not ready")
    if analyzed_checksum is not None and derivative.checksum != analyzed_checksum:
        raise ValueError("Audio-to-MIDI analyzed checksum changed")
    return derivative


async def _manifest_reference_analysis(
    session: AsyncSession,
    project_id: UUID,
    upload: AudioUpload,
    derivative: AudioDerivative | None,
    manifest: dict[str, object],
) -> ReferenceAnalysisVersion | None:
    reference_analysis_id = _manifest_optional_uuid(manifest, "reference_analysis_id")
    if reference_analysis_id is None:
        return None
    analysis = await _reference_analysis_for_project(
        session,
        project_id,
        reference_analysis_id,
    )
    if analysis is None:
        raise ValueError("Recorded ReferenceAnalysis is not available")
    analysis_range = manifest_audio_analysis_range(
        manifest,
        fallback_duration_seconds=upload.duration_seconds,
    )
    conflict = _validate_reference_analysis_source(
        analysis,
        upload=upload,
        derivative=derivative,
        analysis_range=analysis_range,
    )
    if conflict is not None:
        raise ValueError(conflict)
    return analysis


def resolve_audio_analysis_range(
    duration_seconds: float | None,
    requested: AudioAnalysisRange | None,
) -> tuple[AudioAnalysisRangeManifest | None, str | None]:
    if duration_seconds is None or duration_seconds <= 0:
        return None, "Audio duration is unavailable"
    if requested is None:
        return (
            {
                "mode": "full",
                "start_seconds": 0.0,
                "end_seconds": round(duration_seconds, 3),
            },
            None,
        )
    if requested.end_seconds > duration_seconds + 1e-6:
        return None, f"Analysis range exceeds audio duration ({duration_seconds:.3f} seconds)"
    return (
        {
            "mode": "selection",
            "start_seconds": round(requested.start_seconds, 3),
            "end_seconds": round(requested.end_seconds, 3),
        },
        None,
    )


def manifest_audio_analysis_range(
    manifest: dict[str, object],
    *,
    fallback_duration_seconds: float | None,
) -> AudioAnalysisRangeManifest:
    value = manifest.get("analysis_range")
    if value is None and fallback_duration_seconds is not None:
        return {
            "mode": "full",
            "start_seconds": 0.0,
            "end_seconds": float(fallback_duration_seconds),
        }
    if not isinstance(value, dict):
        raise ValueError("Generation run manifest is missing analysis_range")
    mode = value.get("mode")
    start_seconds = value.get("start_seconds")
    end_seconds = value.get("end_seconds")
    if mode not in {"full", "selection"}:
        raise ValueError("Generation run analysis_range mode is invalid")
    if not isinstance(start_seconds, int | float) or not isinstance(
        end_seconds,
        int | float,
    ):
        raise ValueError("Generation run analysis_range bounds are invalid")
    if start_seconds < 0 or end_seconds - start_seconds < 0.1:
        raise ValueError("Generation run analysis_range bounds are invalid")
    return {
        "mode": cast(Literal["full", "selection"], mode),
        "start_seconds": float(start_seconds),
        "end_seconds": float(end_seconds),
    }

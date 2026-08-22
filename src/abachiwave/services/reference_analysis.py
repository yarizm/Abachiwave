import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from uuid import UUID, uuid4

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.core.database import AsyncSessionLocal
from abachiwave.models.audio import (
    AudioDerivative,
    AudioDerivativeKind,
    AudioSourceFormat,
    AudioUploadStatus,
    ReferenceAnalysisVersion,
)
from abachiwave.models.composition import (
    ArrangementPlanVersion,
    ChordProgressionVersion,
    LyricsVersion,
    MidiAssetVersion,
)
from abachiwave.models.demo import GenerationRun, GenerationRunStatus, GenerationRunType
from abachiwave.models.project import Project
from abachiwave.schemas.audio import (
    AudioAnalysisRange,
    ReferenceAnalysisApplyField,
    ReferenceAnalysisApplyRead,
    ReferenceAnalysisApplyRequest,
    ReferenceAnalysisFieldChange,
    ReferenceAnalysisRead,
)
from abachiwave.schemas.song_specs import SongSpecUpdate
from abachiwave.services.audio import (
    get_audio_upload,
    manifest_audio_analysis_range,
    resolve_audio_analysis_range,
)
from abachiwave.services.audio_derivatives import get_audio_derivative
from abachiwave.services.events import add_project_event
from abachiwave.services.generation_runs import lock_generation_run
from abachiwave.services.reference_analysis_provider import (
    AudioAnalysisProvider,
    LocalDeterministicAudioAnalysisProvider,
    ReferenceAnalysisRequest,
)
from abachiwave.services.song_specs import edit_song_spec_version, get_song_spec_version
from abachiwave.services.storage import ObjectStorage, get_object_storage
from abachiwave.services.task_queue import ReferenceAnalysisTaskQueue
from abachiwave.services.versioning import create_version_with_retry
from abachiwave.services.wav_analysis import slice_wav_bytes


@dataclass(frozen=True)
class ReferenceAnalysisCreateResult:
    run: GenerationRun | None
    not_found: str | None = None
    conflict: str | None = None
    invalid_range: str | None = None


@dataclass(frozen=True)
class ReferenceAnalysisApplyResult:
    response: ReferenceAnalysisApplyRead | None
    not_found: str | None = None
    conflict: str | None = None


async def create_reference_analysis_run(
    *,
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
    analysis_range: AudioAnalysisRange | None,
    queue: ReferenceAnalysisTaskQueue,
    provider: AudioAnalysisProvider | None = None,
) -> ReferenceAnalysisCreateResult:
    project = await session.get(Project, str(project_id))
    if project is None:
        return ReferenceAnalysisCreateResult(run=None, not_found="Project not found")
    upload = await get_audio_upload(session, project_id, audio_upload_id)
    if upload is None:
        return ReferenceAnalysisCreateResult(run=None, not_found="AudioUpload not found")
    if upload.status != AudioUploadStatus.available:
        return ReferenceAnalysisCreateResult(
            run=None,
            conflict="Audio upload must be available",
        )
    resolved_range, range_error = resolve_audio_analysis_range(
        upload.duration_seconds,
        analysis_range,
    )
    if range_error is not None:
        return ReferenceAnalysisCreateResult(run=None, invalid_range=range_error)
    if resolved_range is None:
        return ReferenceAnalysisCreateResult(
            run=None,
            invalid_range="Audio duration is unavailable",
        )

    derivative: AudioDerivative | None = None
    if upload.format != AudioSourceFormat.wav:
        derivative = await get_audio_derivative(
            session,
            project_id,
            audio_upload_id,
            kind=AudioDerivativeKind.pcm_wav,
        )
        if derivative is None:
            return ReferenceAnalysisCreateResult(
                run=None,
                conflict="PCM WAV derivative is not ready",
            )

    active_statement: Select[tuple[GenerationRun]] = select(GenerationRun).where(
        GenerationRun.project_id == str(project_id),
        GenerationRun.run_type == GenerationRunType.reference_analysis,
        GenerationRun.status.in_([GenerationRunStatus.queued, GenerationRunStatus.running]),
    )
    active_runs = (await session.execute(active_statement)).scalars().all()
    if any(
        active.input_manifest.get("audio_upload_id") == upload.id
        and active.input_manifest.get("source_checksum") == upload.checksum
        and active.input_manifest.get("analysis_range") == resolved_range
        for active in active_runs
    ):
        return ReferenceAnalysisCreateResult(
            run=None,
            conflict="Reference analysis is already active for this range",
        )

    selected_provider = provider or LocalDeterministicAudioAnalysisProvider()
    run = GenerationRun(
        project_id=str(project_id),
        run_type=GenerationRunType.reference_analysis,
        input_manifest={
            "audio_upload_id": upload.id,
            "audio_derivative_id": derivative.id if derivative is not None else None,
            "source_checksum": upload.checksum,
            "analyzed_checksum": derivative.checksum if derivative is not None else upload.checksum,
            "analysis_range": resolved_range,
        },
        provider_name=selected_provider.name,
        provider_version=selected_provider.version,
        provider_params=selected_provider.default_params(),
    )
    session.add(run)
    await session.flush()
    add_project_event(
        session,
        project_id=project_id,
        event_type="audio.reference_analysis.queued",
        payload={
            "audio_upload_id": upload.id,
            "run_id": run.id,
            "analysis_range": resolved_range,
        },
        generation_run_id=UUID(run.id),
    )
    await session.commit()
    await session.refresh(run)
    try:
        run.arq_job_id = await queue.enqueue_reference_analysis(UUID(run.id))
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
    return ReferenceAnalysisCreateResult(run=run)


async def execute_reference_analysis(
    run_id: UUID,
    *,
    storage: ObjectStorage | None = None,
    provider: AudioAnalysisProvider | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> GenerationRun | None:
    selected_storage = storage or get_object_storage()
    selected_session_factory = session_factory or AsyncSessionLocal
    async with selected_session_factory() as session:
        run = await session.get(GenerationRun, str(run_id))
        if run is None:
            return None
        if run.status == GenerationRunStatus.cancelled:
            return run
        try:
            if run.run_type != GenerationRunType.reference_analysis:
                raise ValueError("GenerationRun is not a reference analysis run")
            selected_provider = provider or _provider_for_run(run)
            run.status = GenerationRunStatus.running
            run.started_at = datetime.now(UTC)
            run.error_code = None
            run.error_message = None
            await session.commit()
            await session.refresh(run)

            project_id = UUID(run.project_id)
            audio_upload_id = _manifest_uuid(run.input_manifest, "audio_upload_id")
            upload = await get_audio_upload(session, project_id, audio_upload_id)
            if upload is None:
                raise ValueError("AudioUpload not found")
            source_checksum = _manifest_string(run.input_manifest, "source_checksum")
            if upload.checksum != source_checksum:
                raise ValueError("Reference analysis source checksum changed")
            analysis_range = manifest_audio_analysis_range(
                run.input_manifest,
                fallback_duration_seconds=upload.duration_seconds,
            )
            derivative = await _manifest_derivative(
                session,
                project_id,
                audio_upload_id,
                run.input_manifest,
            )
            storage_key = derivative.storage_key if derivative is not None else upload.storage_key
            filename = derivative.filename if derivative is not None else upload.filename
            audio_bytes = await asyncio.to_thread(selected_storage.get_bytes, storage_key)
            source_audio_bytes = len(audio_bytes)
            if analysis_range["mode"] == "selection":
                audio_bytes = await asyncio.to_thread(
                    slice_wav_bytes,
                    audio_bytes,
                    start_seconds=analysis_range["start_seconds"],
                    end_seconds=analysis_range["end_seconds"],
                )
            result = await asyncio.to_thread(
                selected_provider.analyze,
                ReferenceAnalysisRequest(
                    audio_bytes=audio_bytes,
                    filename=filename,
                    source_start_seconds=analysis_range["start_seconds"],
                    source_end_seconds=analysis_range["end_seconds"],
                    provider_params=run.provider_params,
                ),
            )

            locked_run = await lock_generation_run(session, run_id)
            if locked_run is None:
                return None
            run = locked_run
            if run.status == GenerationRunStatus.cancelled:
                await session.commit()
                await session.refresh(run)
                return run

            def build_analysis(version_number: int) -> ReferenceAnalysisVersion:
                return ReferenceAnalysisVersion(
                    id=str(uuid4()),
                    project_id=str(project_id),
                    audio_upload_id=upload.id,
                    audio_derivative_id=derivative.id if derivative is not None else None,
                    run_id=run.id,
                    version_number=version_number,
                    source_checksum=source_checksum,
                    analysis_range=dict(analysis_range),
                    tempo_bpm=result.tempo_bpm,
                    beat_grid=result.beat_grid,
                    time_signature=result.time_signature.model_dump(mode="json"),
                    key_candidate=result.key_candidate.model_dump(mode="json"),
                    pitch_range=result.pitch_range.model_dump(mode="json"),
                    loudness=result.loudness.model_dump(mode="json"),
                    structure_sections=[
                        section.model_dump(mode="json") for section in result.structure_sections
                    ],
                    chord_candidates=[
                        chord.model_dump(mode="json") for chord in result.chord_candidates
                    ],
                    instrument_tags=[
                        tag.model_dump(mode="json") for tag in result.instrument_tags
                    ],
                    energy_curve=[point.model_dump(mode="json") for point in result.energy_curve],
                    production_features=[
                        feature.model_dump(mode="json") for feature in result.production_features
                    ],
                    confidence=result.confidence,
                    provider_name=run.provider_name,
                    provider_version=run.provider_version,
                    provider_params=run.provider_params,
                )

            analysis = await create_version_with_retry(
                session=session,
                project_id=project_id,
                load_next_version_number=partial(
                    _next_analysis_version_number,
                    session,
                    audio_upload_id,
                ),
                build_version=build_analysis,
            )
            run.status = GenerationRunStatus.succeeded
            run.provider_usage = {
                "reference_analysis_id": analysis.id,
                "source_audio_bytes": source_audio_bytes,
                "analyzed_audio_bytes": len(audio_bytes),
                "analysis_range": analysis_range,
                "overall_confidence": result.confidence.get("overall", 0.0),
            }
            run.completed_at = datetime.now(UTC)
            run.error_code = None
            run.error_message = None
            add_project_event(
                session,
                project_id=project_id,
                event_type="audio.reference_analysis.ready",
                payload={
                    "audio_upload_id": upload.id,
                    "reference_analysis_id": analysis.id,
                    "run_id": run.id,
                    "analysis_range": analysis_range,
                },
                generation_run_id=run_id,
                artifact_version_id=UUID(analysis.id),
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
            failed_run.error_code = "reference_analysis_failed"
            failed_run.error_message = str(exc)
            failed_run.completed_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(failed_run)
            return failed_run


async def list_reference_analyses(
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[ReferenceAnalysisVersion] | None:
    if await get_audio_upload(session, project_id, audio_upload_id) is None:
        return None
    statement: Select[tuple[ReferenceAnalysisVersion]] = (
        select(ReferenceAnalysisVersion)
        .where(
            ReferenceAnalysisVersion.project_id == str(project_id),
            ReferenceAnalysisVersion.audio_upload_id == str(audio_upload_id),
        )
        .order_by(
            ReferenceAnalysisVersion.version_number.desc(),
            ReferenceAnalysisVersion.created_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_reference_analysis(
    session: AsyncSession,
    project_id: UUID,
    analysis_id: UUID,
) -> ReferenceAnalysisVersion | None:
    statement: Select[tuple[ReferenceAnalysisVersion]] = select(ReferenceAnalysisVersion).where(
        ReferenceAnalysisVersion.project_id == str(project_id),
        ReferenceAnalysisVersion.id == str(analysis_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


def reference_analysis_to_read(analysis: ReferenceAnalysisVersion) -> ReferenceAnalysisRead:
    return ReferenceAnalysisRead.model_validate(analysis)


async def apply_reference_analysis(
    *,
    session: AsyncSession,
    project_id: UUID,
    analysis_id: UUID,
    request: ReferenceAnalysisApplyRequest,
) -> ReferenceAnalysisApplyResult:
    analysis = await get_reference_analysis(session, project_id, analysis_id)
    if analysis is None:
        return ReferenceAnalysisApplyResult(response=None, not_found="ReferenceAnalysis not found")
    song_spec = await get_song_spec_version(session, project_id, request.song_spec_id)
    if song_spec is None:
        return ReferenceAnalysisApplyResult(response=None, not_found="SongSpec not found")

    candidate_values: dict[ReferenceAnalysisApplyField, str | int | float] = {
        ReferenceAnalysisApplyField.tempo_bpm: round(analysis.tempo_bpm),
        ReferenceAnalysisApplyField.key: _analysis_key_value(analysis),
        ReferenceAnalysisApplyField.time_signature: _analysis_time_signature_value(analysis),
    }
    current_values: dict[ReferenceAnalysisApplyField, str | int | float | None] = {
        ReferenceAnalysisApplyField.tempo_bpm: song_spec.tempo_bpm,
        ReferenceAnalysisApplyField.key: song_spec.key,
        ReferenceAnalysisApplyField.time_signature: song_spec.time_signature,
    }
    changes = [
        ReferenceAnalysisFieldChange(
            field=field,
            current_value=current_values[field],
            candidate_value=candidate_values[field],
            confidence=_analysis_field_confidence(analysis, field),
        )
        for field in request.fields
        if current_values[field] != candidate_values[field]
    ]
    if not changes:
        return ReferenceAnalysisApplyResult(
            response=None,
            conflict="Selected analysis fields already match the SongSpec",
        )
    affected_counts = await _song_spec_asset_counts(session, UUID(song_spec.id))
    warnings = [
        (
            "A new SongSpec draft will be created; the approved version remains current "
            "until approval."
        ),
        "Existing lyrics, chords, MIDI, and arrangements remain linked to the source SongSpec.",
    ]
    base_response = {
        "analysis_id": analysis_id,
        "source_song_spec_id": UUID(song_spec.id),
        "selected_fields": request.fields,
        "changes": changes,
        "affected_asset_counts": affected_counts,
        "warnings": warnings,
    }
    if not request.confirm:
        return ReferenceAnalysisApplyResult(
            response=ReferenceAnalysisApplyRead(
                **base_response,
                requires_confirmation=True,
                applied=False,
                new_song_spec_id=None,
                new_song_spec_version=None,
            )
        )

    update_values = {change.field.value: change.candidate_value for change in changes}
    updated_song_spec = await edit_song_spec_version(
        session,
        project_id,
        UUID(song_spec.id),
        SongSpecUpdate.model_validate(update_values),
    )
    if updated_song_spec is None:
        return ReferenceAnalysisApplyResult(response=None, not_found="SongSpec not found")
    add_project_event(
        session,
        project_id=project_id,
        event_type="audio.reference_analysis.applied",
        payload={
            "reference_analysis_id": analysis.id,
            "source_song_spec_id": song_spec.id,
            "new_song_spec_id": updated_song_spec.id,
            "selected_fields": [field.value for field in request.fields],
        },
        artifact_version_id=UUID(updated_song_spec.id),
    )
    await session.commit()
    return ReferenceAnalysisApplyResult(
        response=ReferenceAnalysisApplyRead(
            **base_response,
            requires_confirmation=False,
            applied=True,
            new_song_spec_id=UUID(updated_song_spec.id),
            new_song_spec_version=updated_song_spec.version_number,
        )
    )


def _provider_for_run(run: GenerationRun) -> AudioAnalysisProvider:
    provider = LocalDeterministicAudioAnalysisProvider()
    if run.provider_name != provider.name or run.provider_version != provider.version:
        raise ValueError(
            f"Reference analysis provider {run.provider_name!r} version "
            f"{run.provider_version!r} is unavailable"
        )
    return provider


def _analysis_key_value(analysis: ReferenceAnalysisVersion) -> str:
    value = analysis.key_candidate.get("value")
    if not isinstance(value, str) or not value:
        raise ValueError("Reference analysis key candidate is invalid")
    return value


def _analysis_time_signature_value(analysis: ReferenceAnalysisVersion) -> str:
    value = analysis.time_signature.get("value")
    if not isinstance(value, str) or not value:
        raise ValueError("Reference analysis time signature is invalid")
    return value


def _analysis_field_confidence(
    analysis: ReferenceAnalysisVersion,
    field: ReferenceAnalysisApplyField,
) -> float:
    confidence_key = "key" if field is ReferenceAnalysisApplyField.key else field.value
    value = analysis.confidence.get(confidence_key, 0.0)
    return min(1.0, max(0.0, float(value)))


async def _song_spec_asset_counts(
    session: AsyncSession,
    song_spec_id: UUID,
) -> dict[str, int]:
    song_spec_value = str(song_spec_id)
    lyrics = await session.scalar(
        select(func.count())
        .select_from(LyricsVersion)
        .where(LyricsVersion.song_spec_id == song_spec_value)
    )
    chords = await session.scalar(
        select(func.count())
        .select_from(ChordProgressionVersion)
        .where(ChordProgressionVersion.song_spec_id == song_spec_value)
    )
    midi = await session.scalar(
        select(func.count())
        .select_from(MidiAssetVersion)
        .where(MidiAssetVersion.song_spec_id == song_spec_value)
    )
    arrangements = await session.scalar(
        select(func.count())
        .select_from(ArrangementPlanVersion)
        .where(ArrangementPlanVersion.song_spec_id == song_spec_value)
    )
    return {
        "lyrics": int(lyrics or 0),
        "chords": int(chords or 0),
        "midi": int(midi or 0),
        "arrangements": int(arrangements or 0),
    }


async def _manifest_derivative(
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
    manifest: dict[str, object],
) -> AudioDerivative | None:
    value = manifest.get("audio_derivative_id")
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Generation run audio_derivative_id is invalid")
    derivative = await get_audio_derivative(
        session,
        project_id,
        audio_upload_id,
        UUID(value),
    )
    if derivative is None:
        raise ValueError("AudioDerivative not found")
    analyzed_checksum = _manifest_string(manifest, "analyzed_checksum")
    if derivative.checksum != analyzed_checksum:
        raise ValueError("Reference analysis derivative checksum changed")
    return derivative


async def _next_analysis_version_number(
    session: AsyncSession,
    audio_upload_id: UUID,
) -> int:
    statement = select(func.max(ReferenceAnalysisVersion.version_number)).where(
        ReferenceAnalysisVersion.audio_upload_id == str(audio_upload_id)
    )
    current = await session.scalar(statement)
    return int(current or 0) + 1


def _manifest_uuid(manifest: dict[str, object], key: str) -> UUID:
    return UUID(_manifest_string(manifest, key))


def _manifest_string(manifest: dict[str, object], key: str) -> str:
    value = manifest.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Generation run manifest is missing {key}")
    return value

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.core.config import get_settings
from abachiwave.core.database import AsyncSessionLocal
from abachiwave.models.audio import AudioSourceFormat, AudioUpload, AudioUploadStatus
from abachiwave.models.demo import (
    AudioDemoVersion,
    GenerationRun,
    GenerationRunStatus,
    GenerationRunType,
)
from abachiwave.models.project import Project
from abachiwave.schemas.composition import ChordSection, LyricSection
from abachiwave.schemas.demo import AudioDemoVersionRead, GenerationRunRead
from abachiwave.services.delivery import ExportAssets, resolve_export_assets
from abachiwave.services.demo_provider import (
    DemoGenerationRequest,
    LocalDeterministicWavProvider,
    MusicGenerationProvider,
    UnknownDemoProviderError,
    build_demo_provider,
)
from abachiwave.services.events import add_project_event
from abachiwave.services.generation_runs import lock_generation_run
from abachiwave.services.song_specs import song_spec_to_data
from abachiwave.services.storage import ObjectStorage, get_object_storage
from abachiwave.services.task_queue import DemoTaskQueue
from abachiwave.services.versioning import create_version_with_retry
from abachiwave.services.wav_analysis import analyze_wav_bytes


@dataclass(frozen=True)
class DemoCreateResult:
    run: GenerationRun | None
    missing: list[str]
    not_found: str | None


async def create_demo_generation_run(
    *,
    session: AsyncSession,
    project_id: UUID,
    arrangement_plan_id: UUID | None,
    queue: DemoTaskQueue,
    retry_of_run_id: UUID | None = None,
    provider: MusicGenerationProvider | None = None,
) -> DemoCreateResult:
    project = await session.get(Project, str(project_id))
    if project is None:
        return DemoCreateResult(run=None, missing=[], not_found="Project not found")

    assets, missing, not_found = await resolve_export_assets(
        session,
        project_id,
        arrangement_plan_id,
    )
    if not_found or missing or assets is None:
        return DemoCreateResult(run=None, missing=missing, not_found=not_found)

    selected_provider = provider or build_demo_provider(get_settings())
    run = GenerationRun(
        project_id=str(project_id),
        input_manifest=_build_input_manifest(assets),
        provider_name=selected_provider.name,
        provider_version=selected_provider.version,
        provider_params=selected_provider.default_params(),
        retry_of_run_id=str(retry_of_run_id) if retry_of_run_id else None,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    try:
        run.arq_job_id = await queue.enqueue_demo_generation(UUID(run.id))
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
    return DemoCreateResult(run=run, missing=[], not_found=None)


def _resolve_run_provider(run: GenerationRun) -> MusicGenerationProvider:
    """Reconstruct the provider recorded on a run, failing loudly if unknown.

    Uses settings only to pick the name->impl registry; the run's recorded
    provider_name is authoritative. Unknown names raise so retrying an old
    run after a rollback fails instead of producing a mismatched demo.
    """
    settings = get_settings()
    if run.provider_name != settings.demo_provider_name:
        # The run was created with a different provider than currently
        # configured. Only the local provider can be rebuilt without extra
        # state today.
        if run.provider_name == "local_deterministic_wav":
            return LocalDeterministicWavProvider()
        raise UnknownDemoProviderError(
            f"Run recorded provider {run.provider_name!r} which is not available"
        )
    return build_demo_provider(settings)


async def execute_demo_generation(
    run_id: UUID,
    *,
    storage: ObjectStorage | None = None,
    provider: MusicGenerationProvider | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> GenerationRun | None:
    selected_storage = storage or get_object_storage()
    selected_session_factory = session_factory or AsyncSessionLocal
    stored_key: str | None = None
    async with selected_session_factory() as session:
        run = await session.get(GenerationRun, str(run_id))
        if run is None:
            return None
        if run.status == GenerationRunStatus.cancelled:
            return run
        try:
            # Resolve the provider from the run record inside the try block so
            # an UnknownDemoProviderError is caught by the handler below and the
            # run is marked failed instead of staying stuck in queued. A
            # caller-supplied provider (e.g. test injection) always wins.
            selected_provider = provider or _resolve_run_provider(run)
            run.status = GenerationRunStatus.running
            run.started_at = datetime.now(UTC)
            run.error_code = None
            run.error_message = None
            await session.commit()
            await session.refresh(run)

            project_id = UUID(run.project_id)
            arrangement_plan_id = _manifest_uuid(run.input_manifest, "arrangement_plan_id")
            assets, missing, not_found = await resolve_export_assets(
                session,
                project_id,
                arrangement_plan_id,
            )
            if not_found:
                raise ValueError(not_found)
            if missing or assets is None:
                raise ValueError(f"Demo prerequisites are missing: {', '.join(missing)}")

            await session.refresh(run)
            if run.status == GenerationRunStatus.cancelled:
                return run
            await session.commit()
            audio = await asyncio.to_thread(
                selected_provider.generate_demo,
                _provider_request(assets, run.provider_params),
            )
            audio_metadata = await asyncio.to_thread(analyze_wav_bytes, audio.data)
            locked_run = await lock_generation_run(session, run_id)
            if locked_run is None:
                return None
            run = locked_run
            if run.status == GenerationRunStatus.cancelled:
                await session.commit()
                await session.refresh(run)
                return run

            def build_demo(version_number: int) -> AudioDemoVersion:
                demo_id = str(uuid4())
                filename = f"demo-v{version_number}.wav"
                return AudioDemoVersion(
                    id=demo_id,
                    project_id=str(project_id),
                    run_id=run.id,
                    song_spec_id=assets.song_spec.id,
                    lyrics_version_id=assets.lyrics.id,
                    chord_version_id=assets.chords.id,
                    arrangement_plan_id=assets.arrangement.id,
                    midi_asset_ids=[asset.id for asset in assets.midi_assets],
                    version_number=version_number,
                    storage_key=f"projects/{project_id}/demos/{demo_id}/{filename}",
                    filename=filename,
                    content_type=audio.content_type,
                    size_bytes=len(audio.data),
                    checksum=sha256(audio.data).hexdigest(),
                    duration_seconds=audio.duration_seconds,
                    waveform_peaks=audio_metadata.waveform_peaks,
                    provider_name=audio.provider_name,
                    provider_version=audio.provider_version,
                    provider_params=audio.provider_params,
                )

            demo = await create_version_with_retry(
                session=session,
                project_id=project_id,
                load_next_version_number=partial(
                    _next_demo_version_number,
                    session,
                    project_id,
                ),
                build_version=build_demo,
            )
            stored_key = demo.storage_key
            await asyncio.to_thread(
                selected_storage.put_bytes,
                demo.storage_key,
                audio.data,
                audio.content_type,
            )
            run.status = GenerationRunStatus.succeeded
            run.completed_at = datetime.now(UTC)
            run.error_code = None
            run.error_message = None
            add_project_event(
                session,
                project_id=project_id,
                event_type="demo.generated",
                payload={"demo_id": demo.id, "run_id": run.id},
                generation_run_id=UUID(run.id),
                artifact_version_id=UUID(demo.id),
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
            failed_run.error_code = "demo_generation_failed"
            failed_run.error_message = str(exc)
            failed_run.completed_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(failed_run)
            return failed_run


async def list_demo_versions(
    session: AsyncSession,
    project_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[AudioDemoVersion]:
    statement: Select[tuple[AudioDemoVersion]] = (
        select(AudioDemoVersion)
        .where(AudioDemoVersion.project_id == str(project_id))
        .order_by(AudioDemoVersion.created_at.desc(), AudioDemoVersion.version_number.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_demo_version(
    session: AsyncSession,
    project_id: UUID,
    demo_id: UUID,
) -> AudioDemoVersion | None:
    statement: Select[tuple[AudioDemoVersion]] = select(AudioDemoVersion).where(
        AudioDemoVersion.id == str(demo_id),
        AudioDemoVersion.project_id == str(project_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_generation_runs(
    session: AsyncSession,
    project_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[GenerationRun]:
    statement: Select[tuple[GenerationRun]] = (
        select(GenerationRun)
        .where(GenerationRun.project_id == str(project_id))
        .order_by(GenerationRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_generation_run(session: AsyncSession, task_id: UUID) -> GenerationRun | None:
    return await session.get(GenerationRun, str(task_id))


async def retry_generation_run(
    *,
    session: AsyncSession,
    task_id: UUID,
    queue: DemoTaskQueue,
) -> tuple[GenerationRun | None, str | None, list[str]]:
    failed_run = await get_generation_run(session, task_id)
    if failed_run is None:
        return None, "GenerationRun not found", []
    if failed_run.status != GenerationRunStatus.failed:
        return None, "GenerationRun is not failed", []
    if failed_run.run_type != GenerationRunType.demo_generation:
        return None, "GenerationRun is not retryable", []
    arrangement_plan_id = _manifest_uuid(failed_run.input_manifest, "arrangement_plan_id")
    result = await create_demo_generation_run(
        session=session,
        project_id=UUID(failed_run.project_id),
        arrangement_plan_id=arrangement_plan_id,
        queue=queue,
        retry_of_run_id=UUID(failed_run.id),
    )
    return result.run, result.not_found, result.missing


async def cancel_generation_run(
    session: AsyncSession,
    task_id: UUID,
) -> tuple[GenerationRun | None, str | None]:
    run = await lock_generation_run(session, task_id)
    if run is None:
        return None, "GenerationRun not found"
    if run.status not in {GenerationRunStatus.queued, GenerationRunStatus.running}:
        return None, "GenerationRun cannot be cancelled"
    previous_status_value = run.status.value
    run.status = GenerationRunStatus.cancelled
    run.error_code = "task_cancelled"
    run.error_message = "cancelled by user"
    run.completed_at = datetime.now(UTC)
    if run.run_type == GenerationRunType.audio_derivative:
        upload_id = run.input_manifest.get("audio_upload_id")
        if isinstance(upload_id, str):
            upload = await session.get(AudioUpload, upload_id)
            if (
                upload is not None
                and upload.format != AudioSourceFormat.wav
                and upload.status == AudioUploadStatus.processing
            ):
                upload.status = AudioUploadStatus.failed
                add_project_event(
                    session,
                    project_id=UUID(run.project_id),
                    event_type="audio.normalization.failed",
                    payload={
                        "audio_upload_id": upload.id,
                        "run_id": run.id,
                        "reason": "cancelled",
                    },
                    generation_run_id=UUID(run.id),
                )
    add_project_event(
        session,
        project_id=UUID(run.project_id),
        event_type="task.cancelled",
        payload={"run_id": run.id, "previous_status": previous_status_value},
        generation_run_id=UUID(run.id),
    )
    await session.commit()
    await session.refresh(run)
    return run, None


async def generation_run_to_read(
    session: AsyncSession,
    run: GenerationRun,
) -> GenerationRunRead:
    demo_id = await _demo_id_for_run(session, UUID(run.id))
    return GenerationRunRead(
        id=UUID(run.id),
        project_id=UUID(run.project_id),
        run_type=run.run_type,
        status=run.status,
        arq_job_id=run.arq_job_id,
        input_manifest=run.input_manifest,
        provider_name=run.provider_name,
        provider_version=run.provider_version,
        provider_params=run.provider_params,
        provider_usage=run.provider_usage,
        error_code=run.error_code,
        error_message=run.error_message,
        retry_of_run_id=UUID(run.retry_of_run_id) if run.retry_of_run_id else None,
        result_midi_asset_id=(UUID(run.result_midi_asset_id) if run.result_midi_asset_id else None),
        demo_id=demo_id,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def audio_demo_to_read(demo: AudioDemoVersion) -> AudioDemoVersionRead:
    return AudioDemoVersionRead(
        id=UUID(demo.id),
        project_id=UUID(demo.project_id),
        run_id=UUID(demo.run_id),
        song_spec_id=UUID(demo.song_spec_id),
        lyrics_version_id=UUID(demo.lyrics_version_id),
        chord_version_id=UUID(demo.chord_version_id),
        arrangement_plan_id=UUID(demo.arrangement_plan_id),
        midi_asset_ids=[UUID(asset_id) for asset_id in demo.midi_asset_ids],
        version_number=demo.version_number,
        filename=demo.filename,
        content_type=demo.content_type,
        size_bytes=demo.size_bytes,
        checksum=demo.checksum,
        duration_seconds=demo.duration_seconds,
        waveform_peaks=demo.waveform_peaks,
        provider_name=demo.provider_name,
        provider_version=demo.provider_version,
        provider_params=demo.provider_params,
        download_url=f"/api/v1/projects/{demo.project_id}/demos/{demo.id}/download",
        created_at=demo.created_at,
    )


def _build_input_manifest(assets: ExportAssets) -> dict[str, object]:
    return {
        "song_spec_id": assets.song_spec.id,
        "song_spec_version": assets.song_spec.version_number,
        "lyrics_version_id": assets.lyrics.id,
        "lyrics_version": assets.lyrics.version_number,
        "chord_version_id": assets.chords.id,
        "chord_version": assets.chords.version_number,
        "midi_asset_ids": [asset.id for asset in assets.midi_assets],
        "midi_assets": [
            {
                "id": asset.id,
                "kind": str(asset.kind),
                "version_number": asset.version_number,
                "filename": asset.filename,
            }
            for asset in assets.midi_assets
        ],
        "arrangement_plan_id": assets.arrangement.id,
        "arrangement_plan_version": assets.arrangement.version_number,
    }


def _provider_request(
    assets: ExportAssets,
    provider_params: dict[str, object],
) -> DemoGenerationRequest:
    song_spec = song_spec_to_data(assets.song_spec)
    duration = song_spec.target_duration_seconds or 30
    return DemoGenerationRequest(
        song_spec=song_spec,
        lyric_sections=[LyricSection.model_validate(section) for section in assets.lyrics.sections],
        chord_sections=[ChordSection.model_validate(section) for section in assets.chords.sections],
        duration_seconds=duration,
        provider_params=provider_params,
    )


def _manifest_uuid(manifest: dict[str, object], key: str) -> UUID:
    value = manifest.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Generation run manifest is missing {key}")
    return UUID(value)


async def _next_demo_version_number(session: AsyncSession, project_id: UUID) -> int:
    statement = select(func.max(AudioDemoVersion.version_number)).where(
        AudioDemoVersion.project_id == str(project_id)
    )
    result = await session.execute(statement)
    current = result.scalar_one_or_none()
    return int(current or 0) + 1


async def _demo_id_for_run(session: AsyncSession, run_id: UUID) -> UUID | None:
    statement = select(AudioDemoVersion.id).where(AudioDemoVersion.run_id == str(run_id))
    result = await session.execute(statement)
    value = result.scalar_one_or_none()
    return UUID(value) if value else None

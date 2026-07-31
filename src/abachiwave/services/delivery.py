import hmac
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from hashlib import sha256
from tempfile import SpooledTemporaryFile
from uuid import UUID, uuid4

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.agents.composition import build_arrangement_from_assets
from abachiwave.core.config import get_settings
from abachiwave.models.audio import AudioUpload, AudioUploadStatus
from abachiwave.models.comment import ProjectCommentStatus
from abachiwave.models.composition import (
    ArrangementPlanVersion,
    ChordProgressionVersion,
    ExportBundle,
    ExportBundleStatus,
    LyricsVersion,
    MidiAssetKind,
    MidiAssetVersion,
)
from abachiwave.models.demo import AudioDemoVersion
from abachiwave.models.project import Project
from abachiwave.models.song_spec import SongSpecStatus, SongSpecVersion
from abachiwave.schemas.audio import AudioUploadRead
from abachiwave.schemas.composition import (
    ArrangementPlan,
    ArrangementPlanVersionRead,
    ArrangementUpdate,
    AssetReference,
    AssetTreeRead,
    ChordSection,
    CurrentAssets,
    ExportBundleRead,
    LyricSection,
)
from abachiwave.schemas.demo import AudioDemoVersionRead
from abachiwave.schemas.projects import ProjectRead
from abachiwave.services.comments import comment_to_read, list_project_comments
from abachiwave.services.composition import (
    chord_progression_to_read,
    lyrics_version_to_read,
)
from abachiwave.services.delivery_archive import (
    export_source_size,
    file_size_and_checksum,
    write_export_archive,
)
from abachiwave.services.events import add_project_event, list_project_events
from abachiwave.services.handoff_format import (
    build_handoff_markdown,
    build_handoff_next_actions,
)
from abachiwave.services.song_specs import song_spec_to_data, song_spec_to_read
from abachiwave.services.storage import ObjectStorage, put_storage_file
from abachiwave.services.versioning import create_version_with_retry

EXPORT_CONTENT_TYPE = "application/zip"
EXPORT_SPOOL_MEMORY_BYTES = 8 * 1024 * 1024
ASSET_HISTORY_LIMIT = 200
REQUIRED_MIDI_KINDS = (MidiAssetKind.chord, MidiAssetKind.melody, MidiAssetKind.hook)


@dataclass(frozen=True)
class ArrangementInputs:
    song_spec: SongSpecVersion
    lyrics: LyricsVersion
    chords: ChordProgressionVersion
    midi_assets: list[MidiAssetVersion]


@dataclass(frozen=True)
class ExportAssets(ArrangementInputs):
    arrangement: ArrangementPlanVersion


def arrangement_plan_to_read(version: ArrangementPlanVersion) -> ArrangementPlanVersionRead:
    return ArrangementPlanVersionRead(
        id=UUID(version.id),
        project_id=UUID(version.project_id),
        song_spec_id=UUID(version.song_spec_id),
        lyrics_version_id=UUID(version.lyrics_version_id),
        chord_version_id=UUID(version.chord_version_id),
        midi_asset_ids=[UUID(asset_id) for asset_id in version.midi_asset_ids],
        version_number=version.version_number,
        parent_version_id=UUID(version.parent_version_id) if version.parent_version_id else None,
        source_revision_request_id=(
            UUID(version.source_revision_request_id) if version.source_revision_request_id else None
        ),
        arrangement_plan=ArrangementPlan(
            overview=version.overview,
            sections=version.sections,
            mix_notes=version.mix_notes,
            reference_notes=version.reference_notes,
        ),
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


def export_bundle_to_read(bundle: ExportBundle) -> ExportBundleRead:
    download_url = None
    if (
        bundle.status == ExportBundleStatus.ready
        and bundle.storage_key
        and bundle.download_token_hash
    ):
        download_url = f"/api/v1/exports/{bundle.id}/download?token={_export_token(bundle.id)}"
    return ExportBundleRead(
        id=UUID(bundle.id),
        project_id=UUID(bundle.project_id),
        arrangement_plan_id=(
            UUID(bundle.arrangement_plan_id) if bundle.arrangement_plan_id else None
        ),
        status=bundle.status,
        manifest=bundle.manifest,
        filename=bundle.filename,
        content_type=bundle.content_type,
        size_bytes=bundle.size_bytes,
        checksum=bundle.checksum,
        download_url=download_url,
        error_message=bundle.error_message,
        created_at=bundle.created_at,
        updated_at=bundle.updated_at,
    )


async def list_arrangement_plan_versions(
    session: AsyncSession,
    project_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[ArrangementPlanVersion]:
    statement: Select[tuple[ArrangementPlanVersion]] = (
        select(ArrangementPlanVersion)
        .where(ArrangementPlanVersion.project_id == str(project_id))
        .order_by(ArrangementPlanVersion.version_number.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_arrangement_plan_version(
    session: AsyncSession,
    project_id: UUID,
    arrangement_plan_id: UUID,
) -> ArrangementPlanVersion | None:
    statement: Select[tuple[ArrangementPlanVersion]] = select(ArrangementPlanVersion).where(
        ArrangementPlanVersion.id == str(arrangement_plan_id),
        ArrangementPlanVersion.project_id == str(project_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_latest_arrangement_plan_version(
    session: AsyncSession,
    project_id: UUID,
) -> ArrangementPlanVersion | None:
    statement: Select[tuple[ArrangementPlanVersion]] = (
        select(ArrangementPlanVersion)
        .where(ArrangementPlanVersion.project_id == str(project_id))
        .order_by(ArrangementPlanVersion.version_number.desc())
        .limit(1)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def resolve_arrangement_inputs(
    session: AsyncSession,
    project_id: UUID,
    song_spec: SongSpecVersion,
    lyrics_version_id: UUID | None,
    chord_version_id: UUID | None,
    midi_asset_ids: list[UUID] | None,
) -> tuple[ArrangementInputs | None, list[str], str | None]:
    missing: list[str] = []
    lyrics = (
        await get_lyrics_version(session, project_id, lyrics_version_id)
        if lyrics_version_id
        else await get_latest_lyrics_version(session, project_id)
    )
    if lyrics_version_id and lyrics is None:
        return None, [], "LyricsVersion not found"
    if lyrics is None:
        missing.append("lyrics")

    chords = (
        await get_chord_progression_version(session, project_id, chord_version_id)
        if chord_version_id
        else await get_latest_chord_progression_version(session, project_id)
    )
    if chord_version_id and chords is None:
        return None, [], "ChordProgressionVersion not found"
    if chords is None:
        missing.append("chords")

    midi_assets: list[MidiAssetVersion] = []
    if midi_asset_ids:
        for midi_asset_id in midi_asset_ids:
            asset = await get_midi_asset_version(session, project_id, midi_asset_id)
            if asset is None:
                return None, [], "MidiAssetVersion not found"
            midi_assets.append(asset)
    else:
        midi_assets = list((await get_latest_midi_assets_by_kind(session, project_id)).values())
    midi_by_kind = _latest_midi_by_kind(midi_assets)
    missing = _missing_composition_prerequisites(
        song_spec=song_spec,
        lyrics=lyrics,
        chords=chords,
        midi_by_kind=midi_by_kind,
    )

    if missing:
        return None, missing, None
    if lyrics is None or chords is None:
        return None, missing, None
    return (
        ArrangementInputs(
            song_spec=song_spec,
            lyrics=lyrics,
            chords=chords,
            midi_assets=_sort_midi_assets_for_export(list(midi_by_kind.values())),
        ),
        [],
        None,
    )


async def generate_arrangement_plan_version(
    session: AsyncSession,
    project_id: UUID,
    inputs: ArrangementInputs,
) -> ArrangementPlanVersion:
    song_spec_data = song_spec_to_data(inputs.song_spec)
    plan = build_arrangement_from_assets(
        song_spec=song_spec_data,
        lyric_sections=[LyricSection.model_validate(section) for section in inputs.lyrics.sections],
        chord_sections=[ChordSection.model_validate(section) for section in inputs.chords.sections],
        midi_kinds=[MidiAssetKind(asset.kind) for asset in inputs.midi_assets],
    )
    return await _create_arrangement_plan_version(
        session=session,
        project_id=project_id,
        song_spec_id=UUID(inputs.song_spec.id),
        lyrics_version_id=UUID(inputs.lyrics.id),
        chord_version_id=UUID(inputs.chords.id),
        midi_asset_ids=[UUID(asset.id) for asset in inputs.midi_assets],
        plan=plan,
        parent_version_id=None,
    )


async def edit_arrangement_plan_version(
    session: AsyncSession,
    project_id: UUID,
    arrangement_plan_id: UUID,
    payload: ArrangementUpdate,
) -> ArrangementPlanVersion | None:
    current = await get_arrangement_plan_version(session, project_id, arrangement_plan_id)
    if current is None:
        return None
    plan = ArrangementPlan.model_validate(payload.model_dump())
    return await _create_arrangement_plan_version(
        session=session,
        project_id=project_id,
        song_spec_id=UUID(current.song_spec_id),
        lyrics_version_id=UUID(current.lyrics_version_id),
        chord_version_id=UUID(current.chord_version_id),
        midi_asset_ids=[UUID(asset_id) for asset_id in current.midi_asset_ids],
        plan=plan,
        parent_version_id=UUID(current.id),
    )


async def build_asset_tree(session: AsyncSession, project_id: UUID) -> AssetTreeRead:
    song_specs = await _list_song_specs(session, project_id)
    lyrics_versions = await _list_lyrics_versions(session, project_id)
    chord_versions = await _list_chord_versions(session, project_id)
    midi_assets = await _list_midi_assets(session, project_id)
    arrangements = await list_arrangement_plan_versions(session, project_id)

    approved_song_spec = next(
        (version for version in song_specs if version.status == SongSpecStatus.approved),
        None,
    )
    latest_lyrics = lyrics_versions[0] if lyrics_versions else None
    latest_chords = chord_versions[0] if chord_versions else None
    latest_midi_by_kind = _latest_midi_by_kind(midi_assets)
    latest_arrangement = arrangements[0] if arrangements else None
    arrangement_midi_assets_by_id = (
        await _get_midi_assets_by_ids(
            session,
            project_id,
            latest_arrangement.midi_asset_ids,
        )
        if latest_arrangement
        else {}
    )

    current = CurrentAssets(
        song_spec=_song_spec_ref(approved_song_spec) if approved_song_spec else None,
        lyrics=_lyrics_ref(latest_lyrics) if latest_lyrics else None,
        chords=_chords_ref(latest_chords) if latest_chords else None,
        midi_assets=[
            _midi_ref(latest_midi_by_kind[kind])
            for kind in REQUIRED_MIDI_KINDS
            if kind in latest_midi_by_kind
        ],
        arrangement=_arrangement_ref(latest_arrangement) if latest_arrangement else None,
    )
    timeline = [
        *[_song_spec_ref(version) for version in song_specs],
        *[_lyrics_ref(version) for version in lyrics_versions],
        *[_chords_ref(version) for version in chord_versions],
        *[_midi_ref(version) for version in midi_assets],
        *[_arrangement_ref(version) for version in arrangements],
    ]
    timeline.sort(key=lambda item: item.created_at, reverse=True)
    return AssetTreeRead(
        current=current,
        timeline=timeline,
        missing_prerequisites=_missing_export_prerequisites(
            approved_song_spec=approved_song_spec,
            lyrics=latest_lyrics,
            chords=latest_chords,
            midi_by_kind=latest_midi_by_kind,
            arrangement=latest_arrangement,
            arrangement_midi_assets_by_id=arrangement_midi_assets_by_id,
        ),
    )


async def create_export_bundle(
    *,
    session: AsyncSession,
    project_id: UUID,
    arrangement_plan_id: UUID | None,
    storage: ObjectStorage,
) -> tuple[ExportBundle | None, list[str], str | None]:
    project = await session.get(Project, str(project_id))
    if project is None:
        return None, [], "Project not found"
    export_assets, missing, not_found = await _resolve_export_assets(
        session,
        project_id,
        arrangement_plan_id,
    )
    if not_found or missing:
        return None, missing, not_found
    if export_assets is None:
        return None, ["arrangement"], None

    export_id = str(uuid4())
    filename = f"abachiwave-{project_id}-{export_id[:8]}.zip"
    storage_key = f"projects/{project_id}/exports/{export_id}/{filename}"
    token = _export_token(export_id)
    manifest = await _build_export_manifest(
        session=session,
        project=project,
        export_id=export_id,
        assets=export_assets,
    )
    stored_key: str | None = None
    try:
        source_size = export_source_size(export_assets.midi_assets, manifest)
        max_size = get_settings().max_export_bundle_bytes
        if source_size > max_size:
            raise ValueError(
                f"Export source assets exceed the {max_size} byte project export limit"
            )
        with SpooledTemporaryFile(
            max_size=EXPORT_SPOOL_MEMORY_BYTES,
            mode="w+b",
        ) as archive:
            write_export_archive(
                archive,
                project=project,
                song_spec=song_spec_to_read(export_assets.song_spec),
                lyrics=lyrics_version_to_read(export_assets.lyrics),
                chords=chord_progression_to_read(export_assets.chords),
                arrangement=arrangement_plan_to_read(export_assets.arrangement),
                midi_assets=export_assets.midi_assets,
                manifest=manifest,
                storage=storage,
            )
            size_bytes, checksum = file_size_and_checksum(archive)
            if size_bytes > max_size:
                raise ValueError(f"Export archive exceeds the {max_size} byte limit")
            put_storage_file(storage, storage_key, archive, EXPORT_CONTENT_TYPE)
        stored_key = storage_key
        bundle = ExportBundle(
            id=export_id,
            project_id=str(project_id),
            arrangement_plan_id=export_assets.arrangement.id,
            status=ExportBundleStatus.ready,
            manifest=manifest,
            storage_key=storage_key,
            filename=filename,
            content_type=EXPORT_CONTENT_TYPE,
            size_bytes=size_bytes,
            checksum=checksum,
            download_token_hash=_hash_export_token(token),
        )
    except Exception as exc:
        bundle = ExportBundle(
            id=export_id,
            project_id=str(project_id),
            arrangement_plan_id=export_assets.arrangement.id,
            status=ExportBundleStatus.failed,
            manifest=manifest,
            content_type=EXPORT_CONTENT_TYPE,
            error_message=str(exc),
        )
    try:
        session.add(bundle)
        add_project_event(
            session,
            project_id=project_id,
            event_type=(
                "export.ready" if bundle.status == ExportBundleStatus.ready else "export.failed"
            ),
            payload={
                "export_id": bundle.id,
                "status": str(bundle.status),
                "filename": bundle.filename,
                "error_message": bundle.error_message,
            },
            artifact_version_id=UUID(bundle.id),
        )
        await session.commit()
        await session.refresh(bundle)
        return bundle, [], None
    except Exception:
        await session.rollback()
        if stored_key is not None:
            with suppress(Exception):
                storage.delete_bytes(stored_key)
        raise


async def resolve_export_assets(
    session: AsyncSession,
    project_id: UUID,
    arrangement_plan_id: UUID | None,
) -> tuple[ExportAssets | None, list[str], str | None]:
    return await _resolve_export_assets(session, project_id, arrangement_plan_id)


async def list_export_bundles(
    session: AsyncSession,
    project_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[ExportBundle]:
    statement: Select[tuple[ExportBundle]] = (
        select(ExportBundle)
        .where(ExportBundle.project_id == str(project_id))
        .order_by(ExportBundle.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_project_export_bundle(
    session: AsyncSession,
    project_id: UUID,
    export_id: UUID,
) -> ExportBundle | None:
    statement: Select[tuple[ExportBundle]] = select(ExportBundle).where(
        ExportBundle.id == str(export_id),
        ExportBundle.project_id == str(project_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_export_bundle_by_id(
    session: AsyncSession,
    export_id: UUID,
) -> ExportBundle | None:
    return await session.get(ExportBundle, str(export_id))


def validate_export_download_token(bundle: ExportBundle, token: str) -> bool:
    if bundle.download_token_hash is None:
        return False
    return hmac.compare_digest(bundle.download_token_hash, _hash_export_token(token))


async def get_lyrics_version(
    session: AsyncSession,
    project_id: UUID,
    lyrics_version_id: UUID,
) -> LyricsVersion | None:
    statement: Select[tuple[LyricsVersion]] = select(LyricsVersion).where(
        LyricsVersion.id == str(lyrics_version_id),
        LyricsVersion.project_id == str(project_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_latest_lyrics_version(
    session: AsyncSession,
    project_id: UUID,
) -> LyricsVersion | None:
    statement: Select[tuple[LyricsVersion]] = (
        select(LyricsVersion)
        .where(LyricsVersion.project_id == str(project_id))
        .order_by(LyricsVersion.version_number.desc())
        .limit(1)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_chord_progression_version(
    session: AsyncSession,
    project_id: UUID,
    chord_version_id: UUID,
) -> ChordProgressionVersion | None:
    statement: Select[tuple[ChordProgressionVersion]] = select(ChordProgressionVersion).where(
        ChordProgressionVersion.id == str(chord_version_id),
        ChordProgressionVersion.project_id == str(project_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_latest_chord_progression_version(
    session: AsyncSession,
    project_id: UUID,
) -> ChordProgressionVersion | None:
    statement: Select[tuple[ChordProgressionVersion]] = (
        select(ChordProgressionVersion)
        .where(ChordProgressionVersion.project_id == str(project_id))
        .order_by(ChordProgressionVersion.version_number.desc())
        .limit(1)
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_midi_asset_version(
    session: AsyncSession,
    project_id: UUID,
    midi_asset_id: UUID,
) -> MidiAssetVersion | None:
    statement: Select[tuple[MidiAssetVersion]] = select(MidiAssetVersion).where(
        MidiAssetVersion.id == str(midi_asset_id),
        MidiAssetVersion.project_id == str(project_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_latest_midi_assets_by_kind(
    session: AsyncSession,
    project_id: UUID,
) -> dict[MidiAssetKind, MidiAssetVersion]:
    assets = await _list_midi_assets(session, project_id)
    return _latest_midi_by_kind(assets)


async def _create_arrangement_plan_version(
    *,
    session: AsyncSession,
    project_id: UUID,
    song_spec_id: UUID,
    lyrics_version_id: UUID,
    chord_version_id: UUID,
    midi_asset_ids: list[UUID],
    plan: ArrangementPlan,
    parent_version_id: UUID | None,
    source_revision_request_id: UUID | None = None,
    commit: bool = True,
) -> ArrangementPlanVersion:
    version = await create_version_with_retry(
        session=session,
        project_id=project_id,
        load_next_version_number=partial(
            _next_arrangement_version_number,
            session,
            project_id,
        ),
        build_version=lambda version_number: ArrangementPlanVersion(
            project_id=str(project_id),
            song_spec_id=str(song_spec_id),
            lyrics_version_id=str(lyrics_version_id),
            chord_version_id=str(chord_version_id),
            midi_asset_ids=[str(asset_id) for asset_id in midi_asset_ids],
            version_number=version_number,
            parent_version_id=str(parent_version_id) if parent_version_id else None,
            source_revision_request_id=(
                str(source_revision_request_id) if source_revision_request_id else None
            ),
            overview=plan.overview,
            sections=[section.model_dump() for section in plan.sections],
            mix_notes=plan.mix_notes,
            reference_notes=plan.reference_notes,
        ),
    )
    add_project_event(
        session,
        project_id=project_id,
        event_type="arrangement.edited" if parent_version_id else "arrangement.generated",
        payload={
            "arrangement_plan_id": version.id,
            "version_number": version.version_number,
            "section_count": len(plan.sections),
        },
        artifact_version_id=UUID(version.id),
    )
    if commit:
        await session.commit()
        await session.refresh(version)
    return version


async def _next_arrangement_version_number(session: AsyncSession, project_id: UUID) -> int:
    statement = select(func.max(ArrangementPlanVersion.version_number)).where(
        ArrangementPlanVersion.project_id == str(project_id)
    )
    result = await session.execute(statement)
    current = result.scalar_one_or_none()
    return int(current or 0) + 1


async def _resolve_export_assets(
    session: AsyncSession,
    project_id: UUID,
    arrangement_plan_id: UUID | None,
) -> tuple[ExportAssets | None, list[str], str | None]:
    arrangement = (
        await get_arrangement_plan_version(session, project_id, arrangement_plan_id)
        if arrangement_plan_id
        else await get_latest_arrangement_plan_version(session, project_id)
    )
    if arrangement_plan_id and arrangement is None:
        return None, [], "ArrangementPlanVersion not found"
    if arrangement is None:
        return None, ["arrangement"], None

    song_specs = await _list_song_specs(session, project_id)
    song_spec = next(
        (version for version in song_specs if version.status == SongSpecStatus.approved),
        None,
    )
    lyrics = await get_latest_lyrics_version(session, project_id)
    chords = await get_latest_chord_progression_version(session, project_id)
    midi_by_kind = await get_latest_midi_assets_by_kind(session, project_id)
    arrangement_midi_assets_by_id = await _get_midi_assets_by_ids(
        session,
        project_id,
        arrangement.midi_asset_ids,
    )
    missing = _missing_export_prerequisites(
        approved_song_spec=song_spec,
        lyrics=lyrics,
        chords=chords,
        midi_by_kind=midi_by_kind,
        arrangement=arrangement,
        arrangement_midi_assets_by_id=arrangement_midi_assets_by_id,
    )
    if missing:
        return None, missing, None
    if song_spec is None or lyrics is None or chords is None:
        return None, missing, None
    return (
        ExportAssets(
            song_spec=song_spec,
            lyrics=lyrics,
            chords=chords,
            midi_assets=_sort_midi_assets_for_export(list(midi_by_kind.values())),
            arrangement=arrangement,
        ),
        [],
        None,
    )


async def _build_export_manifest(
    *,
    session: AsyncSession,
    project: Project,
    export_id: str,
    assets: ExportAssets,
) -> dict[str, object]:
    project_id = UUID(project.id)
    tree = await build_asset_tree(session, project_id)
    comments = await list_project_comments(session, project_id)
    events = await list_project_events(session, project_id=project_id, limit=200)
    demos = await _list_demo_versions(session, project_id)
    audio_uploads = await _list_available_audio_uploads(session, project_id)
    from abachiwave.schemas.revisions import ProjectEventRead
    from abachiwave.services.review import build_project_review

    review = await build_project_review(session, project_id)
    exported_at = datetime.now(UTC)
    project_read = ProjectRead.model_validate(project)
    comment_reads = [comment_to_read(comment) for comment in comments]
    demo_reads = [_audio_demo_to_read(demo) for demo in demos]
    upload_reads = [_audio_upload_to_read(upload) for upload in audio_uploads]
    open_comments = [
        comment for comment in comment_reads if comment.status == ProjectCommentStatus.open
    ]
    event_reads = [ProjectEventRead.model_validate(event) for event in events]
    recent_events = event_reads[:12]
    handoff: dict[str, object] | None = None
    if review is not None:
        next_actions = build_handoff_next_actions(review, open_comments)
        handoff = {
            "project": project_read.model_dump(mode="json"),
            "review": review.model_dump(mode="json"),
            "current_assets": tree.current.model_dump(mode="json"),
            "missing_prerequisites": tree.missing_prerequisites,
            "open_comments": [comment.model_dump(mode="json") for comment in open_comments],
            "recent_events": [event.model_dump(mode="json") for event in recent_events],
            "next_actions": next_actions,
            "handoff_markdown": build_handoff_markdown(
                project=project_read,
                review=review,
                asset_tree=tree,
                open_comments=open_comments,
                recent_events=recent_events,
                next_actions=next_actions,
                generated_at=exported_at,
            ),
            "generated_at": exported_at.isoformat(),
        }
    return {
        "export_id": export_id,
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
        },
        "exported_at": exported_at.isoformat(),
        "assets": {
            "song_spec": _song_spec_ref(assets.song_spec).model_dump(mode="json"),
            "lyrics": _lyrics_ref(assets.lyrics).model_dump(mode="json"),
            "chords": _chords_ref(assets.chords).model_dump(mode="json"),
            "midi_assets": [
                _midi_ref(asset).model_dump(mode="json") for asset in assets.midi_assets
            ],
            "arrangement": _arrangement_ref(assets.arrangement).model_dump(mode="json"),
        },
        "timeline": [item.model_dump(mode="json") for item in tree.timeline],
        "review": review.model_dump(mode="json") if review else None,
        "comments": [comment.model_dump(mode="json") for comment in comment_reads],
        "events": [event.model_dump(mode="json") for event in event_reads],
        "demos": [
            {
                **demo.model_dump(mode="json"),
                "storage_key": demos[index].storage_key,
                "archive_path": _demo_archive_path(demos[index]),
            }
            for index, demo in enumerate(demo_reads)
        ],
        "audio_uploads": [
            {
                **upload.model_dump(mode="json"),
                "storage_key": audio_uploads[index].storage_key,
                "archive_path": _audio_upload_archive_path(audio_uploads[index]),
            }
            for index, upload in enumerate(upload_reads)
        ],
        "handoff": handoff,
    }


async def _list_demo_versions(session: AsyncSession, project_id: UUID) -> list[AudioDemoVersion]:
    statement: Select[tuple[AudioDemoVersion]] = (
        select(AudioDemoVersion)
        .where(AudioDemoVersion.project_id == str(project_id))
        .order_by(AudioDemoVersion.created_at.desc(), AudioDemoVersion.version_number.desc())
        .limit(ASSET_HISTORY_LIMIT)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def _list_available_audio_uploads(
    session: AsyncSession,
    project_id: UUID,
) -> list[AudioUpload]:
    statement: Select[tuple[AudioUpload]] = (
        select(AudioUpload)
        .where(
            AudioUpload.project_id == str(project_id),
            AudioUpload.status == AudioUploadStatus.available,
        )
        .order_by(AudioUpload.created_at.desc(), AudioUpload.id.desc())
        .limit(ASSET_HISTORY_LIMIT)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


def _audio_demo_to_read(demo: AudioDemoVersion) -> AudioDemoVersionRead:
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


def _audio_upload_to_read(upload: AudioUpload) -> AudioUploadRead:
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


def _demo_archive_path(demo: AudioDemoVersion) -> str:
    return f"demos/{_archive_filename(demo.filename)}"


def _audio_upload_archive_path(upload: AudioUpload) -> str:
    return f"audio-uploads/{upload.id[:8]}-{_archive_filename(upload.filename)}"


def _archive_filename(filename: str) -> str:
    safe = "".join(
        character if character.isalnum() or character in "._-" else "-" for character in filename
    )
    return safe.strip(".-") or "asset.bin"


async def _list_song_specs(session: AsyncSession, project_id: UUID) -> list[SongSpecVersion]:
    statement: Select[tuple[SongSpecVersion]] = (
        select(SongSpecVersion)
        .where(SongSpecVersion.project_id == str(project_id))
        .order_by(SongSpecVersion.version_number.desc())
        .limit(ASSET_HISTORY_LIMIT)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def _list_lyrics_versions(session: AsyncSession, project_id: UUID) -> list[LyricsVersion]:
    statement: Select[tuple[LyricsVersion]] = (
        select(LyricsVersion)
        .where(LyricsVersion.project_id == str(project_id))
        .order_by(LyricsVersion.version_number.desc())
        .limit(ASSET_HISTORY_LIMIT)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def _list_chord_versions(
    session: AsyncSession,
    project_id: UUID,
) -> list[ChordProgressionVersion]:
    statement: Select[tuple[ChordProgressionVersion]] = (
        select(ChordProgressionVersion)
        .where(ChordProgressionVersion.project_id == str(project_id))
        .order_by(ChordProgressionVersion.version_number.desc())
        .limit(ASSET_HISTORY_LIMIT)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def _list_midi_assets(session: AsyncSession, project_id: UUID) -> list[MidiAssetVersion]:
    statement: Select[tuple[MidiAssetVersion]] = (
        select(MidiAssetVersion)
        .where(MidiAssetVersion.project_id == str(project_id))
        .order_by(MidiAssetVersion.created_at.desc(), MidiAssetVersion.version_number.desc())
        .limit(ASSET_HISTORY_LIMIT)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def _get_midi_assets_by_ids(
    session: AsyncSession,
    project_id: UUID,
    asset_ids: list[str],
) -> dict[str, MidiAssetVersion]:
    if not asset_ids:
        return {}
    statement: Select[tuple[MidiAssetVersion]] = select(MidiAssetVersion).where(
        MidiAssetVersion.project_id == str(project_id),
        MidiAssetVersion.id.in_(asset_ids),
    )
    result = await session.execute(statement)
    return {asset.id: asset for asset in result.scalars().all()}


def _latest_midi_by_kind(
    assets: Iterable[MidiAssetVersion],
) -> dict[MidiAssetKind, MidiAssetVersion]:
    latest: dict[MidiAssetKind, MidiAssetVersion] = {}
    for asset in sorted(assets, key=lambda item: item.version_number, reverse=True):
        kind = MidiAssetKind(asset.kind)
        latest.setdefault(kind, asset)
    return latest


def _missing_export_prerequisites(
    *,
    approved_song_spec: SongSpecVersion | None,
    lyrics: LyricsVersion | None,
    chords: ChordProgressionVersion | None,
    midi_by_kind: dict[MidiAssetKind, MidiAssetVersion],
    arrangement: ArrangementPlanVersion | None,
    arrangement_midi_assets_by_id: dict[str, MidiAssetVersion],
) -> list[str]:
    missing = _missing_composition_prerequisites(
        song_spec=approved_song_spec,
        lyrics=lyrics,
        chords=chords,
        midi_by_kind=midi_by_kind,
    )
    if not _arrangement_matches_current_chain(
        arrangement=arrangement,
        song_spec=approved_song_spec,
        midi_assets_by_id=arrangement_midi_assets_by_id,
    ):
        missing.append("arrangement")
    return missing


def _missing_composition_prerequisites(
    *,
    song_spec: SongSpecVersion | None,
    lyrics: LyricsVersion | None,
    chords: ChordProgressionVersion | None,
    midi_by_kind: dict[MidiAssetKind, MidiAssetVersion],
) -> list[str]:
    missing: list[str] = []
    if song_spec is None:
        missing.append("approved_song_spec")
    if not _lyrics_matches_song_spec(lyrics, song_spec):
        missing.append("lyrics")
    if not _asset_matches_song_spec(chords, song_spec):
        missing.append("chords")
    for kind in REQUIRED_MIDI_KINDS:
        asset = midi_by_kind.get(kind)
        if not _asset_matches_song_spec(asset, song_spec):
            missing.append(f"midi_{kind.value}")
    return missing


def _lyrics_matches_song_spec(
    lyrics: LyricsVersion | None,
    song_spec: SongSpecVersion | None,
) -> bool:
    return lyrics is not None and song_spec is not None and lyrics.song_spec_id == song_spec.id


def _asset_matches_song_spec(
    asset: ChordProgressionVersion | MidiAssetVersion | None,
    song_spec: SongSpecVersion | None,
) -> bool:
    return asset is not None and song_spec is not None and asset.song_spec_id == song_spec.id


def _arrangement_matches_current_chain(
    *,
    arrangement: ArrangementPlanVersion | None,
    song_spec: SongSpecVersion | None,
    midi_assets_by_id: dict[str, MidiAssetVersion],
) -> bool:
    if arrangement is None or song_spec is None or arrangement.song_spec_id != song_spec.id:
        return False
    referenced_kinds: set[MidiAssetKind] = set()
    for asset_id in arrangement.midi_asset_ids:
        asset = midi_assets_by_id.get(asset_id)
        if not _asset_matches_song_spec(asset, song_spec):
            return False
        if asset is not None:
            referenced_kinds.add(MidiAssetKind(asset.kind))
    return referenced_kinds == set(REQUIRED_MIDI_KINDS)


def _sort_midi_assets_for_export(assets: list[MidiAssetVersion]) -> list[MidiAssetVersion]:
    order = {kind: index for index, kind in enumerate(REQUIRED_MIDI_KINDS)}
    return sorted(assets, key=lambda asset: order[MidiAssetKind(asset.kind)])


def _song_spec_ref(version: SongSpecVersion) -> AssetReference:
    status = (
        version.status.value if isinstance(version.status, SongSpecStatus) else str(version.status)
    )
    return AssetReference(
        asset_type="song_spec",
        id=UUID(version.id),
        label=f"SongSpec v{version.version_number}",
        version_number=version.version_number,
        created_at=version.created_at,
        status=status,
    )


def _lyrics_ref(version: LyricsVersion) -> AssetReference:
    return AssetReference(
        asset_type="lyrics",
        id=UUID(version.id),
        label=f"Lyrics v{version.version_number}",
        version_number=version.version_number,
        created_at=version.created_at,
    )


def _chords_ref(version: ChordProgressionVersion) -> AssetReference:
    return AssetReference(
        asset_type="chords",
        id=UUID(version.id),
        label=f"Chords v{version.version_number}",
        version_number=version.version_number,
        created_at=version.created_at,
    )


def _midi_ref(version: MidiAssetVersion) -> AssetReference:
    kind = MidiAssetKind(version.kind)
    return AssetReference(
        asset_type="midi",
        id=UUID(version.id),
        label=f"{kind.value.title()} MIDI v{version.version_number}",
        version_number=version.version_number,
        created_at=version.created_at,
        kind=kind.value,
    )


def _arrangement_ref(version: ArrangementPlanVersion) -> AssetReference:
    return AssetReference(
        asset_type="arrangement",
        id=UUID(version.id),
        label=f"Arrangement v{version.version_number}",
        version_number=version.version_number,
        created_at=version.created_at,
    )


def _export_token(export_id: str) -> str:
    secret = get_settings().s3_secret_access_key.encode()
    return hmac.new(secret, f"export:{export_id}".encode(), sha256).hexdigest()


def _hash_export_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()

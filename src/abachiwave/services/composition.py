import asyncio
from contextlib import suppress
from functools import partial
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.agents.composition import build_chords_from_song_spec, build_lyrics_from_song_spec
from abachiwave.models.composition import (
    ChordProgressionVersion,
    LyricsVersion,
    MidiAssetKind,
    MidiAssetVersion,
)
from abachiwave.models.song_spec import SongSpecVersion
from abachiwave.schemas.composition import (
    ChordPreviewRead,
    ChordProgressionVersionRead,
    ChordSection,
    ChordTransposeRequest,
    ChordUpdate,
    HookCandidate,
    LyricSection,
    LyricsUpdate,
    LyricsVersionRead,
    MidiAssetVersionRead,
)
from abachiwave.schemas.song_specs import SongSpecData
from abachiwave.services.chord_theory import (
    normalize_chord_sections,
    transpose_chord_sections,
)
from abachiwave.services.events import add_project_event
from abachiwave.services.midi import build_midi_bytes
from abachiwave.services.song_specs import song_spec_to_data
from abachiwave.services.storage import ObjectStorage
from abachiwave.services.versioning import create_version_with_retry

MIDI_CONTENT_TYPE = "audio/midi"
DEFAULT_MIDI_KINDS = (MidiAssetKind.chord, MidiAssetKind.melody, MidiAssetKind.hook)


def lyrics_version_to_read(version: LyricsVersion) -> LyricsVersionRead:
    return LyricsVersionRead(
        id=UUID(version.id),
        project_id=UUID(version.project_id),
        song_spec_id=UUID(version.song_spec_id),
        version_number=version.version_number,
        parent_version_id=UUID(version.parent_version_id) if version.parent_version_id else None,
        source_revision_request_id=(
            UUID(version.source_revision_request_id) if version.source_revision_request_id else None
        ),
        schema_version=version.schema_version,
        sections=[LyricSection.model_validate(section) for section in version.sections],
        hook_candidates=[
            HookCandidate.model_validate(candidate) for candidate in version.hook_candidates
        ],
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


def chord_progression_to_read(version: ChordProgressionVersion) -> ChordProgressionVersionRead:
    sections = normalize_chord_sections(
        [ChordSection.model_validate(section) for section in version.sections],
        key_name=version.key,
        time_signature=version.time_signature,
    )
    return ChordProgressionVersionRead(
        id=UUID(version.id),
        project_id=UUID(version.project_id),
        song_spec_id=UUID(version.song_spec_id),
        lyrics_version_id=UUID(version.lyrics_version_id) if version.lyrics_version_id else None,
        version_number=version.version_number,
        parent_version_id=UUID(version.parent_version_id) if version.parent_version_id else None,
        schema_version=version.schema_version,
        key=version.key,
        tempo_bpm=version.tempo_bpm,
        time_signature=version.time_signature,
        sections=sections,
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


def midi_asset_to_read(version: MidiAssetVersion) -> MidiAssetVersionRead:
    return MidiAssetVersionRead(
        id=UUID(version.id),
        project_id=UUID(version.project_id),
        song_spec_id=UUID(version.song_spec_id),
        lyrics_version_id=UUID(version.lyrics_version_id) if version.lyrics_version_id else None,
        chord_version_id=UUID(version.chord_version_id) if version.chord_version_id else None,
        version_number=version.version_number,
        kind=version.kind,
        source_revision_request_id=(
            UUID(version.source_revision_request_id) if version.source_revision_request_id else None
        ),
        source_audio_upload_id=(
            UUID(version.source_audio_upload_id) if version.source_audio_upload_id else None
        ),
        filename=version.filename,
        content_type=version.content_type,
        size_bytes=version.size_bytes,
        checksum=version.checksum,
        created_at=version.created_at,
    )


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


async def list_lyrics_versions(
    session: AsyncSession,
    project_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[LyricsVersion]:
    statement: Select[tuple[LyricsVersion]] = (
        select(LyricsVersion)
        .where(LyricsVersion.project_id == str(project_id))
        .order_by(LyricsVersion.version_number.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def generate_lyrics_version(
    session: AsyncSession,
    project_id: UUID,
    song_spec: SongSpecVersion,
) -> LyricsVersion:
    song_spec_data = song_spec_to_data(song_spec)
    sections, hook_candidates = build_lyrics_from_song_spec(song_spec_data)
    return await _create_lyrics_version(
        session=session,
        project_id=project_id,
        song_spec_id=UUID(song_spec.id),
        sections=sections,
        hook_candidates=hook_candidates,
        parent_version_id=None,
    )


async def edit_lyrics_version(
    session: AsyncSession,
    project_id: UUID,
    lyrics_version_id: UUID,
    payload: LyricsUpdate,
) -> LyricsVersion | None:
    current = await get_lyrics_version(session, project_id, lyrics_version_id)
    if current is None:
        return None
    return await _create_lyrics_version(
        session=session,
        project_id=project_id,
        song_spec_id=UUID(current.song_spec_id),
        sections=payload.sections,
        hook_candidates=payload.hook_candidates,
        parent_version_id=UUID(current.id),
    )


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


async def list_chord_progression_versions(
    session: AsyncSession,
    project_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[ChordProgressionVersion]:
    statement: Select[tuple[ChordProgressionVersion]] = (
        select(ChordProgressionVersion)
        .where(ChordProgressionVersion.project_id == str(project_id))
        .order_by(ChordProgressionVersion.version_number.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def generate_chord_progression_version(
    session: AsyncSession,
    project_id: UUID,
    song_spec: SongSpecVersion,
    lyrics_version: LyricsVersion | None,
) -> ChordProgressionVersion:
    song_spec_data = song_spec_to_data(song_spec)
    lyric_sections = (
        [LyricSection.model_validate(section) for section in lyrics_version.sections]
        if lyrics_version
        else None
    )
    sections = build_chords_from_song_spec(song_spec_data, lyric_sections)
    return await _create_chord_progression_version(
        session=session,
        project_id=project_id,
        song_spec_id=UUID(song_spec.id),
        lyrics_version_id=UUID(lyrics_version.id) if lyrics_version else None,
        key=song_spec_data.key or "C major",
        tempo_bpm=song_spec_data.tempo_bpm or 120,
        time_signature=song_spec_data.time_signature or "4/4",
        sections=sections,
        parent_version_id=None,
    )


async def edit_chord_progression_version(
    session: AsyncSession,
    project_id: UUID,
    chord_version_id: UUID,
    payload: ChordUpdate,
) -> ChordProgressionVersion | None:
    current = await get_chord_progression_version(session, project_id, chord_version_id)
    if current is None:
        return None
    return await _create_chord_progression_version(
        session=session,
        project_id=project_id,
        song_spec_id=UUID(current.song_spec_id),
        lyrics_version_id=UUID(current.lyrics_version_id) if current.lyrics_version_id else None,
        key=current.key,
        tempo_bpm=current.tempo_bpm,
        time_signature=current.time_signature,
        sections=payload.sections,
        parent_version_id=UUID(current.id),
    )


async def transpose_chord_progression_version(
    session: AsyncSession,
    project_id: UUID,
    chord_version_id: UUID,
    payload: ChordTransposeRequest,
) -> ChordProgressionVersion | None:
    current = await get_chord_progression_version(session, project_id, chord_version_id)
    if current is None:
        return None
    current_sections = normalize_chord_sections(
        [ChordSection.model_validate(section) for section in current.sections],
        key_name=current.key,
        time_signature=current.time_signature,
    )
    output_key, sections = transpose_chord_sections(
        current_sections,
        key_name=current.key,
        time_signature=current.time_signature,
        semitones=payload.semitones,
        section_ids=set(payload.section_ids) if payload.section_ids else None,
    )
    version = await _create_chord_progression_version(
        session=session,
        project_id=project_id,
        song_spec_id=UUID(current.song_spec_id),
        lyrics_version_id=UUID(current.lyrics_version_id) if current.lyrics_version_id else None,
        key=output_key,
        tempo_bpm=current.tempo_bpm,
        time_signature=current.time_signature,
        sections=sections,
        parent_version_id=UUID(current.id),
        commit=False,
    )
    add_project_event(
        session,
        project_id=project_id,
        event_type="chords.transposed",
        payload={
            "chord_version_id": version.id,
            "source_chord_version_id": current.id,
            "semitones": payload.semitones,
            "section_ids": payload.section_ids,
            "key": output_key,
        },
        artifact_version_id=UUID(version.id),
    )
    await session.commit()
    await session.refresh(version)
    return version


async def preview_chord_progression(
    session: AsyncSession,
    project_id: UUID,
    chord_version_id: UUID,
    payload: ChordUpdate,
) -> ChordPreviewRead | None:
    current = await get_chord_progression_version(session, project_id, chord_version_id)
    if current is None:
        return None
    sections = normalize_chord_sections(
        payload.sections,
        key_name=current.key,
        time_signature=current.time_signature,
    )
    return ChordPreviewRead(
        source_chord_id=UUID(current.id),
        key=current.key,
        tempo_bpm=current.tempo_bpm,
        time_signature=current.time_signature,
        sections=sections,
    )


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


async def list_midi_asset_versions(
    session: AsyncSession,
    project_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[MidiAssetVersion]:
    statement: Select[tuple[MidiAssetVersion]] = (
        select(MidiAssetVersion)
        .where(MidiAssetVersion.project_id == str(project_id))
        .order_by(MidiAssetVersion.created_at.desc(), MidiAssetVersion.version_number.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def generate_midi_asset_versions(
    *,
    session: AsyncSession,
    project_id: UUID,
    song_spec: SongSpecVersion,
    lyrics_version: LyricsVersion | None,
    chord_version: ChordProgressionVersion | None,
    kinds: list[MidiAssetKind] | None,
    storage: ObjectStorage,
) -> list[MidiAssetVersion]:
    song_spec_data = song_spec_to_data(song_spec)
    lyric_sections = _lyric_sections_for_midi(song_spec_data, lyrics_version)
    chord_sections = _chord_sections_for_midi(song_spec_data, lyric_sections, chord_version)
    requested_kinds = kinds or list(DEFAULT_MIDI_KINDS)
    created_assets: list[MidiAssetVersion] = []
    for kind in requested_kinds:
        midi_bytes = build_midi_bytes(
            kind=kind,
            song_spec=song_spec_data,
            chord_sections=chord_sections,
            lyric_sections=lyric_sections,
        )
        asset = await create_midi_asset_version_from_bytes(
            session=session,
            project_id=project_id,
            song_spec_id=UUID(song_spec.id),
            lyrics_version_id=UUID(lyrics_version.id) if lyrics_version else None,
            chord_version_id=UUID(chord_version.id) if chord_version else None,
            kind=kind,
            midi_bytes=midi_bytes,
            filename=None,
            storage=storage,
        )
        created_assets.append(asset)
    return created_assets


async def create_midi_asset_version_from_bytes(
    *,
    session: AsyncSession,
    project_id: UUID,
    song_spec_id: UUID,
    lyrics_version_id: UUID | None,
    chord_version_id: UUID | None,
    kind: MidiAssetKind,
    midi_bytes: bytes,
    filename: str | None,
    storage: ObjectStorage,
    source_revision_request_id: UUID | None = None,
    source_audio_upload_id: UUID | None = None,
    commit: bool = True,
) -> MidiAssetVersion:
    def build_asset(version_number: int) -> MidiAssetVersion:
        asset_id = str(uuid4())
        resolved_filename = filename or f"{kind.value}-v{version_number}.mid"
        return MidiAssetVersion(
            id=asset_id,
            project_id=str(project_id),
            song_spec_id=str(song_spec_id),
            lyrics_version_id=str(lyrics_version_id) if lyrics_version_id else None,
            chord_version_id=str(chord_version_id) if chord_version_id else None,
            source_revision_request_id=(
                str(source_revision_request_id) if source_revision_request_id else None
            ),
            source_audio_upload_id=(
                str(source_audio_upload_id) if source_audio_upload_id else None
            ),
            version_number=version_number,
            kind=kind,
            storage_key=f"projects/{project_id}/midi/{asset_id}/{resolved_filename}",
            filename=resolved_filename,
            content_type=MIDI_CONTENT_TYPE,
            size_bytes=len(midi_bytes),
            checksum=sha256(midi_bytes).hexdigest(),
        )

    asset = await create_version_with_retry(
        session=session,
        project_id=project_id,
        load_next_version_number=partial(
            _next_midi_version_number,
            session,
            project_id,
            kind,
        ),
        build_version=build_asset,
    )
    try:
        await asyncio.to_thread(storage.put_bytes, asset.storage_key, midi_bytes, MIDI_CONTENT_TYPE)
    except Exception:
        with suppress(Exception):
            await asyncio.to_thread(storage.delete_bytes, asset.storage_key)
        raise
    add_project_event(
        session,
        project_id=project_id,
        event_type="midi.generated",
        payload={
            "midi_asset_id": asset.id,
            "kind": kind.value,
            "version_number": asset.version_number,
            "filename": asset.filename,
        },
        artifact_version_id=UUID(asset.id),
    )
    if commit:
        await session.commit()
        await session.refresh(asset)
    return asset


async def _create_lyrics_version(
    *,
    session: AsyncSession,
    project_id: UUID,
    song_spec_id: UUID,
    sections: list[LyricSection],
    hook_candidates: list[HookCandidate],
    parent_version_id: UUID | None,
    source_revision_request_id: UUID | None = None,
    commit: bool = True,
) -> LyricsVersion:
    version = await create_version_with_retry(
        session=session,
        project_id=project_id,
        load_next_version_number=partial(_next_lyrics_version_number, session, project_id),
        build_version=lambda version_number: LyricsVersion(
            project_id=str(project_id),
            song_spec_id=str(song_spec_id),
            version_number=version_number,
            parent_version_id=str(parent_version_id) if parent_version_id else None,
            source_revision_request_id=(
                str(source_revision_request_id) if source_revision_request_id else None
            ),
            sections=[section.model_dump(exclude_computed_fields=True) for section in sections],
            hook_candidates=[candidate.model_dump() for candidate in hook_candidates],
        ),
    )
    add_project_event(
        session,
        project_id=project_id,
        event_type="lyrics.edited" if parent_version_id else "lyrics.generated",
        payload={
            "lyrics_version_id": version.id,
            "version_number": version.version_number,
            "section_count": len(sections),
        },
        artifact_version_id=UUID(version.id),
    )
    if commit:
        await session.commit()
        await session.refresh(version)
    return version


async def _create_chord_progression_version(
    *,
    session: AsyncSession,
    project_id: UUID,
    song_spec_id: UUID,
    lyrics_version_id: UUID | None,
    key: str,
    tempo_bpm: int,
    time_signature: str,
    sections: list[ChordSection],
    parent_version_id: UUID | None,
    commit: bool = True,
) -> ChordProgressionVersion:
    normalized_sections = normalize_chord_sections(
        sections,
        key_name=key,
        time_signature=time_signature,
    )
    version = await create_version_with_retry(
        session=session,
        project_id=project_id,
        load_next_version_number=partial(_next_chord_version_number, session, project_id),
        build_version=lambda version_number: ChordProgressionVersion(
            project_id=str(project_id),
            song_spec_id=str(song_spec_id),
            lyrics_version_id=str(lyrics_version_id) if lyrics_version_id else None,
            version_number=version_number,
            parent_version_id=str(parent_version_id) if parent_version_id else None,
            schema_version=2,
            key=key,
            tempo_bpm=tempo_bpm,
            time_signature=time_signature,
            sections=[section.model_dump(mode="json") for section in normalized_sections],
        ),
    )
    add_project_event(
        session,
        project_id=project_id,
        event_type="chords.edited" if parent_version_id else "chords.generated",
        payload={
            "chord_version_id": version.id,
            "version_number": version.version_number,
            "section_count": len(normalized_sections),
        },
        artifact_version_id=UUID(version.id),
    )
    if commit:
        await session.commit()
        await session.refresh(version)
    return version


def _lyric_sections_for_midi(
    song_spec_data: SongSpecData,
    lyrics_version: LyricsVersion | None,
) -> list[LyricSection]:
    if lyrics_version:
        return [LyricSection.model_validate(section) for section in lyrics_version.sections]
    sections, _hook_candidates = build_lyrics_from_song_spec(song_spec_data)
    return sections


def _chord_sections_for_midi(
    song_spec_data: SongSpecData,
    lyric_sections: list[LyricSection],
    chord_version: ChordProgressionVersion | None,
) -> list[ChordSection]:
    if chord_version:
        return [ChordSection.model_validate(section) for section in chord_version.sections]
    return build_chords_from_song_spec(song_spec_data, lyric_sections)


async def _next_lyrics_version_number(session: AsyncSession, project_id: UUID) -> int:
    statement = select(func.max(LyricsVersion.version_number)).where(
        LyricsVersion.project_id == str(project_id)
    )
    result = await session.execute(statement)
    current = result.scalar_one_or_none()
    return int(current or 0) + 1


async def _next_chord_version_number(session: AsyncSession, project_id: UUID) -> int:
    statement = select(func.max(ChordProgressionVersion.version_number)).where(
        ChordProgressionVersion.project_id == str(project_id)
    )
    result = await session.execute(statement)
    current = result.scalar_one_or_none()
    return int(current or 0) + 1


async def _next_midi_version_number(
    session: AsyncSession,
    project_id: UUID,
    kind: MidiAssetKind,
) -> int:
    statement = select(func.max(MidiAssetVersion.version_number)).where(
        MidiAssetVersion.project_id == str(project_id),
        MidiAssetVersion.kind == kind,
    )
    result = await session.execute(statement)
    current = result.scalar_one_or_none()
    return int(current or 0) + 1

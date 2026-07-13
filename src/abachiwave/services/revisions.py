from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from hashlib import sha256
from io import BytesIO
from uuid import UUID, uuid4

from mido import MidiFile
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.models.composition import (
    ArrangementPlanVersion,
    LyricsVersion,
    MidiAssetKind,
    MidiAssetVersion,
)
from abachiwave.models.project import Project
from abachiwave.models.revision import (
    RevisionRequest,
    RevisionRequestStatus,
    RevisionTaskTarget,
)
from abachiwave.schemas.composition import (
    ArrangementSection,
    LyricSection,
)
from abachiwave.schemas.revisions import (
    RestoreAssetType,
    RevisionRequestRead,
    RevisionTask,
    VersionDiffRead,
    VersionReference,
    VersionRestoreRead,
)
from abachiwave.services.composition import (
    MIDI_CONTENT_TYPE,
    lyrics_version_to_read,
    midi_asset_to_read,
)
from abachiwave.services.delivery import (
    arrangement_plan_to_read,
    get_latest_arrangement_plan_version,
    get_latest_lyrics_version,
    get_latest_midi_assets_by_kind,
    get_lyrics_version,
    get_midi_asset_version,
)
from abachiwave.services.demo import get_demo_version
from abachiwave.services.events import add_project_event
from abachiwave.services.revision_diff import (
    build_arrangement_diff,
    build_demo_diff,
    build_lyrics_diff,
    build_midi_diff,
)
from abachiwave.services.storage import ObjectStorage
from abachiwave.services.versioning import create_version_with_retry


@dataclass(frozen=True)
class RevisionApplyResult:
    revision: RevisionRequest | None
    created_versions: list[VersionReference]
    not_found: str | None
    conflict: str | None


async def create_revision_request(
    session: AsyncSession,
    project_id: UUID,
    feedback: str,
) -> RevisionRequest | None:
    project = await session.get(Project, str(project_id))
    if project is None:
        return None
    tasks = await _plan_revision_tasks(session, project_id, feedback)
    revision = RevisionRequest(
        project_id=str(project_id),
        feedback=feedback,
        tasks=[task.model_dump(mode="json") for task in tasks],
        created_versions=[],
    )
    session.add(revision)
    await session.flush()
    add_project_event(
        session,
        project_id=project_id,
        event_type="revision.planned",
        payload={"feedback": feedback, "task_count": len(tasks)},
        revision_request_id=UUID(revision.id),
    )
    await session.commit()
    await session.refresh(revision)
    return revision


async def list_revision_requests(
    session: AsyncSession,
    project_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[RevisionRequest]:
    statement: Select[tuple[RevisionRequest]] = (
        select(RevisionRequest)
        .where(RevisionRequest.project_id == str(project_id))
        .order_by(RevisionRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_revision_request(
    session: AsyncSession,
    project_id: UUID,
    revision_id: UUID,
) -> RevisionRequest | None:
    statement: Select[tuple[RevisionRequest]] = select(RevisionRequest).where(
        RevisionRequest.id == str(revision_id),
        RevisionRequest.project_id == str(project_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def reject_revision_request(
    session: AsyncSession,
    project_id: UUID,
    revision_id: UUID,
) -> tuple[RevisionRequest | None, str | None]:
    revision = await get_revision_request(session, project_id, revision_id)
    if revision is None:
        return None, "RevisionRequest not found"
    if revision.status != RevisionRequestStatus.planned:
        return None, "RevisionRequest is not planned"
    revision.status = RevisionRequestStatus.rejected
    revision.rejected_at = datetime.now(UTC)
    add_project_event(
        session,
        project_id=project_id,
        event_type="revision.rejected",
        payload={"revision_request_id": revision.id},
        revision_request_id=revision_id,
    )
    await session.commit()
    await session.refresh(revision)
    return revision, None


async def apply_revision_request(
    *,
    session: AsyncSession,
    project_id: UUID,
    revision_id: UUID,
    task_ids: list[str] | None,
    storage: ObjectStorage,
) -> RevisionApplyResult:
    revision = await get_revision_request(session, project_id, revision_id)
    if revision is None:
        return RevisionApplyResult(None, [], "RevisionRequest not found", None)
    if revision.status != RevisionRequestStatus.planned:
        return RevisionApplyResult(None, [], None, "RevisionRequest is not planned")

    selected = _selected_tasks(revision, task_ids)
    if not selected:
        return RevisionApplyResult(revision, [], None, "No supported revision tasks selected")

    created: list[VersionReference] = []
    for task in selected:
        if task.target == RevisionTaskTarget.lyrics:
            lyrics = await _apply_lyrics_task(session, project_id, revision_id, task)
            if lyrics is None:
                return RevisionApplyResult(None, created, "LyricsVersion not found", None)
            created.append(_lyrics_reference(lyrics))
        elif task.target == RevisionTaskTarget.midi_melody:
            midi = await _apply_melody_task(session, project_id, revision_id, task, storage)
            if midi is None:
                return RevisionApplyResult(None, created, "MidiAssetVersion not found", None)
            created.append(_midi_reference(midi))
        elif task.target == RevisionTaskTarget.arrangement:
            arrangement = await _apply_arrangement_task(session, project_id, revision_id, task)
            if arrangement is None:
                return RevisionApplyResult(None, created, "ArrangementPlanVersion not found", None)
            created.append(_arrangement_reference(arrangement))

    revision.status = RevisionRequestStatus.applied
    revision.created_versions = [version.model_dump(mode="json") for version in created]
    revision.applied_at = datetime.now(UTC)
    add_project_event(
        session,
        project_id=project_id,
        event_type="revision.applied",
        payload={"created_versions": revision.created_versions},
        revision_request_id=revision_id,
    )
    await session.commit()
    await session.refresh(revision)
    return RevisionApplyResult(revision, created, None, None)


async def build_version_diff(
    session: AsyncSession,
    project_id: UUID,
    asset_type: str,
    left_id: UUID,
    right_id: UUID,
) -> tuple[VersionDiffRead | None, str | None]:
    if asset_type == "lyrics":
        left_lyrics = await get_lyrics_version(session, project_id, left_id)
        right_lyrics = await get_lyrics_version(session, project_id, right_id)
        if left_lyrics is None or right_lyrics is None:
            return None, "LyricsVersion not found"
        return build_lyrics_diff(left_lyrics, right_lyrics), None
    if asset_type == "midi_melody":
        left_midi = await get_midi_asset_version(session, project_id, left_id)
        right_midi = await get_midi_asset_version(session, project_id, right_id)
        if (
            left_midi is None
            or right_midi is None
            or left_midi.kind != MidiAssetKind.melody
            or right_midi.kind != MidiAssetKind.melody
        ):
            return None, "MidiAssetVersion not found"
        return build_midi_diff(left_midi, right_midi), None
    if asset_type == "arrangement":
        left_arrangement = await _get_arrangement(session, project_id, left_id)
        right_arrangement = await _get_arrangement(session, project_id, right_id)
        if left_arrangement is None or right_arrangement is None:
            return None, "ArrangementPlanVersion not found"
        return build_arrangement_diff(left_arrangement, right_arrangement), None
    if asset_type == "demo":
        left_demo = await get_demo_version(session, project_id, left_id)
        right_demo = await get_demo_version(session, project_id, right_id)
        if left_demo is None or right_demo is None:
            return None, "AudioDemoVersion not found"
        return build_demo_diff(left_demo, right_demo), None
    return None, "Unsupported asset_type"


async def restore_version(
    *,
    session: AsyncSession,
    project_id: UUID,
    asset_type: RestoreAssetType,
    version_id: UUID,
    storage: ObjectStorage,
) -> tuple[object | None, str | None]:
    if asset_type == "lyrics":
        source_lyrics = await get_lyrics_version(session, project_id, version_id)
        if source_lyrics is None:
            return None, "LyricsVersion not found"
        restored = await create_version_with_retry(
            session=session,
            project_id=project_id,
            load_next_version_number=partial(
                _next_lyrics_version_number,
                session,
                project_id,
            ),
            build_version=lambda version_number: LyricsVersion(
                project_id=str(project_id),
                song_spec_id=source_lyrics.song_spec_id,
                version_number=version_number,
                parent_version_id=source_lyrics.id,
                sections=source_lyrics.sections,
                hook_candidates=source_lyrics.hook_candidates,
            ),
        )
        add_project_event(
            session,
            project_id=project_id,
            event_type="version.restored",
            payload={"asset_type": asset_type, "source_version_id": source_lyrics.id},
            artifact_version_id=UUID(restored.id),
        )
        await session.commit()
        await session.refresh(restored)
        return restored, None
    if asset_type == "midi_melody":
        source_midi = await get_midi_asset_version(session, project_id, version_id)
        if source_midi is None or source_midi.kind != MidiAssetKind.melody:
            return None, "MidiAssetVersion not found"
        restored_midi = await _copy_midi_version(
            session=session,
            project_id=project_id,
            source=source_midi,
            storage=storage,
            source_revision_request_id=None,
        )
        add_project_event(
            session,
            project_id=project_id,
            event_type="version.restored",
            payload={"asset_type": asset_type, "source_version_id": source_midi.id},
            artifact_version_id=UUID(restored_midi.id),
        )
        await session.commit()
        await session.refresh(restored_midi)
        return restored_midi, None
    if asset_type == "arrangement":
        source_arrangement = await _get_arrangement(session, project_id, version_id)
        if source_arrangement is None:
            return None, "ArrangementPlanVersion not found"
        restored_arrangement = await create_version_with_retry(
            session=session,
            project_id=project_id,
            load_next_version_number=partial(
                _next_arrangement_version_number,
                session,
                project_id,
            ),
            build_version=lambda version_number: ArrangementPlanVersion(
                project_id=str(project_id),
                song_spec_id=source_arrangement.song_spec_id,
                lyrics_version_id=source_arrangement.lyrics_version_id,
                chord_version_id=source_arrangement.chord_version_id,
                midi_asset_ids=source_arrangement.midi_asset_ids,
                version_number=version_number,
                parent_version_id=source_arrangement.id,
                overview=source_arrangement.overview,
                sections=source_arrangement.sections,
                mix_notes=source_arrangement.mix_notes,
                reference_notes=source_arrangement.reference_notes,
            ),
        )
        add_project_event(
            session,
            project_id=project_id,
            event_type="version.restored",
            payload={"asset_type": asset_type, "source_version_id": source_arrangement.id},
            artifact_version_id=UUID(restored_arrangement.id),
        )
        await session.commit()
        await session.refresh(restored_arrangement)
        return restored_arrangement, None
    return None, "Unsupported asset_type"


def revision_request_to_read(revision: RevisionRequest) -> RevisionRequestRead:
    return RevisionRequestRead(
        id=UUID(revision.id),
        project_id=UUID(revision.project_id),
        feedback=revision.feedback,
        status=revision.status,
        tasks=[RevisionTask.model_validate(task) for task in revision.tasks],
        created_versions=[
            VersionReference.model_validate(version) for version in revision.created_versions
        ],
        applied_at=revision.applied_at,
        rejected_at=revision.rejected_at,
        created_at=revision.created_at,
        updated_at=revision.updated_at,
    )


def restored_version_to_read(
    asset_type: RestoreAssetType,
    version: object,
) -> VersionRestoreRead:
    if asset_type == "lyrics" and isinstance(version, LyricsVersion):
        return VersionRestoreRead(asset_type=asset_type, version=lyrics_version_to_read(version))
    if asset_type == "midi_melody" and isinstance(version, MidiAssetVersion):
        return VersionRestoreRead(asset_type=asset_type, version=midi_asset_to_read(version))
    if asset_type == "arrangement" and isinstance(version, ArrangementPlanVersion):
        return VersionRestoreRead(asset_type=asset_type, version=arrangement_plan_to_read(version))
    raise TypeError("Unsupported restored version")


async def _plan_revision_tasks(
    session: AsyncSession,
    project_id: UUID,
    feedback: str,
) -> list[RevisionTask]:
    normalized = feedback.lower()
    tasks: list[RevisionTask] = []
    section_id = _target_section_id(feedback)

    if _mentions_lyrics(normalized):
        lyrics = await get_latest_lyrics_version(session, project_id)
        tasks.append(
            _task(
                target=RevisionTaskTarget.lyrics,
                target_section_id=section_id,
                action="rewrite_lyrics",
                summary=f"Revise lyrics for {section_id or 'the most relevant section'}.",
                affected_asset_ids=[UUID(lyrics.id)] if lyrics else [],
                supported=lyrics is not None,
            )
        )
    if _mentions_melody(normalized):
        midi_by_kind = await get_latest_midi_assets_by_kind(session, project_id)
        melody = midi_by_kind.get(MidiAssetKind.melody)
        tasks.append(
            _task(
                target=RevisionTaskTarget.midi_melody,
                target_section_id=section_id,
                action="raise_melody",
                summary=f"Raise the melody guide for {section_id or 'the hook/chorus'}.",
                affected_asset_ids=[UUID(melody.id)] if melody else [],
                supported=melody is not None,
            )
        )
    if _mentions_arrangement(normalized):
        arrangement = await get_latest_arrangement_plan_version(session, project_id)
        tasks.append(
            _task(
                target=RevisionTaskTarget.arrangement,
                target_section_id=section_id,
                action="adjust_arrangement",
                summary=f"Update arrangement notes for {section_id or 'the requested sections'}.",
                affected_asset_ids=[UUID(arrangement.id)] if arrangement else [],
                supported=arrangement is not None,
            )
        )
    if not tasks:
        arrangement = await get_latest_arrangement_plan_version(session, project_id)
        tasks.append(
            _task(
                target=RevisionTaskTarget.arrangement,
                target_section_id=section_id,
                action="unsupported_feedback",
                summary="The request could not be mapped to lyrics, melody MIDI, or arrangement.",
                affected_asset_ids=[UUID(arrangement.id)] if arrangement else [],
                supported=False,
            )
        )
    return tasks


def _task(
    *,
    target: RevisionTaskTarget,
    target_section_id: str | None,
    action: str,
    summary: str,
    affected_asset_ids: list[UUID],
    supported: bool,
) -> RevisionTask:
    return RevisionTask(
        id=f"{target.value}_{action}",
        target=target,
        target_section_id=target_section_id,
        action=action,
        summary=summary,
        affected_asset_ids=affected_asset_ids,
        requires_demo_regeneration=supported,
        supported=supported,
    )


def _selected_tasks(revision: RevisionRequest, task_ids: list[str] | None) -> list[RevisionTask]:
    selected_ids = set(task_ids or [])
    tasks = [RevisionTask.model_validate(task) for task in revision.tasks]
    if selected_ids:
        tasks = [task for task in tasks if task.id in selected_ids]
    return [task for task in tasks if task.supported]


async def _apply_lyrics_task(
    session: AsyncSession,
    project_id: UUID,
    revision_id: UUID,
    task: RevisionTask,
) -> LyricsVersion | None:
    current = await get_latest_lyrics_version(session, project_id)
    if current is None:
        return None
    sections = [LyricSection.model_validate(section) for section in current.sections]
    revised_sections = [_revise_lyric_section(section, task) for section in sections]
    version = await create_version_with_retry(
        session=session,
        project_id=project_id,
        load_next_version_number=partial(_next_lyrics_version_number, session, project_id),
        build_version=lambda version_number: LyricsVersion(
            project_id=str(project_id),
            song_spec_id=current.song_spec_id,
            version_number=version_number,
            parent_version_id=current.id,
            source_revision_request_id=str(revision_id),
            sections=[section.model_dump() for section in revised_sections],
            hook_candidates=current.hook_candidates,
        ),
    )
    add_project_event(
        session,
        project_id=project_id,
        event_type="revision.version_created",
        payload={"asset_type": "lyrics", "task_id": task.id},
        revision_request_id=revision_id,
        artifact_version_id=UUID(version.id),
    )
    return version


async def _apply_melody_task(
    session: AsyncSession,
    project_id: UUID,
    revision_id: UUID,
    task: RevisionTask,
    storage: ObjectStorage,
) -> MidiAssetVersion | None:
    midi_by_kind = await get_latest_midi_assets_by_kind(session, project_id)
    current = midi_by_kind.get(MidiAssetKind.melody)
    if current is None:
        return None
    data = storage.get_bytes(current.storage_key)
    raised_data = _transpose_midi(data, semitones=2)
    def build_version(version_number: int) -> MidiAssetVersion:
        asset_id = str(uuid4())
        filename = f"melody-v{version_number}.mid"
        return MidiAssetVersion(
            id=asset_id,
            project_id=str(project_id),
            song_spec_id=current.song_spec_id,
            lyrics_version_id=current.lyrics_version_id,
            chord_version_id=current.chord_version_id,
            source_revision_request_id=str(revision_id),
            source_audio_upload_id=current.source_audio_upload_id,
            version_number=version_number,
            kind=MidiAssetKind.melody,
            storage_key=f"projects/{project_id}/midi/{asset_id}/{filename}",
            filename=filename,
            content_type=MIDI_CONTENT_TYPE,
            size_bytes=len(raised_data),
            checksum=sha256(raised_data).hexdigest(),
        )

    version = await create_version_with_retry(
        session=session,
        project_id=project_id,
        load_next_version_number=partial(
            _next_midi_version_number,
            session,
            project_id,
            MidiAssetKind.melody,
        ),
        build_version=build_version,
    )
    storage.put_bytes(version.storage_key, raised_data, MIDI_CONTENT_TYPE)
    add_project_event(
        session,
        project_id=project_id,
        event_type="revision.version_created",
        payload={"asset_type": "midi_melody", "task_id": task.id},
        revision_request_id=revision_id,
        artifact_version_id=UUID(version.id),
    )
    return version


async def _apply_arrangement_task(
    session: AsyncSession,
    project_id: UUID,
    revision_id: UUID,
    task: RevisionTask,
) -> ArrangementPlanVersion | None:
    current = await get_latest_arrangement_plan_version(session, project_id)
    if current is None:
        return None
    sections = [
        _revise_arrangement_section(ArrangementSection.model_validate(section), task)
        for section in current.sections
    ]
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
            song_spec_id=current.song_spec_id,
            lyrics_version_id=current.lyrics_version_id,
            chord_version_id=current.chord_version_id,
            midi_asset_ids=current.midi_asset_ids,
            version_number=version_number,
            parent_version_id=current.id,
            source_revision_request_id=str(revision_id),
            overview=f"{current.overview}\nRevision focus: {task.summary}",
            sections=[section.model_dump() for section in sections],
            mix_notes=current.mix_notes,
            reference_notes=f"{current.reference_notes}\nRevision note: {task.summary}",
        ),
    )
    add_project_event(
        session,
        project_id=project_id,
        event_type="revision.version_created",
        payload={"asset_type": "arrangement", "task_id": task.id},
        revision_request_id=revision_id,
        artifact_version_id=UUID(version.id),
    )
    return version


def _revise_lyric_section(section: LyricSection, task: RevisionTask) -> LyricSection:
    if task.target_section_id and task.target_section_id not in section.section_id.lower():
        return section
    text = f"{section.text}\nRevision: make this section more direct, vivid, and singable."
    return LyricSection(section_id=section.section_id, label=section.label, text=text)


def _revise_arrangement_section(
    section: ArrangementSection,
    task: RevisionTask,
) -> ArrangementSection:
    if task.target_section_id and task.target_section_id not in section.section_id.lower():
        return section
    lowered = task.summary.lower()
    instruments = section.instruments
    if "drum" in lowered or "鼓" in task.summary:
        instruments = [instrument for instrument in instruments if "drum" not in instrument.lower()]
        if not instruments:
            instruments = ["lead vocal", "guitar"]
    notes = f"{section.production_notes} Revision: {task.summary}"
    if "空" in task.summary or "sparse" in lowered:
        notes = f"{notes} Leave more space and reduce density."
    return ArrangementSection(
        section_id=section.section_id,
        label=section.label,
        instruments=instruments,
        energy_level=(
            max(1, section.energy_level - 1)
            if "空" in task.summary
            else section.energy_level
        ),
        production_notes=notes,
    )


async def _copy_midi_version(
    *,
    session: AsyncSession,
    project_id: UUID,
    source: MidiAssetVersion,
    storage: ObjectStorage,
    source_revision_request_id: UUID | None,
) -> MidiAssetVersion:
    data = storage.get_bytes(source.storage_key)

    def build_restored(version_number: int) -> MidiAssetVersion:
        asset_id = str(uuid4())
        filename = f"melody-v{version_number}.mid"
        return MidiAssetVersion(
            id=asset_id,
            project_id=str(project_id),
            song_spec_id=source.song_spec_id,
            lyrics_version_id=source.lyrics_version_id,
            chord_version_id=source.chord_version_id,
            source_revision_request_id=(
                str(source_revision_request_id) if source_revision_request_id else None
            ),
            source_audio_upload_id=source.source_audio_upload_id,
            version_number=version_number,
            kind=MidiAssetKind.melody,
            storage_key=f"projects/{project_id}/midi/{asset_id}/{filename}",
            filename=filename,
            content_type=source.content_type,
            size_bytes=len(data),
            checksum=sha256(data).hexdigest(),
        )

    restored = await create_version_with_retry(
        session=session,
        project_id=project_id,
        load_next_version_number=partial(
            _next_midi_version_number,
            session,
            project_id,
            MidiAssetKind.melody,
        ),
        build_version=build_restored,
    )
    storage.put_bytes(restored.storage_key, data, source.content_type)
    return restored


def _transpose_midi(data: bytes, *, semitones: int) -> bytes:
    midi = MidiFile(file=BytesIO(data))
    for track in midi.tracks:
        for message in track:
            if message.type in {"note_on", "note_off"}:
                message.note = max(0, min(127, int(message.note) + semitones))
    buffer = BytesIO()
    midi.save(file=buffer)
    return buffer.getvalue()


async def _get_arrangement(
    session: AsyncSession,
    project_id: UUID,
    version_id: UUID,
) -> ArrangementPlanVersion | None:
    statement: Select[tuple[ArrangementPlanVersion]] = select(ArrangementPlanVersion).where(
        ArrangementPlanVersion.id == str(version_id),
        ArrangementPlanVersion.project_id == str(project_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def _next_lyrics_version_number(session: AsyncSession, project_id: UUID) -> int:
    statement = select(func.max(LyricsVersion.version_number)).where(
        LyricsVersion.project_id == str(project_id)
    )
    result = await session.execute(statement)
    return int(result.scalar_one_or_none() or 0) + 1


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
    return int(result.scalar_one_or_none() or 0) + 1


async def _next_arrangement_version_number(session: AsyncSession, project_id: UUID) -> int:
    statement = select(func.max(ArrangementPlanVersion.version_number)).where(
        ArrangementPlanVersion.project_id == str(project_id)
    )
    result = await session.execute(statement)
    return int(result.scalar_one_or_none() or 0) + 1


def _lyrics_reference(version: LyricsVersion) -> VersionReference:
    return VersionReference(
        asset_type="lyrics",
        id=UUID(version.id),
        label=f"Lyrics v{version.version_number}",
        version_number=version.version_number,
        parent_version_id=UUID(version.parent_version_id) if version.parent_version_id else None,
        source_revision_request_id=(
            UUID(version.source_revision_request_id) if version.source_revision_request_id else None
        ),
    )


def _midi_reference(version: MidiAssetVersion) -> VersionReference:
    return VersionReference(
        asset_type="midi_melody",
        id=UUID(version.id),
        label=f"Melody MIDI v{version.version_number}",
        version_number=version.version_number,
        source_revision_request_id=(
            UUID(version.source_revision_request_id) if version.source_revision_request_id else None
        ),
    )


def _arrangement_reference(version: ArrangementPlanVersion) -> VersionReference:
    return VersionReference(
        asset_type="arrangement",
        id=UUID(version.id),
        label=f"Arrangement v{version.version_number}",
        version_number=version.version_number,
        parent_version_id=UUID(version.parent_version_id) if version.parent_version_id else None,
        source_revision_request_id=(
            UUID(version.source_revision_request_id) if version.source_revision_request_id else None
        ),
    )


def _mentions_lyrics(value: str) -> bool:
    return any(token in value for token in ("歌词", "词", "lyric", "line", "hook"))


def _mentions_melody(value: str) -> bool:
    return any(token in value for token in ("旋律", "melody", "抬高", "higher", "hook"))


def _mentions_arrangement(value: str) -> bool:
    return any(
        token in value
        for token in (
            "编曲",
            "鼓",
            "前奏",
            "桥段",
            "空",
            "靠前",
            "arrangement",
            "drum",
            "intro",
            "bridge",
        )
    )


def _target_section_id(feedback: str) -> str | None:
    normalized = feedback.lower()
    candidates = (
        ("副歌", "chorus"),
        ("chorus", "chorus"),
        ("桥段", "bridge"),
        ("bridge", "bridge"),
        ("前奏", "intro"),
        ("intro", "intro"),
        ("主歌", "verse"),
        ("verse", "verse"),
        ("hook", "hook"),
    )
    for token, section_id in candidates:
        if token in normalized or token in feedback:
            return section_id
    return None

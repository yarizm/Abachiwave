from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.models.composition import (
    ArrangementPlanVersion,
    ChordProgressionVersion,
    LyricsVersion,
    MidiAssetVersion,
)
from abachiwave.models.demo import AudioDemoVersion
from abachiwave.models.song_spec import (
    SongSpecStatus,
    SongSpecVersion,
    StructureChangePreview,
    StructureChangePreviewStatus,
)
from abachiwave.schemas.composition import (
    ArrangementPlan,
    ArrangementSection,
    ChordSection,
    HookCandidate,
    LyricLine,
    LyricSection,
    create_chord_event_id,
    create_lyric_line_id,
)
from abachiwave.schemas.song_specs import (
    SongSpecData,
    StructureSection,
    canonical_section_slug,
)
from abachiwave.schemas.structure import (
    StructureAssetImpact,
    StructureChangeRead,
    StructureChangeRequest,
    StructureCreatedVersion,
    StructureImpact,
    StructureRename,
    StructureSectionInput,
)
from abachiwave.services.composition import (
    _create_chord_progression_version,
    _create_lyrics_version,
)
from abachiwave.services.delivery import (
    _create_arrangement_plan_version,
    get_latest_arrangement_plan_version,
    get_latest_chord_progression_version,
    get_latest_lyrics_version,
    get_latest_midi_assets_by_kind,
)
from abachiwave.services.events import add_project_event
from abachiwave.services.song_specs import (
    _create_song_spec_version,
    get_song_spec_version,
    project_exists,
    song_spec_to_data,
)
from abachiwave.services.versioning import lock_project_for_version_write


class StructureResourceNotFoundError(RuntimeError):
    pass


class StructureConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class CurrentStructureAssets:
    lyrics: LyricsVersion | None
    chords: ChordProgressionVersion | None
    arrangement: ArrangementPlanVersion | None
    midi_assets: list[MidiAssetVersion]
    demo: AudioDemoVersion | None


async def change_project_structure(
    session: AsyncSession,
    project_id: UUID,
    payload: StructureChangeRequest,
) -> StructureChangeRead:
    if not await project_exists(session, project_id):
        raise StructureResourceNotFoundError("Project not found")
    source = await get_song_spec_version(session, project_id, payload.source_song_spec_id)
    if source is None:
        raise StructureResourceNotFoundError("SongSpec not found")
    if payload.preview_id is not None:
        await lock_project_for_version_write(session, project_id)
    await _require_current_approved_song_spec(session, project_id, source)
    _validate_section_sources(source, payload.sections)
    assets = await _load_current_assets(session, project_id)
    impact = _build_impact(source, payload.sections, assets)
    if not _has_structure_changes(impact):
        raise StructureConflictError("The proposed structure does not contain any changes")

    if payload.preview_id is None:
        created_preview = StructureChangePreview(
            project_id=str(project_id),
            source_song_spec_id=source.id,
            proposed_sections=[section.model_dump(mode="json") for section in payload.sections],
            impact=impact.model_dump(mode="json"),
        )
        session.add(created_preview)
        await session.commit()
        await session.refresh(created_preview)
        return _preview_to_read(created_preview, created_versions=[])

    loaded_preview = await _get_preview(session, project_id, payload.preview_id)
    if loaded_preview is None:
        raise StructureResourceNotFoundError("Structure preview not found")
    preview = loaded_preview
    if preview.status != StructureChangePreviewStatus.pending:
        raise StructureConflictError("Structure preview has already been applied")
    proposed_sections = [section.model_dump(mode="json") for section in payload.sections]
    if preview.source_song_spec_id != source.id or preview.proposed_sections != proposed_sections:
        raise StructureConflictError("Structure changed after preview; create a new preview")
    if preview.impact != impact.model_dump(mode="json"):
        raise StructureConflictError("Project assets changed after preview; create a new preview")

    try:
        created_versions = await _apply_structure_change(
            session=session,
            project_id=project_id,
            source=source,
            sections=payload.sections,
            assets=assets,
        )
        preview.status = StructureChangePreviewStatus.applied
        preview.applied_at = datetime.now(UTC)
        add_project_event(
            session,
            project_id=project_id,
            event_type="structure.applied",
            payload={
                "preview_id": preview.id,
                "source_song_spec_id": source.id,
                "section_ids": [section.section_id for section in payload.sections],
                "created_versions": [
                    version.model_dump(mode="json") for version in created_versions
                ],
                "requires_midi_regeneration": impact.requires_midi_regeneration,
                "requires_demo_regeneration": impact.requires_demo_regeneration,
            },
        )
        await session.commit()
        await session.refresh(preview)
    except Exception:
        await session.rollback()
        raise
    return _preview_to_read(preview, created_versions=created_versions)


async def _require_current_approved_song_spec(
    session: AsyncSession,
    project_id: UUID,
    source: SongSpecVersion,
) -> None:
    statement: Select[tuple[SongSpecVersion]] = (
        select(SongSpecVersion)
        .where(
            SongSpecVersion.project_id == str(project_id),
            SongSpecVersion.status == SongSpecStatus.approved,
        )
        .order_by(SongSpecVersion.version_number.desc())
        .limit(1)
    )
    result = await session.execute(statement)
    current = result.scalar_one_or_none()
    if current is None:
        raise StructureConflictError("Approve a SongSpec before editing the structure")
    if current.id != source.id:
        raise StructureConflictError("SongSpec changed; reload the workspace and preview again")


async def _load_current_assets(
    session: AsyncSession,
    project_id: UUID,
) -> CurrentStructureAssets:
    lyrics = await get_latest_lyrics_version(session, project_id)
    chords = await get_latest_chord_progression_version(session, project_id)
    arrangement = await get_latest_arrangement_plan_version(session, project_id)
    midi_assets = list((await get_latest_midi_assets_by_kind(session, project_id)).values())
    demo_statement: Select[tuple[AudioDemoVersion]] = (
        select(AudioDemoVersion)
        .where(AudioDemoVersion.project_id == str(project_id))
        .order_by(AudioDemoVersion.version_number.desc())
        .limit(1)
    )
    demo = (await session.execute(demo_statement)).scalar_one_or_none()
    return CurrentStructureAssets(
        lyrics=lyrics,
        chords=chords,
        arrangement=arrangement,
        midi_assets=midi_assets,
        demo=demo,
    )


def _build_impact(
    source: SongSpecVersion,
    proposed: list[StructureSectionInput],
    assets: CurrentStructureAssets,
) -> StructureImpact:
    current = [StructureSection.model_validate(section) for section in source.structure_sections]
    current_by_id = {section.section_id: section for section in current}
    proposed_sections = [
        StructureSection.model_validate(section.model_dump()) for section in proposed
    ]
    proposed_by_id = {section.section_id: section for section in proposed_sections}
    added = [section for section in proposed_sections if section.section_id not in current_by_id]
    removed = [section for section in current if section.section_id not in proposed_by_id]
    renamed = [
        StructureRename(
            section_id=section.section_id,
            before=current_by_id[section.section_id].label,
            after=section.label,
        )
        for section in proposed_sections
        if section.section_id in current_by_id
        and current_by_id[section.section_id].label != section.label
    ]
    shared_current = [
        section.section_id for section in current if section.section_id in proposed_by_id
    ]
    shared_proposed = [
        section.section_id for section in proposed_sections if section.section_id in current_by_id
    ]
    affected = [
        StructureAssetImpact(
            asset_type="song_spec",
            id=UUID(source.id),
            version_number=source.version_number,
            action="new_version",
        )
    ]
    for asset_type, version_asset in (
        ("lyrics", assets.lyrics),
        ("chords", assets.chords),
        ("arrangement", assets.arrangement),
    ):
        if version_asset is not None:
            affected.append(
                StructureAssetImpact(
                    asset_type=asset_type,
                    id=UUID(version_asset.id),
                    version_number=version_asset.version_number,
                    action="new_version",
                )
            )
    for midi_asset in sorted(assets.midi_assets, key=lambda item: str(item.kind)):
        affected.append(
            StructureAssetImpact(
                asset_type=f"midi_{midi_asset.kind}",
                id=UUID(midi_asset.id),
                version_number=midi_asset.version_number,
                action="regenerate",
            )
        )
    if assets.demo is not None:
        affected.append(
            StructureAssetImpact(
                asset_type="demo",
                id=UUID(assets.demo.id),
                version_number=assets.demo.version_number,
                action="regenerate",
            )
        )
    warnings: list[str] = []
    if assets.midi_assets:
        warnings.append("Existing MIDI files keep their history but must be regenerated.")
    if assets.demo is not None:
        warnings.append("Existing demos remain playable but no longer match the current structure.")
    return StructureImpact(
        added_sections=added,
        removed_sections=removed,
        renamed_sections=renamed,
        reordered=shared_current != shared_proposed,
        affected_assets=affected,
        requires_midi_regeneration=bool(assets.midi_assets),
        requires_demo_regeneration=assets.demo is not None,
        warnings=warnings,
    )


async def _apply_structure_change(
    *,
    session: AsyncSession,
    project_id: UUID,
    source: SongSpecVersion,
    sections: list[StructureSectionInput],
    assets: CurrentStructureAssets,
) -> list[StructureCreatedVersion]:
    stable_sections = [
        StructureSection.model_validate(section.model_dump()) for section in sections
    ]
    source_data = song_spec_to_data(source)
    data = SongSpecData(
        **{
            **source_data.model_dump(exclude={"song_structure", "structure_sections"}),
            "song_structure": [section.label for section in stable_sections],
            "structure_sections": stable_sections,
        }
    )
    song_spec = await _create_song_spec_version(
        session=session,
        project_id=project_id,
        intake_id=UUID(source.intake_id) if source.intake_id else None,
        data=data,
        parent_version_id=UUID(source.id),
        commit=False,
    )
    await session.execute(
        update(SongSpecVersion)
        .where(
            SongSpecVersion.project_id == str(project_id),
            SongSpecVersion.status == SongSpecStatus.approved,
        )
        .values(status=SongSpecStatus.superseded)
    )
    song_spec.status = SongSpecStatus.approved
    song_spec.approved_at = datetime.now(UTC)
    created = [
        StructureCreatedVersion(
            asset_type="song_spec",
            id=UUID(song_spec.id),
            version_number=song_spec.version_number,
            parent_version_id=UUID(source.id),
        )
    ]

    lyrics = None
    if assets.lyrics is not None:
        lyrics = await _create_lyrics_version(
            session=session,
            project_id=project_id,
            song_spec_id=UUID(song_spec.id),
            sections=_remap_lyrics(assets.lyrics, sections),
            hook_candidates=[
                HookCandidate.model_validate(candidate)
                for candidate in assets.lyrics.hook_candidates
            ],
            parent_version_id=UUID(assets.lyrics.id),
            commit=False,
        )
        created.append(
            StructureCreatedVersion(
                asset_type="lyrics",
                id=UUID(lyrics.id),
                version_number=lyrics.version_number,
                parent_version_id=UUID(assets.lyrics.id),
            )
        )

    chords = None
    if assets.chords is not None:
        chords = await _create_chord_progression_version(
            session=session,
            project_id=project_id,
            song_spec_id=UUID(song_spec.id),
            lyrics_version_id=UUID(lyrics.id) if lyrics else None,
            key=assets.chords.key,
            tempo_bpm=assets.chords.tempo_bpm,
            time_signature=assets.chords.time_signature,
            sections=_remap_chords(assets.chords, sections),
            parent_version_id=UUID(assets.chords.id),
            commit=False,
        )
        created.append(
            StructureCreatedVersion(
                asset_type="chords",
                id=UUID(chords.id),
                version_number=chords.version_number,
                parent_version_id=UUID(assets.chords.id),
            )
        )

    if assets.arrangement is not None and lyrics is not None and chords is not None:
        arrangement = await _create_arrangement_plan_version(
            session=session,
            project_id=project_id,
            song_spec_id=UUID(song_spec.id),
            lyrics_version_id=UUID(lyrics.id),
            chord_version_id=UUID(chords.id),
            midi_asset_ids=[UUID(asset_id) for asset_id in assets.arrangement.midi_asset_ids],
            plan=ArrangementPlan(
                overview=assets.arrangement.overview,
                sections=_remap_arrangement(assets.arrangement, sections),
                mix_notes=assets.arrangement.mix_notes,
                reference_notes=assets.arrangement.reference_notes,
            ),
            parent_version_id=UUID(assets.arrangement.id),
            commit=False,
        )
        created.append(
            StructureCreatedVersion(
                asset_type="arrangement",
                id=UUID(arrangement.id),
                version_number=arrangement.version_number,
                parent_version_id=UUID(assets.arrangement.id),
            )
        )
    return created


def _find_source[S](existing: dict[str, S], target: StructureSectionInput) -> S | None:
    key = canonical_section_slug(target.source_section_id or target.section_id)
    source = existing.get(key)
    if source is None and key.startswith("section-") and key.removeprefix("section-").isdigit():
        # Chinese-only labels: generation falls back to "section" while
        # build_structure_sections numbers them "section-N".
        source = existing.get("section")
    return source


def _remap_lyrics(
    version: LyricsVersion,
    sections: list[StructureSectionInput],
) -> list[LyricSection]:
    existing = {
        canonical_section_slug(section.section_id): section
        for section in (LyricSection.model_validate(item) for item in version.sections)
    }
    remapped: list[LyricSection] = []
    for target in sections:
        source = _find_source(existing, target)
        if source is None:
            text = f"Draft pending for {target.label}."
            lines = [
                LyricLine(
                    line_id=create_lyric_line_id(target.section_id, 0),
                    text=text,
                )
            ]
        else:
            lines = [
                LyricLine(
                    line_id=(
                        line.line_id
                        if target.section_id == source.section_id
                        else create_lyric_line_id(target.section_id, index)
                    ),
                    text=line.text,
                    rhyme_label=line.rhyme_label,
                )
                for index, line in enumerate(source.lines)
            ]
            text = "\n".join(line.text for line in lines)
        remapped.append(
            LyricSection(
                section_id=target.section_id,
                label=target.label,
                text=text,
                lines=lines,
            )
        )
    return remapped


def _remap_chords(
    version: ChordProgressionVersion,
    sections: list[StructureSectionInput],
) -> list[ChordSection]:
    existing = {
        canonical_section_slug(section.section_id): section
        for section in (ChordSection.model_validate(item) for item in version.sections)
    }
    remapped: list[ChordSection] = []
    for target in sections:
        source = _find_source(existing, target)
        if source is None:
            remapped.append(
                ChordSection(
                    section_id=target.section_id,
                    label=target.label,
                    bars=4,
                    chords=["N.C."],
                )
            )
            continue
        measures = []
        for measure in source.measures:
            events = [
                {
                    "event_id": create_chord_event_id(
                        target.section_id,
                        measure.measure_number,
                        event_index,
                    ),
                    "measure": measure.measure_number,
                    "beat": event.beat,
                    "duration_beats": event.duration_beats,
                    "symbol": event.symbol,
                    "inversion": event.inversion,
                }
                for event_index, event in enumerate(measure.events)
            ]
            measures.append(
                {
                    "measure_number": measure.measure_number,
                    "events": events,
                }
            )
        remapped.append(
            ChordSection(
                section_id=target.section_id,
                label=target.label,
                measures=measures,
            )
        )
    return remapped


def _remap_arrangement(
    version: ArrangementPlanVersion,
    sections: list[StructureSectionInput],
) -> list[ArrangementSection]:
    existing = {
        canonical_section_slug(section.section_id): section
        for section in (ArrangementSection.model_validate(item) for item in version.sections)
    }
    remapped: list[ArrangementSection] = []
    for target in sections:
        source = _find_source(existing, target)
        if source is None:
            remapped.append(
                ArrangementSection(
                    section_id=target.section_id,
                    label=target.label,
                    instruments=["TBD"],
                    energy_level=5,
                    production_notes=f"Production notes pending for {target.label}.",
                )
            )
            continue
        remapped.append(
            ArrangementSection(
                section_id=target.section_id,
                label=target.label,
                instruments=source.instruments,
                energy_level=source.energy_level,
                production_notes=source.production_notes,
            )
        )
    return remapped


def _validate_section_sources(
    source: SongSpecVersion,
    proposed: list[StructureSectionInput],
) -> None:
    current_ids = {
        StructureSection.model_validate(section).section_id for section in source.structure_sections
    }
    remapped_existing = sorted(
        section.section_id
        for section in proposed
        if section.section_id in current_ids
        and section.source_section_id is not None
        and section.source_section_id != section.section_id
    )
    if remapped_existing:
        raise StructureConflictError(
            "source_section_id can only be used for new duplicated sections"
        )
    invalid = sorted(
        {
            section.source_section_id
            for section in proposed
            if section.source_section_id is not None
            and section.source_section_id not in current_ids
        }
    )
    if invalid:
        raise StructureConflictError(
            f"Duplicate source sections no longer exist: {', '.join(invalid)}"
        )


def _has_structure_changes(impact: StructureImpact) -> bool:
    return bool(
        impact.added_sections
        or impact.removed_sections
        or impact.renamed_sections
        or impact.reordered
    )


async def _get_preview(
    session: AsyncSession,
    project_id: UUID,
    preview_id: UUID,
) -> StructureChangePreview | None:
    statement: Select[tuple[StructureChangePreview]] = select(StructureChangePreview).where(
        StructureChangePreview.id == str(preview_id),
        StructureChangePreview.project_id == str(project_id),
    )
    return (await session.execute(statement)).scalar_one_or_none()


def _preview_to_read(
    preview: StructureChangePreview,
    *,
    created_versions: list[StructureCreatedVersion],
) -> StructureChangeRead:
    proposed = [
        StructureSectionInput.model_validate(section) for section in preview.proposed_sections
    ]
    return StructureChangeRead(
        preview_id=UUID(preview.id),
        status=("applied" if preview.status == StructureChangePreviewStatus.applied else "preview"),
        source_song_spec_id=UUID(preview.source_song_spec_id),
        sections=[StructureSection.model_validate(section.model_dump()) for section in proposed],
        impact=StructureImpact.model_validate(preview.impact),
        created_versions=created_versions,
        created_at=preview.created_at,
        applied_at=preview.applied_at,
    )

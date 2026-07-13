from typing import cast
from uuid import UUID

from abachiwave.models.composition import (
    ArrangementPlanVersion,
    LyricsVersion,
    MidiAssetKind,
    MidiAssetVersion,
)
from abachiwave.models.demo import AudioDemoVersion
from abachiwave.schemas.revisions import (
    VersionAssetType,
    VersionDiffChange,
    VersionDiffRead,
    VersionEndpointReference,
)

DiffableVersion = LyricsVersion | MidiAssetVersion | ArrangementPlanVersion | AudioDemoVersion


def build_lyrics_diff(left: LyricsVersion, right: LyricsVersion) -> VersionDiffRead:
    left_sections = {section["section_id"]: section for section in left.sections}
    right_sections = {section["section_id"]: section for section in right.sections}
    changes: list[VersionDiffChange] = []
    for section_id in sorted(set(left_sections) | set(right_sections)):
        left_text = str(left_sections.get(section_id, {}).get("text", ""))
        right_text = str(right_sections.get(section_id, {}).get("text", ""))
        if left_text != right_text:
            changes.append(
                VersionDiffChange(
                    field=f"sections.{section_id}.text",
                    label=f"{section_id} lyrics",
                    left=left_text,
                    right=right_text,
                    summary="Lyric text changed.",
                )
            )
    return _build_diff("lyrics", left, right, changes)


def build_midi_diff(left: MidiAssetVersion, right: MidiAssetVersion) -> VersionDiffRead:
    changes = [
        VersionDiffChange(
            field="checksum",
            label="MIDI checksum",
            left=left.checksum,
            right=right.checksum,
            summary=(
                "MIDI file content changed."
                if left.checksum != right.checksum
                else "MIDI file content is unchanged."
            ),
        )
    ]
    if left.size_bytes != right.size_bytes:
        changes.append(
            VersionDiffChange(
                field="size_bytes",
                label="File size",
                left=str(left.size_bytes),
                right=str(right.size_bytes),
                summary="MIDI file size changed.",
            )
        )
    return _build_diff("midi_melody", left, right, changes)


def build_arrangement_diff(
    left: ArrangementPlanVersion,
    right: ArrangementPlanVersion,
) -> VersionDiffRead:
    changes: list[VersionDiffChange] = []
    for field in ("overview", "mix_notes", "reference_notes"):
        left_value = str(getattr(left, field))
        right_value = str(getattr(right, field))
        if left_value != right_value:
            changes.append(
                VersionDiffChange(
                    field=field,
                    label=field.replace("_", " "),
                    left=left_value,
                    right=right_value,
                    summary="Arrangement text changed.",
                )
            )
    if left.sections != right.sections:
        changes.append(
            VersionDiffChange(
                field="sections",
                label="Arrangement sections",
                left=str(left.sections),
                right=str(right.sections),
                summary="Arrangement section details changed.",
            )
        )
    return _build_diff("arrangement", left, right, changes)


def build_demo_diff(left: AudioDemoVersion, right: AudioDemoVersion) -> VersionDiffRead:
    changes = [
        VersionDiffChange(
            field="checksum",
            label="Audio checksum",
            left=left.checksum,
            right=right.checksum,
            summary=(
                "Demo audio content changed."
                if left.checksum != right.checksum
                else "Demo audio content is unchanged."
            ),
        ),
        VersionDiffChange(
            field="duration_seconds",
            label="Duration",
            left=str(left.duration_seconds),
            right=str(right.duration_seconds),
            summary="Demo duration comparison.",
        ),
    ]
    return _build_diff("demo", left, right, changes)


def _build_diff(
    asset_type: str,
    left: DiffableVersion,
    right: DiffableVersion,
    changes: list[VersionDiffChange],
) -> VersionDiffRead:
    return VersionDiffRead(
        asset_type=cast(VersionAssetType, asset_type),
        left=_endpoint_ref(left),
        right=_endpoint_ref(right),
        summary=f"{len(changes)} changes detected." if changes else "No changes detected.",
        changes=changes,
    )


def _endpoint_ref(version: DiffableVersion) -> VersionEndpointReference:
    label = f"v{version.version_number}"
    if isinstance(version, LyricsVersion):
        label = f"Lyrics v{version.version_number}"
    elif isinstance(version, MidiAssetVersion):
        label = f"{MidiAssetKind(version.kind).value.title()} MIDI v{version.version_number}"
    elif isinstance(version, ArrangementPlanVersion):
        label = f"Arrangement v{version.version_number}"
    elif isinstance(version, AudioDemoVersion):
        label = f"Demo v{version.version_number}"
    return VersionEndpointReference(
        id=UUID(version.id),
        label=label,
        version_number=version.version_number,
        created_at=version.created_at,
    )

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.models.composition import ExportBundleStatus, MidiAssetKind
from abachiwave.models.demo import GenerationRunStatus
from abachiwave.models.project import Project
from abachiwave.schemas.review import (
    ProjectReviewItem,
    ProjectReviewRead,
    ProjectReviewStatus,
    ReviewItemStatus,
)
from abachiwave.services.delivery import build_asset_tree, list_export_bundles
from abachiwave.services.demo import list_demo_versions, list_generation_runs


async def build_project_review(
    session: AsyncSession,
    project_id: UUID,
) -> ProjectReviewRead | None:
    project = await session.get(Project, str(project_id))
    if project is None:
        return None

    asset_tree = await build_asset_tree(session, project_id)
    demos = await list_demo_versions(session, project_id)
    exports = await list_export_bundles(session, project_id)
    runs = await list_generation_runs(session, project_id)

    current = asset_tree.current
    missing = set(asset_tree.missing_prerequisites)
    midi_kinds = {MidiAssetKind(asset.kind) for asset in current.midi_assets if asset.kind}
    required_midi = {MidiAssetKind.chord, MidiAssetKind.melody, MidiAssetKind.hook}
    ready_exports = [bundle for bundle in exports if bundle.status == ExportBundleStatus.ready]
    failed_exports = [bundle for bundle in exports if bundle.status == ExportBundleStatus.failed]
    active_runs = [
        run
        for run in runs
        if run.status in {GenerationRunStatus.queued, GenerationRunStatus.running}
    ]
    failed_runs = [run for run in runs if run.status == GenerationRunStatus.failed]

    items = [
        _item(
            "song_spec",
            "Approved SongSpec",
            "pass" if current.song_spec else "fail",
            (
                f"Using {current.song_spec.label}."
                if current.song_spec
                else "Approve a complete SongSpec before generating assets."
            ),
            18,
        ),
        _item(
            "lyrics",
            "Lyrics",
            "pass" if current.lyrics else "fail",
            (
                f"Using {current.lyrics.label}."
                if current.lyrics
                else "Generate or restore a lyrics version."
            ),
            12,
        ),
        _item(
            "chords",
            "Chords",
            "pass" if current.chords else "fail",
            (
                f"Using {current.chords.label}."
                if current.chords
                else "Generate or restore a chord progression."
            ),
            12,
        ),
        _midi_item(midi_kinds, required_midi),
        _item(
            "arrangement",
            "Arrangement",
            "pass" if current.arrangement else "fail",
            (
                f"Using {current.arrangement.label}."
                if current.arrangement
                else "Generate an arrangement plan from the complete asset chain."
            ),
            14,
        ),
        _demo_item(has_demo=bool(demos), missing=missing, active_run_count=len(active_runs)),
        _export_item(
            has_ready_export=bool(ready_exports),
            failed_export_count=len(failed_exports),
            missing=missing,
        ),
        _run_item(active_count=len(active_runs), failed_count=len(failed_runs)),
    ]
    score = _score(items)
    return ProjectReviewRead(
        project_id=project_id,
        status=_review_status(items, score),
        score=score,
        items=items,
        next_actions=_next_actions(items),
        generated_at=datetime.now(UTC),
    )


def _item(
    item_id: str,
    label: str,
    status: ReviewItemStatus,
    detail: str,
    weight: int,
) -> ProjectReviewItem:
    return ProjectReviewItem(
        id=item_id,
        label=label,
        status=status,
        detail=detail,
        weight=weight,
    )


def _midi_item(
    midi_kinds: set[MidiAssetKind],
    required_midi: set[MidiAssetKind],
) -> ProjectReviewItem:
    missing = sorted(kind.value for kind in required_midi - midi_kinds)
    if not missing:
        return _item("midi", "MIDI assets", "pass", "Chord, melody, and hook MIDI exist.", 16)
    if midi_kinds:
        return _item(
            "midi",
            "MIDI assets",
            "warning",
            f"Missing MIDI kinds: {', '.join(missing)}.",
            16,
        )
    return _item("midi", "MIDI assets", "fail", "Generate chord, melody, and hook MIDI.", 16)


def _demo_item(
    *,
    has_demo: bool,
    missing: set[str],
    active_run_count: int,
) -> ProjectReviewItem:
    if has_demo:
        return _item("demo", "Demo", "pass", "At least one playable demo exists.", 10)
    if active_run_count:
        return _item("demo", "Demo", "warning", "A generation task is still running.", 10)
    if not missing:
        return _item("demo", "Demo", "warning", "Generate a demo for listening review.", 10)
    return _item("demo", "Demo", "fail", "Complete the asset chain before generating a demo.", 10)


def _export_item(
    *,
    has_ready_export: bool,
    failed_export_count: int,
    missing: set[str],
) -> ProjectReviewItem:
    if has_ready_export:
        return _item("export", "Export bundle", "pass", "A ready ZIP export exists.", 14)
    if failed_export_count:
        return _item("export", "Export bundle", "warning", "The latest export attempt failed.", 14)
    if not missing:
        return _item("export", "Export bundle", "warning", "Create a ZIP export package.", 14)
    return _item("export", "Export bundle", "fail", "Resolve missing prerequisites first.", 14)


def _run_item(*, active_count: int, failed_count: int) -> ProjectReviewItem:
    if active_count:
        return _item(
            "generation_runs",
            "Task health",
            "warning",
            f"{active_count} generation task is still active.",
            4,
        )
    if failed_count:
        return _item(
            "generation_runs",
            "Task health",
            "warning",
            f"{failed_count} generation task has failed and may need retry.",
            4,
        )
    return _item("generation_runs", "Task health", "pass", "No active or failed tasks.", 4)


def _score(items: list[ProjectReviewItem]) -> int:
    total = sum(item.weight for item in items)
    earned = 0.0
    for item in items:
        if item.status == "pass":
            earned += item.weight
        elif item.status == "warning":
            earned += item.weight * 0.5
    return round((earned / total) * 100) if total else 0


def _review_status(
    items: list[ProjectReviewItem],
    score: int,
) -> ProjectReviewStatus:
    required_failures = {
        item.id for item in items if item.status == "fail" and item.id != "demo"
    }
    if required_failures:
        return "blocked"
    if score >= 85:
        return "ready"
    return "needs_work"


def _next_actions(items: list[ProjectReviewItem]) -> list[str]:
    return [item.detail for item in items if item.status in {"fail", "warning"}][:5]

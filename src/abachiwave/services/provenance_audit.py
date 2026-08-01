from collections import defaultdict
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.models.composition import (
    ArrangementPlanVersion,
    ChordProgressionVersion,
    LyricsVersion,
    MidiAssetVersion,
)
from abachiwave.models.demo import AudioDemoVersion
from abachiwave.models.song_spec import SongSpecVersion
from abachiwave.services.events import add_project_event

type AssetModel = (
    type[LyricsVersion]
    | type[ChordProgressionVersion]
    | type[MidiAssetVersion]
    | type[ArrangementPlanVersion]
    | type[AudioDemoVersion]
)
FindingStatus = Literal["repairable", "repaired", "unresolved", "concurrent_change"]
ASSET_MODELS: tuple[tuple[str, AssetModel], ...] = (
    ("lyrics", LyricsVersion),
    ("chords", ChordProgressionVersion),
    ("midi", MidiAssetVersion),
    ("arrangement", ArrangementPlanVersion),
    ("demo", AudioDemoVersion),
)


class ProvenanceFinding(BaseModel):
    asset_type: str
    asset_id: UUID
    project_id: UUID
    current_song_spec_id: UUID
    inferred_song_spec_id: UUID | None
    reason: str
    status: FindingStatus


class ProvenanceAuditReport(BaseModel):
    scanned: int
    repairable: int
    repaired: int
    unresolved: int
    findings: list[ProvenanceFinding]


async def audit_asset_provenance(
    session: AsyncSession,
    *,
    project_id: UUID | None = None,
    apply: bool = False,
) -> ProvenanceAuditReport:
    specs_by_project = await _load_song_specs(session, project_id)
    findings: list[ProvenanceFinding] = []
    scanned = 0
    repaired_by_project: dict[UUID, list[UUID]] = defaultdict(list)

    for asset_type, model in ASSET_MODELS:
        statement: Select[tuple[object]] = select(model)
        if project_id is not None:
            statement = statement.where(model.project_id == str(project_id))
        assets = (await session.execute(statement)).scalars().all()
        scanned += len(assets)
        for raw_asset in assets:
            asset = cast(
                LyricsVersion
                | ChordProgressionVersion
                | MidiAssetVersion
                | ArrangementPlanVersion
                | AudioDemoVersion,
                raw_asset,
            )
            finding = _find_provenance_issue(
                asset_type=asset_type,
                asset_id=UUID(asset.id),
                project_id=UUID(asset.project_id),
                song_spec_id=UUID(asset.song_spec_id),
                created_at=asset.created_at,
                specs=specs_by_project.get(UUID(asset.project_id), []),
            )
            if finding is None:
                continue
            if apply and finding.inferred_song_spec_id is not None:
                result = await session.execute(
                    update(model)
                    .where(
                        model.id == str(finding.asset_id),
                        model.song_spec_id == str(finding.current_song_spec_id),
                    )
                    .values(song_spec_id=str(finding.inferred_song_spec_id))
                )
                if cast(int, getattr(result, "rowcount", 0)) == 1:
                    finding.status = "repaired"
                    repaired_by_project[finding.project_id].append(finding.asset_id)
                else:
                    finding.status = "concurrent_change"
                    finding.reason = "Asset provenance changed after the audit snapshot"
            findings.append(finding)

    if apply:
        for repaired_project_id, asset_ids in repaired_by_project.items():
            add_project_event(
                session,
                project_id=repaired_project_id,
                event_type="provenance.repaired",
                payload={
                    "asset_ids": [str(asset_id) for asset_id in asset_ids],
                    "repaired_count": len(asset_ids),
                },
            )
        await session.commit()

    return ProvenanceAuditReport(
        scanned=scanned,
        repairable=sum(finding.inferred_song_spec_id is not None for finding in findings),
        repaired=sum(finding.status == "repaired" for finding in findings),
        unresolved=sum(
            finding.status in {"unresolved", "concurrent_change"} for finding in findings
        ),
        findings=findings,
    )


async def _load_song_specs(
    session: AsyncSession,
    project_id: UUID | None,
) -> dict[UUID, list[SongSpecVersion]]:
    statement: Select[tuple[SongSpecVersion]] = select(SongSpecVersion)
    if project_id is not None:
        statement = statement.where(SongSpecVersion.project_id == str(project_id))
    statement = statement.order_by(
        SongSpecVersion.project_id,
        SongSpecVersion.approved_at.desc(),
        SongSpecVersion.version_number.desc(),
    )
    grouped: dict[UUID, list[SongSpecVersion]] = defaultdict(list)
    for song_spec in (await session.execute(statement)).scalars().all():
        grouped[UUID(song_spec.project_id)].append(song_spec)
    return grouped


def _find_provenance_issue(
    *,
    asset_type: str,
    asset_id: UUID,
    project_id: UUID,
    song_spec_id: UUID,
    created_at: datetime,
    specs: list[SongSpecVersion],
) -> ProvenanceFinding | None:
    referenced = next((spec for spec in specs if spec.id == str(song_spec_id)), None)
    asset_created_at = _utc(created_at)
    if referenced is not None and referenced.approved_at is not None:
        if asset_created_at >= _utc(referenced.approved_at):
            return None
        reason = "Asset predates the approval of its referenced SongSpec"
    else:
        reason = "Referenced SongSpec has no approval timestamp"

    candidates = [
        spec
        for spec in specs
        if spec.approved_at is not None and _utc(spec.approved_at) <= asset_created_at
    ]
    inferred: UUID | None = None
    if candidates:
        latest_approved_at = max(_utc(spec.approved_at) for spec in candidates if spec.approved_at)
        latest = [
            spec
            for spec in candidates
            if spec.approved_at is not None and _utc(spec.approved_at) == latest_approved_at
        ]
        if len(latest) == 1:
            inferred = UUID(latest[0].id)
        else:
            reason = "Multiple SongSpecs share the latest safe approval timestamp"
    else:
        reason = "No previously approved SongSpec can be inferred safely"

    return ProvenanceFinding(
        asset_type=asset_type,
        asset_id=asset_id,
        project_id=project_id,
        current_song_spec_id=song_spec_id,
        inferred_song_spec_id=inferred,
        reason=reason,
        status="repairable" if inferred else "unresolved",
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

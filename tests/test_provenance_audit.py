from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.models.composition import LyricsVersion
from abachiwave.models.project import Project
from abachiwave.models.revision import ProjectEvent
from abachiwave.models.song_spec import SongSpecStatus, SongSpecVersion
from abachiwave.services.provenance_audit import audit_asset_provenance


@pytest.mark.asyncio
async def test_provenance_audit_dry_run_and_safe_apply(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    project_id = uuid4()
    old_spec_id = uuid4()
    new_spec_id = uuid4()
    approved_at = datetime(2026, 1, 1, tzinfo=UTC)
    asset_created_at = approved_at + timedelta(hours=1)
    new_approved_at = approved_at + timedelta(hours=2)

    async with session_factory() as session:
        session.add(Project(id=str(project_id), name="Provenance audit"))
        session.add_all(
            [
                SongSpecVersion(
                    id=str(old_spec_id),
                    project_id=str(project_id),
                    version_number=1,
                    status=SongSpecStatus.superseded,
                    approved_at=approved_at,
                    created_at=approved_at,
                ),
                SongSpecVersion(
                    id=str(new_spec_id),
                    project_id=str(project_id),
                    version_number=2,
                    status=SongSpecStatus.approved,
                    approved_at=new_approved_at,
                    created_at=new_approved_at - timedelta(minutes=5),
                ),
            ]
        )
        lyrics = LyricsVersion(
            project_id=str(project_id),
            song_spec_id=str(new_spec_id),
            version_number=1,
            sections=[],
            hook_candidates=[],
            created_at=asset_created_at,
        )
        session.add(lyrics)
        await session.commit()
        await session.refresh(lyrics)

        dry_run = await audit_asset_provenance(session, project_id=project_id)
        assert dry_run.scanned == 1
        assert dry_run.repairable == 1
        assert dry_run.repaired == 0
        assert dry_run.unresolved == 0
        assert dry_run.findings[0].inferred_song_spec_id == old_spec_id
        await session.refresh(lyrics)
        assert lyrics.song_spec_id == str(new_spec_id)

        applied = await audit_asset_provenance(session, project_id=project_id, apply=True)
        assert applied.repaired == 1
        assert applied.unresolved == 0
        await session.refresh(lyrics)
        assert lyrics.song_spec_id == str(old_spec_id)
        events = list(
            (
                await session.execute(
                    select(ProjectEvent).where(ProjectEvent.project_id == str(project_id))
                )
            )
            .scalars()
            .all()
        )
        assert events[-1].event_type == "provenance.repaired"
        assert events[-1].payload["repaired_count"] == 1


@pytest.mark.asyncio
async def test_provenance_audit_reports_unresolved_and_honors_project_filter(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    included_project_id = uuid4()
    excluded_project_id = uuid4()
    approved_at = datetime(2026, 1, 2, tzinfo=UTC)

    async with session_factory() as session:
        for project_id in (included_project_id, excluded_project_id):
            song_spec_id = uuid4()
            session.add(Project(id=str(project_id), name=f"Project {project_id}"))
            session.add(
                SongSpecVersion(
                    id=str(song_spec_id),
                    project_id=str(project_id),
                    version_number=1,
                    status=SongSpecStatus.approved,
                    approved_at=approved_at,
                    created_at=approved_at,
                )
            )
            session.add(
                LyricsVersion(
                    project_id=str(project_id),
                    song_spec_id=str(song_spec_id),
                    version_number=1,
                    sections=[],
                    hook_candidates=[],
                    created_at=approved_at - timedelta(hours=1),
                )
            )
        await session.commit()

        report = await audit_asset_provenance(session, project_id=included_project_id, apply=True)

    assert report.scanned == 1
    assert report.repairable == 0
    assert report.repaired == 0
    assert report.unresolved == 1
    assert report.findings[0].project_id == included_project_id
    assert report.findings[0].status == "unresolved"

import sqlite3
from pathlib import Path

from alembic.command import upgrade
from alembic.config import Config


def test_alembic_migration_smoke(tmp_path: Path) -> None:
    db_path = tmp_path / "migration-smoke.db"
    config = Config("alembic.ini")
    config.set_main_option("script_location", "migrations")
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")

    upgrade(config, "head")

    assert db_path.exists()
    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        }
    assert {
        "projects",
        "idea_intakes",
        "song_spec_versions",
        "lyrics_versions",
        "chord_progression_versions",
        "midi_asset_versions",
        "arrangement_plan_versions",
        "export_bundles",
        "generation_runs",
        "audio_demo_versions",
        "audio_uploads",
        "project_comments",
        "revision_requests",
        "project_events",
    }.issubset(tables)
    with sqlite3.connect(db_path) as connection:
        demo_columns = {
            row[1]
            for row in connection.execute("pragma table_info(audio_demo_versions)").fetchall()
        }
    assert "waveform_peaks" in demo_columns
    with sqlite3.connect(db_path) as connection:
        indexes = {
            row[0]
            for row in connection.execute(
                "select name from sqlite_master where type = 'index'"
            ).fetchall()
        }
    assert {
        "ix_projects_created_at",
        "ix_audio_uploads_project_created",
        "ix_project_comments_project_created",
        "ix_revision_requests_project_created",
        "ix_project_events_project_created",
        "ix_generation_runs_project_created",
        "ix_audio_demo_versions_project_created",
        "ix_export_bundles_project_created",
    }.issubset(indexes)

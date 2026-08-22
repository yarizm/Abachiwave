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
        "audio_markers",
        "audio_derivatives",
        "audio_demo_versions",
        "audio_uploads",
        "reference_analysis_versions",
        "project_comments",
        "revision_requests",
        "project_events",
        "provider_profiles",
        "prompt_template_versions",
        "generation_candidates",
        "evaluation_runs",
        "structure_change_previews",
    }.issubset(tables)
    with sqlite3.connect(db_path) as connection:
        song_spec_columns = {
            row[1] for row in connection.execute("pragma table_info(song_spec_versions)").fetchall()
        }
    assert "structure_sections" in song_spec_columns
    with sqlite3.connect(db_path) as connection:
        lyrics_columns = {
            row[1] for row in connection.execute("pragma table_info(lyrics_versions)").fetchall()
        }
    assert "schema_version" in lyrics_columns
    with sqlite3.connect(db_path) as connection:
        chord_columns = {
            row[1]
            for row in connection.execute(
                "pragma table_info(chord_progression_versions)"
            ).fetchall()
        }
    assert "schema_version" in chord_columns
    with sqlite3.connect(db_path) as connection:
        midi_columns = {
            row[1]
            for row in connection.execute("pragma table_info(midi_asset_versions)").fetchall()
        }
        midi_foreign_keys = connection.execute(
            "pragma foreign_key_list(midi_asset_versions)"
        ).fetchall()
    assert {
        "parent_version_id",
        "schema_version",
        "note_events",
        "tempo_map",
        "time_signature_map",
    }.issubset(midi_columns)
    assert any(
        row[2] == "midi_asset_versions" and row[3] == "parent_version_id"
        for row in midi_foreign_keys
    )
    with sqlite3.connect(db_path) as connection:
        demo_columns = {
            row[1]
            for row in connection.execute("pragma table_info(audio_demo_versions)").fetchall()
        }
    assert "waveform_peaks" in demo_columns
    with sqlite3.connect(db_path) as connection:
        run_columns = {
            row[1] for row in connection.execute("pragma table_info(generation_runs)").fetchall()
        }
    with sqlite3.connect(db_path) as connection:
        marker_columns = {
            row[1] for row in connection.execute("pragma table_info(audio_markers)").fetchall()
        }
        marker_foreign_keys = connection.execute(
            "pragma foreign_key_list(audio_markers)"
        ).fetchall()
    assert {"audio_upload_id", "position_seconds", "label", "section_id", "notes"}.issubset(
        marker_columns
    )
    assert {row[2] for row in marker_foreign_keys} == {"projects", "audio_uploads"}
    with sqlite3.connect(db_path) as connection:
        derivative_columns = {
            row[1]
            for row in connection.execute("pragma table_info(audio_derivatives)").fetchall()
        }
        derivative_foreign_keys = connection.execute(
            "pragma foreign_key_list(audio_derivatives)"
        ).fetchall()
    assert {
        "audio_upload_id",
        "kind",
        "storage_key",
        "format",
        "sample_rate",
        "channels",
        "duration_seconds",
        "checksum",
        "source_checksum",
    }.issubset(derivative_columns)
    assert {row[2] for row in derivative_foreign_keys} == {"projects", "audio_uploads"}
    with sqlite3.connect(db_path) as connection:
        upload_column_rows = connection.execute("pragma table_info(audio_uploads)").fetchall()
    upload_columns = {row[1] for row in upload_column_rows}
    upload_nullability = {row[1]: row[3] for row in upload_column_rows}
    assert "format" in upload_columns
    assert upload_nullability["duration_seconds"] == 0
    assert upload_nullability["sample_rate"] == 0
    assert upload_nullability["channels"] == 0
    assert upload_nullability["waveform_peaks"] == 0
    assert {"provider_usage", "error_code"}.issubset(run_columns)
    with sqlite3.connect(db_path) as connection:
        analysis_columns = {
            row[1]
            for row in connection.execute(
                "pragma table_info(reference_analysis_versions)"
            ).fetchall()
        }
        analysis_foreign_keys = connection.execute(
            "pragma foreign_key_list(reference_analysis_versions)"
        ).fetchall()
    assert {
        "audio_upload_id",
        "audio_derivative_id",
        "run_id",
        "version_number",
        "analysis_range",
        "tempo_bpm",
        "beat_grid",
        "time_signature",
        "key_candidate",
        "pitch_range",
        "loudness",
        "structure_sections",
        "chord_candidates",
        "instrument_tags",
        "energy_curve",
        "production_features",
        "confidence",
        "provider_name",
        "provider_version",
    }.issubset(analysis_columns)
    assert {row[2] for row in analysis_foreign_keys} == {
        "projects",
        "audio_uploads",
        "audio_derivatives",
        "generation_runs",
    }
    with sqlite3.connect(db_path) as connection:
        midi_columns = {
            row[1]
            for row in connection.execute("pragma table_info(midi_asset_versions)").fetchall()
        }
        midi_foreign_keys = connection.execute(
            "pragma foreign_key_list(midi_asset_versions)"
        ).fetchall()
    assert {"source_reference_analysis_id", "source_provider_manifest"}.issubset(
        midi_columns
    )
    assert "reference_analysis_versions" in {row[2] for row in midi_foreign_keys}
    with sqlite3.connect(db_path) as connection:
        evaluation_columns = {
            row[1] for row in connection.execute("pragma table_info(evaluation_runs)").fetchall()
        }
    assert {
        "workflow",
        "status",
        "arq_job_id",
        "sample_count",
        "error_code",
        "error_message",
        "started_at",
        "completed_at",
        "updated_at",
    }.issubset(evaluation_columns)
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
        "ix_generation_candidates_project_created",
        "ix_evaluation_runs_workflow",
        "ix_evaluation_runs_status",
        "ix_structure_change_previews_project_created",
        "ix_audio_markers_upload_position",
        "ix_audio_derivatives_project_created",
    }.issubset(indexes)

from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from abachiwave.core.database import Base


class MidiAssetKind(StrEnum):
    chord = "chord"
    melody = "melody"
    hook = "hook"


class ExportBundleStatus(StrEnum):
    ready = "ready"
    failed = "failed"


class LyricsVersion(Base):
    __tablename__ = "lyrics_versions"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_lyrics_versions_project_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    song_spec_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("song_spec_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("lyrics_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_revision_request_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("revision_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sections: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    hook_candidates: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ChordProgressionVersion(Base):
    __tablename__ = "chord_progression_versions"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_chord_progression_versions_project_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    song_spec_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("song_spec_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lyrics_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("lyrics_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("chord_progression_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    tempo_bpm: Mapped[int] = mapped_column(Integer, nullable=False)
    time_signature: Mapped[str] = mapped_column(String(16), nullable=False)
    sections: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class MidiAssetVersion(Base):
    __tablename__ = "midi_asset_versions"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "kind",
            "version_number",
            name="uq_midi_asset_versions_project_kind_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    song_spec_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("song_spec_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lyrics_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("lyrics_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chord_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("chord_progression_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_revision_request_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("revision_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_audio_upload_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("audio_uploads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[MidiAssetKind] = mapped_column(String(16), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="audio/midi",
        server_default="audio/midi",
    )
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ArrangementPlanVersion(Base):
    __tablename__ = "arrangement_plan_versions"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_arrangement_plan_versions_project_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    song_spec_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("song_spec_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lyrics_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("lyrics_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chord_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chord_progression_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    midi_asset_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("arrangement_plan_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_revision_request_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("revision_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    overview: Mapped[str] = mapped_column(Text, nullable=False)
    sections: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    mix_notes: Mapped[str] = mapped_column(Text, nullable=False)
    reference_notes: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ExportBundle(Base):
    __tablename__ = "export_bundles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    arrangement_plan_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("arrangement_plan_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[ExportBundleStatus] = mapped_column(
        String(16),
        nullable=False,
        default=ExportBundleStatus.ready,
        server_default=ExportBundleStatus.ready.value,
    )
    manifest: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="application/zip",
        server_default="application/zip",
    )
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    download_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

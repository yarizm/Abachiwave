from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from abachiwave.core.database import Base


class GenerationRunStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class GenerationRunType(StrEnum):
    demo_generation = "demo_generation"
    audio_to_midi = "audio_to_midi"


class GenerationRun(Base):
    __tablename__ = "generation_runs"
    __table_args__ = (
        Index("ix_generation_runs_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_type: Mapped[GenerationRunType] = mapped_column(
        String(32),
        nullable=False,
        default=GenerationRunType.demo_generation,
        server_default=GenerationRunType.demo_generation.value,
    )
    status: Mapped[GenerationRunStatus] = mapped_column(
        String(24),
        nullable=False,
        default=GenerationRunStatus.queued,
        server_default=GenerationRunStatus.queued.value,
        index=True,
    )
    arq_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_manifest: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_params: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_of_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("generation_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    result_midi_asset_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("midi_asset_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class AudioDemoVersion(Base):
    __tablename__ = "audio_demo_versions"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_audio_demo_versions_project_version",
        ),
        Index("ix_audio_demo_versions_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("generation_runs.id", ondelete="CASCADE"),
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
    arrangement_plan_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("arrangement_plan_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    midi_asset_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="audio/wav",
        server_default="audio/wav",
    )
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    waveform_peaks: Mapped[list[float]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default="[]",
    )
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_params: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

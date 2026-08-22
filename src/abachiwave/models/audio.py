from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
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


class AudioUploadKind(StrEnum):
    humming = "humming"
    reference = "reference"
    scratch = "scratch"
    other = "other"


class AudioSourceFormat(StrEnum):
    wav = "wav"
    mp3 = "mp3"
    m4a = "m4a"
    flac = "flac"
    ogg = "ogg"


class AudioUploadStatus(StrEnum):
    processing = "processing"
    available = "available"
    failed = "failed"
    archived = "archived"


class AudioUpload(Base):
    __tablename__ = "audio_uploads"
    __table_args__ = (
        Index("ix_audio_uploads_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[AudioUploadKind] = mapped_column(String(24), nullable=False, index=True)
    status: Mapped[AudioUploadStatus] = mapped_column(
        String(24),
        nullable=False,
        default=AudioUploadStatus.available,
        server_default=AudioUploadStatus.available.value,
        index=True,
    )
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    format: Mapped[AudioSourceFormat] = mapped_column(
        String(16),
        nullable=False,
        default=AudioSourceFormat.wav,
        server_default=AudioSourceFormat.wav.value,
    )
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    waveform_peaks: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class AudioDerivativeKind(StrEnum):
    pcm_wav = "pcm_wav"


class AudioDerivative(Base):
    __tablename__ = "audio_derivatives"
    __table_args__ = (
        UniqueConstraint(
            "audio_upload_id",
            "kind",
            "source_checksum",
            name="uq_audio_derivatives_upload_kind_source",
        ),
        Index("ix_audio_derivatives_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audio_upload_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("audio_uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[AudioDerivativeKind] = mapped_column(String(32), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    channels: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
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


class AudioMarker(Base):
    __tablename__ = "audio_markers"
    __table_args__ = (
        CheckConstraint("position_seconds >= 0", name="audio_marker_position_nonnegative"),
        Index(
            "ix_audio_markers_upload_position",
            "audio_upload_id",
            "position_seconds",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audio_upload_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("audio_uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    section_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ReferenceAnalysisVersion(Base):
    __tablename__ = "reference_analysis_versions"
    __table_args__ = (
        UniqueConstraint(
            "audio_upload_id",
            "version_number",
            name="uq_reference_analysis_upload_version",
        ),
        UniqueConstraint("run_id", name="uq_reference_analysis_run"),
        CheckConstraint("version_number > 0", name="reference_analysis_version_positive"),
        CheckConstraint("tempo_bpm > 0", name="reference_analysis_tempo_positive"),
        Index(
            "ix_reference_analysis_upload_created",
            "audio_upload_id",
            "created_at",
        ),
        Index(
            "ix_reference_analysis_project_created",
            "project_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audio_upload_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("audio_uploads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audio_derivative_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("audio_derivatives.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("generation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_range: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    tempo_bpm: Mapped[float] = mapped_column(Float, nullable=False)
    beat_grid: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    time_signature: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    key_candidate: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    pitch_range: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    loudness: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    structure_sections: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    chord_candidates: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    instrument_tags: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    energy_curve: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    production_features: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_params: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

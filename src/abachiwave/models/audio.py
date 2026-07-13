from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from abachiwave.core.database import Base


class AudioUploadKind(StrEnum):
    humming = "humming"
    reference = "reference"
    scratch = "scratch"
    other = "other"


class AudioUploadStatus(StrEnum):
    available = "available"
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
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    channels: Mapped[int] = mapped_column(Integer, nullable=False)
    waveform_peaks: Mapped[list[float]] = mapped_column(JSON, nullable=False)
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

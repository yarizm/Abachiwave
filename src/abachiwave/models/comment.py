from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from abachiwave.core.database import Base


class ProjectCommentStatus(StrEnum):
    open = "open"
    resolved = "resolved"


class ProjectCommentTargetType(StrEnum):
    project = "project"
    song_spec = "song_spec"
    lyrics = "lyrics"
    chords = "chords"
    midi = "midi"
    arrangement = "arrangement"
    demo = "demo"
    audio_upload = "audio_upload"
    export = "export"
    revision = "revision"


class ProjectComment(Base):
    __tablename__ = "project_comments"
    __table_args__ = (
        Index("ix_project_comments_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_name: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProjectCommentStatus] = mapped_column(
        String(24),
        nullable=False,
        default=ProjectCommentStatus.open,
        server_default=ProjectCommentStatus.open.value,
        index=True,
    )
    target_type: Mapped[ProjectCommentTargetType] = mapped_column(
        String(32),
        nullable=False,
        default=ProjectCommentTargetType.project,
        server_default=ProjectCommentTargetType.project.value,
        index=True,
    )
    target_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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

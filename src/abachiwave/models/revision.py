from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from abachiwave.core.database import Base


class RevisionRequestStatus(StrEnum):
    planned = "planned"
    applied = "applied"
    rejected = "rejected"


class RevisionTaskTarget(StrEnum):
    lyrics = "lyrics"
    midi_melody = "midi_melody"
    arrangement = "arrangement"


class RevisionRequest(Base):
    __tablename__ = "revision_requests"
    __table_args__ = (
        Index("ix_revision_requests_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feedback: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RevisionRequestStatus] = mapped_column(
        String(24),
        nullable=False,
        default=RevisionRequestStatus.planned,
        server_default=RevisionRequestStatus.planned.value,
        index=True,
    )
    tasks: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    created_versions: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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


class ProjectEvent(Base):
    __tablename__ = "project_events"
    __table_args__ = (
        Index("ix_project_events_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    revision_request_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("revision_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    generation_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("generation_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    artifact_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

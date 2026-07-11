from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from abachiwave.core.database import Base


class IdeaIntakeStatus(StrEnum):
    needs_clarification = "needs_clarification"
    ready_for_generation = "ready_for_generation"
    generated = "generated"


class SongSpecStatus(StrEnum):
    draft = "draft"
    approved = "approved"
    superseded = "superseded"


class IdeaIntake(Base):
    __tablename__ = "idea_intakes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    idea: Mapped[str] = mapped_column(Text, nullable=False)
    answers: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    questions: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[IdeaIntakeStatus] = mapped_column(
        String(32),
        nullable=False,
        default=IdeaIntakeStatus.needs_clarification,
        server_default=IdeaIntakeStatus.needs_clarification.value,
    )
    generation_source: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="deterministic",
        server_default="deterministic",
    )
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


class SongSpecVersion(Base):
    __tablename__ = "song_spec_versions"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "version_number",
            name="uq_song_spec_versions_project_version",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intake_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("idea_intakes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SongSpecStatus] = mapped_column(
        String(24),
        nullable=False,
        default=SongSpecStatus.draft,
        server_default=SongSpecStatus.draft.value,
    )
    parent_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("song_spec_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    theme: Mapped[str | None] = mapped_column(Text, nullable=True)
    genre: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    language: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tempo_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    time_signature: Mapped[str | None] = mapped_column(String(16), nullable=True)
    target_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mood_curve: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True)
    song_structure: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
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

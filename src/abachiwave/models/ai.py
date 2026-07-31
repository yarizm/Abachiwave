from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
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


class TextWorkflow(StrEnum):
    song_spec = "song_spec"
    lyrics = "lyrics"
    arrangement = "arrangement"
    revision = "revision"


class GenerationCandidateStatus(StrEnum):
    pending = "pending"
    selected = "selected"


class EvaluationRunStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class ProviderProfile(Base):
    __tablename__ = "provider_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    capabilities: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    default_params: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
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


class PromptTemplateVersion(Base):
    __tablename__ = "prompt_template_versions"
    __table_args__ = (
        UniqueConstraint("workflow", "version_number", name="uq_prompt_workflow_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    workflow: Mapped[TextWorkflow] = mapped_column(String(32), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    template_body: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class GenerationCandidate(Base):
    __tablename__ = "generation_candidates"
    __table_args__ = (
        UniqueConstraint("run_id", "candidate_index", name="uq_candidate_run_index"),
        Index("ix_generation_candidates_project_created", "project_id", "created_at"),
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
    provider_profile_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("provider_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    prompt_template_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("prompt_template_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workflow: Mapped[TextWorkflow] = mapped_column(String(32), nullable=False, index=True)
    candidate_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[GenerationCandidateStatus] = mapped_column(
        String(24),
        nullable=False,
        default=GenerationCandidateStatus.pending,
        server_default=GenerationCandidateStatus.pending.value,
        index=True,
    )
    content: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_asset_ids: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    generation_params: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    provider_usage: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    selected_asset_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    selected_asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    __table_args__ = (Index("ix_evaluation_runs_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    sample_set: Mapped[str] = mapped_column(String(120), nullable=False)
    workflow: Mapped[TextWorkflow] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[EvaluationRunStatus] = mapped_column(
        String(24),
        nullable=False,
        default=EvaluationRunStatus.queued,
        server_default=EvaluationRunStatus.queued.value,
        index=True,
    )
    arq_job_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_profile_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("provider_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    prompt_template_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("prompt_template_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    metrics: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    human_scores: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
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

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from abachiwave.models.ai import (
    EvaluationRunStatus,
    GenerationCandidateStatus,
    TextWorkflow,
)
from abachiwave.schemas.composition import (
    ArrangementPlan,
    HookCandidate,
    LyricSection,
)
from abachiwave.schemas.demo import GenerationRunRead
from abachiwave.schemas.revisions import RevisionTask
from abachiwave.schemas.song_specs import SongSpecData


class LyricsCandidateContent(BaseModel):
    sections: list[LyricSection] = Field(min_length=1)
    hook_candidates: list[HookCandidate] = Field(default_factory=list)


class RevisionCandidateContent(BaseModel):
    feedback: str = Field(min_length=1, max_length=4000)
    tasks: list[RevisionTask] = Field(min_length=1)


CandidateContent = (
    SongSpecData | LyricsCandidateContent | ArrangementPlan | RevisionCandidateContent
)


class CandidateGenerateRequest(BaseModel):
    workflow: TextWorkflow
    provider_profile_id: UUID | None = None
    candidate_count: int = Field(default=1, ge=1, le=3)
    intake_id: UUID | None = None
    song_spec_id: UUID | None = None
    lyrics_version_id: UUID | None = None
    chord_version_id: UUID | None = None
    midi_asset_ids: list[UUID] | None = None
    feedback: str | None = Field(default=None, max_length=4000)

    @field_validator("feedback")
    @classmethod
    def normalize_feedback(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def validate_workflow_inputs(self) -> "CandidateGenerateRequest":
        if self.workflow == TextWorkflow.song_spec and self.intake_id is None:
            raise ValueError("song_spec workflow requires intake_id")
        if (
            self.workflow in {TextWorkflow.lyrics, TextWorkflow.arrangement}
            and self.song_spec_id is None
        ):
            raise ValueError(f"{self.workflow.value} workflow requires song_spec_id")
        if self.workflow == TextWorkflow.revision and self.feedback is None:
            raise ValueError("revision workflow requires feedback")
        return self


class ProviderCapabilityRead(BaseModel):
    id: UUID
    provider_name: str
    display_name: str
    capabilities: list[TextWorkflow]
    model: str | None
    default_params: dict[str, object]
    enabled: bool
    is_default: bool


class EvaluationSampleSetRead(BaseModel):
    name: str
    sample_count: int
    workflows: dict[str, int]
    categories: list[str]


class EvaluationRunCreate(BaseModel):
    workflow: TextWorkflow
    provider_profile_id: UUID | None = None
    sample_set: str = Field(default="creative-briefs-v1", min_length=1, max_length=120)


class EvaluationRunRead(BaseModel):
    id: UUID
    sample_set: str
    workflow: TextWorkflow
    status: EvaluationRunStatus
    arq_job_id: str | None
    sample_count: int
    provider_profile_id: UUID | None
    prompt_template_version_id: UUID | None
    metrics: dict[str, object]
    human_scores: dict[str, object]
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BlindSampleRating(BaseModel):
    sample_id: str = Field(min_length=1, max_length=160)
    output_a_theme_consistency: int = Field(ge=1, le=5)
    output_a_editability: int = Field(ge=1, le=5)
    output_b_theme_consistency: int = Field(ge=1, le=5)
    output_b_editability: int = Field(ge=1, le=5)
    preferred_output: Literal["A", "B", "tie"]


class EvaluationHumanScoreCreate(BaseModel):
    evaluator_alias: str = Field(min_length=1, max_length=120)
    ratings: list[BlindSampleRating] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("evaluator_alias")
    @classmethod
    def normalize_evaluator_alias(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("evaluator_alias must not be blank")
        return normalized

    @model_validator(mode="after")
    def require_unique_samples(self) -> "EvaluationHumanScoreCreate":
        sample_ids = [rating.sample_id for rating in self.ratings]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("ratings must contain unique sample_id values")
        return self


class GenerationCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    run_id: UUID
    provider_profile_id: UUID | None
    prompt_template_version_id: UUID | None
    workflow: TextWorkflow
    candidate_index: int
    status: GenerationCandidateStatus
    content: dict[str, object]
    score: float | None
    source_asset_ids: dict[str, object]
    generation_params: dict[str, object]
    provider_usage: dict[str, object]
    selected_asset_type: str | None
    selected_asset_id: UUID | None
    selected_at: datetime | None
    created_at: datetime


class CandidateSelectionRead(BaseModel):
    candidate: GenerationCandidateRead
    asset_type: str
    asset_id: UUID


class CandidateGenerationRead(BaseModel):
    run: GenerationRunRead

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from abachiwave.models.revision import RevisionRequestStatus, RevisionTaskTarget
from abachiwave.schemas.composition import (
    ArrangementPlanVersionRead,
    LyricsVersionRead,
    MidiAssetVersionRead,
)
from abachiwave.schemas.demo import AudioDemoVersionRead, GenerationRunRead

VersionAssetType = Literal["lyrics", "midi_melody", "arrangement", "demo"]
RestoreAssetType = Literal["lyrics", "midi_melody", "arrangement"]


class RevisionRequestCreate(BaseModel):
    feedback: str = Field(min_length=1, max_length=4000)
    provider_profile_id: UUID | None = None
    candidate_count: int | None = Field(default=None, ge=1, le=3)

    @field_validator("feedback")
    @classmethod
    def normalize_feedback(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("feedback must not be blank")
        return normalized


class RevisionTask(BaseModel):
    id: str
    target: RevisionTaskTarget
    target_section_id: str | None
    action: str
    summary: str
    affected_asset_ids: list[UUID]
    requires_demo_regeneration: bool
    supported: bool


class VersionReference(BaseModel):
    asset_type: RestoreAssetType
    id: UUID
    label: str
    version_number: int
    parent_version_id: UUID | None = None
    source_revision_request_id: UUID | None = None


class RevisionRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    feedback: str
    status: RevisionRequestStatus
    tasks: list[RevisionTask]
    created_versions: list[VersionReference]
    applied_at: datetime | None
    rejected_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RevisionApplyRequest(BaseModel):
    task_ids: list[str] | None = None
    regenerate_demo: bool = False

    @field_validator("task_ids")
    @classmethod
    def normalize_task_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        deduped = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if not deduped:
            raise ValueError("task_ids must not be empty")
        return deduped


class RevisionApplyRead(BaseModel):
    revision: RevisionRequestRead
    created_versions: list[VersionReference]
    demo_run: GenerationRunRead | None = None


class VersionDiffChange(BaseModel):
    field: str
    label: str
    left: str | None
    right: str | None
    summary: str


class VersionEndpointReference(BaseModel):
    id: UUID
    label: str
    version_number: int
    created_at: datetime


class VersionDiffRead(BaseModel):
    asset_type: VersionAssetType
    left: VersionEndpointReference
    right: VersionEndpointReference
    summary: str
    changes: list[VersionDiffChange]


class VersionRestoreRequest(BaseModel):
    asset_type: RestoreAssetType
    version_id: UUID


class VersionRestoreRead(BaseModel):
    asset_type: RestoreAssetType
    version: LyricsVersionRead | MidiAssetVersionRead | ArrangementPlanVersionRead


class ProjectEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    event_type: str
    payload: dict[str, object]
    revision_request_id: UUID | None
    generation_run_id: UUID | None
    artifact_version_id: UUID | None
    created_at: datetime


class DemoComparisonRead(BaseModel):
    left: AudioDemoVersionRead
    right: AudioDemoVersionRead

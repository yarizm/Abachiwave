from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from abachiwave.models.comment import ProjectCommentStatus, ProjectCommentTargetType


class ProjectCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    author_name: str = Field(default="Local collaborator", min_length=1, max_length=120)
    target_type: ProjectCommentTargetType = ProjectCommentTargetType.project
    target_id: UUID | None = None

    @field_validator("body", "author_name")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class ProjectCommentUpdate(BaseModel):
    body: str | None = Field(default=None, min_length=1, max_length=4000)
    status: ProjectCommentStatus | None = None

    @field_validator("body")
    @classmethod
    def normalize_body(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("body must not be blank")
        return normalized


class ProjectCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    author_name: str
    body: str
    status: ProjectCommentStatus
    target_type: ProjectCommentTargetType
    target_id: UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

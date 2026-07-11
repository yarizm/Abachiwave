from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ReviewItemStatus = Literal["pass", "warning", "fail"]
ProjectReviewStatus = Literal["ready", "needs_work", "blocked"]


class ProjectReviewItem(BaseModel):
    id: str
    label: str
    status: ReviewItemStatus
    detail: str
    weight: int = Field(ge=1, le=100)


class ProjectReviewRead(BaseModel):
    project_id: UUID
    status: ProjectReviewStatus
    score: int = Field(ge=0, le=100)
    items: list[ProjectReviewItem]
    next_actions: list[str]
    generated_at: datetime

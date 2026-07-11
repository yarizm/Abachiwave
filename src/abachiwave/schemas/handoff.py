from datetime import datetime

from pydantic import BaseModel

from abachiwave.schemas.comments import ProjectCommentRead
from abachiwave.schemas.composition import CurrentAssets
from abachiwave.schemas.projects import ProjectRead
from abachiwave.schemas.review import ProjectReviewRead
from abachiwave.schemas.revisions import ProjectEventRead


class ProjectHandoffRead(BaseModel):
    project: ProjectRead
    review: ProjectReviewRead
    current_assets: CurrentAssets
    missing_prerequisites: list[str]
    open_comments: list[ProjectCommentRead]
    recent_events: list[ProjectEventRead]
    next_actions: list[str]
    handoff_markdown: str
    generated_at: datetime

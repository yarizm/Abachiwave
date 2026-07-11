from typing import Literal

from pydantic import BaseModel

DependencyState = Literal["ok", "unavailable"]


class DependencyReadiness(BaseModel):
    database: DependencyState
    redis: DependencyState
    storage: DependencyState


class ReadinessRead(BaseModel):
    status: Literal["ready", "not_ready"]
    dependencies: DependencyReadiness

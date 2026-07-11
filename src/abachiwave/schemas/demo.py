from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from abachiwave.models.demo import GenerationRunStatus, GenerationRunType


class DemoGenerateRequest(BaseModel):
    arrangement_plan_id: UUID | None = None


class GenerationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    run_type: GenerationRunType
    status: GenerationRunStatus
    arq_job_id: str | None
    input_manifest: dict[str, object]
    provider_name: str
    provider_version: str
    provider_params: dict[str, object]
    error_message: str | None
    retry_of_run_id: UUID | None
    result_midi_asset_id: UUID | None
    demo_id: UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AudioDemoVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    run_id: UUID
    song_spec_id: UUID
    lyrics_version_id: UUID
    chord_version_id: UUID
    arrangement_plan_id: UUID
    midi_asset_ids: list[UUID]
    version_number: int
    filename: str
    content_type: str
    size_bytes: int
    checksum: str
    duration_seconds: int
    waveform_peaks: list[float]
    provider_name: str
    provider_version: str
    provider_params: dict[str, object]
    download_url: str
    created_at: datetime

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from abachiwave.models.audio import AudioUploadKind, AudioUploadStatus
from abachiwave.models.composition import MidiAssetKind


class AudioUploadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    kind: AudioUploadKind
    status: AudioUploadStatus
    filename: str
    content_type: str
    size_bytes: int
    checksum: str
    duration_seconds: float
    sample_rate: int
    channels: int
    waveform_peaks: list[float]
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AudioUploadUpdate(BaseModel):
    kind: AudioUploadKind | None = None
    status: AudioUploadStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AudioExtractMidiRequest(BaseModel):
    song_spec_id: UUID
    target_kind: MidiAssetKind = MidiAssetKind.melody

    @field_validator("target_kind")
    @classmethod
    def melody_only(cls, value: MidiAssetKind) -> MidiAssetKind:
        if value is not MidiAssetKind.melody:
            raise ValueError("only melody extraction is supported")
        return value

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from abachiwave.models.audio import (
    AudioDerivativeKind,
    AudioSourceFormat,
    AudioUploadKind,
    AudioUploadStatus,
)
from abachiwave.models.composition import MidiAssetKind


class AudioUploadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    kind: AudioUploadKind
    status: AudioUploadStatus
    filename: str
    content_type: str
    format: AudioSourceFormat
    size_bytes: int
    checksum: str
    duration_seconds: float | None
    sample_rate: int | None
    channels: int | None
    waveform_peaks: list[float] | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AudioUploadUpdate(BaseModel):
    kind: AudioUploadKind | None = None
    status: AudioUploadStatus | None = None
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("status")
    @classmethod
    def editable_status_only(cls, value: AudioUploadStatus | None) -> AudioUploadStatus | None:
        if value not in {None, AudioUploadStatus.available, AudioUploadStatus.archived}:
            raise ValueError("status can only be available or archived")
        return value

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AudioAnalysisRange(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_duration(self) -> "AudioAnalysisRange":
        if self.end_seconds - self.start_seconds < 0.1:
            raise ValueError("analysis range must be at least 0.1 seconds")
        return self


class AudioExtractMidiRequest(BaseModel):
    song_spec_id: UUID
    target_kind: MidiAssetKind = MidiAssetKind.melody
    analysis_range: AudioAnalysisRange | None = None
    reference_analysis_id: UUID | None = None

    @field_validator("target_kind")
    @classmethod
    def melody_only(cls, value: MidiAssetKind) -> MidiAssetKind:
        if value is not MidiAssetKind.melody:
            raise ValueError("only melody extraction is supported")
        return value


class AudioMarkerCreate(BaseModel):
    position_seconds: float = Field(ge=0)
    label: str = Field(min_length=1, max_length=120)
    section_id: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("label must not be blank")
        return normalized

    @field_validator("section_id", "notes")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AudioMarkerUpdate(BaseModel):
    position_seconds: float | None = Field(default=None, ge=0)
    label: str | None = Field(default=None, min_length=1, max_length=120)
    section_id: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("label")
    @classmethod
    def normalize_optional_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("label must not be blank")
        return normalized

    @field_validator("section_id", "notes")
    @classmethod
    def normalize_update_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class AudioMarkerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    audio_upload_id: UUID
    position_seconds: float
    label: str
    section_id: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AudioDerivativeCreateRequest(BaseModel):
    kind: AudioDerivativeKind = AudioDerivativeKind.pcm_wav


class AudioDerivativeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    audio_upload_id: UUID
    kind: AudioDerivativeKind
    filename: str
    content_type: str
    format: str
    sample_rate: int
    channels: int
    duration_seconds: float
    size_bytes: int
    checksum: str
    source_checksum: str
    created_at: datetime
    updated_at: datetime


class ReferenceAnalysisCreateRequest(BaseModel):
    analysis_range: AudioAnalysisRange | None = None


class ReferenceAnalysisRange(BaseModel):
    mode: Literal["full", "selection"]
    start_seconds: float
    end_seconds: float


class ReferenceTimeSignature(BaseModel):
    value: str
    confidence: float = Field(ge=0, le=1)


class ReferenceKeyCandidate(BaseModel):
    tonic: str
    mode: str
    value: str
    confidence: float = Field(ge=0, le=1)


class ReferencePitchRange(BaseModel):
    low_midi: int = Field(ge=0, le=127)
    high_midi: int = Field(ge=0, le=127)
    low_note: str
    high_note: str
    confidence: float = Field(ge=0, le=1)


class ReferenceLoudnessPoint(BaseModel):
    time_seconds: float = Field(ge=0)
    dbfs: float


class ReferenceLoudness(BaseModel):
    integrated_dbfs: float
    peak_dbfs: float
    dynamic_range_db: float = Field(ge=0)
    curve: list[ReferenceLoudnessPoint]
    confidence: float = Field(ge=0, le=1)


class ReferenceStructureSection(BaseModel):
    label: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)


class ReferenceChordCandidate(BaseModel):
    symbol: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)


class ReferenceInstrumentTag(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)


class ReferenceEnergyPoint(BaseModel):
    time_seconds: float = Field(ge=0)
    value: float = Field(ge=0, le=1)


class ReferenceProductionFeature(BaseModel):
    label: str
    value: str
    confidence: float = Field(ge=0, le=1)


class ReferenceAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    audio_upload_id: UUID
    audio_derivative_id: UUID | None
    run_id: UUID
    version_number: int
    source_checksum: str
    analysis_range: ReferenceAnalysisRange
    tempo_bpm: float
    beat_grid: list[float]
    time_signature: ReferenceTimeSignature
    key_candidate: ReferenceKeyCandidate
    pitch_range: ReferencePitchRange
    loudness: ReferenceLoudness
    structure_sections: list[ReferenceStructureSection]
    chord_candidates: list[ReferenceChordCandidate]
    instrument_tags: list[ReferenceInstrumentTag]
    energy_curve: list[ReferenceEnergyPoint]
    production_features: list[ReferenceProductionFeature]
    confidence: dict[str, float]
    provider_name: str
    provider_version: str
    provider_params: dict[str, object]
    created_at: datetime


class ReferenceAnalysisApplyField(StrEnum):
    tempo_bpm = "tempo_bpm"
    key = "key"
    time_signature = "time_signature"


class ReferenceAnalysisApplyRequest(BaseModel):
    song_spec_id: UUID
    fields: list[ReferenceAnalysisApplyField] = Field(min_length=1, max_length=3)
    confirm: bool = False

    @field_validator("fields")
    @classmethod
    def unique_fields(
        cls,
        value: list[ReferenceAnalysisApplyField],
    ) -> list[ReferenceAnalysisApplyField]:
        if len(set(value)) != len(value):
            raise ValueError("analysis apply fields must be unique")
        return value


class ReferenceAnalysisFieldChange(BaseModel):
    field: ReferenceAnalysisApplyField
    current_value: str | int | float | None
    candidate_value: str | int | float
    confidence: float = Field(ge=0, le=1)


class ReferenceAnalysisApplyRead(BaseModel):
    analysis_id: UUID
    source_song_spec_id: UUID
    selected_fields: list[ReferenceAnalysisApplyField]
    changes: list[ReferenceAnalysisFieldChange]
    affected_asset_counts: dict[str, int]
    warnings: list[str]
    requires_confirmation: bool
    applied: bool
    new_song_spec_id: UUID | None
    new_song_spec_version: int | None

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from abachiwave.models.composition import ExportBundleStatus, MidiAssetKind


class LyricSection(BaseModel):
    section_id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("section_id", "label", "text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class HookCandidate(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=500)

    @field_validator("id", "text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class ChordSection(BaseModel):
    section_id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    bars: int = Field(ge=1, le=64)
    chords: list[str] = Field(min_length=1, max_length=64)

    @field_validator("section_id", "label")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("chords")
    @classmethod
    def normalize_chords(cls, value: list[str]) -> list[str]:
        normalized = [chord.strip() for chord in value if chord.strip()]
        if not normalized:
            raise ValueError("chords must not be empty")
        return normalized


class LyricsGenerateRequest(BaseModel):
    song_spec_id: UUID


class LyricsUpdate(BaseModel):
    sections: list[LyricSection] = Field(min_length=1)
    hook_candidates: list[HookCandidate] = Field(default_factory=list)


class LyricsVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    song_spec_id: UUID
    version_number: int
    parent_version_id: UUID | None
    source_revision_request_id: UUID | None
    sections: list[LyricSection]
    hook_candidates: list[HookCandidate]
    created_at: datetime
    updated_at: datetime


class ChordGenerateRequest(BaseModel):
    song_spec_id: UUID
    lyrics_version_id: UUID | None = None


class ChordUpdate(BaseModel):
    sections: list[ChordSection] = Field(min_length=1)


class ChordProgressionVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    song_spec_id: UUID
    lyrics_version_id: UUID | None
    version_number: int
    parent_version_id: UUID | None
    key: str
    tempo_bpm: int
    time_signature: str
    sections: list[ChordSection]
    created_at: datetime
    updated_at: datetime


class MidiGenerateRequest(BaseModel):
    song_spec_id: UUID
    lyrics_version_id: UUID | None = None
    chord_version_id: UUID | None = None
    kinds: list[MidiAssetKind] | None = None

    @field_validator("kinds")
    @classmethod
    def normalize_kinds(cls, value: list[MidiAssetKind] | None) -> list[MidiAssetKind] | None:
        if value is None:
            return None
        deduped = list(dict.fromkeys(value))
        if not deduped:
            raise ValueError("kinds must not be empty")
        return deduped


class MidiAssetVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    song_spec_id: UUID
    lyrics_version_id: UUID | None
    chord_version_id: UUID | None
    version_number: int
    kind: MidiAssetKind
    source_revision_request_id: UUID | None
    source_audio_upload_id: UUID | None
    filename: str
    content_type: str
    size_bytes: int
    checksum: str
    created_at: datetime


class ArrangementSection(BaseModel):
    section_id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    instruments: list[str] = Field(min_length=1, max_length=24)
    energy_level: int = Field(ge=1, le=10)
    production_notes: str = Field(min_length=1, max_length=2000)

    @field_validator("section_id", "label", "production_notes")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("instruments")
    @classmethod
    def normalize_instruments(cls, value: list[str]) -> list[str]:
        normalized = [instrument.strip() for instrument in value if instrument.strip()]
        if not normalized:
            raise ValueError("instruments must not be empty")
        return normalized


class ArrangementPlan(BaseModel):
    overview: str = Field(min_length=1, max_length=4000)
    sections: list[ArrangementSection] = Field(min_length=1)
    mix_notes: str = Field(min_length=1, max_length=4000)
    reference_notes: str = Field(min_length=1, max_length=4000)

    @field_validator("overview", "mix_notes", "reference_notes")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class ArrangementGenerateRequest(BaseModel):
    song_spec_id: UUID
    lyrics_version_id: UUID | None = None
    chord_version_id: UUID | None = None
    midi_asset_ids: list[UUID] | None = None

    @field_validator("midi_asset_ids")
    @classmethod
    def normalize_midi_asset_ids(cls, value: list[UUID] | None) -> list[UUID] | None:
        if value is None:
            return None
        deduped = list(dict.fromkeys(value))
        if not deduped:
            raise ValueError("midi_asset_ids must not be empty")
        return deduped


class ArrangementUpdate(ArrangementPlan):
    pass


class ArrangementPlanVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    song_spec_id: UUID
    lyrics_version_id: UUID
    chord_version_id: UUID
    midi_asset_ids: list[UUID]
    version_number: int
    parent_version_id: UUID | None
    source_revision_request_id: UUID | None
    arrangement_plan: ArrangementPlan
    created_at: datetime
    updated_at: datetime


class AssetReference(BaseModel):
    asset_type: str
    id: UUID
    label: str
    version_number: int
    created_at: datetime
    status: str | None = None
    kind: str | None = None


class CurrentAssets(BaseModel):
    song_spec: AssetReference | None
    lyrics: AssetReference | None
    chords: AssetReference | None
    midi_assets: list[AssetReference]
    arrangement: AssetReference | None


class AssetTreeRead(BaseModel):
    current: CurrentAssets
    timeline: list[AssetReference]
    missing_prerequisites: list[str]


class ExportCreateRequest(BaseModel):
    arrangement_plan_id: UUID | None = None


class ExportBundleRead(BaseModel):
    id: UUID
    project_id: UUID
    arrangement_plan_id: UUID | None
    status: ExportBundleStatus
    manifest: dict[str, object]
    filename: str | None
    content_type: str
    size_bytes: int | None
    checksum: str | None
    download_url: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

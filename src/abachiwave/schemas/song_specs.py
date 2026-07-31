from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from abachiwave.models.song_spec import IdeaIntakeStatus, SongSpecStatus

SONG_SPEC_FIELDS = (
    "theme",
    "genre",
    "language",
    "tempo_bpm",
    "key",
    "time_signature",
    "target_duration_seconds",
    "mood_curve",
    "song_structure",
)


class ClarificationQuestion(BaseModel):
    id: str
    field: str
    prompt: str
    required: bool = True


class IdeaIntakeCreate(BaseModel):
    idea: str = Field(min_length=1, max_length=4000)
    answers: dict[str, str] = Field(default_factory=dict)

    @field_validator("idea")
    @classmethod
    def normalize_idea(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("idea must not be blank")
        return normalized

    @field_validator("answers")
    @classmethod
    def normalize_answers(cls, value: dict[str, str]) -> dict[str, str]:
        return {key.strip(): answer.strip() for key, answer in value.items() if answer.strip()}


class IdeaIntakeRead(BaseModel):
    intake_id: UUID
    idea: str
    answers: dict[str, str]
    status: IdeaIntakeStatus
    questions: list[ClarificationQuestion]
    generation_source: str
    created_at: datetime
    updated_at: datetime


class StructureSection(BaseModel):
    section_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    label: str = Field(min_length=1, max_length=120)

    @field_validator("section_id", "label")
    @classmethod
    def normalize_section_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


def build_structure_sections(labels: list[str]) -> list[StructureSection]:
    sections: list[StructureSection] = []
    counts: dict[str, int] = {}
    for index, label in enumerate(labels):
        normalized_label = label.strip()
        base = "".join(
            character if character.isascii() and character.isalnum() else "-"
            for character in normalized_label.lower()
        )
        base = "-".join(part for part in base.split("-") if part) or f"section-{index + 1}"
        base = base[:56]
        counts[base] = counts.get(base, 0) + 1
        suffix = f"-{counts[base]}" if counts[base] > 1 else ""
        sections.append(StructureSection(section_id=f"{base}{suffix}", label=normalized_label))
    return sections


class SongSpecData(BaseModel):
    theme: str | None = Field(default=None, max_length=1000)
    genre: list[str] | None = None
    language: str | None = Field(default=None, max_length=32)
    tempo_bpm: int | None = Field(default=None, ge=40, le=240)
    key: str | None = Field(default=None, max_length=64)
    time_signature: str | None = Field(default=None, pattern=r"^\d+/\d+$")
    target_duration_seconds: int | None = Field(default=None, ge=30, le=900)
    mood_curve: dict[str, str] | None = None
    song_structure: list[str] | None = None
    structure_sections: list[StructureSection] | None = None

    @field_validator("theme", "language", "key", "time_signature")
    @classmethod
    def normalize_optional_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("genre", "song_structure")
    @classmethod
    def normalize_optional_string_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip() for item in value if item.strip()]
        return normalized or None

    @field_validator("mood_curve")
    @classmethod
    def normalize_mood_curve(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        normalized = {
            key.strip(): curve_value.strip()
            for key, curve_value in value.items()
            if key.strip() and curve_value.strip()
        }
        return normalized or None

    def missing_required_fields(self) -> list[str]:
        missing: list[str] = []
        for field_name in SONG_SPEC_FIELDS:
            value = getattr(self, field_name)
            if value is None or value == [] or value == {}:
                missing.append(field_name)
        return missing

    @model_validator(mode="after")
    def synchronize_structure_fields(self) -> "SongSpecData":
        if self.structure_sections:
            self.song_structure = [section.label for section in self.structure_sections]
        elif self.song_structure:
            self.structure_sections = build_structure_sections(self.song_structure)
        return self

    def to_model_values(self) -> dict[str, Any]:
        return self.model_dump()


class SongSpecGenerateRequest(BaseModel):
    intake_id: UUID
    provider_profile_id: UUID | None = None
    candidate_count: int | None = Field(default=None, ge=1, le=3)


class SongSpecUpdate(BaseModel):
    theme: str | None = Field(default=None, max_length=1000)
    genre: list[str] | None = None
    language: str | None = Field(default=None, max_length=32)
    tempo_bpm: int | None = Field(default=None, ge=40, le=240)
    key: str | None = Field(default=None, max_length=64)
    time_signature: str | None = Field(default=None, pattern=r"^\d+/\d+$")
    target_duration_seconds: int | None = Field(default=None, ge=30, le=900)
    mood_curve: dict[str, str] | None = None
    song_structure: list[str] | None = None

    @field_validator("theme", "language", "key", "time_signature")
    @classmethod
    def normalize_optional_string(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("genre", "song_structure")
    @classmethod
    def normalize_optional_string_list(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip() for item in value if item.strip()]
        return normalized or None

    @field_validator("mood_curve")
    @classmethod
    def normalize_mood_curve(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        normalized = {
            key.strip(): curve_value.strip()
            for key, curve_value in value.items()
            if key.strip() and curve_value.strip()
        }
        return normalized or None


class SongSpecVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    intake_id: UUID | None
    version_number: int
    status: SongSpecStatus
    parent_version_id: UUID | None
    approved_at: datetime | None
    song_spec: SongSpecData
    missing_required_fields: list[str]
    created_at: datetime
    updated_at: datetime

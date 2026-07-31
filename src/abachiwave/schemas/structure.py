from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from abachiwave.schemas.song_specs import StructureSection


class StructureSectionInput(StructureSection):
    source_section_id: str | None = Field(
        default=None,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )


class StructureChangeRequest(BaseModel):
    source_song_spec_id: UUID
    sections: list[StructureSectionInput] = Field(min_length=1, max_length=32)
    preview_id: UUID | None = None

    @model_validator(mode="after")
    def validate_unique_section_ids(self) -> "StructureChangeRequest":
        section_ids = [section.section_id for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("section_id values must be unique")
        return self


class StructureRename(BaseModel):
    section_id: str
    before: str
    after: str


class StructureAssetImpact(BaseModel):
    asset_type: str
    id: UUID
    version_number: int
    action: Literal["new_version", "regenerate"]


class StructureImpact(BaseModel):
    added_sections: list[StructureSection]
    removed_sections: list[StructureSection]
    renamed_sections: list[StructureRename]
    reordered: bool
    affected_assets: list[StructureAssetImpact]
    requires_midi_regeneration: bool
    requires_demo_regeneration: bool
    warnings: list[str]


class StructureCreatedVersion(BaseModel):
    asset_type: Literal["song_spec", "lyrics", "chords", "arrangement"]
    id: UUID
    version_number: int
    parent_version_id: UUID


class StructureChangeRead(BaseModel):
    preview_id: UUID
    status: Literal["preview", "applied"]
    source_song_spec_id: UUID
    sections: list[StructureSection]
    impact: StructureImpact
    created_versions: list[StructureCreatedVersion]
    created_at: datetime
    applied_at: datetime | None

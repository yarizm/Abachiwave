from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from abachiwave.schemas.composition import LyricLine, LyricSection


class LyricsRewriteScope(StrEnum):
    line = "line"
    section = "section"
    all = "all"


class LyricsRewriteAction(StrEnum):
    rewrite = "rewrite"
    expand = "expand"
    compress = "compress"
    change_rhyme = "change_rhyme"
    adjust_tone = "adjust_tone"


class LyricsRewriteRequest(BaseModel):
    scope: LyricsRewriteScope
    action: LyricsRewriteAction
    section_id: str | None = Field(default=None, max_length=64)
    line_id: str | None = Field(default=None, max_length=64)
    instruction: str | None = Field(default=None, max_length=500)
    tone: str | None = Field(default=None, max_length=80)
    rhyme_ending: str | None = Field(default=None, max_length=80)
    rhyme_label: str | None = Field(default=None, max_length=16)
    banned_phrases: list[str] = Field(default_factory=list, max_length=50)
    preferred_terms: list[str] = Field(default_factory=list, max_length=50)
    sections: list[LyricSection] | None = None

    @field_validator(
        "section_id",
        "line_id",
        "instruction",
        "tone",
        "rhyme_ending",
        "rhyme_label",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None

    @field_validator("banned_phrases", "preferred_terms")
    @classmethod
    def normalize_term_list(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            term = item.strip()
            if term and term.casefold() not in {current.casefold() for current in normalized}:
                normalized.append(term)
        return normalized

    @model_validator(mode="after")
    def validate_target(self) -> "LyricsRewriteRequest":
        if self.scope == LyricsRewriteScope.line and not self.line_id:
            raise ValueError("line_id is required for line rewrites")
        if self.scope == LyricsRewriteScope.section and not self.section_id:
            raise ValueError("section_id is required for section rewrites")
        if self.action == LyricsRewriteAction.change_rhyme and not self.rhyme_ending:
            raise ValueError("rhyme_ending is required when changing rhyme")
        return self


class LyricDiffSegment(BaseModel):
    kind: str
    text: str


class LyricRewriteChange(BaseModel):
    section_id: str
    line_id: str
    before: LyricLine
    after: LyricLine
    diff: list[LyricDiffSegment]


class LyricsRewritePreview(BaseModel):
    source_lyrics_id: UUID
    scope: LyricsRewriteScope
    action: LyricsRewriteAction
    candidate_sections: list[LyricSection]
    changes: list[LyricRewriteChange]
    detected_banned_phrases: list[str]
    warnings: list[str]

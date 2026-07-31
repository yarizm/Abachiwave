import re
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from abachiwave.models.composition import ExportBundleStatus, MidiAssetKind

_WORD_PATTERN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_ENDING_PATTERN = re.compile(
    r"([A-Za-z]+|[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff])[^A-Za-z\u3400-\u9fff]*$"
)
_VOWEL_GROUP_PATTERN = re.compile(r"[aeiouy]+", re.IGNORECASE)


class LyricLine(BaseModel):
    line_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=500)
    rhyme_label: str | None = Field(default=None, max_length=16)

    @field_validator("line_id", "text")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("rhyme_label")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def character_count(self) -> int:
        return len("".join(self.text.split()))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def word_count(self) -> int:
        return len(_WORD_PATTERN.findall(self.text)) + len(_CJK_PATTERN.findall(self.text))

    @computed_field  # type: ignore[prop-decorator]
    @property
    def syllable_count(self) -> int:
        return lyric_syllable_count(self.text)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def rhyme_key(self) -> str | None:
        return lyric_rhyme_key(self.text)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def stress_positions(self) -> list[int]:
        return list(range(1, min(self.syllable_count, 16) + 1, 2))


class LyricSection(BaseModel):
    section_id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=4000)
    lines: list[LyricLine] = Field(default_factory=list, min_length=1, max_length=64)

    @model_validator(mode="before")
    @classmethod
    def synchronize_text_and_lines(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        text = str(data.get("text") or "").strip()
        raw_lines = data.get("lines")
        lines = list(raw_lines) if isinstance(raw_lines, list) else []
        joined = "\n".join(_line_text(line) for line in lines if _line_text(line)).strip()
        if "lines" in data:
            if joined:
                text = joined
        elif text:
            lines = []
            for index, line_text in enumerate(_split_lyric_text(text)):
                lines.append(
                    {
                        "line_id": create_lyric_line_id(
                            str(data.get("section_id") or "section"), index
                        ),
                        "text": line_text,
                        "rhyme_label": None,
                    }
                )
        data["text"] = text
        data["lines"] = lines
        return data

    @field_validator("section_id", "label", "text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("lines")
    @classmethod
    def require_unique_line_ids(cls, value: list[LyricLine]) -> list[LyricLine]:
        ids = [line.line_id for line in value]
        if len(ids) != len(set(ids)):
            raise ValueError("line IDs must be unique within a section")
        return value


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


class ChordEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=64)
    measure: int = Field(ge=1, le=64)
    beat: float = Field(ge=1, le=32)
    duration_beats: float = Field(gt=0, le=32)
    symbol: str = Field(min_length=1, max_length=48)
    inversion: int | None = Field(default=None, ge=0, le=6)
    root: str | None = Field(default=None, max_length=8)
    bass: str | None = Field(default=None, max_length=8)
    quality: str | None = Field(default=None, max_length=64)
    extensions: list[str] = Field(default_factory=list, max_length=8)
    pitch_classes: list[int] = Field(default_factory=list, max_length=12)
    midi_notes: list[int] = Field(default_factory=list, max_length=12)
    roman_numeral: str | None = Field(default=None, max_length=32)
    nashville_number: str | None = Field(default=None, max_length=32)
    borrowed: bool = False

    @field_validator("event_id", "symbol")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("pitch_classes")
    @classmethod
    def validate_pitch_classes(cls, value: list[int]) -> list[int]:
        if any(pitch_class < 0 or pitch_class > 11 for pitch_class in value):
            raise ValueError("pitch classes must be between 0 and 11")
        return value

    @field_validator("midi_notes")
    @classmethod
    def validate_midi_notes(cls, value: list[int]) -> list[int]:
        if any(note < 0 or note > 127 for note in value):
            raise ValueError("MIDI notes must be between 0 and 127")
        return value


class ChordMeasure(BaseModel):
    measure_number: int = Field(ge=1, le=64)
    events: list[ChordEvent] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def require_matching_measure_and_unique_ids(self) -> "ChordMeasure":
        if any(event.measure != self.measure_number for event in self.events):
            raise ValueError("chord event measure must match its parent measure")
        event_ids = [event.event_id for event in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("chord event IDs must be unique within a measure")
        return self


class ChordSection(BaseModel):
    section_id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=120)
    bars: int = Field(default=1, ge=1, le=64)
    chords: list[str] = Field(default_factory=list, max_length=256)
    measures: list[ChordMeasure] = Field(default_factory=list, min_length=1, max_length=64)

    @model_validator(mode="before")
    @classmethod
    def synchronize_legacy_and_structured_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        section_id = str(data.get("section_id") or "section")
        raw_measures = data.get("measures")
        measures = list(raw_measures) if isinstance(raw_measures, list) else []
        raw_chords = data.get("chords")
        chords = [str(chord).strip() for chord in raw_chords or [] if str(chord).strip()]

        if measures:
            chords = [
                str(event.get("symbol") or "").strip()
                for measure in measures
                if isinstance(measure, dict)
                for event in measure.get("events", [])
                if isinstance(event, dict) and str(event.get("symbol") or "").strip()
            ]
        elif chords:
            bar_count = max(1, min(64, int(data.get("bars") or len(chords))))
            measures = [
                {
                    "measure_number": index + 1,
                    "events": [
                        {
                            "event_id": create_chord_event_id(section_id, index + 1, 0),
                            "measure": index + 1,
                            "beat": 1,
                            "duration_beats": 4,
                            "symbol": chords[index % len(chords)],
                        }
                    ],
                }
                for index in range(bar_count)
            ]

        data["bars"] = len(measures) or int(data.get("bars") or 1)
        data["chords"] = chords
        data["measures"] = measures
        return data

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

    @model_validator(mode="after")
    def require_ordered_measures_and_unique_event_ids(self) -> "ChordSection":
        expected = list(range(1, len(self.measures) + 1))
        if [measure.measure_number for measure in self.measures] != expected:
            raise ValueError("chord measures must be sequential and start at 1")
        event_ids = [event.event_id for measure in self.measures for event in measure.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("chord event IDs must be unique within a section")
        return self


def create_chord_event_id(section_id: str, measure_number: int, event_index: int) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            f"abachiwave:chords:{section_id}:{measure_number}:{event_index}",
        )
    )


class LyricsGenerateRequest(BaseModel):
    song_spec_id: UUID
    provider_profile_id: UUID | None = None
    candidate_count: int | None = Field(default=None, ge=1, le=3)


class LyricsUpdate(BaseModel):
    sections: list[LyricSection] = Field(min_length=1)
    hook_candidates: list[HookCandidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_unique_ids(self) -> "LyricsUpdate":
        section_ids = [section.section_id for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("section IDs must be unique")
        line_ids = [line.line_id for section in self.sections for line in section.lines]
        if len(line_ids) != len(set(line_ids)):
            raise ValueError("line IDs must be unique across the lyrics version")
        hook_ids = [candidate.id for candidate in self.hook_candidates]
        if len(hook_ids) != len(set(hook_ids)):
            raise ValueError("hook candidate IDs must be unique")
        return self


class LyricsVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    song_spec_id: UUID
    version_number: int
    parent_version_id: UUID | None
    source_revision_request_id: UUID | None
    schema_version: int
    sections: list[LyricSection]
    hook_candidates: list[HookCandidate]
    created_at: datetime
    updated_at: datetime


def create_lyric_line_id(section_id: str, index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"abachiwave:lyrics:{section_id}:{index}"))


def lyric_syllable_count(text: str) -> int:
    cjk_count = len(_CJK_PATTERN.findall(text))
    english_count = 0
    for word in _WORD_PATTERN.findall(text):
        normalized = word.lower().strip("'")
        groups = len(_VOWEL_GROUP_PATTERN.findall(normalized))
        if normalized.endswith("e") and groups > 1 and not normalized.endswith(("le", "ye")):
            groups -= 1
        english_count += max(1, groups)
    return cjk_count + english_count


def lyric_rhyme_key(text: str) -> str | None:
    match = _ENDING_PATTERN.search(text.strip())
    if not match:
        return None
    ending = match.group(1).casefold()
    if _CJK_PATTERN.fullmatch(ending):
        return ending
    vowel_tail = re.search(r"[aeiouy][a-z]*$", ending)
    return vowel_tail.group(0) if vowel_tail else ending[-3:]


def _split_lyric_text(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _line_text(value: object) -> str:
    if isinstance(value, LyricLine):
        return value.text.strip()
    if isinstance(value, dict):
        return str(value.get("text") or "").strip()
    return ""


class ChordGenerateRequest(BaseModel):
    song_spec_id: UUID
    lyrics_version_id: UUID | None = None


class ChordUpdate(BaseModel):
    sections: list[ChordSection] = Field(min_length=1)

    @model_validator(mode="after")
    def require_unique_ids(self) -> "ChordUpdate":
        section_ids = [section.section_id for section in self.sections]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError("section IDs must be unique")
        event_ids = [
            event.event_id
            for section in self.sections
            for measure in section.measures
            for event in measure.events
        ]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("chord event IDs must be unique across the progression")
        return self


class ChordTransposeRequest(BaseModel):
    semitones: int = Field(ge=-11, le=11)
    section_ids: list[str] | None = Field(default=None, min_length=1)

    @field_validator("semitones")
    @classmethod
    def require_nonzero_interval(cls, value: int) -> int:
        if value == 0:
            raise ValueError("semitones must not be zero")
        return value

    @field_validator("section_ids")
    @classmethod
    def normalize_section_ids(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [section_id.strip() for section_id in value if section_id.strip()]
        if not normalized:
            raise ValueError("section_ids must not be empty")
        if len(normalized) != len(set(normalized)):
            raise ValueError("section_ids must be unique")
        return normalized


class ChordPreviewRead(BaseModel):
    source_chord_id: UUID
    key: str
    tempo_bpm: int
    time_signature: str
    sections: list[ChordSection]


class ChordProgressionVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    song_spec_id: UUID
    lyrics_version_id: UUID | None
    version_number: int
    parent_version_id: UUID | None
    schema_version: int
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
    provider_profile_id: UUID | None = None
    candidate_count: int | None = Field(default=None, ge=1, le=3)

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

import re

from abachiwave.models.composition import MidiAssetKind
from abachiwave.schemas.composition import (
    ArrangementPlan,
    ArrangementSection,
    ChordSection,
    HookCandidate,
    LyricSection,
)
from abachiwave.schemas.song_specs import SongSpecData

MAJOR_SCALE_STEPS = (0, 2, 4, 5, 7, 9, 11)
MINOR_SCALE_STEPS = (0, 2, 3, 5, 7, 8, 10)
NOTE_TO_SEMITONE = {
    "C": 0,
    "C#": 1,
    "DB": 1,
    "D": 2,
    "D#": 3,
    "EB": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "GB": 6,
    "G": 7,
    "G#": 8,
    "AB": 8,
    "A": 9,
    "A#": 10,
    "BB": 10,
    "B": 11,
}
SEMITONE_TO_NOTE = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def build_lyrics_from_song_spec(
    song_spec: SongSpecData,
) -> tuple[list[LyricSection], list[HookCandidate]]:
    theme = song_spec.theme or "the central idea"
    structure = song_spec.song_structure or ["verse", "chorus"]
    mood_curve = song_spec.mood_curve or {}
    sections = [
        LyricSection(
            section_id=_section_id(section),
            label=_section_label(section),
            text=_section_lyric_text(section, theme, mood_curve),
        )
        for section in structure
    ]
    hook_candidates = [
        HookCandidate(id="hook_1", text=f"Carry {theme.lower()} into the light"),
        HookCandidate(id="hook_2", text=f"We keep moving through {theme.lower()}"),
        HookCandidate(id="hook_3", text=f"{theme[:80]} keeps calling us home"),
    ]
    return sections, hook_candidates


def build_chords_from_song_spec(
    song_spec: SongSpecData,
    lyric_sections: list[LyricSection] | None = None,
) -> list[ChordSection]:
    structure = (
        [section.section_id for section in lyric_sections]
        if lyric_sections
        else song_spec.song_structure or ["verse", "chorus"]
    )
    chord_map = _diatonic_chords(song_spec.key or "C major")
    return [
        ChordSection(
            section_id=_section_id(section),
            label=_section_label(section),
            bars=len(chords),
            chords=chords,
        )
        for section in structure
        for chords in [_progression_for_section(section, chord_map)]
    ]


def build_arrangement_from_assets(
    *,
    song_spec: SongSpecData,
    lyric_sections: list[LyricSection],
    chord_sections: list[ChordSection],
    midi_kinds: list[MidiAssetKind],
) -> ArrangementPlan:
    genre_text = ", ".join(song_spec.genre or ["modern pop"])
    theme = song_spec.theme or "the song idea"
    section_lookup = {section.section_id: section for section in lyric_sections}
    arrangement_sections = [
        ArrangementSection(
            section_id=section.section_id,
            label=section.label,
            instruments=_instruments_for_section(section.section_id, genre_text),
            energy_level=_energy_for_section(section.section_id),
            production_notes=_production_notes_for_section(
                section,
                section_lookup.get(section.section_id),
            ),
        )
        for section in chord_sections
    ]
    midi_text = ", ".join(sorted(kind.value for kind in midi_kinds))
    return ArrangementPlan(
        overview=(
            f"Build a {genre_text} arrangement around {theme.lower()} with clear section "
            "contrast and a focused lift into the hook."
        ),
        sections=arrangement_sections,
        mix_notes=(
            "Keep vocal and hook MIDI centered, pan guitars/keys moderately wide, and leave "
            "low-mid space for bass movement. Automate reverb sends upward into final chorus."
        ),
        reference_notes=(
            f"Use the approved SongSpec tempo/key as the production grid and treat {midi_text} "
            "MIDI files as editable guide parts rather than final performances."
        ),
    )


def _section_lyric_text(section: str, theme: str, mood_curve: dict[str, str]) -> str:
    section_id = _section_id(section)
    mood = mood_curve.get(section_id) or mood_curve.get("overall") or "steady and focused"
    if "chorus" in section_id:
        lines = [
            f"We lift the sound of {theme.lower()}",
            f"Every heartbeat turns toward {mood}",
            "The night opens wide when the voices arrive",
            f"We sing {theme.lower()} until it feels alive",
        ]
    elif "bridge" in section_id:
        lines = [
            f"A quiet turn reveals {theme.lower()}",
            f"The band drops low, then climbs from {mood}",
            "One last breath before the sky breaks through",
            "A new line answers what we thought we knew",
        ]
    else:
        lines = [
            f"I trace the shape of {theme.lower()}",
            f"Small details move in a {mood} way",
            "The room holds still around the first confession",
            "Each step finds rhythm in the delay",
        ]
    return "\n".join(lines)


def _instruments_for_section(section_id: str, genre_text: str) -> list[str]:
    base = ["lead vocal", "electric bass", "drum kit"]
    if "electronic" in genre_text:
        base = ["lead vocal", "sub bass", "drum machine"]
    if "intro" in section_id:
        return ["filtered keys", "ambient guitar", "soft pulse"]
    if "verse" in section_id and "pre_chorus" not in section_id:
        return [*base, "muted guitar", "warm pad"]
    if "pre_chorus" in section_id:
        return [*base, "rising synth", "picked guitar"]
    if "chorus" in section_id:
        return [*base, "wide guitars", "stacked hook synth", "backing vocals"]
    if "bridge" in section_id:
        return ["lead vocal", "half-time drums", "textural keys", "subtle strings"]
    if "outro" in section_id:
        return ["lead vocal ad-libs", "reduced drums", "delay guitar"]
    return [*base, "supporting keys"]


def _energy_for_section(section_id: str) -> int:
    if "intro" in section_id or "outro" in section_id:
        return 3
    if "verse" in section_id and "pre_chorus" not in section_id:
        return 4
    if "pre_chorus" in section_id:
        return 6
    if "final_chorus" in section_id:
        return 9
    if "chorus" in section_id:
        return 8
    if "bridge" in section_id:
        return 5
    return 5


def _production_notes_for_section(
    chord_section: ChordSection,
    lyric_section: LyricSection | None,
) -> str:
    lyric_hint = ""
    if lyric_section is not None:
        line_count = len([line for line in lyric_section.text.splitlines() if line.strip()])
        lyric_hint = f" Shape the phrasing around {line_count} lyric lines."
    chords = " - ".join(chord_section.chords)
    return (
        f"Use {chord_section.bars} bars over {chords}; keep transitions quantized to the "
        f"section boundary and reserve the strongest fill for the last bar.{lyric_hint}"
    )


def _progression_for_section(section: str, chord_map: dict[str, str]) -> list[str]:
    section_id = _section_id(section)
    if "pre_chorus" in section_id:
        degrees = ("IV", "V", "vi", "V")
    elif "chorus" in section_id:
        degrees = ("I", "V", "vi", "IV")
    elif "bridge" in section_id:
        degrees = ("vi", "IV", "I", "V")
    elif "outro" in section_id:
        degrees = ("I", "IV", "I", "I")
    else:
        degrees = ("I", "V", "vi", "IV")
    return [chord_map[degree] for degree in degrees]


def _diatonic_chords(key: str) -> dict[str, str]:
    tonic, minor = _parse_key(key)
    root = NOTE_TO_SEMITONE.get(tonic.upper(), 0)
    if minor:
        scale = [(root + step) % 12 for step in MINOR_SCALE_STEPS]
        return {
            "I": _format_chord(scale[0], minor=True),
            "i": _format_chord(scale[0], minor=True),
            "IV": _format_chord(scale[3], minor=True),
            "iv": _format_chord(scale[3], minor=True),
            "V": _format_chord(scale[4], minor=True),
            "v": _format_chord(scale[4], minor=True),
            "vi": _format_chord(scale[5], minor=False),
            "VI": _format_chord(scale[5], minor=False),
            "VII": _format_chord(scale[6], minor=False),
        }
    scale = [(root + step) % 12 for step in MAJOR_SCALE_STEPS]
    return {
        "I": _format_chord(scale[0], minor=False),
        "ii": _format_chord(scale[1], minor=True),
        "iii": _format_chord(scale[2], minor=True),
        "IV": _format_chord(scale[3], minor=False),
        "V": _format_chord(scale[4], minor=False),
        "vi": _format_chord(scale[5], minor=True),
    }


def _parse_key(key: str) -> tuple[str, bool]:
    match = re.search(r"\b([A-Ga-g](?:#|b)?)(?:\s+|-)?(major|minor|maj|min|m)?\b", key)
    if not match:
        return "C", False
    quality = (match.group(2) or "major").lower()
    tonic = match.group(1).replace("b", "B")
    return tonic, quality in {"minor", "min", "m"}


def _format_chord(semitone: int, *, minor: bool) -> str:
    suffix = "m" if minor else ""
    return f"{SEMITONE_TO_NOTE[semitone]}{suffix}"


def _section_id(section: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", section.lower()).strip("_")
    return normalized or "section"


def _section_label(section: str) -> str:
    return _section_id(section).replace("_", " ").title()

import re
from dataclasses import dataclass
from functools import lru_cache

from music21 import harmony, roman
from music21 import interval as music21_interval
from music21 import key as music21_key
from music21.chord import ChordException

from abachiwave.schemas.composition import (
    ChordEvent,
    ChordMeasure,
    ChordSection,
    create_chord_event_id,
)

_TIME_SIGNATURE_PATTERN = re.compile(r"^\s*(\d{1,2})\s*/\s*(\d{1,2})\s*$")
_KEY_PATTERN = re.compile(
    r"^\s*([A-Ga-g](?:#|b|-)?)(?:\s+|-)?(major|minor|maj|min|m)?\s*$",
    re.IGNORECASE,
)
_FLAT_NOTE_PATTERN = re.compile(r"([A-Ga-g])b")
_MUSIC21_FLAT_PATTERN = re.compile(
    r"([A-G])-(?=(?:maj|min|m|dim|aug|sus|add|[0-9]|/|$))",
)
_EXTENSION_PATTERN = re.compile(r"(13|11|9|7|6)")
_NASHVILLE_DEGREES = {
    0: "1",
    1: "b2",
    2: "2",
    3: "b3",
    4: "3",
    5: "4",
    6: "#4",
    7: "5",
    8: "b6",
    9: "6",
    10: "b7",
    11: "7",
}


class ChordTheoryError(ValueError):
    pass


@dataclass(frozen=True)
class ChordAnalysis:
    symbol: str
    inversion: int
    root: str | None
    bass: str | None
    quality: str | None
    extensions: tuple[str, ...]
    pitch_classes: tuple[int, ...]
    midi_notes: tuple[int, ...]
    roman_numeral: str | None
    nashville_number: str | None
    borrowed: bool


def parse_time_signature(value: str) -> tuple[int, int]:
    match = _TIME_SIGNATURE_PATTERN.fullmatch(value)
    if match is None:
        raise ChordTheoryError(f"Unsupported time signature: {value}")
    numerator = int(match.group(1))
    denominator = int(match.group(2))
    if numerator < 1 or numerator > 32 or denominator not in {1, 2, 4, 8, 16}:
        raise ChordTheoryError(f"Unsupported time signature: {value}")
    return numerator, denominator


def normalize_chord_sections(
    sections: list[ChordSection],
    *,
    key_name: str,
    time_signature: str,
) -> list[ChordSection]:
    beats_per_measure, _denominator = parse_time_signature(time_signature)
    parsed_key = parse_key(key_name)
    normalized_sections: list[ChordSection] = []
    used_event_ids: set[str] = set()

    for section in sections:
        normalized_measures: list[ChordMeasure] = []
        for expected_measure, measure in enumerate(section.measures, start=1):
            if measure.measure_number != expected_measure:
                raise ChordTheoryError(
                    f"Section {section.label} measures must be sequential and start at 1"
                )
            normalized_events: list[ChordEvent] = []
            previous_end = 0.0
            for event_index, event in enumerate(
                sorted(measure.events, key=lambda item: (item.beat, item.event_id))
            ):
                duration = event.duration_beats
                if (
                    len(measure.events) == 1
                    and event.beat == 1
                    and duration == 4
                    and beats_per_measure != 4
                    and not event.midi_notes
                ):
                    duration = float(beats_per_measure)
                event_end = event.beat - 1 + duration
                if event.beat > beats_per_measure or event_end > beats_per_measure + 1e-6:
                    raise ChordTheoryError(
                        f"Chord {event.symbol} exceeds measure {measure.measure_number} "
                        f"in {time_signature}"
                    )
                if event.beat - 1 < previous_end - 1e-6:
                    raise ChordTheoryError(
                        f"Chord events overlap in {section.label}, measure {measure.measure_number}"
                    )
                previous_end = event_end
                analysis = analyze_chord_symbol(event.symbol, parsed_key, event.inversion)
                event_id = event.event_id
                if event_id in used_event_ids:
                    event_id = create_chord_event_id(
                        section.section_id,
                        measure.measure_number,
                        event_index,
                    )
                used_event_ids.add(event_id)
                normalized_events.append(
                    ChordEvent(
                        event_id=event_id,
                        measure=measure.measure_number,
                        beat=event.beat,
                        duration_beats=duration,
                        symbol=analysis.symbol,
                        inversion=analysis.inversion,
                        root=analysis.root,
                        bass=analysis.bass,
                        quality=analysis.quality,
                        extensions=list(analysis.extensions),
                        pitch_classes=list(analysis.pitch_classes),
                        midi_notes=list(analysis.midi_notes),
                        roman_numeral=analysis.roman_numeral,
                        nashville_number=analysis.nashville_number,
                        borrowed=analysis.borrowed,
                    )
                )
            normalized_measures.append(
                ChordMeasure(
                    measure_number=measure.measure_number,
                    events=normalized_events,
                )
            )
        normalized_sections.append(
            ChordSection(
                section_id=section.section_id,
                label=section.label,
                measures=[measure.model_dump(mode="json") for measure in normalized_measures],
            )
        )
    return normalized_sections


def transpose_chord_sections(
    sections: list[ChordSection],
    *,
    key_name: str,
    time_signature: str,
    semitones: int,
    section_ids: set[str] | None,
) -> tuple[str, list[ChordSection]]:
    selected_ids = section_ids or {section.section_id for section in sections}
    missing_ids = selected_ids.difference(section.section_id for section in sections)
    if missing_ids:
        missing = ", ".join(sorted(missing_ids))
        raise ChordTheoryError(f"Chord sections not found: {missing}")

    full_progression = section_ids is None
    output_key = transpose_key_name(key_name, semitones) if full_progression else key_name
    transposition: int | music21_interval.Interval = semitones
    if full_progression:
        transposition = music21_interval.Interval(
            parse_key(key_name).tonic,
            parse_key(output_key).tonic,
        )
    transposed_sections: list[ChordSection] = []
    for section in sections:
        measures: list[dict[str, object]] = []
        for measure in section.measures:
            events: list[dict[str, object]] = []
            for event in measure.events:
                symbol = (
                    transpose_chord_symbol(event.symbol, transposition)
                    if section.section_id in selected_ids
                    else event.symbol
                )
                events.append(
                    {
                        "event_id": event.event_id,
                        "measure": event.measure,
                        "beat": event.beat,
                        "duration_beats": event.duration_beats,
                        "symbol": symbol,
                        "inversion": event.inversion,
                    }
                )
            measures.append(
                {
                    "measure_number": measure.measure_number,
                    "events": events,
                }
            )
        transposed_sections.append(
            ChordSection(
                section_id=section.section_id,
                label=section.label,
                measures=measures,
            )
        )
    return output_key, normalize_chord_sections(
        transposed_sections,
        key_name=output_key,
        time_signature=time_signature,
    )


def analyze_chord_symbol(
    symbol: str,
    parsed_key: music21_key.Key,
    inversion: int | None = None,
) -> ChordAnalysis:
    return _analyze_chord_symbol_cached(symbol.strip(), key_display_name(parsed_key), inversion)


@lru_cache(maxsize=2048)
def _analyze_chord_symbol_cached(
    symbol: str,
    key_name: str,
    inversion: int | None,
) -> ChordAnalysis:
    if _is_no_chord(symbol):
        return ChordAnalysis(
            symbol="N.C.",
            inversion=0,
            root=None,
            bass=None,
            quality=None,
            extensions=(),
            pitch_classes=(),
            midi_notes=(),
            roman_numeral="N.C.",
            nashville_number="N.C.",
            borrowed=False,
        )

    parsed_key = parse_key(key_name)
    try:
        chord = harmony.ChordSymbol(_to_music21_notation(symbol))
        if not chord.pitches or chord.root() is None:
            raise ChordTheoryError(f"Unsupported chord symbol: {symbol}")
        parsed_inversion = chord.inversion()
        target_inversion = parsed_inversion if inversion is None else inversion
        chord.inversion(target_inversion)
    except (ChordException, ValueError, TypeError) as exc:
        raise ChordTheoryError(f"Unsupported chord symbol: {symbol}") from exc

    root = chord.root()
    bass = chord.bass()
    if root is None or bass is None:
        raise ChordTheoryError(f"Unsupported chord symbol: {symbol}")
    pitch_classes = tuple(dict.fromkeys(pitch.pitchClass for pitch in chord.pitches))
    scale_pitch_classes = {pitch.pitchClass for pitch in parsed_key.getPitches()}
    try:
        roman_figure = str(roman.romanNumeralFromChord(chord, parsed_key).figure)
    except (ChordException, ValueError, TypeError):
        roman_figure = None
    quality = chord.chordKind or "unknown"
    return ChordAnalysis(
        symbol=_from_music21_notation(chord.figure),
        inversion=int(chord.inversion()),
        root=_from_music21_notation(root.name),
        bass=_from_music21_notation(bass.name),
        quality=quality,
        extensions=_extensions_for_chord(chord.figure, quality),
        pitch_classes=pitch_classes,
        midi_notes=_playback_midi_notes(tuple(int(pitch.midi) for pitch in chord.pitches)),
        roman_numeral=roman_figure,
        nashville_number=_nashville_number(chord, parsed_key, quality),
        borrowed=any(pitch_class not in scale_pitch_classes for pitch_class in pitch_classes),
    )


def transpose_chord_symbol(
    symbol: str,
    transposition: int | music21_interval.Interval,
) -> str:
    if _is_no_chord(symbol):
        return "N.C."
    try:
        chord = harmony.ChordSymbol(_to_music21_notation(symbol))
        transposed = chord.transpose(transposition)
    except (ChordException, ValueError, TypeError) as exc:
        raise ChordTheoryError(f"Unsupported chord symbol: {symbol}") from exc
    if not isinstance(transposed, harmony.ChordSymbol):
        raise ChordTheoryError(f"Could not transpose chord symbol: {symbol}")
    return _from_music21_notation(transposed.figure)


def parse_key(value: str) -> music21_key.Key:
    match = _KEY_PATTERN.fullmatch(value.replace("\u266d", "b").replace("\u266f", "#"))
    if match is None:
        raise ChordTheoryError(f"Unsupported key: {value}")
    raw_tonic = match.group(1)
    tonic = _to_music21_notation(f"{raw_tonic[0].upper()}{raw_tonic[1:]}")
    raw_mode = (match.group(2) or "major").lower()
    mode = "minor" if raw_mode in {"minor", "min", "m"} else "major"
    try:
        return music21_key.Key(tonic, mode)
    except (ValueError, TypeError) as exc:
        raise ChordTheoryError(f"Unsupported key: {value}") from exc


def transpose_key_name(value: str, semitones: int) -> str:
    transposed = parse_key(value).transpose(semitones)
    if not isinstance(transposed, music21_key.Key):
        raise ChordTheoryError(f"Could not transpose key: {value}")
    return key_display_name(transposed)


def key_display_name(value: music21_key.Key) -> str:
    return f"{_from_music21_notation(value.tonic.name)} {value.mode}"


def _extensions_for_chord(figure: str, quality: str) -> tuple[str, ...]:
    extensions = list(dict.fromkeys(_EXTENSION_PATTERN.findall(f" {figure}")))
    quality_extensions = {
        "sixth": "6",
        "seventh": "7",
        "ninth": "9",
        "11th": "11",
        "13th": "13",
    }
    for label, extension in quality_extensions.items():
        if label in quality and extension not in extensions:
            extensions.append(extension)
    return tuple(extensions)


def _nashville_number(
    chord: harmony.ChordSymbol,
    parsed_key: music21_key.Key,
    quality: str,
) -> str:
    root = chord.root()
    bass = chord.bass()
    if root is None or bass is None:
        return "?"
    root_degree = _NASHVILLE_DEGREES[(root.pitchClass - parsed_key.tonic.pitchClass) % 12]
    suffix = _quality_suffix(quality)
    result = f"{root_degree}{suffix}"
    if bass.pitchClass != root.pitchClass:
        bass_degree = _NASHVILLE_DEGREES[(bass.pitchClass - parsed_key.tonic.pitchClass) % 12]
        result = f"{result}/{bass_degree}"
    return result


def _quality_suffix(quality: str) -> str:
    if quality == "major":
        return ""
    if quality == "minor":
        return "m"
    if quality == "major-seventh":
        return "maj7"
    if quality == "minor-seventh":
        return "m7"
    if quality == "dominant-seventh":
        return "7"
    if "diminished" in quality:
        return "dim7" if "seventh" in quality else "dim"
    if "augmented" in quality:
        return "aug"
    if "suspended" in quality:
        return "sus"
    match = re.search(r"(13|11|9|7|6)", quality)
    return match.group(1) if match else ""


def _playback_midi_notes(notes: tuple[int, ...]) -> tuple[int, ...]:
    if not notes:
        return ()
    normalized = list(notes)
    while min(normalized) < 48:
        normalized = [note + 12 for note in normalized]
    while max(normalized) > 84:
        normalized = [note - 12 for note in normalized]
    return tuple(normalized)


def _is_no_chord(symbol: str) -> bool:
    return symbol.strip().upper().replace(" ", "") in {"N.C.", "N.C", "NC"}


def _to_music21_notation(value: str) -> str:
    normalized = value.strip().replace("\u266d", "b").replace("\u266f", "#")
    return _FLAT_NOTE_PATTERN.sub(lambda match: f"{match.group(1).upper()}-", normalized)


def _from_music21_notation(value: str) -> str:
    return _MUSIC21_FLAT_PATTERN.sub(r"\1b", value)

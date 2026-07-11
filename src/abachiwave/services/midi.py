from io import BytesIO
from re import match

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from abachiwave.models.composition import MidiAssetKind
from abachiwave.schemas.composition import ChordSection, LyricSection
from abachiwave.schemas.song_specs import SongSpecData

TICKS_PER_BEAT = 480
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
MAJOR_SCALE = (0, 2, 4, 5, 7, 9, 11)


def build_midi_bytes(
    *,
    kind: MidiAssetKind,
    song_spec: SongSpecData,
    chord_sections: list[ChordSection],
    lyric_sections: list[LyricSection],
) -> bytes:
    midi = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    tempo_bpm = song_spec.tempo_bpm or 120
    numerator, denominator = _parse_time_signature(song_spec.time_signature or "4/4")
    _add_meta_track(midi, tempo_bpm, numerator, denominator)
    if kind is MidiAssetKind.chord:
        _add_chord_track(midi, chord_sections, numerator)
    elif kind is MidiAssetKind.hook:
        _add_hook_track(midi, song_spec, lyric_sections, numerator)
    else:
        _add_melody_track(midi, song_spec, chord_sections, numerator)
    buffer = BytesIO()
    midi.save(file=buffer)
    return buffer.getvalue()


def _add_meta_track(
    midi: MidiFile,
    tempo_bpm: int,
    numerator: int,
    denominator: int,
) -> None:
    track = MidiTrack()
    track.append(MetaMessage("track_name", name="Abachiwave Meta", time=0))
    track.append(MetaMessage("set_tempo", tempo=bpm2tempo(tempo_bpm), time=0))
    track.append(
        MetaMessage(
            "time_signature",
            numerator=numerator,
            denominator=denominator,
            time=0,
        )
    )
    track.append(MetaMessage("end_of_track", time=0))
    midi.tracks.append(track)


def _add_chord_track(
    midi: MidiFile,
    chord_sections: list[ChordSection],
    beats_per_bar: int,
) -> None:
    track = MidiTrack()
    track.append(MetaMessage("track_name", name="Chord Progression", time=0))
    track.append(Message("program_change", program=0, time=0))
    bar_ticks = beats_per_bar * TICKS_PER_BEAT
    for section in chord_sections:
        for chord in section.chords:
            notes = _chord_to_notes(chord)
            for note in notes:
                track.append(Message("note_on", note=note, velocity=70, time=0))
            for index, note in enumerate(notes):
                track.append(
                    Message(
                        "note_off",
                        note=note,
                        velocity=0,
                        time=bar_ticks if index == 0 else 0,
                    )
                )
    track.append(MetaMessage("end_of_track", time=0))
    midi.tracks.append(track)


def _add_melody_track(
    midi: MidiFile,
    song_spec: SongSpecData,
    chord_sections: list[ChordSection],
    beats_per_bar: int,
) -> None:
    track = MidiTrack()
    track.append(MetaMessage("track_name", name="Deterministic Melody", time=0))
    track.append(Message("program_change", program=80, time=0))
    scale = _scale_notes(song_spec.key or "C major", octave=5)
    total_bars = max(4, sum(max(section.bars, len(section.chords)) for section in chord_sections))
    for beat_index in range(total_bars * beats_per_bar):
        note = scale[(beat_index * 2 + beat_index // beats_per_bar) % len(scale)]
        track.append(Message("note_on", note=note, velocity=76, time=0))
        track.append(Message("note_off", note=note, velocity=0, time=TICKS_PER_BEAT))
    track.append(MetaMessage("end_of_track", time=0))
    midi.tracks.append(track)


def _add_hook_track(
    midi: MidiFile,
    song_spec: SongSpecData,
    lyric_sections: list[LyricSection],
    beats_per_bar: int,
) -> None:
    track = MidiTrack()
    track.append(MetaMessage("track_name", name="Hook Motif", time=0))
    track.append(Message("program_change", program=81, time=0))
    scale = _scale_notes(song_spec.key or "C major", octave=5)
    hook_seed = sum(len(section.text) for section in lyric_sections) or 1
    motif = [scale[(hook_seed + offset) % len(scale)] for offset in (0, 2, 4, 2)]
    for _ in range(2):
        for beat_index in range(beats_per_bar):
            note = motif[beat_index % len(motif)]
            track.append(Message("note_on", note=note, velocity=88, time=0))
            track.append(Message("note_off", note=note, velocity=0, time=TICKS_PER_BEAT))
    track.append(MetaMessage("end_of_track", time=0))
    midi.tracks.append(track)


def _parse_time_signature(value: str) -> tuple[int, int]:
    parts = value.split("/", maxsplit=1)
    if len(parts) != 2:
        return 4, 4
    numerator = int(parts[0]) if parts[0].isdigit() else 4
    denominator = int(parts[1]) if parts[1].isdigit() else 4
    return max(1, numerator), max(1, denominator)


def _scale_notes(key: str, *, octave: int) -> list[int]:
    tonic = _key_tonic(key)
    root = NOTE_TO_SEMITONE.get(tonic.upper(), 0)
    base = 12 * (octave + 1)
    return [base + ((root + step) % 12) for step in MAJOR_SCALE]


def _key_tonic(key: str) -> str:
    key_match = match(r"^\s*([A-Ga-g](?:#|b)?)", key)
    if key_match is None:
        return "C"
    return key_match.group(1).replace("b", "B")


def _chord_to_notes(chord: str) -> list[int]:
    chord_match = match(r"^\s*([A-Ga-g](?:#|b)?)(m|minor|dim)?", chord)
    if chord_match is None:
        return [60, 64, 67]
    root_name = chord_match.group(1).replace("b", "B").upper()
    quality = (chord_match.group(2) or "").lower()
    root = 48 + NOTE_TO_SEMITONE.get(root_name, 0)
    if quality == "dim":
        intervals = (0, 3, 6)
    elif quality in {"m", "minor"}:
        intervals = (0, 3, 7)
    else:
        intervals = (0, 4, 7)
    return [root + interval for interval in intervals]

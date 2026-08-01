from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from re import match
from uuid import NAMESPACE_URL, uuid5

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo, tempo2bpm

from abachiwave.models.composition import MidiAssetKind, MidiTransformOperation
from abachiwave.schemas.composition import (
    ChordSection,
    LyricSection,
    MidiNoteEvent,
    MidiTempoEvent,
    MidiTimeSignatureEvent,
    MidiTransformRequest,
)
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


@dataclass(frozen=True)
class MidiDocument:
    note_events: list[MidiNoteEvent]
    tempo_map: list[MidiTempoEvent]
    time_signature_map: list[MidiTimeSignatureEvent]


def build_midi_document(
    *,
    kind: MidiAssetKind,
    song_spec: SongSpecData,
    chord_sections: list[ChordSection],
    lyric_sections: list[LyricSection],
) -> MidiDocument:
    tempo_bpm = song_spec.tempo_bpm or 120
    numerator, denominator = parse_time_signature(song_spec.time_signature or "4/4")
    if kind is MidiAssetKind.chord:
        notes = _build_chord_notes(chord_sections, numerator, denominator)
    elif kind is MidiAssetKind.hook:
        notes = _build_hook_notes(song_spec, lyric_sections, numerator, denominator)
    else:
        notes = _build_melody_notes(song_spec, chord_sections, numerator, denominator)
    return MidiDocument(
        note_events=notes,
        tempo_map=[MidiTempoEvent(beat=0, bpm=tempo_bpm)],
        time_signature_map=[
            MidiTimeSignatureEvent(
                beat=0,
                numerator=numerator,
                denominator=denominator,
            )
        ],
    )


def render_midi_document(
    *,
    kind: MidiAssetKind,
    note_events: list[MidiNoteEvent],
    tempo_map: list[MidiTempoEvent],
    time_signature_map: list[MidiTimeSignatureEvent],
) -> bytes:
    midi = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    midi.tracks.append(_build_meta_track(tempo_map, time_signature_map))
    midi.tracks.append(_build_note_track(kind, note_events))
    buffer = BytesIO()
    midi.save(file=buffer)
    return buffer.getvalue()


def parse_midi_document(data: bytes) -> MidiDocument:
    midi = MidiFile(file=BytesIO(data))
    ticks_per_beat = midi.ticks_per_beat or TICKS_PER_BEAT
    notes: list[MidiNoteEvent] = []
    tempos: list[MidiTempoEvent] = []
    signatures: list[MidiTimeSignatureEvent] = []
    note_ordinal = 0

    for track_index, track in enumerate(midi.tracks):
        absolute_tick = 0
        active: dict[tuple[int, int], list[tuple[int, int, int]]] = defaultdict(list)
        for message in track:
            absolute_tick += int(message.time)
            beat = absolute_tick / ticks_per_beat
            if message.type == "set_tempo":
                tempos.append(MidiTempoEvent(beat=beat, bpm=round(tempo2bpm(message.tempo), 6)))
                continue
            if message.type == "time_signature":
                signatures.append(
                    MidiTimeSignatureEvent(
                        beat=beat,
                        numerator=message.numerator,
                        denominator=message.denominator,
                    )
                )
                continue
            if message.type == "note_on" and message.velocity > 0:
                active[(message.channel, message.note)].append(
                    (absolute_tick, message.velocity, note_ordinal)
                )
                note_ordinal += 1
                continue
            if message.type not in {"note_off", "note_on"}:
                continue
            key = (message.channel, message.note)
            if not active[key]:
                continue
            start_tick, velocity, ordinal = active[key].pop(0)
            end_tick = max(start_tick + 1, absolute_tick)
            notes.append(
                MidiNoteEvent(
                    note_id=str(
                        uuid5(
                            NAMESPACE_URL,
                            (
                                "abachiwave:midi:"
                                f"{track_index}:{message.channel}:{message.note}:"
                                f"{start_tick}:{end_tick}:{ordinal}"
                            ),
                        )
                    ),
                    pitch=message.note,
                    start_beat=start_tick / ticks_per_beat,
                    duration_beats=(end_tick - start_tick) / ticks_per_beat,
                    velocity=velocity,
                    channel=message.channel,
                )
            )

    return MidiDocument(
        note_events=_sort_notes(notes),
        tempo_map=_dedupe_tempos(tempos) or [MidiTempoEvent(beat=0, bpm=120)],
        time_signature_map=_dedupe_signatures(signatures)
        or [MidiTimeSignatureEvent(beat=0, numerator=4, denominator=4)],
    )


def transform_midi_notes(
    note_events: list[MidiNoteEvent],
    request: MidiTransformRequest,
    *,
    key_name: str,
) -> list[MidiNoteEvent]:
    selected_ids = set(request.note_ids) if request.note_ids else None
    transformed = [event.model_copy(deep=True) for event in note_events]

    if request.operation is MidiTransformOperation.legato:
        return _apply_legato(transformed, selected_ids, request.legato_gap_beats)

    for index, event in enumerate(transformed):
        if selected_ids is not None and event.note_id not in selected_ids:
            continue
        update: dict[str, float | int] = {}
        if request.operation is MidiTransformOperation.quantize:
            update["start_beat"] = _round_to_grid(event.start_beat, request.grid_beats)
            update["duration_beats"] = max(
                request.grid_beats,
                _round_to_grid(event.duration_beats, request.grid_beats),
            )
        elif request.operation is MidiTransformOperation.transpose:
            update["pitch"] = _clamp(event.pitch + request.semitones, 0, 127)
        elif request.operation is MidiTransformOperation.velocity:
            update["velocity"] = _clamp(event.velocity + request.velocity_delta, 1, 127)
        elif request.operation is MidiTransformOperation.humanize:
            digest = sha256(event.note_id.encode("utf-8")).digest()
            beat_shift = ((digest[0] / 255) * 2 - 1) * request.humanize_beats
            velocity_shift = round(((digest[1] / 255) * 2 - 1) * 8)
            update["start_beat"] = max(0, event.start_beat + beat_shift)
            update["velocity"] = _clamp(event.velocity + velocity_shift, 1, 127)
        elif request.operation is MidiTransformOperation.scale_snap:
            update["pitch"] = _snap_pitch_to_scale(event.pitch, key_name)
        transformed[index] = event.model_copy(update=update)
    return _sort_notes(transformed)


def parse_time_signature(value: str) -> tuple[int, int]:
    parts = value.split("/", maxsplit=1)
    if len(parts) != 2:
        return 4, 4
    numerator = int(parts[0]) if parts[0].isdigit() else 4
    denominator = int(parts[1]) if parts[1].isdigit() else 4
    if denominator & (denominator - 1):
        denominator = 4
    return _clamp(numerator, 1, 32), _clamp(denominator, 1, 32)


def _build_chord_notes(
    sections: list[ChordSection],
    numerator: int,
    denominator: int,
) -> list[MidiNoteEvent]:
    notes: list[MidiNoteEvent] = []
    section_start = 0.0
    beat_factor = 4 / denominator
    bar_beats = numerator * beat_factor
    for section in sections:
        for measure in section.measures:
            measure_start = section_start + (measure.measure_number - 1) * bar_beats
            for event_index, event in enumerate(measure.events):
                start_beat = measure_start + (event.beat - 1) * beat_factor
                duration = max(1 / TICKS_PER_BEAT, event.duration_beats * beat_factor)
                for note_index, pitch in enumerate(event.midi_notes):
                    notes.append(
                        MidiNoteEvent(
                            note_id=_generated_note_id(
                                MidiAssetKind.chord,
                                section.section_id,
                                measure.measure_number,
                                event_index,
                                note_index,
                            ),
                            section_id=section.section_id,
                            pitch=pitch,
                            start_beat=start_beat,
                            duration_beats=duration,
                            velocity=70,
                        )
                    )
        section_start += max(1, len(section.measures), section.bars) * bar_beats
    return _sort_notes(notes)


def _build_melody_notes(
    song_spec: SongSpecData,
    sections: list[ChordSection],
    numerator: int,
    denominator: int,
) -> list[MidiNoteEvent]:
    notes: list[MidiNoteEvent] = []
    scale = _scale_notes(song_spec.key or "C major", octave=5)
    beat_factor = 4 / denominator
    section_start = 0.0
    global_beat = 0
    source_sections = sections or [
        ChordSection(section_id="song", label="Song", bars=4, chords=["C"])
    ]
    for section in source_sections:
        bar_count = max(1, len(section.measures), section.bars)
        for beat_index in range(bar_count * numerator):
            pitch = scale[(global_beat * 2 + global_beat // numerator) % len(scale)]
            notes.append(
                MidiNoteEvent(
                    note_id=_generated_note_id(
                        MidiAssetKind.melody,
                        section.section_id,
                        beat_index,
                    ),
                    section_id=section.section_id,
                    pitch=pitch,
                    start_beat=section_start + beat_index * beat_factor,
                    duration_beats=beat_factor,
                    velocity=76,
                )
            )
            global_beat += 1
        section_start += bar_count * numerator * beat_factor
    return _sort_notes(notes)


def _build_hook_notes(
    song_spec: SongSpecData,
    sections: list[LyricSection],
    numerator: int,
    denominator: int,
) -> list[MidiNoteEvent]:
    scale = _scale_notes(song_spec.key or "C major", octave=5)
    hook_seed = sum(len(section.text) for section in sections) or 1
    motif = [scale[(hook_seed + offset) % len(scale)] for offset in (0, 2, 4, 2)]
    beat_factor = 4 / denominator
    hook_index = next(
        (
            index
            for index, section in enumerate(sections)
            if "chorus" in section.label.lower() or "hook" in section.label.lower()
        ),
        0,
    )
    section = sections[hook_index] if sections else None
    section_id = section.section_id if section else "hook"
    section_start = hook_index * 4 * numerator * beat_factor
    notes: list[MidiNoteEvent] = []
    for beat_index in range(numerator * 2):
        notes.append(
            MidiNoteEvent(
                note_id=_generated_note_id(MidiAssetKind.hook, section_id, beat_index),
                section_id=section_id,
                pitch=motif[beat_index % len(motif)],
                start_beat=section_start + beat_index * beat_factor,
                duration_beats=beat_factor,
                velocity=88,
            )
        )
    return notes


def _build_meta_track(
    tempo_map: list[MidiTempoEvent],
    time_signature_map: list[MidiTimeSignatureEvent],
) -> MidiTrack:
    track = MidiTrack([MetaMessage("track_name", name="Abachiwave Meta", time=0)])
    timeline: list[tuple[int, int, MetaMessage]] = []
    for tempo_event in tempo_map or [MidiTempoEvent(beat=0, bpm=120)]:
        timeline.append(
            (
                _beat_to_tick(tempo_event.beat),
                0,
                MetaMessage("set_tempo", tempo=bpm2tempo(tempo_event.bpm), time=0),
            )
        )
    for signature_event in time_signature_map or [
        MidiTimeSignatureEvent(beat=0, numerator=4, denominator=4)
    ]:
        timeline.append(
            (
                _beat_to_tick(signature_event.beat),
                1,
                MetaMessage(
                    "time_signature",
                    numerator=signature_event.numerator,
                    denominator=signature_event.denominator,
                    time=0,
                ),
            )
        )
    _append_absolute_messages(track, timeline)
    return track


def _build_note_track(kind: MidiAssetKind, notes: list[MidiNoteEvent]) -> MidiTrack:
    names = {
        MidiAssetKind.chord: "Chord Progression",
        MidiAssetKind.melody: "Melody",
        MidiAssetKind.hook: "Hook Motif",
    }
    programs = {
        MidiAssetKind.chord: 0,
        MidiAssetKind.melody: 80,
        MidiAssetKind.hook: 81,
    }
    track = MidiTrack(
        [
            MetaMessage("track_name", name=names[kind], time=0),
            Message("program_change", program=programs[kind], time=0),
        ]
    )
    timeline: list[tuple[int, int, Message]] = []
    for note in notes:
        start_tick = _beat_to_tick(note.start_beat)
        end_tick = max(start_tick + 1, _beat_to_tick(note.start_beat + note.duration_beats))
        timeline.append(
            (
                start_tick,
                1,
                Message(
                    "note_on",
                    note=note.pitch,
                    velocity=note.velocity,
                    channel=note.channel,
                    time=0,
                ),
            )
        )
        timeline.append(
            (
                end_tick,
                0,
                Message(
                    "note_off",
                    note=note.pitch,
                    velocity=0,
                    channel=note.channel,
                    time=0,
                ),
            )
        )
    _append_absolute_messages(track, timeline)
    return track


def _append_absolute_messages(
    track: MidiTrack,
    timeline: list[tuple[int, int, Message | MetaMessage]],
) -> None:
    last_tick = 0
    for absolute_tick, priority, message in sorted(
        timeline,
        key=lambda item: (item[0], item[1]),
    ):
        del priority
        message.time = max(0, absolute_tick - last_tick)
        track.append(message)
        last_tick = absolute_tick
    track.append(MetaMessage("end_of_track", time=0))


def _apply_legato(
    notes: list[MidiNoteEvent],
    selected_ids: set[str] | None,
    gap_beats: float,
) -> list[MidiNoteEvent]:
    selected = [
        note for note in notes if selected_ids is None or note.note_id in selected_ids
    ]
    selected.sort(key=lambda note: (note.channel, note.start_beat, note.pitch))
    by_channel: dict[int, list[MidiNoteEvent]] = defaultdict(list)
    for note in selected:
        by_channel[note.channel].append(note)
    replacements: dict[str, MidiNoteEvent] = {}
    for channel_notes in by_channel.values():
        for current, following in zip(channel_notes, channel_notes[1:], strict=False):
            available = following.start_beat - current.start_beat - gap_beats
            if available > 0:
                replacements[current.note_id] = current.model_copy(
                    update={"duration_beats": max(1 / TICKS_PER_BEAT, available)}
                )
    return _sort_notes([replacements.get(note.note_id, note) for note in notes])


def _snap_pitch_to_scale(pitch: int, key_name: str) -> int:
    root = NOTE_TO_SEMITONE.get(_key_tonic(key_name).upper(), 0)
    pitch_classes = {(root + step) % 12 for step in MAJOR_SCALE}
    candidates = [
        candidate
        for candidate in range(max(0, pitch - 6), min(127, pitch + 6) + 1)
        if candidate % 12 in pitch_classes
    ]
    return min(candidates, key=lambda candidate: (abs(candidate - pitch), candidate))


def _scale_notes(key: str, *, octave: int) -> list[int]:
    root = NOTE_TO_SEMITONE.get(_key_tonic(key).upper(), 0)
    base = 12 * (octave + 1)
    return [base + ((root + step) % 12) for step in MAJOR_SCALE]


def _key_tonic(key: str) -> str:
    key_match = match(r"^\s*([A-Ga-g](?:#|b)?)", key)
    return key_match.group(1).replace("b", "B") if key_match else "C"


def _generated_note_id(kind: MidiAssetKind, *parts: object) -> str:
    return str(uuid5(NAMESPACE_URL, ":".join(["abachiwave", "midi", kind.value, *map(str, parts)])))


def _round_to_grid(value: float, grid: float) -> float:
    return round(value / grid) * grid


def _beat_to_tick(beat: float) -> int:
    return max(0, round(beat * TICKS_PER_BEAT))


def _sort_notes(notes: list[MidiNoteEvent]) -> list[MidiNoteEvent]:
    return sorted(notes, key=lambda event: (event.start_beat, event.pitch, event.note_id))


def _dedupe_tempos(events: list[MidiTempoEvent]) -> list[MidiTempoEvent]:
    by_beat = {event.beat: event for event in events}
    return [by_beat[beat] for beat in sorted(by_beat)]


def _dedupe_signatures(
    events: list[MidiTimeSignatureEvent],
) -> list[MidiTimeSignatureEvent]:
    by_beat = {event.beat: event for event in events}
    return [by_beat[beat] for beat in sorted(by_beat)]


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))

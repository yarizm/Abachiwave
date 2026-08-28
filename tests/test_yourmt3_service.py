"""Unit tests for the parts of the YourMT3 sidecar that run without the model.

The sidecar cannot be exercised end to end in CI: it needs a 536 MB checkpoint that
is not redistributed with this repository. What can be tested here is everything
around the model call -- the MIDI it consumes and the MIDI it emits.
"""

from io import BytesIO

from mido import Message, MetaMessage, MidiFile, MidiTrack

from abachiwave.yourmt3_service import Note, build_midi, parse_notes


def _midi_with(messages: list[Message | MetaMessage], ticks_per_beat: int = 480) -> MidiFile:
    midi = MidiFile(type=0, ticks_per_beat=ticks_per_beat)
    track = MidiTrack()
    for message in messages:
        track.append(message)
    midi.tracks.append(track)
    return midi


def test_parse_notes_reads_absolute_times_across_a_tempo_change() -> None:
    midi = _midi_with(
        [
            MetaMessage("set_tempo", tempo=500_000, time=0),
            Message("note_on", note=60, velocity=80, time=0),
            Message("note_off", note=60, velocity=0, time=480),
            MetaMessage("set_tempo", tempo=1_000_000, time=0),
            Message("note_on", note=62, velocity=70, time=0),
            Message("note_off", note=62, velocity=0, time=480),
        ]
    )

    notes = parse_notes(midi)

    assert [(n.pitch, round(n.onset, 3), round(n.offset, 3)) for n in notes] == [
        (60, 0.0, 0.5),
        (62, 0.5, 1.5),
    ]


def test_parse_notes_ignores_program_assignment() -> None:
    midi = MidiFile(type=1, ticks_per_beat=480)
    for channel, program, pitch in ((0, 100, 60), (1, 65, 67)):
        track = MidiTrack()
        track.append(Message("program_change", channel=channel, program=program, time=0))
        track.append(Message("note_on", channel=channel, note=pitch, velocity=90, time=0))
        track.append(Message("note_off", channel=channel, note=pitch, velocity=0, time=480))
        midi.tracks.append(track)

    # YourMT3 labels unaccompanied singing as a wind instrument, so filtering on the
    # singing-voice program would discard every note.
    assert [note.pitch for note in parse_notes(midi)] == [60, 67]


def test_parse_notes_treats_a_zero_velocity_note_on_as_a_note_off() -> None:
    midi = _midi_with(
        [
            Message("note_on", note=64, velocity=100, time=0),
            Message("note_on", note=64, velocity=0, time=240),
        ]
    )

    notes = parse_notes(midi)

    assert len(notes) == 1
    assert round(notes[0].offset, 3) == 0.25


def test_build_midi_round_trips_through_the_parser() -> None:
    original = [
        Note(60, 0.0, 0.5, 80),
        Note(64, 0.5, 0.75, 80),
        Note(67, 1.25, 2.0, 80),
    ]

    parsed = parse_notes(MidiFile(file=BytesIO(build_midi(original))))

    assert [(n.pitch, round(n.onset, 3), round(n.offset, 3)) for n in parsed] == [
        (60, 0.0, 0.5),
        (64, 0.5, 0.75),
        (67, 1.25, 2.0),
    ]


def test_build_midi_keeps_a_repeated_pitch_as_two_notes() -> None:
    # A note_on for a pitch that is still sounding would merge the pair, which is exactly
    # the re-articulation the pipeline exists to preserve.
    parsed = parse_notes(
        MidiFile(file=BytesIO(build_midi([Note(60, 0.0, 0.5, 80), Note(60, 0.5, 1.0, 80)])))
    )

    assert [(n.pitch, round(n.onset, 3), round(n.offset, 3)) for n in parsed] == [
        (60, 0.0, 0.5),
        (60, 0.5, 1.0),
    ]


def test_build_midi_emits_a_valid_empty_file_for_no_notes() -> None:
    data = build_midi([])

    assert data.startswith(b"MThd")
    assert parse_notes(MidiFile(file=BytesIO(data))) == []

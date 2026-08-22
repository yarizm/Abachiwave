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
from abachiwave.services.chord_theory import normalize_chord_sections
from abachiwave.services.midi_document import (
    build_midi_document,
    parse_midi_document,
    render_midi_document,
    transform_midi_notes,
)


def _notes() -> list[MidiNoteEvent]:
    return [
        MidiNoteEvent(
            note_id="note-1",
            pitch=60,
            start_beat=0.13,
            duration_beats=0.62,
            velocity=64,
        ),
        MidiNoteEvent(
            note_id="note-2",
            pitch=64,
            start_beat=1,
            duration_beats=0.5,
            velocity=80,
        ),
    ]


def test_rendered_midi_document_round_trips_through_mido_parser() -> None:
    data = render_midi_document(
        kind=MidiAssetKind.melody,
        note_events=_notes(),
        tempo_map=[MidiTempoEvent(beat=0, bpm=128)],
        time_signature_map=[MidiTimeSignatureEvent(beat=0, numerator=4, denominator=4)],
    )

    parsed = parse_midi_document(data)

    assert data.startswith(b"MThd")
    assert len(parsed.note_events) == 2
    assert parsed.tempo_map[0].bpm == 128
    assert parsed.time_signature_map[0].numerator == 4


def test_generated_documents_keep_sections_and_use_actual_hook_offset() -> None:
    song_spec = SongSpecData(
        theme="test",
        genre=["rock"],
        language="en",
        tempo_bpm=120,
        key="C major",
        time_signature="4/4",
        target_duration_seconds=30,
        mood_curve={},
        song_structure=["verse", "chorus"],
        structure_sections=[],
    )
    lyric_sections = [
        LyricSection(section_id="verse", label="Verse", text="verse"),
        LyricSection(section_id="chorus", label="Chorus", text="chorus"),
    ]
    chord_sections = [
        ChordSection(section_id="verse", label="Verse", bars=2, chords=["C", "G"]),
        ChordSection(section_id="chorus", label="Chorus", bars=4, chords=["F", "C", "G", "C"]),
    ]
    chord_sections = normalize_chord_sections(
        chord_sections,
        key_name="C major",
        time_signature="4/4",
    )

    documents = {
        kind: build_midi_document(
            kind=kind,
            song_spec=song_spec,
            chord_sections=chord_sections,
            lyric_sections=lyric_sections,
        )
        for kind in MidiAssetKind
    }

    assert documents[MidiAssetKind.hook].note_events[0].start_beat == 8
    assert {event.section_id for event in documents[MidiAssetKind.chord].note_events} == {
        "verse",
        "chorus",
    }
    assert {event.section_id for event in documents[MidiAssetKind.melody].note_events} == {
        "verse",
        "chorus",
    }
    assert {event.section_id for event in documents[MidiAssetKind.hook].note_events} == {"chorus"}
    assert documents[MidiAssetKind.hook].note_events == build_midi_document(
        kind=MidiAssetKind.hook,
        song_spec=song_spec,
        chord_sections=chord_sections,
        lyric_sections=lyric_sections,
    ).note_events


def test_midi_note_transforms_are_deterministic_and_selection_scoped() -> None:
    notes = _notes()
    quantized = transform_midi_notes(
        notes,
        MidiTransformRequest(
            midi_asset_id="00000000-0000-0000-0000-000000000001",
            operation=MidiTransformOperation.quantize,
            note_ids=["note-1"],
            grid_beats=0.25,
        ),
        key_name="E major",
    )
    assert quantized[0].start_beat == 0.25
    assert quantized[0].duration_beats == 0.5
    assert quantized[1] == notes[1]

    humanize_request = MidiTransformRequest(
        midi_asset_id="00000000-0000-0000-0000-000000000001",
        operation=MidiTransformOperation.humanize,
    )
    assert transform_midi_notes(notes, humanize_request, key_name="E major") == (
        transform_midi_notes(notes, humanize_request, key_name="E major")
    )

    snapped = transform_midi_notes(
        notes,
        MidiTransformRequest(
            midi_asset_id="00000000-0000-0000-0000-000000000001",
            operation=MidiTransformOperation.scale_snap,
        ),
        key_name="E major",
    )
    assert all(note.pitch % 12 in {1, 3, 4, 6, 8, 9, 11} for note in snapped)


def test_legato_and_velocity_transform_note_content() -> None:
    notes = _notes()
    legato = transform_midi_notes(
        notes,
        MidiTransformRequest(
            midi_asset_id="00000000-0000-0000-0000-000000000001",
            operation=MidiTransformOperation.legato,
            legato_gap_beats=0.1,
        ),
        key_name="C major",
    )
    assert legato[0].duration_beats == 0.77

    louder = transform_midi_notes(
        notes,
        MidiTransformRequest(
            midi_asset_id="00000000-0000-0000-0000-000000000001",
            operation=MidiTransformOperation.velocity,
            velocity_delta=80,
        ),
        key_name="C major",
    )
    assert [note.velocity for note in louder] == [127, 127]

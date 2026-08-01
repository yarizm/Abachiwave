from abachiwave.models.composition import MidiAssetKind
from abachiwave.schemas.composition import ChordSection, LyricSection
from abachiwave.schemas.song_specs import SongSpecData
from abachiwave.services.midi_document import (
    TICKS_PER_BEAT,
    build_midi_document,
    render_midi_document,
)

__all__ = ["TICKS_PER_BEAT", "build_midi_bytes"]


def build_midi_bytes(
    *,
    kind: MidiAssetKind,
    song_spec: SongSpecData,
    chord_sections: list[ChordSection],
    lyric_sections: list[LyricSection],
) -> bytes:
    document = build_midi_document(
        kind=kind,
        song_spec=song_spec,
        chord_sections=chord_sections,
        lyric_sections=lyric_sections,
    )
    return render_midi_document(
        kind=kind,
        note_events=document.note_events,
        tempo_map=document.tempo_map,
        time_signature_map=document.time_signature_map,
    )

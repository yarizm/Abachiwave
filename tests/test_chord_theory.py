from abachiwave.schemas.composition import ChordSection
from abachiwave.services.chord_theory import (
    normalize_chord_sections,
    transpose_chord_sections,
)


def test_full_progression_transpose_uses_target_key_spelling() -> None:
    sections = normalize_chord_sections(
        [
            ChordSection(
                section_id="chorus",
                label="Chorus",
                bars=4,
                chords=["E", "B", "C#m", "A"],
            )
        ],
        key_name="E major",
        time_signature="4/4",
    )

    output_key, transposed = transpose_chord_sections(
        sections,
        key_name="E major",
        time_signature="4/4",
        semitones=2,
        section_ids=None,
    )

    assert output_key == "F# major"
    assert transposed[0].chords == ["F#", "C#", "D#m", "B"]
    assert [
        measure.events[0].roman_numeral for measure in transposed[0].measures
    ] == ["I", "V", "vi", "IV"]

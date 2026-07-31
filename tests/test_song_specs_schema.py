from pydantic import ValidationError

from abachiwave.schemas.song_specs import (
    IdeaIntakeCreate,
    SongSpecData,
    build_structure_sections,
    canonical_section_slug,
)


def test_song_spec_reports_missing_required_fields() -> None:
    song_spec = SongSpecData(theme="Night ride", tempo_bpm=128)

    assert "theme" not in song_spec.missing_required_fields()
    assert "tempo_bpm" not in song_spec.missing_required_fields()
    assert "key" in song_spec.missing_required_fields()


def test_song_spec_rejects_invalid_tempo() -> None:
    try:
        SongSpecData(tempo_bpm=20)
    except ValidationError as exc:
        assert "greater than or equal to 40" in str(exc)
    else:
        raise AssertionError("invalid tempo should fail validation")


def test_idea_intake_normalizes_answers() -> None:
    payload = IdeaIntakeCreate(idea="  Night song  ", answers={" key ": " E major ", "empty": " "})

    assert payload.idea == "Night song"
    assert payload.answers == {"key": "E major"}


def test_canonical_section_slug_normalizes_legacy_ids() -> None:
    assert canonical_section_slug("pre chorus") == "pre-chorus"
    assert canonical_section_slug("pre_chorus") == "pre-chorus"
    assert canonical_section_slug("  Chorus ") == "chorus"
    assert canonical_section_slug("预副歌") == "section"


def test_build_structure_sections_keeps_dedup_suffix() -> None:
    sections = build_structure_sections(["pre chorus", "chorus", "chorus"])

    assert [section.section_id for section in sections] == ["pre-chorus", "chorus", "chorus-2"]

from abachiwave.agents.song_spec import build_clarification_questions, build_song_spec_from_input


def test_incomplete_idea_returns_targeted_questions() -> None:
    questions = build_clarification_questions("A lonely late-night song")

    fields = {question.field for question in questions}
    assert "tempo_bpm" in fields
    assert "key" in fields
    assert "song_structure" in fields


def test_complete_idea_builds_song_spec_without_missing_fields() -> None:
    song_spec = build_song_spec_from_input(
        "Chinese j-pop influenced indie rock song about riding home late at night. "
        "Verse restrained and lonely, chorus lifting and hopeful. "
        "128 BPM, E major, 4/4, 3:30, standard structure."
    )

    assert song_spec.theme
    assert song_spec.language == "zh-CN"
    assert song_spec.genre == ["indie rock", "j-pop influenced", "pop", "rock"]
    assert song_spec.tempo_bpm == 128
    assert song_spec.key == "E major"
    assert song_spec.time_signature == "4/4"
    assert song_spec.target_duration_seconds == 210
    assert song_spec.missing_required_fields() == []

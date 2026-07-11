import pytest

from abachiwave.workflows import build_composition_workflow, build_song_workflow


def test_song_workflow_builds() -> None:
    workflow = build_song_workflow()

    assert hasattr(workflow, "ainvoke")


@pytest.mark.asyncio
async def test_song_workflow_runs_deterministic_nodes() -> None:
    workflow = build_song_workflow()

    result = await workflow.ainvoke(
        {
            "project_id": "project-1",
            "idea": (
                "Chinese indie rock song about riding home late at night. "
                "Verse restrained and lonely, chorus lifting and hopeful. "
                "128 BPM, E major, 4/4, 3:30, standard structure."
            ),
        }
    )

    assert result["intake_status"] == "ready_for_generation"
    assert result["missing_required_fields"] == []
    assert result["song_spec"]["tempo_bpm"] == 128


def test_composition_workflow_builds() -> None:
    workflow = build_composition_workflow()

    assert hasattr(workflow, "ainvoke")


@pytest.mark.asyncio
async def test_composition_workflow_runs_deterministic_nodes() -> None:
    workflow = build_composition_workflow()

    result = await workflow.ainvoke(
        {
            "project_id": "project-1",
            "song_spec_id": "song-spec-1",
            "song_spec_status": "approved",
            "song_spec": {
                "theme": "Late ride home",
                "genre": ["indie rock"],
                "language": "zh-CN",
                "tempo_bpm": 128,
                "key": "E major",
                "time_signature": "4/4",
                "target_duration_seconds": 210,
                "mood_curve": {"verse": "restrained", "chorus": "lifting"},
                "song_structure": ["verse", "chorus", "bridge"],
            },
        }
    )

    assert result["can_generate"] is True
    assert len(result["lyrics_sections"]) == 3
    assert result["chord_sections"][0]["chords"] == ["E", "B", "C#m", "A"]
    assert result["midi_asset_kinds"] == ["chord", "melody", "hook"]
    assert result["arrangement_plan"]["sections"][0]["energy_level"] == 4

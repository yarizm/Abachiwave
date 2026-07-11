from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from abachiwave.agents.composition import (
    build_arrangement_from_assets,
    build_chords_from_song_spec,
    build_lyrics_from_song_spec,
)
from abachiwave.models.composition import MidiAssetKind
from abachiwave.models.song_spec import SongSpecStatus
from abachiwave.schemas.composition import ChordSection, LyricSection
from abachiwave.schemas.song_specs import SongSpecData


class CompositionState(TypedDict, total=False):
    project_id: str
    song_spec_id: str
    song_spec_status: str
    song_spec: dict[str, object]
    can_generate: bool
    lyrics_sections: list[dict[str, object]]
    hook_candidates: list[dict[str, object]]
    chord_sections: list[dict[str, object]]
    midi_asset_kinds: list[str]
    arrangement_plan: dict[str, object]


async def approved_song_spec_node(state: CompositionState) -> CompositionState:
    return {
        **state,
        "can_generate": state.get("song_spec_status") == SongSpecStatus.approved.value,
    }


async def lyrics_generator_node(state: CompositionState) -> CompositionState:
    if not state.get("can_generate"):
        return state
    song_spec = SongSpecData.model_validate(state.get("song_spec", {}))
    sections, hook_candidates = build_lyrics_from_song_spec(song_spec)
    return {
        **state,
        "lyrics_sections": [section.model_dump() for section in sections],
        "hook_candidates": [candidate.model_dump() for candidate in hook_candidates],
    }


async def harmony_generator_node(state: CompositionState) -> CompositionState:
    if not state.get("can_generate"):
        return state
    song_spec = SongSpecData.model_validate(state.get("song_spec", {}))
    sections, _hook_candidates = build_lyrics_from_song_spec(song_spec)
    chord_sections = build_chords_from_song_spec(song_spec, sections)
    return {
        **state,
        "chord_sections": [section.model_dump() for section in chord_sections],
    }


async def midi_generator_node(state: CompositionState) -> CompositionState:
    if not state.get("can_generate"):
        return state
    return {
        **state,
        "midi_asset_kinds": [kind.value for kind in MidiAssetKind],
    }


async def arrangement_generator_node(state: CompositionState) -> CompositionState:
    if not state.get("can_generate"):
        return state
    song_spec = SongSpecData.model_validate(state.get("song_spec", {}))
    lyric_sections = [
        LyricSection.model_validate(section) for section in state.get("lyrics_sections", [])
    ]
    chord_sections = [
        ChordSection.model_validate(section) for section in state.get("chord_sections", [])
    ]
    midi_kinds = [MidiAssetKind(kind) for kind in state.get("midi_asset_kinds", [])]
    arrangement = build_arrangement_from_assets(
        song_spec=song_spec,
        lyric_sections=lyric_sections,
        chord_sections=chord_sections,
        midi_kinds=midi_kinds,
    )
    return {
        **state,
        "arrangement_plan": arrangement.model_dump(),
    }


def build_composition_workflow() -> Any:
    graph = StateGraph(CompositionState)
    graph.add_node("approved_song_spec", approved_song_spec_node)
    graph.add_node("lyrics_generator", lyrics_generator_node)
    graph.add_node("harmony_generator", harmony_generator_node)
    graph.add_node("midi_generator", midi_generator_node)
    graph.add_node("arrangement_generator", arrangement_generator_node)
    graph.set_entry_point("approved_song_spec")
    graph.add_edge("approved_song_spec", "lyrics_generator")
    graph.add_edge("lyrics_generator", "harmony_generator")
    graph.add_edge("harmony_generator", "midi_generator")
    graph.add_edge("midi_generator", "arrangement_generator")
    graph.add_edge("arrangement_generator", END)
    return graph.compile()

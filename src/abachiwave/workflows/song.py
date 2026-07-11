from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from abachiwave.agents.song_spec import build_clarification_questions, build_song_spec_from_input
from abachiwave.models.song_spec import IdeaIntakeStatus
from abachiwave.schemas.song_specs import ClarificationQuestion, SongSpecData


class SongState(TypedDict, total=False):
    project_id: str
    idea: str
    answers: dict[str, str]
    questions: list[dict[str, object]]
    intake_status: str
    song_spec: dict[str, object]
    missing_required_fields: list[str]


async def idea_intake_node(state: SongState) -> SongState:
    return {
        **state,
        "idea": state.get("idea", "").strip(),
        "answers": {
            key.strip(): value.strip()
            for key, value in state.get("answers", {}).items()
            if value.strip()
        },
    }


async def requirement_clarifier_node(state: SongState) -> SongState:
    questions: list[ClarificationQuestion] = build_clarification_questions(
        state.get("idea", ""),
        state.get("answers", {}),
    )
    status = (
        IdeaIntakeStatus.needs_clarification
        if questions
        else IdeaIntakeStatus.ready_for_generation
    )
    return {
        **state,
        "questions": [question.model_dump() for question in questions],
        "intake_status": status.value,
    }


async def song_spec_builder_node(state: SongState) -> SongState:
    song_spec: SongSpecData = build_song_spec_from_input(
        state.get("idea", ""),
        state.get("answers", {}),
    )
    return {
        **state,
        "song_spec": song_spec.model_dump(),
        "missing_required_fields": song_spec.missing_required_fields(),
    }


async def noop_node(state: SongState) -> SongState:
    return state


def build_song_workflow() -> Any:
    graph = StateGraph(SongState)
    graph.add_node("idea_intake", idea_intake_node)
    graph.add_node("requirement_clarifier", requirement_clarifier_node)
    graph.add_node("song_spec_builder", song_spec_builder_node)
    graph.set_entry_point("idea_intake")
    graph.add_edge("idea_intake", "requirement_clarifier")
    graph.add_edge("requirement_clarifier", "song_spec_builder")
    graph.add_edge("song_spec_builder", END)
    return graph.compile()

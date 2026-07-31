from dataclasses import dataclass

from pydantic import BaseModel

from abachiwave.agents.composition import (
    build_arrangement_from_assets,
    build_chords_from_song_spec,
    build_lyrics_from_song_spec,
)
from abachiwave.agents.song_spec import build_song_spec_from_input
from abachiwave.models.ai import TextWorkflow
from abachiwave.models.composition import MidiAssetKind
from abachiwave.models.revision import RevisionTaskTarget
from abachiwave.schemas.ai import LyricsCandidateContent, RevisionCandidateContent
from abachiwave.schemas.composition import LyricSection
from abachiwave.schemas.revisions import RevisionTask
from abachiwave.schemas.song_specs import SONG_SPEC_FIELDS, SongSpecData

SAMPLE_SET_NAME = "creative-briefs-v1"


@dataclass(frozen=True)
class EvaluationSample:
    id: str
    category: str
    workflow: TextWorkflow
    context: dict[str, object]
    fallback: BaseModel
    expectations: dict[str, object]


@dataclass(frozen=True)
class CreativeScenario:
    id: str
    category: str
    idea: str
    answers: dict[str, str]
    canonical_spec: SongSpecData
    feedback: str
    revision_target: RevisionTaskTarget
    existing_lyrics: str | None = None


SCENARIOS = (
    CreativeScenario(
        id="zh_indie_night_bus",
        category="chinese_indie_rock",
        idea="写一首关于深夜坐末班车回家的中文独立摇滚，主歌克制，副歌释怀。",
        answers={
            "theme": "深夜末班车与回家的释怀",
            "genre": "indie rock",
            "language": "zh-CN",
            "tempo_bpm": "112 BPM",
            "key": "E major",
            "time_signature": "4/4",
            "target_duration_seconds": "210 seconds",
            "mood_curve": "主歌克制孤独，副歌向上释怀",
            "song_structure": "intro, verse, pre_chorus, chorus, bridge, final_chorus, outro",
        },
        canonical_spec=SongSpecData(
            theme="深夜末班车与回家的释怀",
            genre=["indie rock"],
            language="zh-CN",
            tempo_bpm=112,
            key="E major",
            time_signature="4/4",
            target_duration_seconds=210,
            mood_curve={"verse": "restrained", "chorus": "releasing and hopeful"},
            song_structure=["intro", "verse", "pre_chorus", "chorus", "bridge", "outro"],
        ),
        feedback="副歌歌词更有力量，但保留回家的意象。",
        revision_target=RevisionTaskTarget.lyrics,
    ),
    CreativeScenario(
        id="en_pop_new_city",
        category="english_pop",
        idea="English pop song about starting over in a new city.",
        answers={
            "theme": "starting over in a new city",
            "genre": "pop",
            "language": "en",
            "tempo_bpm": "118 BPM",
            "key": "C major",
            "time_signature": "4/4",
            "target_duration_seconds": "195 seconds",
            "mood_curve": "uncertain verse, confident chorus",
            "song_structure": "intro, verse, chorus, verse, bridge, final_chorus, outro",
        },
        canonical_spec=SongSpecData(
            theme="starting over in a new city",
            genre=["pop"],
            language="en",
            tempo_bpm=118,
            key="C major",
            time_signature="4/4",
            target_duration_seconds=195,
            mood_curve={"verse": "uncertain", "chorus": "confident"},
            song_structure=["intro", "verse", "chorus", "bridge", "final_chorus", "outro"],
        ),
        feedback="Lift the final chorus melody without changing the verse.",
        revision_target=RevisionTaskTarget.midi_melody,
    ),
    CreativeScenario(
        id="instrumental_frozen_ruins",
        category="instrumental_soundtrack",
        idea="Instrumental game soundtrack for exploring frozen ruins.",
        answers={
            "theme": "exploring frozen ruins",
            "genre": "cinematic electronic",
            "language": "instrumental",
            "tempo_bpm": "84 BPM",
            "key": "D minor",
            "time_signature": "6/8",
            "target_duration_seconds": "240 seconds",
            "mood_curve": "sparse discovery, tense middle, unresolved ending",
            "song_structure": "intro, exploration, danger, discovery, outro",
        },
        canonical_spec=SongSpecData(
            theme="exploring frozen ruins",
            genre=["cinematic", "electronic"],
            language="instrumental",
            tempo_bpm=84,
            key="D minor",
            time_signature="6/8",
            target_duration_seconds=240,
            mood_curve={"overall": "sparse to tense, then unresolved"},
            song_structure=["intro", "exploration", "danger", "discovery", "outro"],
        ),
        feedback="Make the discovery section wider and remove drums from the intro.",
        revision_target=RevisionTaskTarget.arrangement,
    ),
    CreativeScenario(
        id="existing_lyrics_after_rain",
        category="existing_lyrics_continuation",
        idea="Continue an existing English alt-pop lyric after the first verse.",
        answers={
            "theme": "learning to speak after a long silence",
            "genre": "alternative pop",
            "language": "en",
            "tempo_bpm": "96 BPM",
            "key": "A minor",
            "time_signature": "4/4",
            "target_duration_seconds": "205 seconds",
            "mood_curve": "intimate opening, cathartic final chorus",
            "song_structure": "verse, pre_chorus, chorus, verse, bridge, final_chorus",
        },
        canonical_spec=SongSpecData(
            theme="learning to speak after a long silence",
            genre=["alternative pop"],
            language="en",
            tempo_bpm=96,
            key="A minor",
            time_signature="4/4",
            target_duration_seconds=205,
            mood_curve={"verse": "intimate", "final_chorus": "cathartic"},
            song_structure=["verse", "pre_chorus", "chorus", "bridge", "final_chorus"],
        ),
        feedback="Rewrite the bridge so it answers the opening line.",
        revision_target=RevisionTaskTarget.lyrics,
        existing_lyrics=(
            "After the rain, the hallway keeps your name\nI count the doors I never opened"
        ),
    ),
    CreativeScenario(
        id="incomplete_quiet_departure",
        category="incomplete_input",
        idea="A quiet song about leaving.",
        answers={},
        canonical_spec=SongSpecData(
            theme="a quiet departure",
            genre=["folk"],
            language="en",
            tempo_bpm=76,
            key="G major",
            time_signature="4/4",
            target_duration_seconds=180,
            mood_curve={"overall": "quiet and unresolved"},
            song_structure=["verse", "chorus", "verse", "bridge", "chorus"],
        ),
        feedback="The arrangement should stay sparse until the last chorus.",
        revision_target=RevisionTaskTarget.arrangement,
    ),
    CreativeScenario(
        id="zh_folk_old_photo",
        category="chinese_folk",
        idea="中文民谣，主题是搬家时发现一张旧照片。",
        answers={
            "theme": "搬家时发现旧照片",
            "genre": "folk",
            "language": "zh-CN",
            "tempo_bpm": "72 BPM",
            "key": "G major",
            "time_signature": "3/4",
            "target_duration_seconds": "220 seconds",
            "mood_curve": "温暖回忆逐渐转为告别",
            "song_structure": "intro, verse, chorus, verse, bridge, chorus, outro",
        },
        canonical_spec=SongSpecData(
            theme="搬家时发现旧照片",
            genre=["folk"],
            language="zh-CN",
            tempo_bpm=72,
            key="G major",
            time_signature="3/4",
            target_duration_seconds=220,
            mood_curve={"overall": "warm memory turning into farewell"},
            song_structure=["intro", "verse", "chorus", "bridge", "outro"],
        ),
        feedback="第二段主歌歌词减少抽象表达，多写具体物件。",
        revision_target=RevisionTaskTarget.lyrics,
    ),
    CreativeScenario(
        id="electronic_rain_signal",
        category="electronic",
        idea="Electronic track about a radio signal crossing a storm.",
        answers={
            "theme": "a radio signal crossing a storm",
            "genre": "electronic",
            "language": "en",
            "tempo_bpm": "126 BPM",
            "key": "F# minor",
            "time_signature": "4/4",
            "target_duration_seconds": "230 seconds",
            "mood_curve": "minimal pulse, dense drop, clear outro",
            "song_structure": "intro, verse, build, chorus, break, final_chorus, outro",
        },
        canonical_spec=SongSpecData(
            theme="a radio signal crossing a storm",
            genre=["electronic"],
            language="en",
            tempo_bpm=126,
            key="F# minor",
            time_signature="4/4",
            target_duration_seconds=230,
            mood_curve={"overall": "minimal to dense, then clear"},
            song_structure=["intro", "verse", "build", "chorus", "break", "outro"],
        ),
        feedback="Raise the hook melody by a small interval in the final chorus.",
        revision_target=RevisionTaskTarget.midi_melody,
    ),
    CreativeScenario(
        id="city_pop_summer_platform",
        category="japanese_city_pop",
        idea="Japanese city-pop song about a summer train platform.",
        answers={
            "theme": "a summer train platform farewell",
            "genre": "city pop",
            "language": "ja",
            "tempo_bpm": "110 BPM",
            "key": "B major",
            "time_signature": "4/4",
            "target_duration_seconds": "215 seconds",
            "mood_curve": "bright surface with a bittersweet bridge",
            "song_structure": "intro, verse, pre_chorus, chorus, bridge, final_chorus, outro",
        },
        canonical_spec=SongSpecData(
            theme="a summer train platform farewell",
            genre=["city pop"],
            language="ja",
            tempo_bpm=110,
            key="B major",
            time_signature="4/4",
            target_duration_seconds=215,
            mood_curve={"overall": "bright with a bittersweet bridge"},
            song_structure=["intro", "verse", "pre_chorus", "chorus", "bridge", "outro"],
        ),
        feedback="Thin the bridge arrangement, then make the final chorus feel brighter.",
        revision_target=RevisionTaskTarget.arrangement,
    ),
)


def load_sample_set(name: str = SAMPLE_SET_NAME) -> tuple[EvaluationSample, ...]:
    if name != SAMPLE_SET_NAME:
        raise KeyError(name)
    samples: list[EvaluationSample] = []
    for scenario in SCENARIOS:
        samples.extend(_samples_for_scenario(scenario))
    return tuple(samples)


def sample_set_summary() -> dict[str, object]:
    samples = load_sample_set()
    return {
        "name": SAMPLE_SET_NAME,
        "sample_count": len(samples),
        "workflows": {
            workflow.value: sum(sample.workflow == workflow for sample in samples)
            for workflow in TextWorkflow
        },
        "categories": sorted({sample.category for sample in samples}),
    }


def _samples_for_scenario(scenario: CreativeScenario) -> list[EvaluationSample]:
    parsed_spec = build_song_spec_from_input(scenario.idea, scenario.answers)
    parsed_values = parsed_spec.model_dump(mode="json")
    explicit_fields = {
        field: parsed_values[field]
        for field in SONG_SPEC_FIELDS
        if field not in parsed_spec.missing_required_fields()
    }
    null_fields = parsed_spec.missing_required_fields()
    lyric_sections, hooks = build_lyrics_from_song_spec(scenario.canonical_spec)
    lyrics = LyricsCandidateContent(sections=lyric_sections, hook_candidates=hooks)
    chord_sections = build_chords_from_song_spec(scenario.canonical_spec, lyric_sections)
    arrangement = build_arrangement_from_assets(
        song_spec=scenario.canonical_spec,
        lyric_sections=lyric_sections,
        chord_sections=chord_sections,
        midi_kinds=list(MidiAssetKind),
    )
    revision = RevisionCandidateContent(
        feedback=scenario.feedback,
        tasks=[
            RevisionTask(
                id=f"{scenario.revision_target.value}_evaluation",
                target=scenario.revision_target,
                target_section_id=None,
                action="evaluation_revision",
                summary=scenario.feedback,
                affected_asset_ids=[],
                requires_demo_regeneration=True,
                supported=True,
            )
        ],
    )
    lyrics_context: dict[str, object] = {
        "song_spec": scenario.canonical_spec.model_dump(mode="json")
    }
    if scenario.existing_lyrics:
        lyrics_context["existing_lyrics"] = scenario.existing_lyrics
        lyrics_context["instruction"] = "Continue the existing lyric without replacing it."
    return [
        EvaluationSample(
            id=f"{scenario.id}.song_spec",
            category=scenario.category,
            workflow=TextWorkflow.song_spec,
            context={"idea": scenario.idea, "answers": scenario.answers},
            fallback=parsed_spec,
            expectations={"exact_fields": explicit_fields, "null_fields": null_fields},
        ),
        EvaluationSample(
            id=f"{scenario.id}.lyrics",
            category=scenario.category,
            workflow=TextWorkflow.lyrics,
            context=lyrics_context,
            fallback=lyrics,
            expectations={
                "section_ids": [section.section_id for section in lyric_sections],
                "minimum_hook_count": 1,
            },
        ),
        EvaluationSample(
            id=f"{scenario.id}.arrangement",
            category=scenario.category,
            workflow=TextWorkflow.arrangement,
            context={
                "song_spec": scenario.canonical_spec.model_dump(mode="json"),
                "lyrics": [section.model_dump(mode="json") for section in lyric_sections],
                "chords": [section.model_dump(mode="json") for section in chord_sections],
                "midi_kinds": [kind.value for kind in MidiAssetKind],
            },
            fallback=arrangement,
            expectations={"section_ids": [section.section_id for section in chord_sections]},
        ),
        EvaluationSample(
            id=f"{scenario.id}.revision",
            category=scenario.category,
            workflow=TextWorkflow.revision,
            context={
                "feedback": scenario.feedback,
                "available_targets": [target.value for target in RevisionTaskTarget],
            },
            fallback=revision,
            expectations={"targets": [scenario.revision_target.value]},
        ),
    ]


def lyric_lines(content: LyricsCandidateContent) -> list[str]:
    return [
        line.strip().casefold()
        for section in content.sections
        for line in section.text.splitlines()
        if line.strip()
    ]


def existing_lyric_sections(text: str) -> list[LyricSection]:
    return [LyricSection(section_id="existing_verse", label="Existing verse", text=text)]

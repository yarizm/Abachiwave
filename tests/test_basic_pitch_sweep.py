from pathlib import Path

import pytest
from pydantic import ValidationError

from abachiwave.evaluations.audio_to_midi import BenchmarkSample
from abachiwave.evaluations.basic_pitch_sweep import (
    BasicPitchSweepCandidate,
    BasicPitchSweepDefinition,
    rank_basic_pitch_scores,
    score_basic_pitch_report,
    split_benchmark_samples_by_group,
)


def test_grouped_split_is_deterministic_and_keeps_singers_isolated() -> None:
    samples = [
        _sample("track-1", "singer-a"),
        _sample("track-2", "singer-a"),
        _sample("track-3", "singer-b"),
        _sample("track-4", "singer-c"),
        _sample("track-5", "singer-d"),
    ]

    first = split_benchmark_samples_by_group(
        samples,
        group_attribute="singer_id",
        holdout_fraction=0.25,
        split_seed="vocadito-v1",
    )
    second = split_benchmark_samples_by_group(
        samples,
        group_attribute="singer_id",
        holdout_fraction=0.25,
        split_seed="vocadito-v1",
    )

    assert first == second
    assert len(first.holdout_groups) == 1
    assert set(first.development_groups).isdisjoint(first.holdout_groups)
    development_singers = {
        sample.attributes["singer_id"] for sample in first.development_samples
    }
    holdout_singers = {sample.attributes["singer_id"] for sample in first.holdout_samples}
    assert development_singers.isdisjoint(holdout_singers)
    assert len(first.development_samples) + len(first.holdout_samples) == len(samples)


def test_sweep_definition_rejects_duplicate_effective_parameters() -> None:
    with pytest.raises(ValidationError, match="unique effective parameters"):
        BasicPitchSweepDefinition.model_validate(
            {
                "schema_version": 1,
                "group_attribute": "singer_id",
                "holdout_fraction": 0.25,
                "split_seed": "fixture",
                "baseline_candidate_id": "baseline",
                "candidates": [
                    {"id": "baseline", "params": {}},
                    {"id": "same-default", "params": {"onset_threshold": 0.6}},
                ],
            }
        )


def test_score_ranking_prioritizes_macro_offset_f1_then_no_offset_f1() -> None:
    candidate_a = BasicPitchSweepCandidate(id="candidate-a", params={})
    candidate_b = BasicPitchSweepCandidate(
        id="candidate-b",
        params={"onset_threshold": 0.4},
    )
    score_a = score_basic_pitch_report(
        candidate_a,
        _report(macro_pitch=0.60, macro_offset=0.40, micro_offset=0.42),
        report_path="a.json",
    )
    score_b = score_basic_pitch_report(
        candidate_b,
        _report(macro_pitch=0.55, macro_offset=0.41, micro_offset=0.40),
        report_path="b.json",
    )

    ranked = rank_basic_pitch_scores([score_a, score_b])

    assert [score.candidate_id for score in ranked] == ["candidate-b", "candidate-a"]
    assert ranked[0].provider_params["onset_threshold"] == 0.4


def _sample(sample_id: str, singer_id: str) -> BenchmarkSample:
    return BenchmarkSample(
        id=sample_id,
        category="vocal_phrase",
        audio_path=Path(f"{sample_id}.wav"),
        reference_midi_path=Path(f"{sample_id}.mid"),
        audio_sha256="a" * 64,
        reference_midi_sha256="b" * 64,
        attributes={"singer_id": singer_id},
    )


def _report(
    *,
    macro_pitch: float,
    macro_offset: float,
    micro_offset: float,
) -> dict[str, object]:
    return {
        "benchmark": {
            "overall": {
                "sample_count": 4,
                "macro_onset_pitch_f1": macro_pitch,
                "macro_onset_pitch_offset_f1": macro_offset,
                "onset_pitch_f1": macro_pitch - 0.01,
                "onset_pitch_offset_f1": micro_offset,
                "empty_result_rate": 0.0,
                "median_latency_seconds": 0.5,
            }
        }
    }

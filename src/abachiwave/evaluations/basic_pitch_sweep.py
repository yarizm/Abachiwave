from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from abachiwave.evaluations.audio_to_midi import (
    AudioToMidiBenchmarkManifest,
    BenchmarkSample,
    load_benchmark_manifest,
)
from abachiwave.services.audio_to_midi_provider import resolve_basic_pitch_params


class BasicPitchSweepCandidate(BaseModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    params: dict[str, bool | float] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def validate_params(
        cls,
        params: dict[str, bool | float],
    ) -> dict[str, bool | float]:
        resolved = resolve_basic_pitch_params(dict(params))
        return {name: resolved[name] for name in params}

    def effective_params(self) -> dict[str, bool | float]:
        return resolve_basic_pitch_params(dict(self.params))


class BasicPitchSweepDefinition(BaseModel):
    schema_version: Literal[1]
    objective: Literal["macro_onset_pitch_offset_f1"] = "macro_onset_pitch_offset_f1"
    group_attribute: str = Field(min_length=1, max_length=100)
    holdout_fraction: float = Field(gt=0, lt=0.5)
    split_seed: str = Field(min_length=1, max_length=200)
    baseline_candidate_id: str = Field(
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9._-]+$",
    )
    minimum_macro_f1_improvement: float = Field(default=0.02, ge=0, le=1)
    target_macro_onset_pitch_f1: float = Field(default=0.64, ge=0, le=1)
    target_macro_onset_pitch_offset_f1: float = Field(default=0.50, ge=0, le=1)
    candidates: list[BasicPitchSweepCandidate] = Field(min_length=2, max_length=32)

    @model_validator(mode="after")
    def validate_candidates(self) -> BasicPitchSweepDefinition:
        candidate_ids = [candidate.id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("Basic Pitch sweep candidate ids must be unique")
        if self.baseline_candidate_id not in candidate_ids:
            raise ValueError("baseline_candidate_id must identify a sweep candidate")
        effective_params = [
            tuple(sorted(candidate.effective_params().items()))
            for candidate in self.candidates
        ]
        if len(effective_params) != len(set(effective_params)):
            raise ValueError("Basic Pitch sweep candidates must have unique effective parameters")
        return self


@dataclass(frozen=True)
class GroupedSampleSplit:
    development_samples: tuple[BenchmarkSample, ...]
    holdout_samples: tuple[BenchmarkSample, ...]
    development_groups: tuple[str, ...]
    holdout_groups: tuple[str, ...]


class BasicPitchSweepScore(BaseModel):
    candidate_id: str
    provider_params: dict[str, bool | float]
    sample_count: int = Field(gt=0)
    macro_onset_pitch_f1: float = Field(ge=0, le=1)
    macro_onset_pitch_offset_f1: float = Field(ge=0, le=1)
    onset_pitch_f1: float = Field(ge=0, le=1)
    onset_pitch_offset_f1: float = Field(ge=0, le=1)
    empty_result_rate: float = Field(ge=0, le=1)
    median_latency_seconds: float = Field(ge=0)
    report_path: str


def prepare_basic_pitch_benchmark_manifest(
    manifest_path: Path,
    *,
    provider_params: dict[str, object] | None = None,
    sample_ids: list[str] | None = None,
) -> AudioToMidiBenchmarkManifest:
    manifest = load_benchmark_manifest(manifest_path)
    merged_provider_params: dict[str, object] = {
        **manifest.provider_params,
        **(provider_params or {}),
    }
    resolve_basic_pitch_params(merged_provider_params)
    selected_samples = manifest.samples
    if sample_ids is not None:
        if not sample_ids:
            raise ValueError("at least one --sample-id is required when filtering samples")
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("benchmark sample ids must be unique")
        requested_ids = set(sample_ids)
        available_ids = {sample.id for sample in manifest.samples}
        unknown_ids = sorted(requested_ids - available_ids)
        if unknown_ids:
            raise ValueError(f"benchmark sample ids do not exist: {unknown_ids}")
        selected_samples = [
            sample for sample in manifest.samples if sample.id in requested_ids
        ]
    return manifest.model_copy(
        update={
            "provider_params": merged_provider_params,
            "samples": selected_samples,
        }
    )


def parse_basic_pitch_param_assignments(
    values: list[str],
) -> dict[str, bool | float]:
    params: dict[str, bool | float] = {}
    for value in values:
        name, separator, raw_value = value.partition("=")
        name = name.strip()
        raw_value = raw_value.strip()
        if not separator or not name or not raw_value:
            raise ValueError("--provider-param must use NAME=VALUE")
        if name in params:
            raise ValueError(f"duplicate Basic Pitch provider parameter: {name}")
        if raw_value.lower() in {"true", "false"}:
            parsed: bool | float = raw_value.lower() == "true"
        else:
            try:
                parsed = float(raw_value)
            except ValueError as error:
                raise ValueError(
                    f"Basic Pitch provider parameter {name} must be numeric or boolean"
                ) from error
        params[name] = parsed
    resolve_basic_pitch_params(dict(params))
    return params


def split_benchmark_samples_by_group(
    samples: list[BenchmarkSample],
    *,
    group_attribute: str,
    holdout_fraction: float,
    split_seed: str,
) -> GroupedSampleSplit:
    if not 0 < holdout_fraction < 0.5:
        raise ValueError("holdout_fraction must be between 0 and 0.5")
    groups_by_sample_id: dict[str, str] = {}
    for sample in samples:
        if group_attribute not in sample.attributes:
            raise ValueError(
                f"benchmark sample {sample.id} has no {group_attribute} attribute"
            )
        raw_group = sample.attributes[group_attribute]
        group = f"{type(raw_group).__name__}:{raw_group}"
        groups_by_sample_id[sample.id] = group
    groups = sorted(set(groups_by_sample_id.values()))
    if len(groups) < 2:
        raise ValueError("grouped benchmark split requires at least two distinct groups")
    ranked_groups = sorted(
        groups,
        key=lambda group: (sha256(f"{split_seed}\0{group}".encode()).hexdigest(), group),
    )
    holdout_count = max(1, int(len(groups) * holdout_fraction + 0.5))
    holdout_count = min(holdout_count, len(groups) - 1)
    holdout_group_set = set(ranked_groups[:holdout_count])
    development = tuple(
        sample
        for sample in samples
        if groups_by_sample_id[sample.id] not in holdout_group_set
    )
    holdout = tuple(
        sample
        for sample in samples
        if groups_by_sample_id[sample.id] in holdout_group_set
    )
    if not development or not holdout:
        raise ValueError("grouped benchmark split produced an empty partition")
    return GroupedSampleSplit(
        development_samples=development,
        holdout_samples=holdout,
        development_groups=tuple(sorted(set(groups) - holdout_group_set)),
        holdout_groups=tuple(sorted(holdout_group_set)),
    )


def score_basic_pitch_report(
    candidate: BasicPitchSweepCandidate,
    report: dict[str, object],
    *,
    report_path: str,
) -> BasicPitchSweepScore:
    benchmark = report.get("benchmark")
    if not isinstance(benchmark, dict):
        raise ValueError("benchmark report has no benchmark object")
    overall = benchmark.get("overall")
    if not isinstance(overall, dict):
        raise ValueError("benchmark report has no overall metrics")
    return BasicPitchSweepScore(
        candidate_id=candidate.id,
        provider_params=candidate.effective_params(),
        sample_count=_integer_metric(overall, "sample_count"),
        macro_onset_pitch_f1=_float_metric(overall, "macro_onset_pitch_f1"),
        macro_onset_pitch_offset_f1=_float_metric(
            overall,
            "macro_onset_pitch_offset_f1",
        ),
        onset_pitch_f1=_float_metric(overall, "onset_pitch_f1"),
        onset_pitch_offset_f1=_float_metric(overall, "onset_pitch_offset_f1"),
        empty_result_rate=_float_metric(overall, "empty_result_rate"),
        median_latency_seconds=_float_metric(overall, "median_latency_seconds"),
        report_path=report_path,
    )


def rank_basic_pitch_scores(
    scores: list[BasicPitchSweepScore],
) -> list[BasicPitchSweepScore]:
    if not scores:
        raise ValueError("at least one Basic Pitch sweep score is required")
    indexed = list(enumerate(scores))
    indexed.sort(
        key=lambda item: (
            -item[1].macro_onset_pitch_offset_f1,
            -item[1].macro_onset_pitch_f1,
            -item[1].onset_pitch_offset_f1,
            item[1].median_latency_seconds,
            item[0],
        )
    )
    return [score for _index, score in indexed]


def _integer_metric(metrics: dict[str, object], name: str) -> int:
    value = metrics.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"benchmark metric {name} is not an integer")
    return value


def _float_metric(metrics: dict[str, object], name: str) -> float:
    value = metrics.get(name)
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"benchmark metric {name} is not numeric")
    return float(value)

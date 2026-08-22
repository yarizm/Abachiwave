"""Tune Basic Pitch on a grouped development split and verify on held-out groups."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from abachiwave.evaluations.audio_to_midi import load_benchmark_manifest
from abachiwave.evaluations.basic_pitch_sweep import (
    BasicPitchSweepCandidate,
    BasicPitchSweepDefinition,
    BasicPitchSweepScore,
    rank_basic_pitch_scores,
    score_basic_pitch_report,
    split_benchmark_samples_by_group,
)
from support.benchmark_audio_to_midi import run_benchmark


def run_sweep(args: argparse.Namespace) -> dict[str, object]:
    definition_bytes = args.definition.read_bytes()
    definition = BasicPitchSweepDefinition.model_validate_json(definition_bytes)
    manifest = load_benchmark_manifest(args.manifest)
    split = split_benchmark_samples_by_group(
        manifest.samples,
        group_attribute=definition.group_attribute,
        holdout_fraction=definition.holdout_fraction,
        split_seed=definition.split_seed,
    )
    development_ids = [sample.id for sample in split.development_samples]
    holdout_ids = [sample.id for sample in split.holdout_samples]
    reports_directory = args.reports_directory or (
        args.output.parent / f"{args.output.stem}-reports"
    )
    reports_directory.mkdir(parents=True, exist_ok=True)

    development_scores = [
        _run_candidate(
            args,
            candidate,
            partition="development",
            sample_ids=development_ids,
            reports_directory=reports_directory,
        )
        for candidate in definition.candidates
    ]
    development_ranking = rank_basic_pitch_scores(development_scores)
    selected_candidate = _candidate_by_id(
        definition,
        development_ranking[0].candidate_id,
    )
    baseline_candidate = _candidate_by_id(definition, definition.baseline_candidate_id)
    baseline_development = _score_by_id(
        development_scores,
        definition.baseline_candidate_id,
    )
    selected_development = _score_by_id(
        development_scores,
        selected_candidate.id,
    )

    holdout_candidates = [baseline_candidate]
    if selected_candidate.id != baseline_candidate.id:
        holdout_candidates.append(selected_candidate)
    holdout_scores = [
        _run_candidate(
            args,
            candidate,
            partition="holdout",
            sample_ids=holdout_ids,
            reports_directory=reports_directory,
        )
        for candidate in holdout_candidates
    ]
    baseline_holdout = _score_by_id(holdout_scores, baseline_candidate.id)
    selected_holdout = _score_by_id(holdout_scores, selected_candidate.id)
    development_improvement = (
        selected_development.macro_onset_pitch_offset_f1
        - baseline_development.macro_onset_pitch_offset_f1
    )
    holdout_improvement = (
        selected_holdout.macro_onset_pitch_offset_f1
        - baseline_holdout.macro_onset_pitch_offset_f1
    )
    meets_observation_targets = (
        selected_holdout.macro_onset_pitch_f1
        >= definition.target_macro_onset_pitch_f1
        and selected_holdout.macro_onset_pitch_offset_f1
        >= definition.target_macro_onset_pitch_offset_f1
    )
    if meets_observation_targets:
        recommendation = "candidate_meets_observation_targets"
    elif (
        development_improvement < definition.minimum_macro_f1_improvement
        or holdout_improvement <= 0
    ):
        recommendation = "parameter_sweep_does_not_show_generalizable_improvement"
    else:
        recommendation = "parameter_tuning_improves_quality_but_model_gap_remains"

    summary: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest": {
            "path": str(args.manifest.resolve()),
            "sha256": sha256(args.manifest.read_bytes()).hexdigest(),
            "dataset": manifest.dataset.model_dump(mode="json"),
        },
        "definition": {
            "path": str(args.definition.resolve()),
            "sha256": sha256(definition_bytes).hexdigest(),
            **definition.model_dump(mode="json", exclude={"candidates"}),
        },
        "split": {
            "group_attribute": definition.group_attribute,
            "development_groups": list(split.development_groups),
            "holdout_groups": list(split.holdout_groups),
            "development_sample_ids": development_ids,
            "holdout_sample_ids": holdout_ids,
        },
        "development_ranking": [
            score.model_dump(mode="json") for score in development_ranking
        ],
        "holdout_scores": [score.model_dump(mode="json") for score in holdout_scores],
        "selection": {
            "objective": definition.objective,
            "baseline_candidate_id": baseline_candidate.id,
            "selected_candidate_id": selected_candidate.id,
            "development_macro_offset_f1_improvement": development_improvement,
            "holdout_macro_offset_f1_improvement": holdout_improvement,
            "minimum_macro_f1_improvement": definition.minimum_macro_f1_improvement,
        },
        "observation_targets": {
            "macro_onset_pitch_f1": definition.target_macro_onset_pitch_f1,
            "macro_onset_pitch_offset_f1": (
                definition.target_macro_onset_pitch_offset_f1
            ),
            "selected_candidate_meets_targets_on_holdout": meets_observation_targets,
            "formal_release_gate": False,
        },
        "recommendation": recommendation,
    }
    _write_json(args.output, summary)
    return summary


def _run_candidate(
    args: argparse.Namespace,
    candidate: BasicPitchSweepCandidate,
    *,
    partition: str,
    sample_ids: list[str],
    reports_directory: Path,
) -> BasicPitchSweepScore:
    report_path = reports_directory / f"{partition}-{candidate.id}.json"
    report = None
    if args.reuse_existing and report_path.is_file():
        report = _load_reusable_report(report_path, candidate, sample_ids)
    if report is None:
        benchmark_args = argparse.Namespace(
            manifest=args.manifest,
            service_url=args.service_url,
            timeout_seconds=args.timeout_seconds,
            warmup_runs=args.warmup_runs,
            container=None,
            no_resource_sampling=True,
            workspace=args.workspace,
            provider_params=dict(candidate.params),
            sample_ids=sample_ids,
        )
        report, _passed = run_benchmark(benchmark_args)
        report["sweep_partition"] = partition
        report["sweep_candidate_id"] = candidate.id
        _write_json(report_path, report)
    return score_basic_pitch_report(
        candidate,
        report,
        report_path=str(report_path.resolve()),
    )


def _load_reusable_report(
    path: Path,
    candidate: BasicPitchSweepCandidate,
    sample_ids: list[str],
) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    provider = payload.get("provider")
    inputs = payload.get("inputs")
    if not isinstance(provider, dict) or not isinstance(inputs, list):
        return None
    if provider.get("params") != candidate.effective_params():
        return None
    input_ids = [item.get("id") for item in inputs if isinstance(item, dict)]
    if input_ids != sample_ids:
        return None
    return payload


def _candidate_by_id(
    definition: BasicPitchSweepDefinition,
    candidate_id: str,
) -> BasicPitchSweepCandidate:
    for candidate in definition.candidates:
        if candidate.id == candidate_id:
            return candidate
    raise ValueError(f"unknown Basic Pitch sweep candidate: {candidate_id}")


def _score_by_id(
    scores: list[BasicPitchSweepScore],
    candidate_id: str,
) -> BasicPitchSweepScore:
    for score in scores:
        if score.candidate_id == candidate_id:
            return score
    raise ValueError(f"missing Basic Pitch sweep score: {candidate_id}")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    workspace = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--definition",
        type=Path,
        default=workspace / "support" / "basic_pitch_vocadito_sweep.json",
    )
    parser.add_argument("--service-url", default="http://127.0.0.1:8010")
    parser.add_argument("--timeout-seconds", type=float, default=180)
    parser.add_argument("--warmup-runs", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reports-directory", type=Path)
    parser.add_argument("--reuse-existing", action="store_true")
    parser.set_defaults(workspace=workspace)
    args = parser.parse_args()
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    if args.warmup_runs < 0:
        parser.error("--warmup-runs must be non-negative")
    if not args.manifest.is_file():
        parser.error(f"manifest does not exist: {args.manifest}")
    if not args.definition.is_file():
        parser.error(f"sweep definition does not exist: {args.definition}")
    return args


def main() -> int:
    args = parse_args()
    try:
        summary = run_sweep(args)
    except Exception as error:  # noqa: BLE001 - CLI error boundary
        print(f"Basic Pitch sweep failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "selection": summary["selection"],
            },
            indent=2,
        )
    )
    print(f"recommendation: {summary['recommendation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

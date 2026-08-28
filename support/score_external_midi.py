"""Score MIDI produced outside this repository against a benchmark manifest.

`benchmark_audio_to_midi.py` drives the Basic Pitch sidecar directly. A candidate
provider that cannot be installed alongside the project -- a different framework, a
conflicting dependency pin, a model whose weights are not redistributable -- is
evaluated instead by transcribing into a directory of `<sample_id>.mid` files and
scoring them here. That keeps candidate comparison on the same evaluator, tolerances
and reference-selection policy as the committed baselines.

    uv run python -m support.score_external_midi \
      path/to/vocadito/manifest.json \
      --midi-dir path/to/candidate-midi \
      --output path/to/candidate-report.json

An optional `index.json` in the MIDI directory supplies timing, keyed by sample id with
`latency_seconds` and `audio_duration_seconds`. Samples with no MIDI file are skipped
and reported, so a partial run still scores.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from abachiwave.evaluations.audio_to_midi import (
    AudioToMidiBenchmarkManifest,
    BenchmarkSample,
    classify_missed_reference_notes,
    collect_note_timing_errors,
    compare_reference_candidates,
    count_notes_by_program,
    load_benchmark_manifest,
    parse_timed_midi_notes,
)
from abachiwave.evaluations.basic_pitch_sweep import split_benchmark_samples_by_group


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def score_group(
    manifest: AudioToMidiBenchmarkManifest,
    samples: list[BenchmarkSample],
    midi_dir: Path,
    timing: dict[str, dict[str, float]],
    programs: frozenset[int] | None,
) -> dict[str, object]:
    macro_onset: list[float] = []
    macro_offset: list[float] = []
    reference_total = predicted_total = onset_hits = offset_hits = 0
    onset_matched = merged = covered = undetected = 0
    latencies: list[float] = []
    factors: list[float] = []
    signed_duration_ms: list[float] = []
    empty_results = 0

    for sample in samples:
        predicted = parse_timed_midi_notes(
            (midi_dir / f"{sample.id}.mid").read_bytes(), programs=programs
        )
        if not predicted:
            empty_results += 1
        references = [
            (sample.reference_id, parse_timed_midi_notes(sample.reference_midi_path.read_bytes())),
            *(
                (reference.id, parse_timed_midi_notes(reference.midi_path.read_bytes()))
                for reference in sample.alternative_references
            ),
        ]
        selected, metrics = compare_reference_candidates(
            references,
            predicted,
            selection_policy=manifest.reference_selection_policy,
            onset_tolerance_seconds=manifest.onset_tolerance_seconds,
            offset_tolerance_seconds=manifest.offset_tolerance_seconds,
            offset_tolerance_ratio=manifest.offset_tolerance_ratio,
        )
        reference_notes = dict(references)[selected]
        breakdown = classify_missed_reference_notes(
            reference_notes,
            predicted,
            onset_tolerance_seconds=manifest.onset_tolerance_seconds,
            offset_tolerance_seconds=manifest.offset_tolerance_seconds,
            offset_tolerance_ratio=manifest.offset_tolerance_ratio,
        )
        signed_duration_ms.extend(
            error.duration_error_seconds * 1000
            for error in collect_note_timing_errors(
                reference_notes,
                predicted,
                onset_tolerance_seconds=manifest.onset_tolerance_seconds,
                offset_tolerance_seconds=manifest.offset_tolerance_seconds,
                offset_tolerance_ratio=manifest.offset_tolerance_ratio,
            )
        )
        macro_onset.append(metrics.onset_pitch_f1)
        macro_offset.append(metrics.onset_pitch_offset_f1)
        reference_total += metrics.reference_notes
        predicted_total += metrics.predicted_notes
        onset_hits += metrics.onset_pitch_matches
        offset_hits += metrics.onset_pitch_offset_matches
        onset_matched += breakdown.onset_matched
        merged += breakdown.merged_into_same_pitch
        covered += breakdown.covered_by_other_pitch
        undetected += breakdown.undetected
        entry = timing.get(sample.id)
        if entry and entry.get("latency_seconds"):
            latencies.append(float(entry["latency_seconds"]))
            duration = float(entry.get("audio_duration_seconds") or 0)
            if duration > 0:
                factors.append(float(entry["latency_seconds"]) / duration)

    def micro_f1(hits: int) -> float:
        precision = hits / predicted_total if predicted_total else 0.0
        recall = hits / reference_total if reference_total else 0.0
        return 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    missed = reference_total - onset_matched
    macro_no_offset = statistics.fmean(macro_onset)
    macro_with_offset = statistics.fmean(macro_offset)
    return {
        "sample_count": len(samples),
        "reference_notes": reference_total,
        "predicted_notes": predicted_total,
        "empty_result_rate": empty_results / len(samples),
        "macro_onset_pitch_f1": macro_no_offset,
        "macro_onset_pitch_offset_f1": macro_with_offset,
        "macro_offset_gap": macro_no_offset - macro_with_offset,
        "micro_onset_pitch_f1": micro_f1(onset_hits),
        "micro_onset_pitch_offset_f1": micro_f1(offset_hits),
        "onset_recall": onset_matched / reference_total if reference_total else 0.0,
        "missed_notes": {
            "missed": missed,
            "merged_into_same_pitch": merged,
            "covered_by_other_pitch": covered,
            "undetected": undetected,
            "merged_share_of_missed": (merged / missed) if missed else None,
            "undetected_share_of_missed": (undetected / missed) if missed else None,
        },
        "signed_duration_error_ms": {
            "median": statistics.median(signed_duration_ms) if signed_duration_ms else None,
            "mean": statistics.fmean(signed_duration_ms) if signed_duration_ms else None,
        },
        "median_latency_seconds": statistics.median(latencies) if latencies else None,
        "p95_latency_seconds": _percentile(latencies, 0.95),
        "median_real_time_factor": statistics.median(factors) if factors else None,
        "p95_real_time_factor": _percentile(factors, 0.95),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--midi-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--group-by",
        choices=("partition", "category"),
        default="category",
        help="partition uses the grouped development/holdout split, category uses "
        "the manifest's own sample categories",
    )
    parser.add_argument(
        "--programs",
        default="",
        help="comma-separated MIDI programs to keep, e.g. 100,101 for singing voice",
    )
    parser.add_argument("--group-attribute", default="singer_id")
    parser.add_argument("--holdout-fraction", type=float, default=0.25)
    parser.add_argument("--split-seed", default="abachiwave-vocadito-basic-pitch-v1")
    parser.add_argument("--candidate", default="external", help="label recorded in the report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_benchmark_manifest(args.manifest)
    programs = (
        frozenset(int(value) for value in args.programs.split(",")) if args.programs else None
    )
    timing_path = args.midi_dir / "index.json"
    timing: dict[str, dict[str, float]] = (
        json.loads(timing_path.read_text(encoding="utf-8")) if timing_path.is_file() else {}
    )

    available = [s for s in manifest.samples if (args.midi_dir / f"{s.id}.mid").is_file()]
    missing = [s.id for s in manifest.samples if s not in available]
    if not available:
        raise ValueError(f"no <sample_id>.mid files found in {args.midi_dir}")

    groups: dict[str, list[BenchmarkSample]] = {"overall": available}
    if args.group_by == "partition":
        split = split_benchmark_samples_by_group(
            manifest.samples,
            group_attribute=args.group_attribute,
            holdout_fraction=args.holdout_fraction,
            split_seed=args.split_seed,
        )
        development = {s.id for s in split.development_samples}
        groups["development"] = [s for s in available if s.id in development]
        groups["holdout"] = [s for s in available if s.id not in development]
    else:
        by_category: dict[str, list[BenchmarkSample]] = defaultdict(list)
        for sample in available:
            by_category[sample.category].append(sample)
        groups.update(by_category)

    program_totals: dict[int, int] = defaultdict(int)
    for sample in available:
        for program, count in count_notes_by_program(
            (args.midi_dir / f"{sample.id}.mid").read_bytes()
        ).items():
            program_totals[program] += count

    report: dict[str, object] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "candidate": args.candidate,
        "dataset": manifest.dataset.model_dump(mode="json"),
        "manifest": {
            "path": str(args.manifest),
            "sha256": sha256(args.manifest.read_bytes()).hexdigest(),
        },
        "midi_dir": str(args.midi_dir),
        "kept_programs": sorted(programs) if programs else None,
        "predicted_notes_by_program": dict(sorted(program_totals.items())),
        "tolerances": {
            "onset_seconds": manifest.onset_tolerance_seconds,
            "offset_seconds": manifest.offset_tolerance_seconds,
            "offset_ratio": manifest.offset_tolerance_ratio,
        },
        "reference_selection_policy": manifest.reference_selection_policy,
        "samples_without_midi": missing,
        "groups": {
            name: score_group(manifest, members, args.midi_dir, timing, programs)
            for name, members in groups.items()
            if members
        },
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["groups"], indent=2, sort_keys=True))
    if missing:
        print(f"\n{len(missing)} sample(s) had no MIDI and were skipped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

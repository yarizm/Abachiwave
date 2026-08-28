"""Decompose the offset half of the audio-to-MIDI quality gap.

`onset+pitch+offset F1` is always below `onset+pitch F1`; the difference is what a
perfect note-offset layer could recover. This tool measures that ceiling, reports the
*signed* duration error distribution behind it, and grid-searches the cheap global
post-processing transforms (duration scale, duration shift) that would only help if the
error carried a systematic bias.

Run it on the same grouped split the parameter sweep uses, so a transform can be chosen
on development groups and confirmed on holdout groups instead of fitted on both.

    uv run python -m support.analyze_audio_to_midi_offsets \
      path/to/vocadito/manifest.json \
      --output path/to/vocadito/offset-analysis.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import httpx

from abachiwave.evaluations.audio_to_midi import (
    AudioToMidiBenchmarkManifest,
    BenchmarkSample,
    MissedNoteBreakdown,
    NoteTimingError,
    TimedMidiNote,
    classify_missed_reference_notes,
    collect_note_timing_errors,
    compare_reference_candidates,
    parse_timed_midi_notes,
)
from abachiwave.evaluations.basic_pitch_sweep import (
    prepare_basic_pitch_benchmark_manifest,
    split_benchmark_samples_by_group,
)
from abachiwave.schemas.song_specs import SongSpecData
from abachiwave.services.audio_to_midi_provider import (
    AudioToMidiRequest,
    BasicPitchHttpAudioToMidiProvider,
)

MINIMUM_TRANSFORMED_DURATION_SECONDS = 0.010
DURATION_SCALE_GRID = (0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.05, 1.10, 1.20, 1.30)
DURATION_SHIFT_GRID_MS = (-150, -120, -100, -80, -60, -40, -20, 20, 40, 60, 80)
MONOPHONIC_RULES = ("keep_longest", "keep_loudest", "truncate_at_next_onset")

Transform = Callable[[list[TimedMidiNote]], list[TimedMidiNote]]


def scale_durations(notes: list[TimedMidiNote], factor: float) -> list[TimedMidiNote]:
    return [
        TimedMidiNote(
            pitch=note.pitch,
            onset_seconds=note.onset_seconds,
            offset_seconds=note.onset_seconds
            + max(MINIMUM_TRANSFORMED_DURATION_SECONDS, note.duration_seconds * factor),
            velocity=note.velocity,
        )
        for note in notes
    ]


def shift_durations(notes: list[TimedMidiNote], seconds: float) -> list[TimedMidiNote]:
    return [
        TimedMidiNote(
            pitch=note.pitch,
            onset_seconds=note.onset_seconds,
            offset_seconds=note.onset_seconds
            + max(MINIMUM_TRANSFORMED_DURATION_SECONDS, note.duration_seconds + seconds),
            velocity=note.velocity,
        )
        for note in notes
    ]


def enforce_monophony(notes: list[TimedMidiNote], rule: str) -> list[TimedMidiNote]:
    """Remove or clip overlapping notes.

    Only meaningful on a monophonic dataset, where every overlap in the prediction is
    an error by construction. ``truncate_at_next_onset`` keeps every note and only
    clips its offset; the two ``keep_*`` rules drop the losing note outright.
    """
    if rule not in MONOPHONIC_RULES:
        raise ValueError(f"unknown monophonic rule: {rule}")
    ordered = sorted(notes, key=lambda note: (note.onset_seconds, note.pitch))
    if rule == "truncate_at_next_onset":
        clipped: list[TimedMidiNote] = []
        for index, note in enumerate(ordered):
            offset = note.offset_seconds
            for later in ordered[index + 1 :]:
                if later.onset_seconds > note.onset_seconds:
                    offset = min(offset, later.onset_seconds)
                    break
            clipped.append(
                TimedMidiNote(
                    pitch=note.pitch,
                    onset_seconds=note.onset_seconds,
                    offset_seconds=max(
                        note.onset_seconds + MINIMUM_TRANSFORMED_DURATION_SECONDS, offset
                    ),
                    velocity=note.velocity,
                )
            )
        return clipped

    def rank(note: TimedMidiNote) -> float:
        return note.duration_seconds if rule == "keep_longest" else float(note.velocity)

    kept: list[TimedMidiNote] = []
    for note in sorted(ordered, key=lambda item: (item.onset_seconds, -item.velocity)):
        if kept and note.onset_seconds < kept[-1].offset_seconds:
            if rank(note) > rank(kept[-1]):
                kept[-1] = note
            continue
        kept.append(note)
    return sorted(kept, key=lambda note: (note.onset_seconds, note.pitch, note.offset_seconds))


class SamplePrediction:
    """One transcribed sample with its reference candidates kept in memory."""

    def __init__(
        self,
        sample: BenchmarkSample,
        references: list[tuple[str, list[TimedMidiNote]]],
        predicted: list[TimedMidiNote],
    ) -> None:
        self.sample_id = sample.id
        self.category = sample.category
        self.references = references
        self.predicted = predicted


def _benchmark_song_spec() -> SongSpecData:
    return SongSpecData(
        title="Audio-to-MIDI offset analysis",
        language="English",
        genre=["Benchmark"],
        mood="neutral",
        theme="evaluation",
        story_arc="controlled fixture",
        narrative_perspective="instrumental",
        target_duration_seconds=180,
        tempo_bpm=120,
        key="C major",
        time_signature="4/4",
        energy_curve="steady",
        vocal_style="neutral",
        instrumentation=["reference audio"],
        song_structure=["fixture"],
        structure_sections=[],
        constraints=[],
    )


def transcribe_samples(
    manifest: AudioToMidiBenchmarkManifest,
    samples: Sequence[BenchmarkSample],
    provider: BasicPitchHttpAudioToMidiProvider,
) -> list[SamplePrediction]:
    predictions: list[SamplePrediction] = []
    for index, sample in enumerate(samples, start=1):
        references = [
            (
                sample.reference_id,
                parse_timed_midi_notes(sample.reference_midi_path.read_bytes()),
            ),
            *(
                (reference.id, parse_timed_midi_notes(reference.midi_path.read_bytes()))
                for reference in sample.alternative_references
            ),
        ]
        for reference_id, reference_notes in references:
            if not reference_notes:
                raise ValueError(
                    f"reference MIDI has no complete notes: {sample.id}/{reference_id}"
                )
        generated = provider.extract_midi(
            AudioToMidiRequest(
                audio_bytes=sample.audio_path.read_bytes(),
                filename=sample.audio_path.name,
                song_spec=_benchmark_song_spec(),
                provider_params=dict(manifest.provider_params),
            )
        )
        predictions.append(
            SamplePrediction(sample, references, parse_timed_midi_notes(generated.data))
        )
        print(f"[{index}/{len(samples)}] {sample.id}", file=sys.stderr, flush=True)
    return predictions


def score_partition(
    manifest: AudioToMidiBenchmarkManifest,
    predictions: Sequence[SamplePrediction],
    transform: Transform,
) -> dict[str, float | int]:
    macro_onset: list[float] = []
    macro_offset: list[float] = []
    reference_notes = predicted_notes = onset_matches = offset_matches = 0
    for prediction in predictions:
        _selected, metrics = compare_reference_candidates(
            prediction.references,
            transform(prediction.predicted),
            selection_policy=manifest.reference_selection_policy,
            onset_tolerance_seconds=manifest.onset_tolerance_seconds,
            offset_tolerance_seconds=manifest.offset_tolerance_seconds,
            offset_tolerance_ratio=manifest.offset_tolerance_ratio,
        )
        macro_onset.append(metrics.onset_pitch_f1)
        macro_offset.append(metrics.onset_pitch_offset_f1)
        reference_notes += metrics.reference_notes
        predicted_notes += metrics.predicted_notes
        onset_matches += metrics.onset_pitch_matches
        offset_matches += metrics.onset_pitch_offset_matches

    def micro_f1(matches: int) -> float:
        precision = matches / predicted_notes if predicted_notes else 0.0
        recall = matches / reference_notes if reference_notes else 0.0
        return 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    return {
        "sample_count": len(predictions),
        "macro_onset_pitch_f1": statistics.fmean(macro_onset),
        "macro_onset_pitch_offset_f1": statistics.fmean(macro_offset),
        "micro_onset_pitch_f1": micro_f1(onset_matches),
        "micro_onset_pitch_offset_f1": micro_f1(offset_matches),
    }


def _quantile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def _milliseconds(values: Sequence[float]) -> dict[str, float]:
    scaled = [value * 1000 for value in values]
    return {
        "mean": statistics.fmean(scaled),
        "median": statistics.median(scaled),
        "p10": _quantile(scaled, 0.10),
        "p25": _quantile(scaled, 0.25),
        "p75": _quantile(scaled, 0.75),
        "p90": _quantile(scaled, 0.90),
    }


def describe_timing_errors(errors: Sequence[NoteTimingError]) -> dict[str, object]:
    """Summarise signed timing error, and split offset failures by sign.

    A near-zero median duration error together with a roughly even split of failures
    between "too long" and "too short" means the error is symmetric scatter, which no
    global transform can remove.
    """
    if not errors:
        raise ValueError("no onset+pitch matched note pairs to analyse")
    ratios = [
        1 + error.duration_error_seconds / error.reference_duration_seconds
        for error in errors
        if error.reference_duration_seconds > 0
    ]
    reference_durations = [error.reference_duration_seconds for error in errors]
    too_long = sum(
        1
        for error in errors
        if not error.offset_within_tolerance and error.offset_error_seconds > 0
    )
    too_short = sum(
        1
        for error in errors
        if not error.offset_within_tolerance and error.offset_error_seconds < 0
    )
    failures = too_long + too_short
    return {
        "matched_pairs": len(errors),
        "signed_duration_error_ms": _milliseconds(
            [error.duration_error_seconds for error in errors]
        ),
        "signed_onset_error_ms": _milliseconds([error.onset_error_seconds for error in errors]),
        "predicted_over_reference_duration_ratio": {
            "median": statistics.median(ratios),
            "p25": _quantile(ratios, 0.25),
            "p75": _quantile(ratios, 0.75),
        },
        "reference_duration_seconds": {
            "median": statistics.median(reference_durations),
            "p10": _quantile(reference_durations, 0.10),
            "p90": _quantile(reference_durations, 0.90),
        },
        "offset_criterion": {
            "within_tolerance": sum(1 for error in errors if error.offset_within_tolerance),
            "failing_predicted_too_long": too_long,
            "failing_predicted_too_short": too_short,
            "too_long_share_of_failures": (too_long / failures) if failures else None,
        },
    }


def summarise_missed_notes(breakdowns: Sequence[MissedNoteBreakdown]) -> dict[str, object]:
    """Pool the per-sample recall breakdowns into one classification of the misses."""
    reference_notes = sum(item.reference_notes for item in breakdowns)
    onset_matched = sum(item.onset_matched for item in breakdowns)
    merged = sum(item.merged_into_same_pitch for item in breakdowns)
    covered = sum(item.covered_by_other_pitch for item in breakdowns)
    undetected = sum(item.undetected for item in breakdowns)
    missed = reference_notes - onset_matched

    def share(count: int) -> float | None:
        return count / missed if missed else None

    return {
        "reference_notes": reference_notes,
        "onset_matched": onset_matched,
        "onset_recall": onset_matched / reference_notes if reference_notes else 0.0,
        "missed": missed,
        "merged_into_same_pitch": merged,
        "covered_by_other_pitch": covered,
        "undetected": undetected,
        "merged_share_of_missed": share(merged),
        "undetected_share_of_missed": share(undetected),
    }


def analyse_partition(
    manifest: AudioToMidiBenchmarkManifest,
    predictions: Sequence[SamplePrediction],
) -> dict[str, object]:
    errors: list[NoteTimingError] = []
    breakdowns: list[MissedNoteBreakdown] = []
    for prediction in predictions:
        selected, _metrics = compare_reference_candidates(
            prediction.references,
            prediction.predicted,
            selection_policy=manifest.reference_selection_policy,
            onset_tolerance_seconds=manifest.onset_tolerance_seconds,
            offset_tolerance_seconds=manifest.offset_tolerance_seconds,
            offset_tolerance_ratio=manifest.offset_tolerance_ratio,
        )
        reference = dict(prediction.references)[selected]
        errors.extend(
            collect_note_timing_errors(
                reference,
                prediction.predicted,
                onset_tolerance_seconds=manifest.onset_tolerance_seconds,
                offset_tolerance_seconds=manifest.offset_tolerance_seconds,
                offset_tolerance_ratio=manifest.offset_tolerance_ratio,
            )
        )
        breakdowns.append(
            classify_missed_reference_notes(
                reference,
                prediction.predicted,
                onset_tolerance_seconds=manifest.onset_tolerance_seconds,
                offset_tolerance_seconds=manifest.offset_tolerance_seconds,
                offset_tolerance_ratio=manifest.offset_tolerance_ratio,
            )
        )

    identity = score_partition(manifest, predictions, lambda notes: notes)
    baseline_offset_f1 = float(identity["macro_onset_pitch_offset_f1"])
    transforms: list[dict[str, object]] = []
    for factor in DURATION_SCALE_GRID:
        scored = score_partition(
            manifest, predictions, lambda notes, factor=factor: scale_durations(notes, factor)
        )
        transforms.append(
            {
                "transform": "duration_scale",
                "value": factor,
                **scored,
                "macro_offset_f1_delta": float(scored["macro_onset_pitch_offset_f1"])
                - baseline_offset_f1,
            }
        )
    for shift_ms in DURATION_SHIFT_GRID_MS:
        scored = score_partition(
            manifest,
            predictions,
            lambda notes, shift_ms=shift_ms: shift_durations(notes, shift_ms / 1000),
        )
        transforms.append(
            {
                "transform": "duration_shift_ms",
                "value": shift_ms,
                **scored,
                "macro_offset_f1_delta": float(scored["macro_onset_pitch_offset_f1"])
                - baseline_offset_f1,
            }
        )
    for rule in MONOPHONIC_RULES:
        scored = score_partition(
            manifest, predictions, lambda notes, rule=rule: enforce_monophony(notes, rule)
        )
        transforms.append(
            {
                "transform": "monophonic_resolution",
                "value": rule,
                **scored,
                "macro_offset_f1_delta": float(scored["macro_onset_pitch_offset_f1"])
                - baseline_offset_f1,
            }
        )
    best = max(transforms, key=lambda row: float(row["macro_onset_pitch_offset_f1"]))
    best_delta = float(best["macro_offset_f1_delta"])
    return {
        "identity": identity,
        "perfect_offset_layer_ceiling": float(identity["macro_onset_pitch_f1"]),
        "offset_gap": float(identity["macro_onset_pitch_f1"]) - baseline_offset_f1,
        "timing_errors": describe_timing_errors(errors),
        "missed_notes": summarise_missed_notes(breakdowns),
        "transforms": transforms,
        "best_transform": (
            {"transform": "identity", "value": None, "macro_offset_f1_delta": 0.0}
            if best_delta <= 0
            else {
                "transform": best["transform"],
                "value": best["value"],
                "macro_offset_f1_delta": best_delta,
            }
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--service-url", default="http://127.0.0.1:8010")
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--group-attribute", default="singer_id")
    parser.add_argument("--holdout-fraction", type=float, default=0.25)
    parser.add_argument("--split-seed", default="abachiwave-vocadito-basic-pitch-v1")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = prepare_basic_pitch_benchmark_manifest(args.manifest)
    split = split_benchmark_samples_by_group(
        manifest.samples,
        group_attribute=args.group_attribute,
        holdout_fraction=args.holdout_fraction,
        split_seed=args.split_seed,
    )
    provider = BasicPitchHttpAudioToMidiProvider(
        args.service_url, timeout_seconds=args.timeout_seconds
    )
    health = httpx.get(f"{args.service_url.rstrip('/')}/health/ready", timeout=10)
    health.raise_for_status()
    if health.json().get("status") != "ready":
        raise RuntimeError(f"Basic Pitch service is not ready: {health.json()}")

    partitions = {
        "development": transcribe_samples(manifest, split.development_samples, provider),
        "holdout": transcribe_samples(manifest, split.holdout_samples, provider),
    }
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": manifest.dataset.model_dump(mode="json"),
        "manifest": {
            "path": str(args.manifest),
            "sha256": sha256(args.manifest.read_bytes()).hexdigest(),
        },
        "provider": {
            "name": provider.name,
            "version": provider.version,
            "params": {**provider.default_params(), **manifest.provider_params},
        },
        "tolerances": {
            "onset_seconds": manifest.onset_tolerance_seconds,
            "offset_seconds": manifest.offset_tolerance_seconds,
            "offset_ratio": manifest.offset_tolerance_ratio,
        },
        "split": {
            "group_attribute": args.group_attribute,
            "holdout_fraction": args.holdout_fraction,
            "split_seed": args.split_seed,
            "development_groups": list(split.development_groups),
            "holdout_groups": list(split.holdout_groups),
        },
        "partitions": {
            name: analyse_partition(manifest, predictions)
            for name, predictions in partitions.items()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["partitions"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

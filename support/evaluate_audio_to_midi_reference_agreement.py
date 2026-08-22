"""Measure agreement between primary and alternative MIDI references in a manifest."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from abachiwave.evaluations.audio_to_midi import (
    NoteMatchMetrics,
    compare_note_sequences,
    load_benchmark_manifest,
    parse_timed_midi_notes,
)


@dataclass(frozen=True)
class ReferenceAgreementPair:
    sample_id: str
    category: str
    primary_reference_id: str
    alternative_reference_id: str
    metrics: NoteMatchMetrics


def evaluate_reference_agreement(manifest_path: Path) -> dict[str, object]:
    manifest = load_benchmark_manifest(manifest_path)
    pairs: list[ReferenceAgreementPair] = []
    for sample in manifest.samples:
        primary = parse_timed_midi_notes(sample.reference_midi_path.read_bytes())
        if not primary:
            raise ValueError(f"primary reference MIDI is empty: {sample.id}")
        for alternative in sample.alternative_references:
            alternative_notes = parse_timed_midi_notes(alternative.midi_path.read_bytes())
            if not alternative_notes:
                raise ValueError(
                    f"alternative reference MIDI is empty: {sample.id}/{alternative.id}"
                )
            pairs.append(
                ReferenceAgreementPair(
                    sample_id=sample.id,
                    category=sample.category,
                    primary_reference_id=sample.reference_id,
                    alternative_reference_id=alternative.id,
                    metrics=compare_note_sequences(
                        primary,
                        alternative_notes,
                        onset_tolerance_seconds=manifest.onset_tolerance_seconds,
                        offset_tolerance_seconds=manifest.offset_tolerance_seconds,
                        offset_tolerance_ratio=manifest.offset_tolerance_ratio,
                    ),
                )
            )
    if not pairs:
        raise ValueError("manifest contains no alternative references")
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset": manifest.dataset.model_dump(mode="json"),
        "tolerances": {
            "onset_seconds": manifest.onset_tolerance_seconds,
            "offset_seconds": manifest.offset_tolerance_seconds,
            "offset_ratio": manifest.offset_tolerance_ratio,
        },
        "overall": _aggregate(pairs),
        "categories": {
            category: _aggregate([pair for pair in pairs if pair.category == category])
            for category in sorted({pair.category for pair in pairs})
        },
        "pairs": [asdict(pair) for pair in pairs],
    }


def _aggregate(pairs: list[ReferenceAgreementPair]) -> dict[str, float | int]:
    reference_notes = sum(pair.metrics.reference_notes for pair in pairs)
    comparison_notes = sum(pair.metrics.predicted_notes for pair in pairs)
    onset_matches = sum(pair.metrics.onset_pitch_matches for pair in pairs)
    offset_matches = sum(pair.metrics.onset_pitch_offset_matches for pair in pairs)
    onset_precision, onset_recall, onset_f1 = _precision_recall_f1(
        onset_matches,
        reference_notes,
        comparison_notes,
    )
    offset_precision, offset_recall, offset_f1 = _precision_recall_f1(
        offset_matches,
        reference_notes,
        comparison_notes,
    )
    return {
        "pair_count": len(pairs),
        "primary_reference_notes": reference_notes,
        "alternative_reference_notes": comparison_notes,
        "onset_pitch_precision": onset_precision,
        "onset_pitch_recall": onset_recall,
        "onset_pitch_f1": onset_f1,
        "onset_pitch_offset_precision": offset_precision,
        "onset_pitch_offset_recall": offset_recall,
        "onset_pitch_offset_f1": offset_f1,
        "macro_onset_pitch_f1": mean(pair.metrics.onset_pitch_f1 for pair in pairs),
        "macro_onset_pitch_offset_f1": mean(
            pair.metrics.onset_pitch_offset_f1 for pair in pairs
        ),
    }


def _precision_recall_f1(
    matches: int,
    reference_count: int,
    prediction_count: int,
) -> tuple[float, float, float]:
    precision = matches / prediction_count if prediction_count else 0.0
    recall = matches / reference_count if reference_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = evaluate_reference_agreement(args.manifest)
        rendered = json.dumps(report, indent=2, ensure_ascii=False)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0
    except Exception as error:  # noqa: BLE001 - CLI error boundary
        print(
            f"reference agreement failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

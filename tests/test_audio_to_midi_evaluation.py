import json
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from mido import Message, MetaMessage, MidiFile, MidiTrack
from pydantic import ValidationError

from abachiwave.evaluations.audio_to_midi import (
    AudioToMidiBenchmarkManifest,
    MetricThresholds,
    ResourceMetrics,
    SampleBenchmarkResult,
    TimedMidiNote,
    aggregate_benchmark_results,
    collect_note_timing_errors,
    compare_note_sequences,
    compare_reference_candidates,
    evaluate_thresholds,
    load_benchmark_manifest,
    parse_timed_midi_notes,
)


def test_parse_timed_midi_notes_respects_tempo_changes() -> None:
    midi = MidiFile(type=0, ticks_per_beat=480)
    track = MidiTrack()
    track.append(MetaMessage("set_tempo", tempo=500_000, time=0))
    track.append(Message("note_on", note=60, velocity=80, time=0))
    track.append(Message("note_off", note=60, velocity=0, time=480))
    track.append(MetaMessage("set_tempo", tempo=1_000_000, time=0))
    track.append(Message("note_on", note=62, velocity=70, time=0))
    track.append(Message("note_off", note=62, velocity=0, time=480))
    midi.tracks.append(track)
    buffer = BytesIO()
    midi.save(file=buffer)

    notes = parse_timed_midi_notes(buffer.getvalue())

    assert [(note.pitch, note.onset_seconds, note.offset_seconds) for note in notes] == [
        (60, 0.0, 0.5),
        (62, 0.5, 1.5),
    ]


def test_note_matching_reports_pitch_timing_duration_and_velocity_errors() -> None:
    reference = [
        TimedMidiNote(pitch=69, onset_seconds=0, offset_seconds=1, velocity=80),
        TimedMidiNote(pitch=71, onset_seconds=1, offset_seconds=2, velocity=90),
    ]
    predicted = [
        TimedMidiNote(pitch=69, onset_seconds=0.03, offset_seconds=1.15, velocity=75),
        TimedMidiNote(pitch=72, onset_seconds=1.02, offset_seconds=2.02, velocity=95),
    ]

    metrics = compare_note_sequences(reference, predicted)

    assert metrics.onset_pitch_matches == 1
    assert metrics.onset_pitch_offset_matches == 1
    assert metrics.onset_aligned_matches == 2
    assert metrics.onset_pitch_f1 == pytest.approx(0.5)
    assert metrics.onset_pitch_offset_f1 == pytest.approx(0.5)
    assert metrics.onset_mae_ms == pytest.approx(30)
    assert metrics.duration_mae_ms == pytest.approx(120)
    assert metrics.velocity_mae == pytest.approx(5)
    assert metrics.onset_aligned_pitch_mae_semitones == pytest.approx(0.5)

    simultaneous = compare_note_sequences(
        [
            TimedMidiNote(pitch=60, onset_seconds=0, offset_seconds=1, velocity=80),
            TimedMidiNote(pitch=67, onset_seconds=0, offset_seconds=1, velocity=80),
        ],
        [
            TimedMidiNote(pitch=67, onset_seconds=0, offset_seconds=1, velocity=80),
            TimedMidiNote(pitch=60, onset_seconds=0, offset_seconds=1, velocity=80),
        ],
    )
    assert simultaneous.onset_aligned_pitch_mae_semitones == 0

    overlapping = compare_note_sequences(
        [
            TimedMidiNote(pitch=60, onset_seconds=0, offset_seconds=1, velocity=80),
            TimedMidiNote(pitch=60, onset_seconds=0.04, offset_seconds=1, velocity=80),
        ],
        [
            TimedMidiNote(pitch=60, onset_seconds=0.03, offset_seconds=1, velocity=80),
            TimedMidiNote(pitch=60, onset_seconds=0.07, offset_seconds=1, velocity=80),
        ],
        onset_tolerance_seconds=0.05,
    )
    assert overlapping.onset_pitch_matches == 2


def test_aggregate_metrics_are_micro_averaged_and_thresholded() -> None:
    perfect = compare_note_sequences(
        [TimedMidiNote(pitch=60, onset_seconds=0, offset_seconds=1, velocity=80)],
        [TimedMidiNote(pitch=60, onset_seconds=0, offset_seconds=1, velocity=80)],
    )
    missed = compare_note_sequences(
        [TimedMidiNote(pitch=62, onset_seconds=0, offset_seconds=1, velocity=80)],
        [],
    )
    report = aggregate_benchmark_results(
        [
            SampleBenchmarkResult("one", "vocal", 2, 1, 0.5, perfect),
            SampleBenchmarkResult("two", "vocal", 4, 3, 0.75, missed),
        ],
        resources=ResourceMetrics(peak_cpu_percent=125, peak_memory_mib=512),
    )

    overall = report["overall"]
    assert isinstance(overall, dict)
    assert overall["onset_pitch_precision"] == pytest.approx(1)
    assert overall["onset_pitch_recall"] == pytest.approx(0.5)
    assert overall["onset_pitch_f1"] == pytest.approx(2 / 3)
    assert overall["macro_onset_pitch_f1"] == pytest.approx(0.5)
    assert overall["empty_result_rate"] == pytest.approx(0.5)
    assert overall["median_real_time_factor"] == pytest.approx(0.625)
    assert overall["p95_latency_seconds"] == pytest.approx(2.9)

    violations = evaluate_thresholds(
        report,
        {
            "overall": MetricThresholds(
                onset_pitch_f1_min=0.8,
                empty_result_rate_max=0.2,
                peak_memory_mib_max=256,
            )
        },
    )
    assert {(violation.metric, violation.comparator) for violation in violations} == {
        ("onset_pitch_f1", ">="),
        ("empty_result_rate", "<="),
        ("peak_memory_mib", "<="),
    }


def test_manifest_resolves_relative_inputs_and_rejects_unknown_threshold_scope(
    tmp_path: Path,
) -> None:
    directory = tmp_path
    (directory / "fixture.wav").write_bytes(b"RIFF fixture WAVE")
    (directory / "fixture.mid").write_bytes(b"MThd fixture")
    payload = {
        "schema_version": 1,
        "dataset": {
            "name": "Fixture",
            "version": "1",
            "license": "generated",
            "synthetic": True,
        },
        "samples": [
            {
                "id": "fixture",
                "category": "synthetic",
                "audio_path": "fixture.wav",
                "reference_midi_path": "fixture.mid",
                "audio_sha256": sha256(b"RIFF fixture WAVE").hexdigest(),
                "reference_midi_sha256": sha256(b"MThd fixture").hexdigest(),
            }
        ],
        "thresholds": {"overall": {"empty_result_rate_max": 0}},
    }
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_benchmark_manifest(manifest_path)
    assert loaded.samples[0].audio_path == (directory / "fixture.wav").resolve()
    assert loaded.samples[0].reference_midi_path == (directory / "fixture.mid").resolve()

    (directory / "fixture.wav").write_bytes(b"RIFF changed WAVE")
    with pytest.raises(ValueError, match="checksum mismatch"):
        load_benchmark_manifest(manifest_path)
    (directory / "fixture.wav").write_bytes(b"RIFF fixture WAVE")

    payload["thresholds"] = {"vocal": {"onset_pitch_f1_min": 0.5}}
    with pytest.raises(ValidationError, match="threshold scopes"):
        AudioToMidiBenchmarkManifest.model_validate(payload)

    payload["thresholds"] = {}
    payload["dataset"] = {
        "name": "Real fixture",
        "version": "1",
        "license": "CC BY 4.0",
        "synthetic": False,
    }
    with pytest.raises(ValidationError, match="require license_url and source_url"):
        AudioToMidiBenchmarkManifest.model_validate(payload)


def test_manifest_validates_source_artifact_checksum_metadata(tmp_path: Path) -> None:
    directory = tmp_path
    (directory / "fixture.wav").write_bytes(b"RIFF fixture WAVE")
    (directory / "fixture.mid").write_bytes(b"MThd fixture")
    payload = {
        "schema_version": 1,
        "dataset": {
            "name": "Fixture",
            "version": "1",
            "license": "generated",
            "source_artifact_checksums": {"audio.zip": "md5:not-a-checksum"},
            "synthetic": True,
        },
        "samples": [
            {
                "id": "fixture",
                "category": "synthetic",
                "audio_path": "fixture.wav",
                "reference_midi_path": "fixture.mid",
                "audio_sha256": sha256(b"RIFF fixture WAVE").hexdigest(),
                "reference_midi_sha256": sha256(b"MThd fixture").hexdigest(),
            }
        ],
    }

    with pytest.raises(ValidationError, match="invalid source artifact checksum"):
        AudioToMidiBenchmarkManifest.model_validate(payload)


def test_multi_reference_policy_selects_best_offset_f1() -> None:
    predicted = [TimedMidiNote(60, 0, 1, 90)]
    references = [
        ("annotator_1", [TimedMidiNote(60, 0, 0.5, 90)]),
        ("annotator_2", [TimedMidiNote(60, 0, 1, 90)]),
    ]

    primary_id, primary_metrics = compare_reference_candidates(
        references,
        predicted,
        selection_policy="primary",
    )
    best_id, best_metrics = compare_reference_candidates(
        references,
        predicted,
        selection_policy="best_onset_pitch_offset_f1",
    )

    assert primary_id == "annotator_1"
    assert primary_metrics.onset_pitch_offset_f1 == 0
    assert best_id == "annotator_2"
    assert best_metrics.onset_pitch_offset_f1 == 1


def test_manifest_resolves_and_validates_alternative_references(tmp_path: Path) -> None:
    (tmp_path / "fixture.wav").write_bytes(b"RIFF fixture WAVE")
    (tmp_path / "a1.mid").write_bytes(b"MThd annotator one")
    (tmp_path / "a2.mid").write_bytes(b"MThd annotator two")
    payload = {
        "schema_version": 1,
        "dataset": {
            "name": "Fixture",
            "version": "1",
            "license": "generated",
            "synthetic": True,
        },
        "reference_selection_policy": "best_onset_pitch_offset_f1",
        "samples": [
            {
                "id": "fixture",
                "category": "synthetic",
                "audio_path": "fixture.wav",
                "reference_id": "annotator_1",
                "reference_midi_path": "a1.mid",
                "audio_sha256": sha256(b"RIFF fixture WAVE").hexdigest(),
                "reference_midi_sha256": sha256(b"MThd annotator one").hexdigest(),
                "alternative_references": [
                    {
                        "id": "annotator_2",
                        "midi_path": "a2.mid",
                        "midi_sha256": sha256(b"MThd annotator two").hexdigest(),
                    }
                ],
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    manifest = load_benchmark_manifest(manifest_path)

    assert manifest.samples[0].alternative_references[0].midi_path == (
        tmp_path / "a2.mid"
    ).resolve()
    duplicate_payload = json.loads(json.dumps(payload))
    duplicate_payload["samples"][0]["alternative_references"][0]["id"] = "annotator_1"
    with pytest.raises(ValidationError, match="reference ids must be unique"):
        AudioToMidiBenchmarkManifest.model_validate(duplicate_payload)


def _note(pitch: int, onset: float, offset: float, velocity: int = 80) -> TimedMidiNote:
    return TimedMidiNote(
        pitch=pitch,
        onset_seconds=onset,
        offset_seconds=offset,
        velocity=velocity,
    )


def test_collect_note_timing_errors_reports_signed_errors() -> None:
    reference = [_note(60, 0.0, 1.0), _note(62, 2.0, 2.4)]
    predicted = [_note(60, 0.02, 1.30), _note(62, 1.99, 2.30)]

    errors = collect_note_timing_errors(reference, predicted)

    assert len(errors) == 2
    held_too_long, released_too_early = errors
    assert held_too_long.onset_error_seconds == pytest.approx(0.02)
    assert held_too_long.duration_error_seconds == pytest.approx(0.28)
    assert held_too_long.offset_error_seconds == pytest.approx(0.30)
    assert released_too_early.duration_error_seconds == pytest.approx(-0.09)
    assert released_too_early.offset_error_seconds == pytest.approx(-0.10)


def test_collect_note_timing_errors_uses_the_ratio_tolerance_for_long_notes() -> None:
    long_note = collect_note_timing_errors([_note(60, 0.0, 4.0)], [_note(60, 0.0, 4.6)])[0]
    short_note = collect_note_timing_errors([_note(60, 0.0, 0.2)], [_note(60, 0.0, 0.24)])[0]

    assert long_note.allowed_offset_error_seconds == pytest.approx(0.8)
    assert long_note.offset_within_tolerance is True
    assert short_note.allowed_offset_error_seconds == pytest.approx(0.05)
    assert short_note.offset_within_tolerance is True

    outside = collect_note_timing_errors([_note(60, 0.0, 0.2)], [_note(60, 0.0, 0.26)])[0]
    assert outside.offset_within_tolerance is False


def test_collect_note_timing_errors_excludes_unmatched_notes() -> None:
    reference = [_note(60, 0.0, 1.0), _note(64, 5.0, 5.5)]
    predicted = [_note(60, 0.01, 1.0), _note(67, 5.0, 5.5), _note(60, 9.0, 9.5)]

    errors = collect_note_timing_errors(reference, predicted)

    assert len(errors) == 1
    assert errors[0].onset_error_seconds == pytest.approx(0.01)

import wave
from pathlib import Path

import pytest

from abachiwave.evaluations.audio_to_midi import (
    MetricThresholds,
    ResourceMetrics,
    SampleBenchmarkResult,
    TimedMidiNote,
    aggregate_benchmark_results,
    compare_note_sequences,
    evaluate_thresholds,
    load_benchmark_manifest,
    parse_docker_memory_mib,
    parse_timed_midi_notes,
)
from abachiwave.evaluations.audio_to_midi_fixtures import FIXTURES, create_smoke_dataset
from abachiwave.evaluations.basic_pitch_sweep import (
    parse_basic_pitch_param_assignments,
    prepare_basic_pitch_benchmark_manifest,
)


def test_smoke_dataset_generator_creates_valid_audio_midi_pairs(tmp_path: Path) -> None:
    manifest_path = create_smoke_dataset(tmp_path)
    manifest = load_benchmark_manifest(manifest_path)

    assert manifest.dataset.synthetic is True
    assert len(manifest.samples) == len(FIXTURES)
    for sample in manifest.samples:
        with wave.open(str(sample.audio_path), "rb") as reader:
            assert reader.getframerate() == 48_000
            assert reader.getnframes() > 0
        assert parse_timed_midi_notes(sample.reference_midi_path.read_bytes())


@pytest.mark.parametrize(
    ("docker_value", "expected_mib"),
    [
        ("512KiB", 0.5),
        ("609.7MiB", 609.7),
        ("1.5GiB", 1536),
        ("100MB", 100_000_000 / (1024 * 1024)),
    ],
)
def test_docker_memory_parser_normalizes_binary_and_decimal_units(
    docker_value: str,
    expected_mib: float,
) -> None:
    assert parse_docker_memory_mib(docker_value) == pytest.approx(expected_mib)


def test_cpu_threshold_rejects_missing_stream_sample() -> None:
    metrics = compare_note_sequences(
        [TimedMidiNote(60, 0, 1, 80)],
        [TimedMidiNote(60, 0, 1, 80)],
    )
    report = aggregate_benchmark_results(
        [SampleBenchmarkResult("fixture", "synthetic", 1, 0.1, 0.1, metrics)],
        resources=ResourceMetrics(peak_memory_mib=600),
    )

    with pytest.raises(ValueError, match="requires container resource sampling"):
        evaluate_thresholds(
            report,
            {"overall": MetricThresholds(peak_cpu_percent_max=100)},
        )


def test_benchmark_manifest_overrides_provider_params_and_filters_samples(
    tmp_path: Path,
) -> None:
    manifest_path = create_smoke_dataset(tmp_path)
    loaded = load_benchmark_manifest(manifest_path)
    selected_id = loaded.samples[-1].id

    prepared = prepare_basic_pitch_benchmark_manifest(
        manifest_path,
        provider_params={"onset_threshold": 0.4, "melodia_trick": False},
        sample_ids=[selected_id],
    )

    assert [sample.id for sample in prepared.samples] == [selected_id]
    assert prepared.provider_params == {
        "onset_threshold": 0.4,
        "melodia_trick": False,
    }
    with pytest.raises(ValueError, match="do not exist"):
        prepare_basic_pitch_benchmark_manifest(manifest_path, sample_ids=["missing"])


def test_provider_param_cli_values_are_typed_and_unique() -> None:
    assert parse_basic_pitch_param_assignments(
        ["onset_threshold=0.45", "melodia_trick=false"]
    ) == {"onset_threshold": 0.45, "melodia_trick": False}
    with pytest.raises(ValueError, match="duplicate"):
        parse_basic_pitch_param_assignments(
            ["frame_threshold=0.2", "frame_threshold=0.3"]
        )

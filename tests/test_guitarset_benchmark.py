from __future__ import annotations

import json
import wave
from array import array
from io import BytesIO
from pathlib import Path

import pytest

from abachiwave.evaluations.audio_to_midi import (
    load_benchmark_manifest,
    parse_timed_midi_notes,
)
from abachiwave.evaluations.guitarset_benchmark import (
    GuitarSetNote,
    build_guitarset_reference_midi,
    build_selected_guitarset_sample,
    parse_guitarset_jams,
    parse_guitarset_stem,
    validate_guitarset_zenodo_record,
    write_guitarset_subset,
)


def test_parse_guitarset_stem_exposes_category_and_members() -> None:
    solo = parse_guitarset_stem("03_Rock2-142-D_solo")
    assert solo.performer == 3
    assert solo.tempo_bpm == 142
    assert solo.category == "monophonic_instrumental_phrase"
    assert solo.audio_member == "03_Rock2-142-D_solo_mic.wav"

    comp = parse_guitarset_stem("00_SS1-100-C#_comp")
    assert comp.key == "C#"
    assert comp.sample_id == "00_SS1-100-Csharp_comp"
    assert comp.category == "polyphonic_instrumental_phrase"


@pytest.mark.parametrize(
    "stem",
    ["bad", "06_Rock2-142-D_solo", "03_Rock2-0-D_comp"],
)
def test_parse_guitarset_stem_rejects_invalid_metadata(stem: str) -> None:
    with pytest.raises(ValueError):
        parse_guitarset_stem(stem)


def test_validate_guitarset_zenodo_record_pins_license_and_artifacts() -> None:
    payload = {
        "id": 3_371_780,
        "metadata": {"version": "1.1.0", "license": {"id": "cc-by-4.0"}},
        "files": [
            {
                "key": "annotation.zip",
                "size": 39_132_574,
                "checksum": "md5:b39b78e63d3446f2e54ddb7a54df9b10",
                "links": {"self": "https://zenodo.org/annotation.zip"},
            },
            {
                "key": "audio_mono-mic.zip",
                "size": 656_927_981,
                "checksum": "md5:275966d6610ac34999b58426beb119c3",
                "links": {"self": "https://zenodo.org/audio.zip"},
            },
        ],
    }

    artifacts = validate_guitarset_zenodo_record(payload)

    assert artifacts["annotation.zip"].size == 39_132_574
    assert artifacts["audio_mono-mic.zip"].checksum.startswith("md5:")

    bad_payload = {
        **payload,
        "metadata": {"version": "1.1.0", "license": {"id": "cc-by-nc-4.0"}},
    }
    with pytest.raises(ValueError, match="version or license"):
        validate_guitarset_zenodo_record(bad_payload)


def test_parse_guitarset_jams_flattens_string_annotations() -> None:
    duration, notes = parse_guitarset_jams(
        _jams_bytes(
            2.0,
            [
                [{"time": 0.1, "duration": 0.4, "value": 60.1}],
                [{"time": 0.2, "duration": 0.5, "value": 64.8}],
            ],
        )
    )

    assert duration == 2.0
    assert [(note.pitch, note.onset_seconds, note.offset_seconds) for note in notes] == [
        (60, 0.1, 0.5),
        (65, 0.2, 0.7),
    ]


def test_build_guitarset_reference_midi_preserves_polyphonic_timing() -> None:
    reference = build_guitarset_reference_midi(
        (
            GuitarSetNote(0.1, 0.5, 60),
            GuitarSetNote(0.1, 0.7, 64),
        )
    )

    notes = parse_timed_midi_notes(reference)
    assert [(note.pitch, note.velocity) for note in notes] == [(60, 100), (64, 100)]
    assert notes[0].onset_seconds == pytest.approx(0.1)
    assert notes[0].offset_seconds == pytest.approx(0.5)
    assert notes[1].offset_seconds == pytest.approx(0.7)


def test_write_guitarset_subset_emits_product_wav_and_verified_lineage(
    tmp_path: Path,
) -> None:
    metadata = parse_guitarset_stem("03_Rock2-142-D_solo")
    audio = _wav_bytes(duration_seconds=1.0)
    annotation = _jams_bytes(
        1.0,
        [[{"time": 0.1, "duration": 0.4, "value": 60.1}]],
    )
    sample = build_selected_guitarset_sample(
        metadata,
        source_audio_wav=audio,
        source_annotation_jams=annotation,
    )

    manifest_path = write_guitarset_subset(
        tmp_path / "dataset",
        samples=[sample],
        source_url="https://zenodo.org/records/3371780",
        source_artifact_checksums={
            "annotation.zip": "md5:b39b78e63d3446f2e54ddb7a54df9b10",
            "audio_mono-mic.zip": "md5:275966d6610ac34999b58426beb119c3",
        },
    )
    manifest = load_benchmark_manifest(manifest_path)

    with wave.open(str(manifest.samples[0].audio_path), "rb") as reader:
        assert reader.getframerate() == 48_000
        assert reader.getnchannels() == 2
        assert reader.getsampwidth() == 2
    assert manifest.samples[0].source_annotation_member == metadata.annotation_member
    assert manifest.samples[0].source_annotation_sha256 is not None
    assert len(parse_timed_midi_notes(manifest.samples[0].reference_midi_path.read_bytes())) == 1


def test_parse_guitarset_jams_rejects_note_outside_audio() -> None:
    with pytest.raises(ValueError, match="outside file duration"):
        parse_guitarset_jams(
            _jams_bytes(
                1.0,
                [[{"time": 0.9, "duration": 0.2, "value": 60.0}]],
            )
        )


def _jams_bytes(duration: float, string_notes: list[list[dict[str, float]]]) -> bytes:
    payload = {
        "file_metadata": {"duration": duration},
        "annotations": [
            {"namespace": "note_midi", "data": notes} for notes in string_notes
        ],
    }
    return json.dumps(payload).encode()


def _wav_bytes(*, duration_seconds: float) -> bytes:
    frames = array("h", [0] * round(44_100 * duration_seconds))
    output = BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(44_100)
        writer.writeframes(frames.tobytes())
    return output.getvalue()

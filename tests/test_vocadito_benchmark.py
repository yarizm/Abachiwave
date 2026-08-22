from __future__ import annotations

import wave
from array import array
from io import BytesIO
from pathlib import Path

import pytest

from abachiwave.evaluations.audio_to_midi import (
    load_benchmark_manifest,
    parse_timed_midi_notes,
)
from abachiwave.evaluations.vocadito_benchmark import (
    VOCADITO_ARTIFACT_CHECKSUM,
    VocaditoTrackMetadata,
    build_selected_vocadito_sample,
    build_vocadito_reference_midi,
    parse_vocadito_metadata,
    parse_vocadito_notes,
    validate_vocadito_zenodo_record,
    write_vocadito_dataset,
)


def test_validate_vocadito_record_pins_license_and_archive() -> None:
    payload = {
        "id": 5_557_945,
        "metadata": {"license": {"id": "cc-by-4.0"}},
        "files": [
            {
                "key": "vocadito.zip",
                "size": 58_491_239,
                "checksum": VOCADITO_ARTIFACT_CHECKSUM,
                "links": {"self": "https://zenodo.org/vocadito.zip"},
            }
        ],
    }

    artifact = validate_vocadito_zenodo_record(payload)

    assert artifact.size == 58_491_239
    assert artifact.checksum == VOCADITO_ARTIFACT_CHECKSUM
    bad_payload = {**payload, "metadata": {"license": {"id": "cc-by-nc-4.0"}}}
    with pytest.raises(ValueError, match="license"):
        validate_vocadito_zenodo_record(bad_payload)


def test_parse_vocadito_metadata_requires_complete_unique_catalog() -> None:
    rows = ["track_id,singer_id,average_pitch,language"]
    rows.extend(f"{track_id},S{track_id},60,English" for track_id in range(1, 41))

    tracks = parse_vocadito_metadata(("\n".join(rows) + "\n").encode())

    assert len(tracks) == 40
    assert tracks[0].sample_id == "vocadito_01"
    assert tracks[-1].audio_member == "Audio/vocadito_40.wav"

    with pytest.raises(ValueError, match="tracks 1-40"):
        parse_vocadito_metadata(("\n".join(rows[:-1]) + "\n").encode())


def test_parse_vocadito_notes_converts_hz_to_midi() -> None:
    notes = parse_vocadito_notes(
        b"0.1,440.0,0.4\n0.6,261.625565,0.3\n",
        audio_duration_seconds=1.0,
    )

    assert [note.pitch for note in notes] == [69, 60]
    assert [note.onset_seconds for note in notes] == pytest.approx([0.1, 0.6])
    assert [note.offset_seconds for note in notes] == pytest.approx([0.5, 0.9])
    parsed_midi = parse_timed_midi_notes(build_vocadito_reference_midi(notes))
    assert [(note.pitch, note.velocity) for note in parsed_midi] == [(69, 100), (60, 100)]


def test_parse_vocadito_notes_rejects_out_of_bounds_note() -> None:
    with pytest.raises(ValueError, match="outside audio duration"):
        parse_vocadito_notes(
            b"0.9,440.0,0.2\n",
            audio_duration_seconds=1.0,
        )


def test_write_vocadito_dataset_preserves_dual_reference_lineage(tmp_path: Path) -> None:
    audio = _wav_bytes(duration_seconds=1.0)
    samples = []
    for track_id in range(1, 41):
        metadata = VocaditoTrackMetadata(track_id, f"S{track_id}", 60, "English")
        samples.append(
            build_selected_vocadito_sample(
                metadata,
                source_audio_wav=audio,
                source_annotator_1_csv=b"0.1,440.0,0.4\n",
                source_annotator_2_csv=b"0.1,440.0,0.5\n",
            )
        )

    manifest_path = write_vocadito_dataset(
        tmp_path / "dataset",
        samples=samples,
        source_url="https://zenodo.org/records/5557945",
        source_artifact_checksum=VOCADITO_ARTIFACT_CHECKSUM,
    )
    manifest = load_benchmark_manifest(manifest_path)

    assert manifest.reference_selection_policy == "best_onset_pitch_offset_f1"
    assert len(manifest.samples) == 40
    first = manifest.samples[0]
    assert first.reference_id == "annotator_1"
    assert first.alternative_references[0].id == "annotator_2"
    assert first.alternative_references[0].source_annotation_sha256 is not None
    assert first.attributes["language"] == "English"
    with wave.open(str(first.audio_path), "rb") as reader:
        assert reader.getframerate() == 48_000
        assert reader.getnchannels() == 2


def _wav_bytes(*, duration_seconds: float) -> bytes:
    frames = array("h", [0] * round(44_100 * duration_seconds))
    output = BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(44_100)
        writer.writeframes(frames.tobytes())
    return output.getvalue()

from __future__ import annotations

import tarfile
import wave
from array import array
from io import BytesIO
from pathlib import Path

import pytest

from abachiwave.evaluations.audio_to_midi import load_benchmark_manifest
from abachiwave.evaluations.nsynth_benchmark import (
    NsynthNoteMetadata,
    SelectedNsynthSample,
    parse_nsynth_filename,
    select_nsynth_samples,
    write_nsynth_subset,
)


def test_select_nsynth_samples_fills_unique_pitch_family_quotas() -> None:
    archive_bytes = _archive(
        [
            "nsynth-test/audio/guitar_acoustic_001-060-050.wav",
            "nsynth-test/audio/guitar_acoustic_001-060-075.wav",
            "nsynth-test/audio/guitar_electronic_001-061-050.wav",
            "nsynth-test/audio/guitar_acoustic_001-062-050.wav",
            "nsynth-test/audio/vocal_acoustic_000-064-075.wav",
            "nsynth-test/audio/vocal_acoustic_000-067-075.wav",
        ]
    )
    with tarfile.open(fileobj=BytesIO(archive_bytes), mode="r|gz") as archive:
        samples, inspected = select_nsynth_samples(
            archive,
            families=("guitar", "vocal"),
            samples_per_family=2,
            minimum_pitch=48,
            maximum_pitch=84,
        )

    assert inspected == 6
    assert [sample.metadata.pitch for sample in samples] == [60, 62, 64, 67]


def test_select_nsynth_samples_rejects_incomplete_quota() -> None:
    archive_bytes = _archive(["nsynth-test/audio/guitar_acoustic_001-060-050.wav"])
    with (
        tarfile.open(fileobj=BytesIO(archive_bytes), mode="r|gz") as archive,
        pytest.raises(RuntimeError, match="vocal missing 1"),
    ):
        select_nsynth_samples(
            archive,
            families=("guitar", "vocal"),
            samples_per_family=1,
            minimum_pitch=48,
            maximum_pitch=84,
        )


def test_write_nsynth_subset_emits_verified_manifest(tmp_path: Path) -> None:
    source_wav = _wav_bytes()
    sample = SelectedNsynthSample(
        source_member="nsynth-test/audio/vocal_acoustic_000-064-075.wav",
        metadata=_metadata("vocal_acoustic_000-064-075.wav"),
        source_wav=source_wav,
    )
    output = tmp_path / "dataset"

    manifest_path = write_nsynth_subset(
        output,
        samples=[sample],
        archive_url="https://example.test/nsynth.tar.gz",
        archive_etag="archive-etag",
    )
    manifest = load_benchmark_manifest(manifest_path)

    assert manifest.dataset.license == "CC BY 4.0"
    assert manifest.dataset.synthetic is False
    assert manifest.samples[0].source_member == sample.source_member
    assert manifest.samples[0].audio_path.is_file()
    assert manifest.samples[0].reference_midi_path.is_file()


def test_write_nsynth_subset_refuses_nonempty_output(tmp_path: Path) -> None:
    output = tmp_path / "dataset"
    output.mkdir()
    (output / "keep.txt").write_text("user data", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not empty"):
        write_nsynth_subset(
            output,
            samples=[],
            archive_url="https://example.test/nsynth.tar.gz",
            archive_etag="archive-etag",
        )

    assert (output / "keep.txt").read_text(encoding="utf-8") == "user data"


def _metadata(filename: str) -> NsynthNoteMetadata:
    return parse_nsynth_filename(filename)


def _archive(names: list[str]) -> bytes:
    output = BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name in names:
            data = _wav_bytes()
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, BytesIO(data))
    return output.getvalue()


def _wav_bytes() -> bytes:
    frames = array("h", [0] * 160)
    output = BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16_000)
        writer.writeframes(frames.tobytes())
    return output.getvalue()

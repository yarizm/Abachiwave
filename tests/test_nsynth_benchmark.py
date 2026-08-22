from __future__ import annotations

import math
import wave
from array import array
from io import BytesIO

import pytest

from abachiwave.evaluations.audio_to_midi import parse_timed_midi_notes
from abachiwave.evaluations.nsynth_benchmark import (
    build_nsynth_reference_midi,
    normalize_nsynth_wav,
    parse_nsynth_filename,
)


def test_parse_nsynth_filename_exposes_reference_metadata() -> None:
    metadata = parse_nsynth_filename("vocal_acoustic_000-064-075.wav")

    assert metadata.family == "vocal"
    assert metadata.source == "acoustic"
    assert metadata.instrument == 0
    assert metadata.pitch == 64
    assert metadata.velocity == 75
    assert metadata.category == "vocal"
    assert metadata.sample_id == "vocal_acoustic_000-064-075"

    instrumental = parse_nsynth_filename("guitar_acoustic_010-097-025.wav")
    assert instrumental.category == "monophonic_instrumental"


@pytest.mark.parametrize(
    "filename",
    [
        "not-an-nsynth-file.wav",
        "vocal_acoustic_000-128-075.wav",
        "vocal_acoustic_000-064-000.wav",
    ],
)
def test_parse_nsynth_filename_rejects_invalid_metadata(filename: str) -> None:
    with pytest.raises(ValueError):
        parse_nsynth_filename(filename)


def test_normalize_nsynth_wav_resamples_to_product_format() -> None:
    source = _mono_pcm_wav(sample_rate=16_000, duration_seconds=0.25)

    normalized = normalize_nsynth_wav(source)

    with wave.open(BytesIO(normalized), "rb") as reader:
        assert reader.getnchannels() == 2
        assert reader.getsampwidth() == 2
        assert reader.getframerate() == 48_000
        assert reader.getnframes() == 12_000


def test_build_nsynth_reference_midi_uses_filename_note_contract() -> None:
    metadata = parse_nsynth_filename("reed_acoustic_023-050-025.wav")

    notes = parse_timed_midi_notes(build_nsynth_reference_midi(metadata))

    assert len(notes) == 1
    assert notes[0].pitch == 50
    assert notes[0].velocity == 25
    assert notes[0].onset_seconds == pytest.approx(0)
    assert notes[0].offset_seconds == pytest.approx(3.0)


def test_normalize_nsynth_wav_rejects_non_mono_input() -> None:
    with pytest.raises(ValueError, match="mono 16-bit"):
        normalize_nsynth_wav(
            _mono_pcm_wav(sample_rate=16_000, duration_seconds=0.01, channels=2)
        )


def _mono_pcm_wav(
    *,
    sample_rate: int,
    duration_seconds: float,
    channels: int = 1,
) -> bytes:
    samples = array(
        "h",
        (
            round(8_000 * math.sin(2 * math.pi * 440 * index / sample_rate))
            for index in range(round(sample_rate * duration_seconds))
            for _channel in range(channels)
        ),
    )
    output = BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(samples.tobytes())
    return output.getvalue()

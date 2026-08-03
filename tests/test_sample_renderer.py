from __future__ import annotations

import wave
from array import array
from importlib import resources
from io import BytesIO

import pytest

from abachiwave.services.sample_renderer import SAMPLE_RATE, _load_sample, render_sample_demo


def _samples_to_wav(samples: array[int]) -> bytes:
    buffer = BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(SAMPLE_RATE)
        writer.writeframes(
            b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples)
        )
    return buffer.getvalue()


@pytest.mark.parametrize("duration_seconds", [1, 2])
def test_render_produces_expected_length(duration_seconds: int) -> None:
    samples = render_sample_demo(
        bpm=120,
        beats_per_bar=4,
        chord_cycle=["C", "Am", "F", "G"],
        song_key=None,
        duration_seconds=duration_seconds,
    )
    assert len(samples) == SAMPLE_RATE * duration_seconds


def test_render_is_16bit_wav_compatible() -> None:
    samples = render_sample_demo(
        bpm=120,
        beats_per_bar=4,
        chord_cycle=["C"],
        song_key=None,
        duration_seconds=1,
    )
    wav_bytes = _samples_to_wav(samples)
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"
    with wave.open(BytesIO(wav_bytes), "rb") as reader:
        assert reader.getsampwidth() == 2
        assert reader.getnchannels() == 1
        assert reader.getframerate() == SAMPLE_RATE


def test_render_has_energy_above_silence() -> None:
    samples = render_sample_demo(
        bpm=120,
        beats_per_bar=4,
        chord_cycle=["C"],
        song_key=None,
        duration_seconds=1,
    )
    peak = max(abs(sample) for sample in samples)
    assert peak > 1000


def test_load_sample_resampled_to_renderer_rate() -> None:
    package_dir = resources.files("abachiwave.services.audio_assets")
    with wave.open(BytesIO(package_dir.joinpath("kick.wav").read_bytes()), "rb") as reader:
        rate = reader.getframerate()
        frame_count = reader.getnframes()
    resampled = _load_sample("kick")
    assert rate == 44_100
    assert len(resampled) == int(frame_count / (rate / SAMPLE_RATE))
    assert resampled.itemsize == 2


import wave
from io import BytesIO
from math import pi, sin

import pytest

from abachiwave.services.reference_analysis_provider import (
    LocalDeterministicAudioAnalysisProvider,
    ReferenceAnalysisRequest,
)


def test_local_reference_analysis_is_stable_and_source_relative() -> None:
    provider = LocalDeterministicAudioAnalysisProvider()

    result = provider.analyze(
        ReferenceAnalysisRequest(
            audio_bytes=_sine_wav(frequency=440, duration_seconds=2),
            filename="a440.wav",
            source_start_seconds=20,
            source_end_seconds=22,
            provider_params=provider.default_params(),
        )
    )

    assert result.tempo_bpm == 120
    assert result.key_candidate.value == "A major"
    assert result.key_candidate.confidence > 0
    assert result.pitch_range.low_midi == pytest.approx(69, abs=1)
    assert result.pitch_range.high_midi == pytest.approx(69, abs=1)
    assert result.loudness.integrated_dbfs < 0
    assert result.loudness.peak_dbfs < 0
    assert len(result.energy_curve) == 24
    assert all(20 <= point.time_seconds <= 22 for point in result.energy_curve)
    assert result.structure_sections[0].start_seconds == 20
    assert result.structure_sections[-1].end_seconds == 22
    assert result.chord_candidates[0].symbol == "A"
    assert result.confidence["overall"] > 0


def _sine_wav(*, frequency: float, duration_seconds: float) -> bytes:
    sample_rate = 8_000
    buffer = BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        for index in range(round(sample_rate * duration_seconds)):
            sample = round(12_000 * sin(2 * pi * frequency * index / sample_rate))
            writer.writeframesraw(sample.to_bytes(2, "little", signed=True))
    return buffer.getvalue()

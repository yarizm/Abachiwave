from __future__ import annotations

import wave
from io import BytesIO

import pytest

from abachiwave.core.config import Settings
from abachiwave.schemas.song_specs import SongSpecData
from abachiwave.services.demo_provider import (
    DemoGenerationRequest,
    LocalDeterministicWavProvider,
    UnknownDemoProviderError,
    build_demo_provider,
)


def _provider_request(duration_seconds: int = 1) -> DemoGenerationRequest:
    return DemoGenerationRequest(
        song_spec=SongSpecData(
            theme="test",
            genre=["rock"],
            language="en",
            tempo_bpm=120,
            key="C",
            time_signature="4/4",
            target_duration_seconds=30,
            mood_curve={"verse": "0.5", "chorus": "1.0"},
            song_structure=["verse", "chorus"],
            structure_sections=[],
        ),
        lyric_sections=[],
        chord_sections=[],
        duration_seconds=duration_seconds,
        provider_params={},
    )


def test_local_provider_generates_wav() -> None:
    provider = LocalDeterministicWavProvider(default_duration_seconds=1)
    audio = provider.generate_demo(_provider_request())
    assert audio.content_type == "audio/wav"
    assert audio.provider_name == "local_deterministic_wav"
    assert audio.data[:4] == b"RIFF"
    assert audio.data[8:12] == b"WAVE"


def test_local_provider_honors_duration_clamp() -> None:
    provider = LocalDeterministicWavProvider(default_duration_seconds=2)
    audio = provider.generate_demo(_provider_request(duration_seconds=120))
    assert audio.duration_seconds <= 60
    with wave.open(BytesIO(audio.data), "rb") as reader:
        assert reader.getnframes() == 22_050 * audio.duration_seconds


def test_build_demo_provider_returns_default_for_known_name() -> None:
    settings = Settings(_env_file=None, DEMO_PROVIDER_NAME="local_deterministic_wav")
    provider = build_demo_provider(settings)
    assert isinstance(provider, LocalDeterministicWavProvider)


def test_build_demo_provider_raises_for_unknown_name() -> None:
    settings = Settings(_env_file=None, DEMO_PROVIDER_NAME="does_not_exist")
    with pytest.raises(UnknownDemoProviderError):
        build_demo_provider(settings)

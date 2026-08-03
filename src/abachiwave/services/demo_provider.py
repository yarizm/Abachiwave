import sys
import wave
from array import array
from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

from abachiwave.schemas.composition import ChordSection, LyricSection
from abachiwave.schemas.song_specs import SongSpecData
from abachiwave.services.sample_renderer import render_sample_demo

WAV_CONTENT_TYPE = "audio/wav"
DEFAULT_DEMO_SECONDS = 30
MAX_DEMO_SECONDS = 60
SAMPLE_RATE = 22_050


@dataclass(frozen=True)
class DemoGenerationRequest:
    song_spec: SongSpecData
    lyric_sections: list[LyricSection]
    chord_sections: list[ChordSection]
    duration_seconds: int
    provider_params: dict[str, object]


@dataclass(frozen=True)
class GeneratedAudio:
    data: bytes
    duration_seconds: int
    content_type: str
    provider_name: str
    provider_version: str
    provider_params: dict[str, object]


class MusicGenerationProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    def default_params(self) -> dict[str, object]: ...

    def generate_demo(self, request: DemoGenerationRequest) -> GeneratedAudio: ...


class LocalDeterministicWavProvider:
    name = "local_deterministic_wav"
    version = "0.1.0"

    def __init__(self, *, default_duration_seconds: int = DEFAULT_DEMO_SECONDS) -> None:
        self._default_duration_seconds = _clamp_duration(default_duration_seconds)

    def default_params(self) -> dict[str, object]:
        return {
            "duration_seconds": self._default_duration_seconds,
            "sample_rate": SAMPLE_RATE,
            "max_duration_seconds": MAX_DEMO_SECONDS,
        }

    def generate_demo(self, request: DemoGenerationRequest) -> GeneratedAudio:
        duration_seconds = _duration_from_request(request, self._default_duration_seconds)
        bpm = request.song_spec.tempo_bpm or 120
        time_signature_beats = _beats_per_bar(request.song_spec.time_signature)
        chord_cycle = _chord_cycle(request.chord_sections)
        samples = render_sample_demo(
            bpm=bpm,
            beats_per_bar=time_signature_beats,
            chord_cycle=chord_cycle,
            song_key=request.song_spec.key,
            duration_seconds=duration_seconds,
        )
        params = {
            **self.default_params(),
            **request.provider_params,
            "duration_seconds": duration_seconds,
            "bpm": bpm,
        }
        return GeneratedAudio(
            data=_wav_bytes(samples),
            duration_seconds=duration_seconds,
            content_type=WAV_CONTENT_TYPE,
            provider_name=self.name,
            provider_version=self.version,
            provider_params=params,
        )


def _wav_bytes(samples: array[int]) -> bytes:
    little_endian_samples = array("h", samples)
    if sys.byteorder != "little":
        little_endian_samples.byteswap()
    buffer = BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(little_endian_samples.tobytes())
    return buffer.getvalue()


def _duration_from_request(
    request: DemoGenerationRequest,
    default_duration_seconds: int,
) -> int:
    configured = request.provider_params.get("duration_seconds")
    if isinstance(configured, int):
        return _clamp_duration(configured)
    return _clamp_duration(min(request.duration_seconds, default_duration_seconds))


def _clamp_duration(duration_seconds: int) -> int:
    return max(1, min(MAX_DEMO_SECONDS, duration_seconds))


def _beats_per_bar(time_signature: str | None) -> int:
    if not time_signature:
        return 4
    numerator = time_signature.split("/", maxsplit=1)[0]
    try:
        return max(1, min(12, int(numerator)))
    except ValueError:
        return 4


def _chord_cycle(chord_sections: list[ChordSection]) -> list[str]:
    chords: list[str] = []
    for section in chord_sections:
        chords.extend(section.chords[: max(1, section.bars)])
    return chords or ["C"]

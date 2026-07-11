import math
import sys
import wave
from array import array
from dataclasses import dataclass
from io import BytesIO
from typing import Protocol

from abachiwave.schemas.composition import ChordSection, LyricSection
from abachiwave.schemas.song_specs import SongSpecData

WAV_CONTENT_TYPE = "audio/wav"
DEFAULT_DEMO_SECONDS = 30
MAX_DEMO_SECONDS = 60
SAMPLE_RATE = 22_050
_TAU = math.tau
_NOTE_TO_SEMITONE = {
    "C": 0,
    "C#": 1,
    "DB": 1,
    "D": 2,
    "D#": 3,
    "EB": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "GB": 6,
    "G": 7,
    "G#": 8,
    "AB": 8,
    "A": 9,
    "A#": 10,
    "BB": 10,
    "B": 11,
}
_MAJOR_SCALE = (0, 2, 4, 7, 9, 7, 4, 2)
_MINOR_SCALE = (0, 3, 5, 7, 10, 7, 5, 3)


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
        samples = _render_samples(
            duration_seconds=duration_seconds,
            bpm=bpm,
            beats_per_bar=time_signature_beats,
            chord_cycle=chord_cycle,
            song_key=request.song_spec.key,
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


def _render_samples(
    *,
    duration_seconds: int,
    bpm: int,
    beats_per_bar: int,
    chord_cycle: list[str],
    song_key: str | None,
) -> array[int]:
    total_samples = SAMPLE_RATE * duration_seconds
    beat_seconds = 60.0 / bpm
    bar_seconds = beat_seconds * beats_per_bar
    samples = array("h")
    scale = _MINOR_SCALE if song_key and "minor" in song_key.lower() else _MAJOR_SCALE
    for sample_index in range(total_samples):
        time = sample_index / SAMPLE_RATE
        bar_index = int(time / bar_seconds) % len(chord_cycle)
        chord = chord_cycle[bar_index]
        root = _root_frequency(chord)
        third = root * (2 ** ((_third_interval(chord)) / 12))
        fifth = root * (2 ** (7 / 12))
        beat_phase = time % beat_seconds
        bar_phase = time % bar_seconds
        melody_step = int(time / (beat_seconds / 2)) % len(scale)
        melody_frequency = root * 2 * (2 ** (scale[melody_step] / 12))

        click = _click_sample(time, beat_phase)
        bass = _enveloped_sine(root / 2, time, beat_phase, 0.18) * 0.28
        pad = (
            math.sin(_TAU * root * time)
            + math.sin(_TAU * third * time)
            + math.sin(_TAU * fifth * time)
        ) * 0.09
        melody = _enveloped_sine(melody_frequency, time, beat_phase, beat_seconds * 0.45) * 0.16
        downbeat = _enveloped_sine(root, time, bar_phase, 0.22) * 0.16
        value = _soft_clip(click + bass + pad + melody + downbeat)
        samples.append(int(value * 32767))
    return samples


def _click_sample(time: float, beat_phase: float) -> float:
    if beat_phase > 0.035:
        return 0.0
    envelope = 1.0 - (beat_phase / 0.035)
    return math.sin(_TAU * 1800 * time) * envelope * 0.22


def _enveloped_sine(frequency: float, time: float, phase: float, length: float) -> float:
    if phase > length:
        return 0.0
    envelope = max(0.0, 1.0 - (phase / length))
    return math.sin(_TAU * frequency * time) * envelope


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


def _root_frequency(chord: str) -> float:
    root = _root_name(chord)
    semitone = _NOTE_TO_SEMITONE.get(root, 0)
    midi_note = 48 + semitone
    return 440.0 * (2 ** ((midi_note - 69) / 12))


def _root_name(chord: str) -> str:
    cleaned = chord.strip().upper()
    if not cleaned:
        return "C"
    if len(cleaned) >= 2 and cleaned[1] in {"#", "B"}:
        return cleaned[:2]
    return cleaned[0]


def _third_interval(chord: str) -> int:
    cleaned = chord.strip()
    root = _root_name(cleaned)
    suffix = cleaned[len(root) :]
    return 3 if suffix.startswith("m") and not suffix.startswith("maj") else 4


def _soft_clip(value: float) -> float:
    return max(-0.95, min(0.95, math.tanh(value * 1.15)))

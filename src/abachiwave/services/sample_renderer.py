"""Sample-driven demo renderer.

Renders a mono 16-bit 22.05 kHz demo track from the packaged CC0 drum samples
(``audio_assets``) plus dependency-free synthesized bass and chord pads.
"""

from __future__ import annotations

import math
import wave
from array import array
from functools import cache
from importlib import resources
from io import BytesIO

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


@cache
def _load_sample(name: str) -> array[int]:
    """Load a packaged CC0 WAV sample as mono 16-bit ints at ``SAMPLE_RATE``."""
    resource = resources.files("abachiwave.services.audio_assets").joinpath(f"{name}.wav")
    raw = resource.read_bytes()
    with wave.open(BytesIO(raw), "rb") as reader:
        sample_width = reader.getsampwidth()
        channels = reader.getnchannels()
        rate = reader.getframerate()
        frames = reader.readframes(reader.getnframes())
    samples: array[int] = array("h")
    frame_size = sample_width * channels
    for offset in range(0, len(frames) - frame_size + 1, frame_size):
        value = int.from_bytes(frames[offset : offset + sample_width], "little", signed=True)
        for channel in range(1, channels):
            start = offset + channel * sample_width
            value += int.from_bytes(frames[start : start + sample_width], "little", signed=True)
        samples.append(value // channels)
    return _resample_to_output_rate(samples, rate)


def _resample_to_output_rate(samples: array[int], rate: int) -> array[int]:
    """Linearly interpolate a mono buffer to ``SAMPLE_RATE`` (no-op when matched)."""
    if rate == SAMPLE_RATE or len(samples) < 2:
        return samples
    step = rate / SAMPLE_RATE
    out: array[int] = array("h")
    for i in range(int(len(samples) / step)):
        pos = i * step
        index = int(pos)
        frac = pos - index
        if index + 1 < len(samples):
            value = samples[index] * (1 - frac) + samples[index + 1] * frac
        else:
            value = samples[index]
        out.append(int(value))
    return out


def _place(samples: array[int], dst: array[int], at_sample: int, gain: float = 1.0) -> None:
    for i, sample in enumerate(samples):
        position = at_sample + i
        if 0 <= position < len(dst):
            dst[position] = max(-32768, min(32767, dst[position] + int(sample * gain)))


def _root_name(chord: str) -> str:
    cleaned = chord.strip().upper()
    if len(cleaned) >= 2 and cleaned[1] in {"#", "B"}:
        return cleaned[:2]
    return cleaned[:1]


def _root_frequency(chord: str) -> float:
    root = _root_name(chord)
    semitone = _NOTE_TO_SEMITONE.get(root, 0)
    midi_note = 48 + semitone
    return 440.0 * (2 ** ((midi_note - 69) / 12))


def _third_interval(chord: str) -> int:
    cleaned = chord.strip()
    root = _root_name(cleaned)
    suffix = cleaned[len(root) :]
    return 3 if suffix.startswith("m") and not suffix.startswith("maj") else 4


def render_sample_demo(
    *,
    bpm: int,
    beats_per_bar: int,
    chord_cycle: list[str],
    song_key: str | None,
    duration_seconds: int,
) -> array[int]:
    """Render a mono 16-bit demo track from drum samples and synthesized harmony."""
    total_samples = SAMPLE_RATE * duration_seconds
    out: array[int] = array("h", [0]) * total_samples
    beat_samples = int(SAMPLE_RATE * 60.0 / bpm)
    bar_samples = beat_samples * beats_per_bar

    kick = _load_sample("kick")
    snare = _load_sample("snare")
    closed_hat = _load_sample("closed_hat")
    open_hat = _load_sample("open_hat")

    num_bars = max(1, duration_seconds * bpm // (beats_per_bar * 60) + 1)
    for bar in range(num_bars):
        bar_start = bar * bar_samples
        # Drums: kick on 1 & 3, snare on 2 & 4, closed hat on the beat, open hat on offbeats.
        for beat_in_bar in range(beats_per_bar):
            beat_start = bar_start + beat_in_bar * beat_samples
            if beat_in_bar == 0 or beat_in_bar == beats_per_bar // 2:
                _place(kick, out, beat_start, gain=0.9)
            if beat_in_bar in {1, 3}:
                _place(snare, out, beat_start, gain=0.7)
            _place(closed_hat, out, beat_start, gain=0.4)
            _place(open_hat, out, beat_start + beat_samples // 2, gain=0.25)

        # Harmony: root bass + triad pad per chord in the cycle.
        fallback = _root_name(song_key) if song_key else "C"
        chord = chord_cycle[bar % len(chord_cycle)] if chord_cycle else fallback
        root = _root_frequency(chord)
        third = root * (2 ** (_third_interval(chord) / 12))
        fifth = root * (2 ** (7 / 12))
        _place(_bass_tone(root / 2, bar_samples), out, bar_start, gain=0.28)
        _place(_pad_tone(root, third, fifth, bar_samples), out, bar_start, gain=0.09)

    return out


def _bass_tone(frequency: float, length: int) -> array[int]:
    out: array[int] = array("h")
    for i in range(length):
        value = math.sin(_TAU * frequency * i / SAMPLE_RATE)
        env = max(0.0, 1.0 - i / max(1, length))
        out.append(int(value * env * 32767 * 0.5))
    return out


def _pad_tone(root: float, third: float, fifth: float, length: int) -> array[int]:
    out: array[int] = array("h")
    for i in range(length):
        value = (
            math.sin(_TAU * root * i / SAMPLE_RATE)
            + math.sin(_TAU * third * i / SAMPLE_RATE)
            + math.sin(_TAU * fifth * i / SAMPLE_RATE)
        )
        out.append(int(value / 3 * 32767 * 0.3))
    return out

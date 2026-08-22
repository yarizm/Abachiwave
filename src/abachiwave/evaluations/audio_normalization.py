from __future__ import annotations

import sys
import wave
from array import array
from io import BytesIO

TARGET_SAMPLE_RATE = 48_000
TARGET_CHANNELS = 2


def normalize_mono_pcm16_wav(data: bytes, *, source_label: str) -> bytes:
    """Normalize a mono PCM16 fixture to the product derivative WAV format."""
    with wave.open(BytesIO(data), "rb") as reader:
        if reader.getnchannels() != 1 or reader.getsampwidth() != 2:
            raise ValueError(f"{source_label} benchmark input must be mono 16-bit PCM WAV")
        source_rate = reader.getframerate()
        if source_rate <= 0:
            raise ValueError(f"{source_label} benchmark input has invalid sample rate")
        source_frames = reader.readframes(reader.getnframes())
    samples = array("h")
    samples.frombytes(source_frames)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        raise ValueError(f"{source_label} benchmark input is empty")

    target_count = round(len(samples) * TARGET_SAMPLE_RATE / source_rate)
    normalized_mono = array("h")
    for target_index in range(target_count):
        source_position = target_index * source_rate / TARGET_SAMPLE_RATE
        left_index = min(len(samples) - 1, int(source_position))
        right_index = min(len(samples) - 1, left_index + 1)
        fraction = source_position - left_index
        value = round(samples[left_index] * (1 - fraction) + samples[right_index] * fraction)
        normalized_mono.append(max(-32768, min(32767, value)))

    normalized_stereo = array("h")
    for value in normalized_mono:
        normalized_stereo.extend((value, value))
    if sys.byteorder != "little":
        normalized_stereo.byteswap()
    output = BytesIO()
    with wave.open(output, "wb") as writer:
        writer.setnchannels(TARGET_CHANNELS)
        writer.setsampwidth(2)
        writer.setframerate(TARGET_SAMPLE_RATE)
        writer.writeframes(normalized_stereo.tobytes())
    return output.getvalue()

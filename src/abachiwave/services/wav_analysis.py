import wave
from dataclasses import dataclass
from io import BytesIO

WAVEFORM_PEAK_COUNT = 80


class WavAnalysisError(ValueError):
    pass


@dataclass(frozen=True)
class WavMetadata:
    duration_seconds: float
    sample_rate: int
    channels: int
    waveform_peaks: list[float]


def analyze_wav_bytes(data: bytes) -> WavMetadata:
    try:
        with wave.open(BytesIO(data), "rb") as reader:
            channels = reader.getnchannels()
            sample_width = reader.getsampwidth()
            sample_rate = reader.getframerate()
            frame_count = reader.getnframes()
            frames = reader.readframes(frame_count)
    except wave.Error as exc:
        raise WavAnalysisError("Invalid WAV file") from exc
    if channels < 1 or sample_rate < 1 or sample_width not in {1, 2, 4}:
        raise WavAnalysisError("Unsupported WAV format")
    duration_seconds = round(frame_count / sample_rate, 3)
    return WavMetadata(
        duration_seconds=duration_seconds,
        sample_rate=sample_rate,
        channels=channels,
        waveform_peaks=_waveform_peaks(frames, sample_width, channels),
    )


def _waveform_peaks(frames: bytes, sample_width: int, channels: int) -> list[float]:
    frame_size = sample_width * channels
    frame_count = len(frames) // frame_size if frame_size else 0
    if frame_count == 0:
        return [0.0] * WAVEFORM_PEAK_COUNT
    bucket_size = max(1, frame_count // WAVEFORM_PEAK_COUNT)
    max_sample = 128 if sample_width == 1 else 2 ** (sample_width * 8 - 1)
    peaks: list[float] = []
    current_peak = 0
    current_count = 0
    for offset in range(0, len(frames) - frame_size + 1, frame_size):
        peak = 0
        for channel in range(channels):
            sample_offset = offset + channel * sample_width
            sample = _sample_value(frames[sample_offset : sample_offset + sample_width])
            peak = max(peak, abs(sample))
        current_peak = max(current_peak, peak)
        current_count += 1
        if current_count >= bucket_size:
            peaks.append(round(min(1.0, current_peak / max_sample), 4))
            current_peak = 0
            current_count = 0
    if current_count:
        peaks.append(round(min(1.0, current_peak / max_sample), 4))
    if len(peaks) < WAVEFORM_PEAK_COUNT:
        peaks.extend([0.0] * (WAVEFORM_PEAK_COUNT - len(peaks)))
    return peaks[:WAVEFORM_PEAK_COUNT]


def _sample_value(sample_bytes: bytes) -> int:
    if len(sample_bytes) == 1:
        return sample_bytes[0] - 128
    return int.from_bytes(sample_bytes, byteorder="little", signed=True)

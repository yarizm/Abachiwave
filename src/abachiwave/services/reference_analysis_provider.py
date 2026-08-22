import wave
from dataclasses import dataclass
from io import BytesIO
from math import log2, log10, sqrt
from typing import Protocol

from abachiwave.schemas.audio import (
    ReferenceChordCandidate,
    ReferenceEnergyPoint,
    ReferenceInstrumentTag,
    ReferenceKeyCandidate,
    ReferenceLoudness,
    ReferenceLoudnessPoint,
    ReferencePitchRange,
    ReferenceProductionFeature,
    ReferenceStructureSection,
    ReferenceTimeSignature,
)

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


class ReferenceAnalysisProviderError(ValueError):
    pass


@dataclass(frozen=True)
class ReferenceAnalysisRequest:
    audio_bytes: bytes
    filename: str
    source_start_seconds: float
    source_end_seconds: float
    provider_params: dict[str, object]


@dataclass(frozen=True)
class ReferenceAnalysisResult:
    tempo_bpm: float
    beat_grid: list[float]
    time_signature: ReferenceTimeSignature
    key_candidate: ReferenceKeyCandidate
    pitch_range: ReferencePitchRange
    loudness: ReferenceLoudness
    structure_sections: list[ReferenceStructureSection]
    chord_candidates: list[ReferenceChordCandidate]
    instrument_tags: list[ReferenceInstrumentTag]
    energy_curve: list[ReferenceEnergyPoint]
    production_features: list[ReferenceProductionFeature]
    confidence: dict[str, float]


class AudioAnalysisProvider(Protocol):
    name: str
    version: str

    def default_params(self) -> dict[str, object]: ...

    def analyze(self, request: ReferenceAnalysisRequest) -> ReferenceAnalysisResult: ...


@dataclass(frozen=True)
class _PcmSignal:
    samples: list[float]
    sample_rate: float
    channels: int
    duration_seconds: float


class LocalDeterministicAudioAnalysisProvider:
    name = "local_deterministic_reference_analysis"
    version = "1.0"

    def default_params(self) -> dict[str, object]:
        return {
            "tempo_min_bpm": 60,
            "tempo_max_bpm": 180,
            "analysis_sample_rate": 4000,
            "energy_points": 24,
            "algorithm": "pcm_energy_autocorrelation_v1",
        }

    def analyze(self, request: ReferenceAnalysisRequest) -> ReferenceAnalysisResult:
        signal = _decode_pcm_wav(
            request.audio_bytes,
            target_sample_rate=_int_param(request.provider_params, "analysis_sample_rate", 4000),
        )
        if signal.duration_seconds <= 0 or not signal.samples:
            raise ReferenceAnalysisProviderError("Reference audio contains no PCM samples")

        tempo_bpm, tempo_confidence, beat_offset = _estimate_tempo(
            signal,
            minimum_bpm=_int_param(request.provider_params, "tempo_min_bpm", 60),
            maximum_bpm=_int_param(request.provider_params, "tempo_max_bpm", 180),
        )
        energy_curve, loudness = _energy_and_loudness(
            signal,
            source_start_seconds=request.source_start_seconds,
            point_count=_int_param(request.provider_params, "energy_points", 24),
        )
        key_candidate, pitch_range = _estimate_key_and_pitch(signal)
        time_signature = ReferenceTimeSignature(value="4/4", confidence=0.35)
        beat_grid = _beat_grid(
            tempo_bpm,
            beat_offset,
            request.source_start_seconds,
            request.source_end_seconds,
        )
        structure_sections = _structure_candidates(
            request.source_start_seconds,
            request.source_end_seconds,
        )
        chord_candidates = _chord_candidates(
            key_candidate,
            request.source_start_seconds,
            request.source_end_seconds,
        )
        dynamic_confidence = 0.7 if signal.samples else 0.0
        instrument_tags = _instrument_tags(signal, pitch_range.confidence, tempo_confidence)
        production_features = _production_features(signal, loudness.dynamic_range_db)
        structure_confidence = min(
            (section.confidence for section in structure_sections),
            default=0.0,
        )
        chord_confidence = min(
            (candidate.confidence for candidate in chord_candidates),
            default=0.0,
        )
        confidence = {
            "tempo": tempo_confidence,
            "beat_grid": max(0.15, tempo_confidence - 0.08),
            "time_signature": time_signature.confidence,
            "key": key_candidate.confidence,
            "pitch_range": pitch_range.confidence,
            "loudness": loudness.confidence,
            "structure": structure_confidence,
            "chords": chord_confidence,
            "instrument_tags": min((tag.confidence for tag in instrument_tags), default=0.0),
            "energy": dynamic_confidence,
            "production_features": 0.55,
        }
        confidence["overall"] = round(
            sum(confidence.values()) / len(confidence),
            4,
        )
        return ReferenceAnalysisResult(
            tempo_bpm=tempo_bpm,
            beat_grid=beat_grid,
            time_signature=time_signature,
            key_candidate=key_candidate,
            pitch_range=pitch_range,
            loudness=loudness,
            structure_sections=structure_sections,
            chord_candidates=chord_candidates,
            instrument_tags=instrument_tags,
            energy_curve=energy_curve,
            production_features=production_features,
            confidence=confidence,
        )


def _decode_pcm_wav(data: bytes, *, target_sample_rate: int) -> _PcmSignal:
    try:
        with wave.open(BytesIO(data), "rb") as reader:
            channels = reader.getnchannels()
            sample_width = reader.getsampwidth()
            sample_rate = reader.getframerate()
            frame_count = reader.getnframes()
            frames = reader.readframes(frame_count)
    except (EOFError, wave.Error) as exc:
        raise ReferenceAnalysisProviderError("Reference analysis requires a valid WAV") from exc
    if channels < 1 or sample_rate < 1 or sample_width not in {1, 2, 4}:
        raise ReferenceAnalysisProviderError("Reference WAV PCM format is unsupported")

    stride = max(1, sample_rate // max(1, target_sample_rate))
    frame_size = channels * sample_width
    max_sample = 128 if sample_width == 1 else float(2 ** (sample_width * 8 - 1))
    samples: list[float] = []
    for frame_index in range(0, frame_count, stride):
        frame_offset = frame_index * frame_size
        if frame_offset + frame_size > len(frames):
            break
        channel_sum = 0.0
        for channel in range(channels):
            offset = frame_offset + channel * sample_width
            raw = frames[offset : offset + sample_width]
            value = (
                raw[0] - 128
                if sample_width == 1
                else int.from_bytes(raw, "little", signed=True)
            )
            channel_sum += value / max_sample
        samples.append(channel_sum / channels)
    return _PcmSignal(
        samples=samples,
        sample_rate=sample_rate / stride,
        channels=channels,
        duration_seconds=frame_count / sample_rate,
    )


def _estimate_tempo(
    signal: _PcmSignal,
    *,
    minimum_bpm: int,
    maximum_bpm: int,
) -> tuple[float, float, float]:
    window_size = max(1, round(signal.sample_rate * 0.02))
    envelope = [
        sqrt(
            sum(sample * sample for sample in signal.samples[index : index + window_size])
            / window_size
        )
        for index in range(0, len(signal.samples) - window_size + 1, window_size)
    ]
    if len(envelope) < 8:
        return 120.0, 0.18, 0.0
    mean = sum(envelope) / len(envelope)
    centered = [value - mean for value in envelope]
    variance = sum(value * value for value in centered) / len(centered)
    if variance < 1e-7:
        return 120.0, 0.2, 0.0

    envelope_rate = signal.sample_rate / window_size
    best_bpm = 120
    best_score = -1.0
    for bpm in range(max(30, minimum_bpm), min(300, maximum_bpm) + 1):
        lag = max(1, round(envelope_rate * 60 / bpm))
        if lag >= len(centered):
            continue
        numerator = sum(
            centered[index] * centered[index - lag]
            for index in range(lag, len(centered))
        )
        denominator = sum(value * value for value in centered[lag:])
        score = numerator / denominator if denominator > 0 else 0.0
        score -= abs(bpm - 120) * 0.00005
        if score > best_score:
            best_bpm = bpm
            best_score = score
    beat_windows = max(1, round(envelope_rate * 60 / best_bpm))
    first_window_count = min(len(envelope), beat_windows)
    beat_offset = max(range(first_window_count), key=envelope.__getitem__) / envelope_rate
    confidence = round(min(0.92, max(0.25, 0.35 + max(0.0, best_score) * 0.5)), 4)
    return float(best_bpm), confidence, beat_offset


def _energy_and_loudness(
    signal: _PcmSignal,
    *,
    source_start_seconds: float,
    point_count: int,
) -> tuple[list[ReferenceEnergyPoint], ReferenceLoudness]:
    safe_count = min(80, max(8, point_count))
    bucket_size = max(1, len(signal.samples) // safe_count)
    rms_values: list[float] = []
    for index in range(safe_count):
        bucket = signal.samples[index * bucket_size : (index + 1) * bucket_size]
        if not bucket:
            rms_values.append(0.0)
            continue
        rms_values.append(sqrt(sum(sample * sample for sample in bucket) / len(bucket)))
    maximum_rms = max(rms_values, default=0.0)
    interval = signal.duration_seconds / safe_count
    energy_curve = [
        ReferenceEnergyPoint(
            time_seconds=round(source_start_seconds + (index + 0.5) * interval, 3),
            value=round(value / maximum_rms, 4) if maximum_rms > 0 else 0.0,
        )
        for index, value in enumerate(rms_values)
    ]
    curve = [
        ReferenceLoudnessPoint(
            time_seconds=point.time_seconds,
            dbfs=round(_dbfs(rms_values[index]), 3),
        )
        for index, point in enumerate(energy_curve)
    ]
    total_rms = sqrt(
        sum(sample * sample for sample in signal.samples) / max(1, len(signal.samples))
    )
    peak = max((abs(sample) for sample in signal.samples), default=0.0)
    audible_db = sorted(point.dbfs for point in curve if point.dbfs > -90)
    dynamic_range = max(audible_db) - min(audible_db) if audible_db else 0.0
    loudness = ReferenceLoudness(
        integrated_dbfs=round(_dbfs(total_rms), 3),
        peak_dbfs=round(_dbfs(peak), 3),
        dynamic_range_db=round(max(0.0, dynamic_range), 3),
        curve=curve,
        confidence=0.78,
    )
    return energy_curve, loudness


def _estimate_key_and_pitch(
    signal: _PcmSignal,
) -> tuple[ReferenceKeyCandidate, ReferencePitchRange]:
    segment_size = max(1, round(signal.sample_rate * 0.25))
    midi_values: list[int] = []
    for index in range(0, len(signal.samples), segment_size):
        segment = signal.samples[index : index + segment_size]
        frequency = _zero_crossing_frequency(segment, signal.sample_rate)
        if 30 <= frequency <= 2000:
            midi_values.append(round(69 + 12 * log2(frequency / 440)))
    if not midi_values:
        midi_values = [60]
        confidence = 0.15
    else:
        confidence = round(min(0.82, 0.35 + len(midi_values) / 200), 4)
    low_midi = min(127, max(0, min(midi_values)))
    high_midi = min(127, max(0, max(midi_values)))
    pitch_classes = [value % 12 for value in midi_values]
    tonic_index = max(set(pitch_classes), key=pitch_classes.count)
    tonic = NOTE_NAMES[tonic_index]
    key_candidate = ReferenceKeyCandidate(
        tonic=tonic,
        mode="major",
        value=f"{tonic} major",
        confidence=round(max(0.18, confidence - 0.08), 4),
    )
    return key_candidate, ReferencePitchRange(
        low_midi=low_midi,
        high_midi=high_midi,
        low_note=_midi_note_name(low_midi),
        high_note=_midi_note_name(high_midi),
        confidence=confidence,
    )


def _zero_crossing_frequency(samples: list[float], sample_rate: float) -> float:
    if len(samples) < 2:
        return 0.0
    rms = sqrt(sum(sample * sample for sample in samples) / len(samples))
    if rms < 0.005:
        return 0.0
    crossings = sum(
        1
        for previous, current in zip(samples, samples[1:], strict=False)
        if (previous < 0 <= current) or (previous >= 0 > current)
    )
    return crossings * sample_rate / (2 * len(samples))


def _beat_grid(
    tempo_bpm: float,
    beat_offset: float,
    start_seconds: float,
    end_seconds: float,
) -> list[float]:
    interval = 60 / tempo_bpm
    position = start_seconds + beat_offset
    beats: list[float] = []
    while position <= end_seconds + 1e-6 and len(beats) < 10_000:
        beats.append(round(position, 3))
        position += interval
    return beats


def _structure_candidates(
    start_seconds: float,
    end_seconds: float,
) -> list[ReferenceStructureSection]:
    duration = end_seconds - start_seconds
    if duration < 8:
        return [
            ReferenceStructureSection(
                label="main",
                start_seconds=round(start_seconds, 3),
                end_seconds=round(end_seconds, 3),
                confidence=0.3,
            )
        ]
    labels = ("intro", "verse", "chorus", "outro")
    weights = (0.12, 0.38, 0.38, 0.12)
    sections: list[ReferenceStructureSection] = []
    cursor = start_seconds
    for index, (label, weight) in enumerate(zip(labels, weights, strict=True)):
        section_end = end_seconds if index == len(labels) - 1 else cursor + duration * weight
        sections.append(
            ReferenceStructureSection(
                label=label,
                start_seconds=round(cursor, 3),
                end_seconds=round(section_end, 3),
                confidence=0.32,
            )
        )
        cursor = section_end
    return sections


def _chord_candidates(
    key_candidate: ReferenceKeyCandidate,
    start_seconds: float,
    end_seconds: float,
) -> list[ReferenceChordCandidate]:
    tonic_index = NOTE_NAMES.index(key_candidate.tonic)
    symbols = (
        key_candidate.tonic,
        NOTE_NAMES[(tonic_index + 5) % 12],
        NOTE_NAMES[(tonic_index + 7) % 12],
        key_candidate.tonic,
    )
    duration = end_seconds - start_seconds
    candidates: list[ReferenceChordCandidate] = []
    for index, symbol in enumerate(symbols):
        chord_start = start_seconds + duration * index / len(symbols)
        chord_end = start_seconds + duration * (index + 1) / len(symbols)
        candidates.append(
            ReferenceChordCandidate(
                symbol=symbol,
                start_seconds=round(chord_start, 3),
                end_seconds=round(chord_end, 3),
                confidence=round(max(0.18, key_candidate.confidence - 0.08), 4),
            )
        )
    return candidates


def _instrument_tags(
    signal: _PcmSignal,
    pitch_confidence: float,
    tempo_confidence: float,
) -> list[ReferenceInstrumentTag]:
    tags = [
        ReferenceInstrumentTag(
            label="lead_vocal_or_synth",
            confidence=round(max(0.25, pitch_confidence - 0.05), 4),
        )
    ]
    if tempo_confidence >= 0.55:
        tags.append(ReferenceInstrumentTag(label="percussive_content", confidence=0.42))
    if signal.channels > 1:
        tags.append(ReferenceInstrumentTag(label="stereo_mix", confidence=0.9))
    return tags


def _production_features(
    signal: _PcmSignal,
    dynamic_range_db: float,
) -> list[ReferenceProductionFeature]:
    return [
        ReferenceProductionFeature(
            label="channel_layout",
            value="mono" if signal.channels == 1 else "stereo",
            confidence=1.0,
        ),
        ReferenceProductionFeature(
            label="dynamic_profile",
            value="dynamic" if dynamic_range_db >= 8 else "steady",
            confidence=0.72,
        ),
        ReferenceProductionFeature(
            label="analysis_resolution",
            value=f"{round(signal.sample_rate)} Hz downsampled PCM",
            confidence=1.0,
        ),
    ]


def _midi_note_name(value: int) -> str:
    return f"{NOTE_NAMES[value % 12]}{value // 12 - 1}"


def _dbfs(value: float) -> float:
    return -96.0 if value <= 1e-8 else max(-96.0, 20 * log10(value))


def _int_param(params: dict[str, object], key: str, default: int) -> int:
    value = params.get(key)
    return value if isinstance(value, int) else default

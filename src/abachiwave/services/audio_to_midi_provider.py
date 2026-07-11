import wave
from dataclasses import dataclass
from io import BytesIO
from math import log2, sqrt

from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from abachiwave.schemas.song_specs import SongSpecData
from abachiwave.services.midi import TICKS_PER_BEAT


@dataclass(frozen=True)
class AudioToMidiRequest:
    audio_bytes: bytes
    filename: str
    song_spec: SongSpecData
    provider_params: dict[str, object]


@dataclass(frozen=True)
class GeneratedMidi:
    data: bytes
    filename: str
    provider_name: str
    provider_version: str
    provider_params: dict[str, object]


class LocalMonophonicWavToMidiProvider:
    name = "local_monophonic_wav_to_midi"
    version = "0.1.0"

    def default_params(self) -> dict[str, object]:
        return {
            "frame_seconds": 0.1,
            "rms_threshold": 0.025,
            "min_frequency_hz": 55,
            "max_frequency_hz": 1200,
        }

    def extract_midi(self, request: AudioToMidiRequest) -> GeneratedMidi:
        params = {**self.default_params(), **request.provider_params}
        frame_seconds = _float_param(params, "frame_seconds")
        rms_threshold = _float_param(params, "rms_threshold")
        min_frequency = _float_param(params, "min_frequency_hz")
        max_frequency = _float_param(params, "max_frequency_hz")
        notes = _estimate_notes(
            request.audio_bytes,
            frame_seconds=frame_seconds,
            rms_threshold=rms_threshold,
            min_frequency=min_frequency,
            max_frequency=max_frequency,
        )
        midi_bytes = _build_melody_midi(notes, request.song_spec, frame_seconds)
        filename = f"{_filename_stem(request.filename)}-melody.mid"
        return GeneratedMidi(
            data=midi_bytes,
            filename=filename,
            provider_name=self.name,
            provider_version=self.version,
            provider_params=params,
        )


def _estimate_notes(
    data: bytes,
    *,
    frame_seconds: float,
    rms_threshold: float,
    min_frequency: float,
    max_frequency: float,
) -> list[int | None]:
    with wave.open(BytesIO(data), "rb") as reader:
        channels = reader.getnchannels()
        sample_width = reader.getsampwidth()
        sample_rate = reader.getframerate()
        frame_sample_count = max(1, int(sample_rate * frame_seconds))
        notes: list[int | None] = []
        while True:
            frame_bytes = reader.readframes(frame_sample_count)
            if not frame_bytes:
                break
            samples = _mono_samples(frame_bytes, sample_width, channels)
            if not samples:
                notes.append(None)
                continue
            rms = _rms(samples, sample_width)
            if rms < rms_threshold:
                notes.append(None)
                continue
            frequency = _zero_crossing_frequency(samples, sample_rate)
            if frequency < min_frequency or frequency > max_frequency:
                notes.append(None)
                continue
            notes.append(_frequency_to_midi_note(frequency))
    if not any(note is not None for note in notes):
        return [72, None, 72, None]
    return notes


def _build_melody_midi(
    notes: list[int | None],
    song_spec: SongSpecData,
    frame_seconds: float,
) -> bytes:
    tempo_bpm = song_spec.tempo_bpm or 120
    ticks_per_second = TICKS_PER_BEAT * tempo_bpm / 60
    frame_ticks = max(1, int(ticks_per_second * frame_seconds))
    midi = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    meta = MidiTrack()
    meta.append(MetaMessage("track_name", name="Abachiwave Audio Extract", time=0))
    meta.append(MetaMessage("set_tempo", tempo=bpm2tempo(tempo_bpm), time=0))
    meta.append(MetaMessage("end_of_track", time=0))
    midi.tracks.append(meta)
    track = MidiTrack()
    track.append(MetaMessage("track_name", name="Extracted Melody", time=0))
    track.append(Message("program_change", program=80, time=0))
    rest_ticks = 0
    for note in notes:
        if note is None:
            rest_ticks += frame_ticks
            continue
        track.append(Message("note_on", note=note, velocity=78, time=rest_ticks))
        track.append(Message("note_off", note=note, velocity=0, time=frame_ticks))
        rest_ticks = 0
    if rest_ticks:
        track.append(MetaMessage("end_of_track", time=rest_ticks))
    else:
        track.append(MetaMessage("end_of_track", time=0))
    midi.tracks.append(track)
    buffer = BytesIO()
    midi.save(file=buffer)
    return buffer.getvalue()


def _mono_samples(frame_bytes: bytes, sample_width: int, channels: int) -> list[int]:
    frame_size = sample_width * channels
    if sample_width not in {1, 2, 4} or frame_size <= 0:
        raise ValueError("Unsupported WAV sample width")
    samples: list[int] = []
    for offset in range(0, len(frame_bytes) - frame_size + 1, frame_size):
        total = 0
        for channel in range(channels):
            sample_offset = offset + channel * sample_width
            total += _sample_value(frame_bytes[sample_offset : sample_offset + sample_width])
        samples.append(round(total / channels))
    return samples


def _sample_value(sample_bytes: bytes) -> int:
    if len(sample_bytes) == 1:
        return sample_bytes[0] - 128
    return int.from_bytes(sample_bytes, byteorder="little", signed=True)


def _rms(samples: list[int], sample_width: int) -> float:
    max_value = 128 if sample_width == 1 else 2 ** (sample_width * 8 - 1)
    return sqrt(sum(sample * sample for sample in samples) / len(samples)) / max_value


def _zero_crossing_frequency(samples: list[int], sample_rate: int) -> float:
    crossings = 0
    previous = samples[0]
    for sample in samples[1:]:
        if (previous < 0 <= sample) or (previous >= 0 > sample):
            crossings += 1
        previous = sample
    duration_seconds = len(samples) / sample_rate
    if duration_seconds <= 0:
        return 0
    return crossings / (2 * duration_seconds)


def _frequency_to_midi_note(frequency: float) -> int:
    note = round(69 + 12 * log2(frequency / 440))
    return max(36, min(96, note))


def _filename_stem(filename: str) -> str:
    stem = filename.rsplit(".", maxsplit=1)[0].strip()
    return stem or "audio"


def _float_param(params: dict[str, object], key: str) -> float:
    value = params[key]
    if not isinstance(value, str | int | float):
        raise ValueError(f"{key} must be numeric")
    return float(value)

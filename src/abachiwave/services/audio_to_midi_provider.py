import wave
from dataclasses import dataclass
from io import BytesIO
from math import log2, sqrt
from typing import Protocol

import httpx
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo

from abachiwave.core.config import Settings, get_settings
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
    provider_usage: dict[str, object]


class AudioToMidiProvider(Protocol):
    name: str
    version: str

    def default_params(self) -> dict[str, object]: ...

    def extract_midi(self, request: AudioToMidiRequest) -> GeneratedMidi: ...


class UnknownAudioToMidiProviderError(ValueError):
    pass


class AudioToMidiProviderError(RuntimeError):
    code = "audio_to_midi_provider_failed"


class AudioToMidiProviderTimeoutError(AudioToMidiProviderError):
    code = "audio_to_midi_provider_timeout"


class AudioToMidiProviderUnavailableError(AudioToMidiProviderError):
    code = "audio_to_midi_provider_unavailable"


class AudioToMidiProviderResponseError(AudioToMidiProviderError):
    code = "audio_to_midi_provider_invalid_response"


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
            provider_usage={"estimated_frame_count": len(notes)},
        )


class BasicPitchHttpAudioToMidiProvider:
    """HTTP adapter for the isolated Spotify Basic Pitch inference service."""

    name = "spotify_basic_pitch"
    version = "0.4.0"

    def __init__(
        self,
        service_url: str,
        *,
        timeout_seconds: float,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._service_url = service_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def default_params(self) -> dict[str, object]:
        return dict[str, object](basic_pitch_default_params())

    def extract_midi(self, request: AudioToMidiRequest) -> GeneratedMidi:
        params = resolve_basic_pitch_params(request.provider_params)
        form = {
            "onset_threshold": str(params["onset_threshold"]),
            "frame_threshold": str(params["frame_threshold"]),
            "minimum_note_length_ms": str(params["minimum_note_length_ms"]),
            "minimum_frequency_hz": str(params["minimum_frequency_hz"]),
            "maximum_frequency_hz": str(params["maximum_frequency_hz"]),
            "melodia_trick": "true" if params["melodia_trick"] else "false",
            "midi_tempo": str(request.song_spec.tempo_bpm or 120),
        }
        try:
            with httpx.Client(
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.post(
                    f"{self._service_url}/v1/transcriptions",
                    data=form,
                    files={"file": (request.filename, request.audio_bytes, "audio/wav")},
                )
        except httpx.TimeoutException as exc:
            raise AudioToMidiProviderTimeoutError("Basic Pitch service timed out") from exc
        except httpx.RequestError as exc:
            raise AudioToMidiProviderUnavailableError(
                "Basic Pitch service is unavailable"
            ) from exc
        if response.status_code != 200:
            raise AudioToMidiProviderResponseError(
                f"Basic Pitch service returned HTTP {response.status_code}"
            )
        returned_version = response.headers.get("X-Basic-Pitch-Version")
        if returned_version != self.version:
            raise AudioToMidiProviderResponseError(
                "Basic Pitch service version does not match the run"
            )
        if not response.content.startswith(b"MThd"):
            raise AudioToMidiProviderResponseError(
                "Basic Pitch service returned invalid MIDI"
            )
        note_count = _optional_non_negative_int(response.headers.get("X-Note-Count"))
        filename = f"{_filename_stem(request.filename)}-basic-pitch-melody.mid"
        return GeneratedMidi(
            data=response.content,
            filename=filename,
            provider_name=self.name,
            provider_version=self.version,
            provider_params=dict[str, object](params),
            provider_usage={
                "note_count": note_count,
                "service_runtime": response.headers.get("X-Model-Runtime", "unknown"),
            },
        )


def build_audio_to_midi_provider(
    settings: Settings | None = None,
    *,
    provider_name: str | None = None,
) -> AudioToMidiProvider:
    resolved_settings = settings or get_settings()
    name = provider_name or resolved_settings.audio_to_midi_provider_name
    if name == LocalMonophonicWavToMidiProvider.name:
        return LocalMonophonicWavToMidiProvider()
    if name == BasicPitchHttpAudioToMidiProvider.name:
        return BasicPitchHttpAudioToMidiProvider(
            resolved_settings.basic_pitch_service_url,
            timeout_seconds=resolved_settings.basic_pitch_timeout_seconds,
        )
    raise UnknownAudioToMidiProviderError(f"Unknown audio-to-MIDI provider: {name}")


def basic_pitch_default_params() -> dict[str, bool | float]:
    return {
        "onset_threshold": 0.5,
        "frame_threshold": 0.3,
        "minimum_note_length_ms": 127.7,
        "minimum_frequency_hz": 55.0,
        "maximum_frequency_hz": 1760.0,
        "melodia_trick": True,
    }


def resolve_basic_pitch_params(
    overrides: dict[str, object],
) -> dict[str, bool | float]:
    defaults = basic_pitch_default_params()
    unknown = sorted(set(overrides) - set(defaults))
    if unknown:
        raise ValueError(f"unknown Basic Pitch provider parameters: {unknown}")
    params: dict[str, object] = {**defaults, **overrides}
    resolved: dict[str, bool | float] = {
        "onset_threshold": _bounded_float_param(params, "onset_threshold", 0, 1),
        "frame_threshold": _bounded_float_param(params, "frame_threshold", 0, 1),
        "minimum_note_length_ms": _bounded_float_param(
            params,
            "minimum_note_length_ms",
            1,
            10_000,
        ),
        "minimum_frequency_hz": _bounded_float_param(
            params,
            "minimum_frequency_hz",
            1,
            20_000,
        ),
        "maximum_frequency_hz": _bounded_float_param(
            params,
            "maximum_frequency_hz",
            1,
            20_000,
        ),
        "melodia_trick": _bool_param(params, "melodia_trick"),
    }
    minimum_frequency = resolved["minimum_frequency_hz"]
    maximum_frequency = resolved["maximum_frequency_hz"]
    if not isinstance(minimum_frequency, float) or not isinstance(maximum_frequency, float):
        raise TypeError("Basic Pitch frequency parameters must be numeric")
    if minimum_frequency >= maximum_frequency:
        raise ValueError("minimum_frequency_hz must be below maximum_frequency_hz")
    return resolved


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


def _bounded_float_param(
    params: dict[str, object],
    key: str,
    minimum: float,
    maximum: float,
) -> float:
    value = _float_param(params, key)
    if not minimum <= value <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}")
    return value


def _bool_param(params: dict[str, object], key: str) -> bool:
    value = params[key]
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _optional_non_negative_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None

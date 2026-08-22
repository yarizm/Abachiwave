import subprocess
from dataclasses import dataclass
from io import BytesIO
from wave import open as wave_open

from abachiwave.core.config import Settings, get_settings
from abachiwave.services.audio_derivatives import PcmWavData, inspect_pcm_wav


class AudioConversionError(RuntimeError):
    pass


@dataclass(frozen=True)
class FfmpegAudioConverter:
    executable: str = "ffmpeg"
    timeout_seconds: int = 120
    sample_rate: int = 48_000
    channels: int = 2
    name: str = "ffmpeg"
    version: str = "cli"

    def default_params(self) -> dict[str, object]:
        return {
            "codec": "pcm_s16le",
            "container": "wav",
            "sample_rate": self.sample_rate,
            "channels": self.channels,
        }

    def convert_to_pcm_wav(self, source: bytes) -> PcmWavData:
        if not source:
            raise AudioConversionError("Audio source must not be empty")
        command = [
            self.executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-map_metadata",
            "-1",
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            str(self.sample_rate),
            "-ac",
            str(self.channels),
            "-f",
            "s16le",
            "pipe:1",
        ]
        try:
            result = subprocess.run(
                command,
                input=source,
                capture_output=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise AudioConversionError("ffmpeg executable is unavailable") from exc
        except subprocess.TimeoutExpired as exc:
            raise AudioConversionError("Audio conversion exceeded its timeout") from exc
        if result.returncode != 0:
            raise AudioConversionError("ffmpeg could not decode the audio source")
        if not result.stdout:
            raise AudioConversionError("ffmpeg returned an empty PCM stream")
        wav_bytes = _wrap_pcm_s16le(
            result.stdout,
            sample_rate=self.sample_rate,
            channels=self.channels,
        )
        try:
            return inspect_pcm_wav(wav_bytes)
        except ValueError as exc:
            raise AudioConversionError("ffmpeg returned an invalid PCM derivative") from exc


def build_audio_converter(settings: Settings | None = None) -> FfmpegAudioConverter:
    selected = settings or get_settings()
    return FfmpegAudioConverter(
        executable=selected.ffmpeg_binary,
        timeout_seconds=selected.ffmpeg_timeout_seconds,
    )


def _wrap_pcm_s16le(data: bytes, *, sample_rate: int, channels: int) -> bytes:
    frame_size = channels * 2
    if len(data) % frame_size:
        raise AudioConversionError("ffmpeg returned a truncated PCM frame")
    buffer = BytesIO()
    with wave_open(buffer, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(2)
        writer.setframerate(sample_rate)
        writer.writeframes(data)
    return buffer.getvalue()

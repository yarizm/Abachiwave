import subprocess
from typing import Any

import pytest

from abachiwave.services.audio_conversion import AudioConversionError, FfmpegAudioConverter


def test_ffmpeg_converter_uses_pipe_io_and_returns_pcm_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = b"compressed-audio"
    raw_pcm = b"\x00\x00" * 24_000
    captured: dict[str, Any] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout=raw_pcm, stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    converter = FfmpegAudioConverter(executable="ffmpeg-test", timeout_seconds=45)
    converted = converter.convert_to_pcm_wav(source)

    assert captured["command"] == [
        "ffmpeg-test",
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
        "48000",
        "-ac",
        "2",
        "-f",
        "s16le",
        "pipe:1",
    ]
    assert captured["input"] == source
    assert captured["timeout"] == 45
    assert converted.data.startswith(b"RIFF")
    assert converted.sample_rate == 48000
    assert converted.channels == 2
    assert converted.duration_seconds == 0.25


def test_ffmpeg_converter_normalizes_process_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing_run)
    with pytest.raises(AudioConversionError, match="executable is unavailable"):
        FfmpegAudioConverter().convert_to_pcm_wav(b"source")

    def failed_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(command, 1, stdout=b"", stderr=b"decoder detail")

    monkeypatch.setattr(subprocess, "run", failed_run)
    with pytest.raises(AudioConversionError, match="could not decode"):
        FfmpegAudioConverter().convert_to_pcm_wav(b"source")


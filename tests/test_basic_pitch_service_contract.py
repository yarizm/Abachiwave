import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from mido import Message, MidiFile, MidiTrack

from abachiwave.basic_pitch_service import _validate_pcm_wav, app


def test_basic_pitch_container_provides_a_non_root_numba_cache() -> None:
    dockerfile = (
        Path(__file__).resolve().parents[1] / "Dockerfile.basic-pitch"
    ).read_text(encoding="utf-8")
    cache_setting = "ENV NUMBA_CACHE_DIR=/tmp/numba-cache"
    assert cache_setting in dockerfile
    assert dockerfile.index(cache_setting) < dockerfile.index("USER abachiwave")


def test_basic_pitch_service_accepts_wav_signature_and_rejects_other_bytes() -> None:
    _validate_pcm_wav(b"RIFF" + (b"\x00" * 4) + b"WAVE" + (b"\x00" * 32))
    with pytest.raises(HTTPException) as error:
        _validate_pcm_wav(b"not a wav")
    assert error.value.status_code == 415


@pytest.mark.asyncio
async def test_basic_pitch_service_returns_versioned_midi_without_loading_model() -> None:
    calls: list[dict[str, object]] = []

    class FakeRuntime:
        version = "0.4.0"
        model_runtime = "fixture"

        def transcribe(self, _audio_bytes: bytes, **parameters: object) -> tuple[bytes, int]:
            calls.append(parameters)
            return _midi_bytes(), 1

    app.state.runtime = FakeRuntime()
    app.state.inference_lock = asyncio.Lock()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://basic-pitch.test") as client:
        response = await client.post(
            "/v1/transcriptions",
            data={"onset_threshold": "0.62", "midi_tempo": "132"},
            files={"file": ("fixture.wav", _wav_signature(), "audio/wav")},
        )

    assert response.status_code == 200
    assert response.content.startswith(b"MThd")
    assert response.headers["X-Basic-Pitch-Version"] == "0.4.0"
    assert response.headers["X-Model-Runtime"] == "fixture"
    assert response.headers["X-Note-Count"] == "1"
    assert calls[0]["onset_threshold"] == 0.62
    assert calls[0]["midi_tempo"] == 132


def _wav_signature() -> bytes:
    return b"RIFF" + (b"\x00" * 4) + b"WAVE" + (b"\x00" * 32)


def _midi_bytes() -> bytes:
    midi = MidiFile(type=1, ticks_per_beat=480)
    track = MidiTrack()
    track.append(Message("note_on", note=69, velocity=90, time=0))
    track.append(Message("note_off", note=69, velocity=0, time=480))
    midi.tracks.append(track)
    buffer = BytesIO()
    midi.save(file=buffer)
    return buffer.getvalue()

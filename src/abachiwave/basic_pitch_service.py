import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, cast

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

EXPECTED_VERSION = os.getenv("BASIC_PITCH_EXPECTED_VERSION", "0.4.0")
MAX_AUDIO_BYTES = int(os.getenv("BASIC_PITCH_MAX_AUDIO_BYTES", str(25 * 1024 * 1024)))


class BasicPitchRuntime:
    def __init__(self) -> None:
        installed_version = version("basic-pitch")
        if installed_version != EXPECTED_VERSION:
            raise RuntimeError("Installed Basic Pitch version does not match the image contract")
        from basic_pitch import ICASSP_2022_MODEL_PATH  # type: ignore[import-not-found]
        from basic_pitch.inference import Model, predict  # type: ignore[import-not-found]

        self.version = installed_version
        self._predict = predict
        self._model = Model(ICASSP_2022_MODEL_PATH)
        model_type = getattr(self._model, "model_type", None)
        self.model_runtime = getattr(model_type, "name", "unknown").lower()

    def transcribe(
        self,
        audio_bytes: bytes,
        *,
        onset_threshold: float,
        frame_threshold: float,
        minimum_note_length_ms: float,
        minimum_frequency_hz: float,
        maximum_frequency_hz: float,
        melodia_trick: bool,
        midi_tempo: float,
    ) -> tuple[bytes, int]:
        with TemporaryDirectory(prefix="abachiwave-basic-pitch-") as temporary_directory:
            input_path = Path(temporary_directory) / "input.wav"
            output_path = Path(temporary_directory) / "output.mid"
            input_path.write_bytes(audio_bytes)
            _, midi_data, note_events = self._predict(
                input_path,
                self._model,
                onset_threshold=onset_threshold,
                frame_threshold=frame_threshold,
                minimum_note_length=minimum_note_length_ms,
                minimum_frequency=minimum_frequency_hz,
                maximum_frequency=maximum_frequency_hz,
                multiple_pitch_bends=False,
                melodia_trick=melodia_trick,
                midi_tempo=midi_tempo,
            )
            midi_data.write(str(output_path))
            midi_bytes = output_path.read_bytes()
        if not midi_bytes.startswith(b"MThd"):
            raise RuntimeError("Basic Pitch produced invalid MIDI")
        return midi_bytes, len(note_events)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.runtime = await asyncio.to_thread(BasicPitchRuntime)
    app.state.inference_lock = asyncio.Lock()
    yield


app = FastAPI(title="Abachiwave Basic Pitch Service", version="1.0", lifespan=lifespan)


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready(request: Request) -> dict[str, str]:
    runtime = _runtime(request)
    return {
        "status": "ready",
        "basic_pitch_version": runtime.version,
        "model_runtime": runtime.model_runtime,
    }


@app.post("/v1/transcriptions")
async def create_transcription(
    request: Request,
    file: Annotated[UploadFile, File()],
    onset_threshold: Annotated[float, Form(ge=0, le=1)] = 0.5,
    frame_threshold: Annotated[float, Form(ge=0, le=1)] = 0.3,
    minimum_note_length_ms: Annotated[float, Form(ge=1, le=10_000)] = 127.7,
    minimum_frequency_hz: Annotated[float, Form(gt=0, le=20_000)] = 55.0,
    maximum_frequency_hz: Annotated[float, Form(gt=0, le=20_000)] = 1760.0,
    melodia_trick: Annotated[bool, Form()] = True,
    midi_tempo: Annotated[float, Form(ge=20, le=400)] = 120,
) -> Response:
    if minimum_frequency_hz >= maximum_frequency_hz:
        raise HTTPException(status_code=422, detail="minimum frequency must be below maximum")
    audio_bytes = await file.read(MAX_AUDIO_BYTES + 1)
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="audio exceeds service limit")
    _validate_pcm_wav(audio_bytes)
    runtime = _runtime(request)
    try:
        async with request.app.state.inference_lock:
            midi_bytes, note_count = await asyncio.to_thread(
                runtime.transcribe,
                audio_bytes,
                onset_threshold=onset_threshold,
                frame_threshold=frame_threshold,
                minimum_note_length_ms=minimum_note_length_ms,
                minimum_frequency_hz=minimum_frequency_hz,
                maximum_frequency_hz=maximum_frequency_hz,
                melodia_trick=melodia_trick,
                midi_tempo=midi_tempo,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"transcription failed: {type(exc).__name__}",
        ) from exc
    return Response(
        content=midi_bytes,
        media_type="audio/midi",
        headers={
            "Content-Disposition": 'attachment; filename="basic-pitch.mid"',
            "X-Basic-Pitch-Version": runtime.version,
            "X-Model-Runtime": runtime.model_runtime,
            "X-Note-Count": str(note_count),
        },
    )


def _runtime(request: Request) -> BasicPitchRuntime:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="model is not ready")
    return cast(BasicPitchRuntime, runtime)


def _validate_pcm_wav(audio_bytes: bytes) -> None:
    if len(audio_bytes) < 44 or audio_bytes[:4] != b"RIFF" or audio_bytes[8:12] != b"WAVE":
        raise HTTPException(status_code=415, detail="only PCM WAV input is supported")

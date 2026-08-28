"""Isolated HTTP service for the YourMT3 vocal transcription pipeline.

Runs the three-part pipeline measured in docs/audio-to-midi-benchmark.md section 12:
YourMT3 supplies note boundaries, pYIN supplies the pitch of each note, and a global
duration scale corrects YourMT3's systematic length overshoot. Each part fixes one
measured deficit; YourMT3 on its own scores below the Basic Pitch default on singing.

The pipeline resolves one pitch per instant, so it is for monophonic vocal input only.
Callers route to it by upload kind; see the benchmark document section 12.6.

Deployed as a sidecar so the model runtime never enters the API or the general worker.
The module is copied into the image standalone, so it deliberately repeats the small
amount of MIDI handling it needs rather than importing from the application package.
"""

import asyncio
import io
import os
import wave
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

EXPECTED_VERSION = os.getenv("YOURMT3_EXPECTED_VERSION", "0.2.0")
MAX_AUDIO_BYTES = int(os.getenv("YOURMT3_MAX_AUDIO_BYTES", str(25 * 1024 * 1024)))
DEVICE = os.getenv("YOURMT3_DEVICE", "cpu")
EXPECTED_CHECKPOINT_SHA256 = os.getenv(
    "YOURMT3_EXPECTED_CHECKPOINT_SHA256",
    "ae38e415c79efd5592dcb9b658cdb99ddb11d4c4e1eaa364cab04a052473fc25",
)
CHECKPOINT_RELATIVE_PATH = (
    "yourmt3/mc13_256_g4_all_v7_mt3f_sqr_rms_moe_wf4_n8k2_silu_rope_rp_b36_nops/last.ckpt"
)

PYIN_SAMPLE_RATE = 16000
PYIN_HOP_LENGTH = 160
TICKS_PER_BEAT = 480
MIDI_TEMPO_MICROSECONDS = 500_000
MINIMUM_NOTE_SECONDS = 0.010


class Note:
    __slots__ = ("pitch", "onset", "offset", "velocity")

    def __init__(self, pitch: int, onset: float, offset: float, velocity: int) -> None:
        self.pitch = pitch
        self.onset = onset
        self.offset = offset
        self.velocity = velocity


def parse_notes(midi: Any) -> list[Note]:
    """Flatten a mido MidiFile into absolute-time notes, ignoring program assignment.

    Program is ignored on purpose: YourMT3 labels unaccompanied singing as a wind
    instrument, never as its own singing-voice program, so the label carries no
    information for this input.
    """
    from mido import merge_tracks, tick2second

    ticks_per_beat = midi.ticks_per_beat or TICKS_PER_BEAT
    tempo = MIDI_TEMPO_MICROSECONDS
    seconds = 0.0
    active: dict[tuple[int, int], list[tuple[float, int]]] = {}
    notes: list[Note] = []
    for message in merge_tracks(midi.tracks):
        seconds += tick2second(int(message.time), ticks_per_beat, tempo)
        if message.type == "set_tempo":
            tempo = int(message.tempo)
            continue
        key = (getattr(message, "channel", 0), getattr(message, "note", -1))
        if message.type == "note_on" and message.velocity > 0:
            active.setdefault(key, []).append((seconds, message.velocity))
            continue
        if message.type not in {"note_off", "note_on"} or not active.get(key):
            continue
        onset, velocity = active[key].pop(0)
        notes.append(Note(message.note, onset, max(seconds, onset), velocity))
    return sorted(notes, key=lambda note: (note.onset, note.pitch, note.offset))


def build_midi(notes: list[Note]) -> bytes:
    from mido import Message, MetaMessage, MidiFile, MidiTrack, second2tick

    midi = MidiFile(type=0, ticks_per_beat=TICKS_PER_BEAT)
    track = MidiTrack()
    track.append(MetaMessage("set_tempo", tempo=MIDI_TEMPO_MICROSECONDS, time=0))
    events: list[tuple[float, int, int, int]] = []
    for note in notes:
        # note_off before note_on at the same instant, so a repeated pitch re-articulates
        events.append((note.onset, 1, note.pitch, note.velocity))
        events.append((note.offset, 0, note.pitch, 0))
    events.sort(key=lambda event: (event[0], event[1], event[2]))
    previous_ticks = 0
    for seconds, is_on, pitch, velocity in events:
        ticks = int(round(second2tick(seconds, TICKS_PER_BEAT, MIDI_TEMPO_MICROSECONDS)))
        track.append(
            Message(
                "note_on" if is_on else "note_off",
                note=pitch,
                velocity=velocity,
                time=max(0, ticks - previous_ticks),
            )
        )
        previous_ticks = ticks
    midi.tracks.append(track)
    buffer = io.BytesIO()
    midi.save(file=buffer)
    return buffer.getvalue()


class YourMT3Runtime:
    def __init__(self) -> None:
        installed_version = version("mt3-infer")
        if installed_version != EXPECTED_VERSION:
            raise RuntimeError("Installed mt3-infer version does not match the image contract")
        checkpoint_dir = Path(os.environ["MT3_CHECKPOINT_DIR"])
        checkpoint = checkpoint_dir / CHECKPOINT_RELATIVE_PATH
        if not checkpoint.is_file():
            raise RuntimeError(f"YourMT3 checkpoint is missing: {checkpoint}")
        # mt3-infer records the checkpoint hash but does not enforce it on download,
        # so the image verifies it here before the weights are ever loaded.
        digest = sha256()
        with checkpoint.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        self.checkpoint_sha256 = digest.hexdigest()
        if self.checkpoint_sha256 != EXPECTED_CHECKPOINT_SHA256:
            raise RuntimeError("YourMT3 checkpoint checksum does not match the image contract")

        from mt3_infer import load_model  # type: ignore[import-not-found]

        self.version = installed_version
        self.device = DEVICE
        self._model = load_model("yourmt3", device=DEVICE)

    def transcribe(
        self,
        audio_bytes: bytes,
        *,
        duration_scale: float,
        use_pyin_pitch: bool,
    ) -> tuple[bytes, int]:
        import librosa  # type: ignore[import-not-found]
        import numpy as np

        with wave.open(io.BytesIO(audio_bytes), "rb") as reader:
            sample_rate = reader.getframerate()
            channels = reader.getnchannels()
            frames = reader.readframes(reader.getnframes())
        samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1)
        if samples.size == 0:
            raise RuntimeError("audio contains no samples")

        notes = parse_notes(self._model.transcribe(samples, sr=sample_rate))

        if use_pyin_pitch and notes:
            resampled = librosa.resample(samples, orig_sr=sample_rate, target_sr=PYIN_SAMPLE_RATE)
            f0, _voiced, _probability = librosa.pyin(
                resampled,
                fmin=55.0,
                fmax=1760.0,
                sr=PYIN_SAMPLE_RATE,
                frame_length=2048,
                hop_length=PYIN_HOP_LENGTH,
                fill_na=np.nan,
            )
            contour = np.full(f0.shape, np.nan)
            defined = ~np.isnan(f0)
            contour[defined] = librosa.hz_to_midi(f0[defined])
            seconds_per_frame = PYIN_HOP_LENGTH / PYIN_SAMPLE_RATE
            for note in notes:
                low = int(note.onset / seconds_per_frame)
                high = max(low + 1, int(note.offset / seconds_per_frame))
                window = contour[low:high]
                window = window[~np.isnan(window)]
                if window.size:
                    note.pitch = int(round(float(np.median(window))))

        for note in notes:
            duration = max(MINIMUM_NOTE_SECONDS, (note.offset - note.onset) * duration_scale)
            note.offset = note.onset + duration

        midi_bytes = build_midi(notes)
        if not midi_bytes.startswith(b"MThd"):
            raise RuntimeError("YourMT3 pipeline produced invalid MIDI")
        return midi_bytes, len(notes)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.runtime = await asyncio.to_thread(YourMT3Runtime)
    app.state.inference_lock = asyncio.Lock()
    yield


app = FastAPI(title="Abachiwave YourMT3 Service", version="1.0", lifespan=lifespan)


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready(request: Request) -> dict[str, str]:
    runtime = _runtime(request)
    return {
        "status": "ready",
        "mt3_infer_version": runtime.version,
        "device": runtime.device,
        "checkpoint_sha256": runtime.checkpoint_sha256,
    }


@app.post("/v1/transcriptions")
async def create_transcription(
    request: Request,
    file: Annotated[UploadFile, File()],
    duration_scale: Annotated[float, Form(gt=0, le=2)] = 0.85,
    use_pyin_pitch: Annotated[bool, Form()] = True,
) -> Response:
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
                duration_scale=duration_scale,
                use_pyin_pitch=use_pyin_pitch,
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
            "Content-Disposition": 'attachment; filename="yourmt3.mid"',
            "X-MT3-Infer-Version": runtime.version,
            "X-Model-Runtime": runtime.device,
            "X-Note-Count": str(note_count),
        },
    )


def _runtime(request: Request) -> YourMT3Runtime:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise HTTPException(status_code=503, detail="model is not ready")
    return cast(YourMT3Runtime, runtime)


def _validate_pcm_wav(audio_bytes: bytes) -> None:
    if len(audio_bytes) < 44 or audio_bytes[:4] != b"RIFF" or audio_bytes[8:12] != b"WAVE":
        raise HTTPException(status_code=415, detail="only PCM WAV input is supported")

from __future__ import annotations

import csv
import json
import math
import wave
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO, StringIO
from pathlib import Path

from mido import Message, MetaMessage, MidiFile, MidiTrack

from abachiwave.evaluations.audio_normalization import normalize_mono_pcm16_wav

VOCADITO_ZENODO_RECORD_ID = 5_557_945
VOCADITO_LICENSE_ID = "cc-by-4.0"
VOCADITO_ARTIFACT_NAME = "vocadito.zip"
VOCADITO_ARTIFACT_SIZE = 58_491_239
VOCADITO_ARTIFACT_CHECKSUM = "md5:0f304a0088dbab4eb9657f7e400786d8"
VOCADITO_TRACK_IDS = frozenset(range(1, 41))
REFERENCE_VELOCITY = 100
TICKS_PER_SECOND = 960


@dataclass(frozen=True)
class VocaditoSourceArtifact:
    name: str
    size: int
    checksum: str
    content_url: str


@dataclass(frozen=True)
class VocaditoTrackMetadata:
    track_id: int
    singer_id: str
    average_pitch: int
    language: str

    @property
    def stem(self) -> str:
        return f"vocadito_{self.track_id}"

    @property
    def sample_id(self) -> str:
        return f"vocadito_{self.track_id:02d}"

    @property
    def audio_member(self) -> str:
        return f"Audio/{self.stem}.wav"

    def annotation_member(self, annotator: int) -> str:
        if annotator not in {1, 2}:
            raise ValueError("Vocadito annotator must be 1 or 2")
        return f"Annotations/Notes/{self.stem}_notesA{annotator}.csv"


@dataclass(frozen=True)
class VocaditoNote:
    onset_seconds: float
    offset_seconds: float
    pitch: int
    velocity: int = REFERENCE_VELOCITY


@dataclass(frozen=True)
class SelectedVocaditoSample:
    metadata: VocaditoTrackMetadata
    duration_seconds: float
    annotator_1_notes: tuple[VocaditoNote, ...]
    annotator_2_notes: tuple[VocaditoNote, ...]
    source_audio_wav: bytes
    source_annotator_1_csv: bytes
    source_annotator_2_csv: bytes


def validate_vocadito_zenodo_record(payload: object) -> VocaditoSourceArtifact:
    if not isinstance(payload, dict) or payload.get("id") != VOCADITO_ZENODO_RECORD_ID:
        raise ValueError("unexpected Vocadito Zenodo record id")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Vocadito Zenodo record is missing metadata")
    license_metadata = metadata.get("license")
    license_id = license_metadata.get("id") if isinstance(license_metadata, dict) else None
    if license_id != VOCADITO_LICENSE_ID:
        raise ValueError("unexpected Vocadito Zenodo license")
    files = payload.get("files")
    if not isinstance(files, list):
        raise ValueError("Vocadito Zenodo record is missing files")
    for file_metadata in files:
        if (
            not isinstance(file_metadata, dict)
            or file_metadata.get("key") != VOCADITO_ARTIFACT_NAME
        ):
            continue
        links = file_metadata.get("links")
        content_url = links.get("self") if isinstance(links, dict) else None
        if (
            file_metadata.get("size") != VOCADITO_ARTIFACT_SIZE
            or file_metadata.get("checksum") != VOCADITO_ARTIFACT_CHECKSUM
            or not isinstance(content_url, str)
            or not content_url.startswith("https://")
        ):
            raise ValueError("Vocadito Zenodo artifact metadata mismatch")
        return VocaditoSourceArtifact(
            name=VOCADITO_ARTIFACT_NAME,
            size=VOCADITO_ARTIFACT_SIZE,
            checksum=VOCADITO_ARTIFACT_CHECKSUM,
            content_url=content_url,
        )
    raise ValueError("Vocadito Zenodo record is missing vocadito.zip")


def parse_vocadito_metadata(data: bytes) -> list[VocaditoTrackMetadata]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid Vocadito metadata encoding") from exc
    reader = csv.DictReader(StringIO(text, newline=""))
    if reader.fieldnames != ["track_id", "singer_id", "average_pitch", "language"]:
        raise ValueError("unexpected Vocadito metadata columns")
    tracks: list[VocaditoTrackMetadata] = []
    for row in reader:
        track_id = _integer(row.get("track_id"), "track id")
        average_pitch = _integer(row.get("average_pitch"), "average pitch")
        singer_id = row.get("singer_id") or ""
        language = row.get("language") or ""
        if (
            track_id not in VOCADITO_TRACK_IDS
            or not singer_id.startswith("S")
            or not singer_id[1:].isdigit()
            or not 0 <= average_pitch <= 127
            or not language
        ):
            raise ValueError(f"invalid Vocadito metadata row for track {track_id}")
        tracks.append(
            VocaditoTrackMetadata(
                track_id=track_id,
                singer_id=singer_id,
                average_pitch=average_pitch,
                language=language,
            )
        )
    ids = [track.track_id for track in tracks]
    if len(ids) != len(set(ids)) or set(ids) != VOCADITO_TRACK_IDS:
        raise ValueError("Vocadito metadata must contain tracks 1-40 exactly once")
    return sorted(tracks, key=lambda track: track.track_id)


def parse_vocadito_notes(
    data: bytes,
    *,
    audio_duration_seconds: float,
) -> tuple[VocaditoNote, ...]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid Vocadito note annotation encoding") from exc
    notes: list[VocaditoNote] = []
    for row_number, row in enumerate(csv.reader(StringIO(text, newline="")), start=1):
        if len(row) != 3:
            raise ValueError(f"Vocadito note row {row_number} must contain three columns")
        onset = _number(row[0], "note onset")
        frequency_hz = _number(row[1], "note frequency")
        duration = _number(row[2], "note duration")
        if onset < 0 or frequency_hz <= 0 or duration <= 0:
            raise ValueError(f"Vocadito note row {row_number} has invalid values")
        offset = onset + duration
        if onset > audio_duration_seconds + 0.01 or offset > audio_duration_seconds + 0.01:
            raise ValueError(f"Vocadito note row {row_number} falls outside audio duration")
        pitch = round(69 + 12 * math.log2(frequency_hz / 440))
        if not 0 <= pitch <= 127:
            raise ValueError(f"Vocadito note row {row_number} has invalid MIDI pitch")
        notes.append(
            VocaditoNote(
                onset_seconds=onset,
                offset_seconds=min(offset, audio_duration_seconds),
                pitch=pitch,
            )
        )
    if not notes:
        raise ValueError("Vocadito note annotation is empty")
    return tuple(sorted(notes, key=lambda note: (note.onset_seconds, note.pitch)))


def build_vocadito_reference_midi(notes: tuple[VocaditoNote, ...]) -> bytes:
    if not notes:
        raise ValueError("at least one Vocadito note is required")
    midi = MidiFile(type=1, ticks_per_beat=480)
    meta = MidiTrack()
    meta.append(MetaMessage("set_tempo", tempo=500_000, time=0))
    midi.tracks.append(meta)
    events: list[tuple[int, int, int, int]] = []
    for note in notes:
        onset_tick = round(note.onset_seconds * TICKS_PER_SECOND)
        offset_tick = max(onset_tick + 1, round(note.offset_seconds * TICKS_PER_SECOND))
        events.append((onset_tick, 1, note.pitch, note.velocity))
        events.append((offset_tick, 0, note.pitch, 0))
    events.sort()
    track = MidiTrack()
    previous_tick = 0
    for tick, event_order, pitch, velocity in events:
        track.append(
            Message(
                "note_on" if event_order == 1 else "note_off",
                note=pitch,
                velocity=velocity,
                time=tick - previous_tick,
            )
        )
        previous_tick = tick
    midi.tracks.append(track)
    output = BytesIO()
    midi.save(file=output)
    return output.getvalue()


def build_selected_vocadito_sample(
    metadata: VocaditoTrackMetadata,
    *,
    source_audio_wav: bytes,
    source_annotator_1_csv: bytes,
    source_annotator_2_csv: bytes,
) -> SelectedVocaditoSample:
    with wave.open(BytesIO(source_audio_wav), "rb") as reader:
        audio_duration = reader.getnframes() / reader.getframerate()
    annotator_1_notes = parse_vocadito_notes(
        source_annotator_1_csv,
        audio_duration_seconds=audio_duration,
    )
    annotator_2_notes = parse_vocadito_notes(
        source_annotator_2_csv,
        audio_duration_seconds=audio_duration,
    )
    return SelectedVocaditoSample(
        metadata=metadata,
        duration_seconds=audio_duration,
        annotator_1_notes=annotator_1_notes,
        annotator_2_notes=annotator_2_notes,
        source_audio_wav=source_audio_wav,
        source_annotator_1_csv=source_annotator_1_csv,
        source_annotator_2_csv=source_annotator_2_csv,
    )


def write_vocadito_dataset(
    output_directory: Path,
    *,
    samples: list[SelectedVocaditoSample],
    source_url: str,
    source_artifact_checksum: str,
) -> Path:
    if {sample.metadata.track_id for sample in samples} != VOCADITO_TRACK_IDS:
        raise ValueError("Vocadito benchmark dataset requires all 40 tracks")
    if output_directory.exists() and any(output_directory.iterdir()):
        raise RuntimeError(f"output directory is not empty: {output_directory.resolve()}")

    audio_directory = output_directory / "audio"
    midi_directory = output_directory / "midi"
    audio_directory.mkdir(parents=True, exist_ok=False)
    midi_directory.mkdir(parents=True, exist_ok=False)
    manifest_samples: list[dict[str, object]] = []
    for sample in sorted(samples, key=lambda item: item.metadata.track_id):
        normalized_wav = normalize_mono_pcm16_wav(
            sample.source_audio_wav,
            source_label="Vocadito",
        )
        annotator_1_midi = build_vocadito_reference_midi(sample.annotator_1_notes)
        annotator_2_midi = build_vocadito_reference_midi(sample.annotator_2_notes)
        sample_id = sample.metadata.sample_id
        audio_name = f"{sample_id}.wav"
        annotator_1_name = f"{sample_id}_a1.mid"
        annotator_2_name = f"{sample_id}_a2.mid"
        (audio_directory / audio_name).write_bytes(normalized_wav)
        (midi_directory / annotator_1_name).write_bytes(annotator_1_midi)
        (midi_directory / annotator_2_name).write_bytes(annotator_2_midi)
        manifest_samples.append(
            {
                "id": sample_id,
                "category": "vocal_phrase",
                "audio_path": f"audio/{audio_name}",
                "reference_id": "annotator_1",
                "reference_midi_path": f"midi/{annotator_1_name}",
                "audio_sha256": sha256(normalized_wav).hexdigest(),
                "reference_midi_sha256": sha256(annotator_1_midi).hexdigest(),
                "source_member": sample.metadata.audio_member,
                "source_audio_sha256": sha256(sample.source_audio_wav).hexdigest(),
                "source_annotation_member": sample.metadata.annotation_member(1),
                "source_annotation_sha256": sha256(
                    sample.source_annotator_1_csv
                ).hexdigest(),
                "alternative_references": [
                    {
                        "id": "annotator_2",
                        "midi_path": f"midi/{annotator_2_name}",
                        "midi_sha256": sha256(annotator_2_midi).hexdigest(),
                        "source_annotation_member": sample.metadata.annotation_member(2),
                        "source_annotation_sha256": sha256(
                            sample.source_annotator_2_csv
                        ).hexdigest(),
                    }
                ],
                "attributes": {
                    "track_id": sample.metadata.track_id,
                    "singer_id": sample.metadata.singer_id,
                    "average_pitch": sample.metadata.average_pitch,
                    "language": sample.metadata.language,
                },
            }
        )

    manifest = {
        "schema_version": 1,
        "dataset": {
            "name": "Vocadito complete dual-annotator vocal set",
            "version": "zenodo-5557945",
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "source_url": source_url,
            "reference_policy": (
                "Each track includes both musician-created Vocadito note annotations. Note "
                "frequency in Hz is rounded to the nearest MIDI semitone; velocity is fixed at "
                "100 because it is not annotated. Per the dataset paper's A_max recommendation, "
                "the benchmark selects the annotator with the highest onset+pitch+offset F1 for "
                "each prediction, then reports all metrics against that selected reference."
            ),
            "source_artifact_checksums": {
                VOCADITO_ARTIFACT_NAME: source_artifact_checksum,
            },
            "synthetic": False,
        },
        "onset_tolerance_seconds": 0.05,
        "offset_tolerance_seconds": 0.05,
        "offset_tolerance_ratio": 0.2,
        "reference_selection_policy": "best_onset_pitch_offset_f1",
        "provider_params": {},
        "samples": manifest_samples,
        "thresholds": {},
    }
    manifest_path = output_directory / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _number(value: object, label: str) -> float:
    if not isinstance(value, str):
        raise ValueError(f"Vocadito {label} must be text")
    try:
        result = float(value)
    except ValueError as exc:
        raise ValueError(f"Vocadito {label} must be numeric") from exc
    if not math.isfinite(result):
        raise ValueError(f"Vocadito {label} must be finite")
    return result


def _integer(value: object, label: str) -> int:
    numeric = _number(value, label)
    if not numeric.is_integer():
        raise ValueError(f"Vocadito {label} must be an integer")
    return int(numeric)

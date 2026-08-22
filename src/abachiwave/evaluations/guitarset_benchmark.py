from __future__ import annotations

import json
import math
import re
import wave
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path

from mido import Message, MetaMessage, MidiFile, MidiTrack

from abachiwave.evaluations.audio_normalization import normalize_mono_pcm16_wav

GUITARSET_STEM_PATTERN = re.compile(
    r"^(?P<performer>\d{2})_(?P<style>[A-Za-z0-9]+)-(?P<tempo>\d+)-"
    r"(?P<key>[A-G](?:b|#)?)_(?P<part>solo|comp)$"
)
GUITARSET_KNOWN_BAD_STEMS = {
    "02_Funk2-119-G_comp",
    "04_BN3-154-E_comp",
    "04_Jazz1-200-B_comp",
}
TICKS_PER_SECOND = 960
REFERENCE_VELOCITY = 100
GUITARSET_ZENODO_RECORD_ID = 3_371_780
GUITARSET_VERSION = "1.1.0"
GUITARSET_LICENSE_ID = "cc-by-4.0"
GUITARSET_EXPECTED_ARTIFACTS = {
    "annotation.zip": (39_132_574, "md5:b39b78e63d3446f2e54ddb7a54df9b10"),
    "audio_mono-mic.zip": (656_927_981, "md5:275966d6610ac34999b58426beb119c3"),
}


@dataclass(frozen=True)
class GuitarSetExcerptMetadata:
    stem: str
    performer: int
    style: str
    tempo_bpm: int
    key: str
    part: str

    @property
    def sample_id(self) -> str:
        return self.stem.replace("#", "sharp")

    @property
    def category(self) -> str:
        if self.part == "solo":
            return "monophonic_instrumental_phrase"
        return "polyphonic_instrumental_phrase"

    @property
    def audio_member(self) -> str:
        return f"{self.stem}_mic.wav"

    @property
    def annotation_member(self) -> str:
        return f"{self.stem}.jams"


@dataclass(frozen=True)
class GuitarSetNote:
    onset_seconds: float
    offset_seconds: float
    pitch: int
    velocity: int = REFERENCE_VELOCITY


@dataclass(frozen=True)
class SelectedGuitarSetSample:
    metadata: GuitarSetExcerptMetadata
    duration_seconds: float
    notes: tuple[GuitarSetNote, ...]
    source_audio_wav: bytes
    source_annotation_jams: bytes


@dataclass(frozen=True)
class GuitarSetSourceArtifact:
    name: str
    size: int
    checksum: str
    content_url: str


def parse_guitarset_stem(stem: str) -> GuitarSetExcerptMetadata:
    matched = GUITARSET_STEM_PATTERN.fullmatch(stem)
    if matched is None:
        raise ValueError(f"invalid GuitarSet excerpt stem: {stem}")
    performer = int(matched.group("performer"))
    tempo_bpm = int(matched.group("tempo"))
    if not 0 <= performer <= 5 or tempo_bpm <= 0:
        raise ValueError(f"invalid GuitarSet performer or tempo: {stem}")
    return GuitarSetExcerptMetadata(
        stem=stem,
        performer=performer,
        style=matched.group("style"),
        tempo_bpm=tempo_bpm,
        key=matched.group("key"),
        part=matched.group("part"),
    )


def validate_guitarset_zenodo_record(
    payload: object,
) -> dict[str, GuitarSetSourceArtifact]:
    if not isinstance(payload, dict) or payload.get("id") != GUITARSET_ZENODO_RECORD_ID:
        raise ValueError("unexpected GuitarSet Zenodo record id")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("GuitarSet Zenodo record is missing metadata")
    license_metadata = metadata.get("license")
    license_id = license_metadata.get("id") if isinstance(license_metadata, dict) else None
    if metadata.get("version") != GUITARSET_VERSION or license_id != GUITARSET_LICENSE_ID:
        raise ValueError("unexpected GuitarSet Zenodo version or license")
    files = payload.get("files")
    if not isinstance(files, list):
        raise ValueError("GuitarSet Zenodo record is missing files")

    artifacts: dict[str, GuitarSetSourceArtifact] = {}
    for file_metadata in files:
        if not isinstance(file_metadata, dict):
            continue
        name = file_metadata.get("key")
        if not isinstance(name, str) or name not in GUITARSET_EXPECTED_ARTIFACTS:
            continue
        expected_size, expected_checksum = GUITARSET_EXPECTED_ARTIFACTS[name]
        links = file_metadata.get("links")
        content_url = links.get("self") if isinstance(links, dict) else None
        if (
            file_metadata.get("size") != expected_size
            or file_metadata.get("checksum") != expected_checksum
            or not isinstance(content_url, str)
            or not content_url.startswith("https://")
        ):
            raise ValueError(f"GuitarSet Zenodo artifact metadata mismatch: {name}")
        artifacts[name] = GuitarSetSourceArtifact(
            name=name,
            size=expected_size,
            checksum=expected_checksum,
            content_url=content_url,
        )
    missing = set(GUITARSET_EXPECTED_ARTIFACTS) - set(artifacts)
    if missing:
        raise ValueError(f"GuitarSet Zenodo record is missing artifacts: {sorted(missing)}")
    return artifacts


def parse_guitarset_jams(data: bytes) -> tuple[float, tuple[GuitarSetNote, ...]]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid GuitarSet JAMS JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("GuitarSet JAMS root must be an object")
    file_metadata = payload.get("file_metadata")
    if not isinstance(file_metadata, dict):
        raise ValueError("GuitarSet JAMS is missing file_metadata")
    duration_seconds = _finite_number(file_metadata.get("duration"), "file duration")
    if duration_seconds <= 0:
        raise ValueError("GuitarSet JAMS file duration must be positive")
    annotations = payload.get("annotations")
    if not isinstance(annotations, list):
        raise ValueError("GuitarSet JAMS is missing annotations")

    notes: list[GuitarSetNote] = []
    for annotation in annotations:
        if not isinstance(annotation, dict) or annotation.get("namespace") != "note_midi":
            continue
        observations = annotation.get("data")
        if not isinstance(observations, list):
            raise ValueError("GuitarSet note_midi data must be a list")
        for observation in observations:
            if not isinstance(observation, dict):
                raise ValueError("GuitarSet note observation must be an object")
            onset = _finite_number(observation.get("time"), "note onset")
            duration = _finite_number(observation.get("duration"), "note duration")
            pitch_value = _finite_number(observation.get("value"), "note pitch")
            pitch = round(pitch_value)
            if onset < 0 or duration <= 0 or not 0 <= pitch <= 127:
                raise ValueError("GuitarSet note has invalid onset, duration, or pitch")
            offset = onset + duration
            if onset > duration_seconds + 0.01 or offset > duration_seconds + 0.01:
                raise ValueError("GuitarSet note falls outside file duration")
            notes.append(
                GuitarSetNote(
                    onset_seconds=onset,
                    offset_seconds=min(offset, duration_seconds),
                    pitch=pitch,
                )
            )
    if not notes:
        raise ValueError("GuitarSet JAMS contains no note_midi observations")
    return duration_seconds, tuple(
        sorted(notes, key=lambda note: (note.onset_seconds, note.pitch, note.offset_seconds))
    )


def build_guitarset_reference_midi(notes: tuple[GuitarSetNote, ...]) -> bytes:
    if not notes:
        raise ValueError("at least one GuitarSet note is required")
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
        message_type = "note_on" if event_order == 1 else "note_off"
        track.append(
            Message(
                message_type,
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


def build_selected_guitarset_sample(
    metadata: GuitarSetExcerptMetadata,
    *,
    source_audio_wav: bytes,
    source_annotation_jams: bytes,
) -> SelectedGuitarSetSample:
    duration_seconds, notes = parse_guitarset_jams(source_annotation_jams)
    with wave.open(BytesIO(source_audio_wav), "rb") as reader:
        audio_duration = reader.getnframes() / reader.getframerate()
    if abs(audio_duration - duration_seconds) > 0.01:
        raise ValueError(
            f"GuitarSet audio/JAMS duration mismatch for {metadata.stem}: "
            f"audio={audio_duration}, annotation={duration_seconds}"
        )
    return SelectedGuitarSetSample(
        metadata=metadata,
        duration_seconds=duration_seconds,
        notes=notes,
        source_audio_wav=source_audio_wav,
        source_annotation_jams=source_annotation_jams,
    )


def write_guitarset_subset(
    output_directory: Path,
    *,
    samples: list[SelectedGuitarSetSample],
    source_url: str,
    source_artifact_checksums: dict[str, str],
) -> Path:
    if not samples:
        raise ValueError("at least one GuitarSet sample is required")
    if output_directory.exists() and any(output_directory.iterdir()):
        raise RuntimeError(f"output directory is not empty: {output_directory.resolve()}")
    rendered: list[tuple[SelectedGuitarSetSample, bytes, bytes]] = []
    for sample in samples:
        normalized_wav = normalize_mono_pcm16_wav(
            sample.source_audio_wav,
            source_label="GuitarSet",
        )
        reference_midi = build_guitarset_reference_midi(sample.notes)
        rendered.append((sample, normalized_wav, reference_midi))

    audio_directory = output_directory / "audio"
    midi_directory = output_directory / "midi"
    audio_directory.mkdir(parents=True, exist_ok=False)
    midi_directory.mkdir(parents=True, exist_ok=False)
    manifest_samples: list[dict[str, object]] = []
    for sample, normalized_wav, reference_midi in rendered:
        sample_id = sample.metadata.sample_id
        (audio_directory / f"{sample_id}.wav").write_bytes(normalized_wav)
        (midi_directory / f"{sample_id}.mid").write_bytes(reference_midi)
        manifest_samples.append(
            {
                "id": sample_id,
                "category": sample.metadata.category,
                "audio_path": f"audio/{sample_id}.wav",
                "reference_midi_path": f"midi/{sample_id}.mid",
                "audio_sha256": sha256(normalized_wav).hexdigest(),
                "reference_midi_sha256": sha256(reference_midi).hexdigest(),
                "source_member": sample.metadata.audio_member,
                "source_audio_sha256": sha256(sample.source_audio_wav).hexdigest(),
                "source_annotation_member": sample.metadata.annotation_member,
                "source_annotation_sha256": sha256(
                    sample.source_annotation_jams
                ).hexdigest(),
            }
        )

    manifest = {
        "schema_version": 1,
        "dataset": {
            "name": "GuitarSet microphone phrase subset",
            "version": "1.1.0-zenodo-3371780",
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "source_url": source_url,
            "reference_policy": (
                "Onset, duration and pitch come from GuitarSet 1.1.0 JAMS note_midi "
                "observations across all six strings. Floating pitch is rounded to the nearest "
                "MIDI semitone. JAMS has no note velocity, so reference velocity is fixed at 100 "
                "and must not be used as a release threshold. Known bad annotation stems from "
                "marl/GuitarSet issues 4 and 5 are excluded."
            ),
            "source_artifact_checksums": source_artifact_checksums,
            "synthetic": False,
        },
        "onset_tolerance_seconds": 0.05,
        "offset_tolerance_seconds": 0.05,
        "offset_tolerance_ratio": 0.2,
        "provider_params": {},
        "samples": manifest_samples,
        "thresholds": {},
    }
    manifest_path = output_directory / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _finite_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"GuitarSet {label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"GuitarSet {label} must be finite")
    return result

from __future__ import annotations

import json
import re
import tarfile
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath

from mido import Message, MetaMessage, MidiFile, MidiTrack

from abachiwave.evaluations.audio_normalization import normalize_mono_pcm16_wav

NSYNTH_NAME_PATTERN = re.compile(
    r"^(?P<family>[a-z]+)_(?P<source>acoustic|electronic|synthetic)_"
    r"(?P<instrument>\d{3})-(?P<pitch>\d{3})-(?P<velocity>\d{3})\.wav$"
)
TICKS_PER_SECOND = 960


@dataclass(frozen=True)
class NsynthNoteMetadata:
    filename: str
    family: str
    source: str
    instrument: int
    pitch: int
    velocity: int

    @property
    def category(self) -> str:
        return "vocal" if self.family == "vocal" else "monophonic_instrumental"

    @property
    def sample_id(self) -> str:
        return self.filename.removesuffix(".wav")


@dataclass(frozen=True)
class SelectedNsynthSample:
    source_member: str
    metadata: NsynthNoteMetadata
    source_wav: bytes


def parse_nsynth_filename(filename: str) -> NsynthNoteMetadata:
    matched = NSYNTH_NAME_PATTERN.fullmatch(filename)
    if matched is None:
        raise ValueError(f"invalid NSynth audio filename: {filename}")
    pitch = int(matched.group("pitch"))
    velocity = int(matched.group("velocity"))
    if not 0 <= pitch <= 127 or not 1 <= velocity <= 127:
        raise ValueError(f"invalid NSynth pitch or velocity: {filename}")
    return NsynthNoteMetadata(
        filename=filename,
        family=matched.group("family"),
        source=matched.group("source"),
        instrument=int(matched.group("instrument")),
        pitch=pitch,
        velocity=velocity,
    )


def normalize_nsynth_wav(data: bytes) -> bytes:
    return normalize_mono_pcm16_wav(data, source_label="NSynth")


def build_nsynth_reference_midi(
    metadata: NsynthNoteMetadata,
    *,
    held_seconds: float = 3.0,
) -> bytes:
    if held_seconds <= 0:
        raise ValueError("held_seconds must be positive")
    midi = MidiFile(type=1, ticks_per_beat=480)
    meta = MidiTrack()
    meta.append(MetaMessage("set_tempo", tempo=500_000, time=0))
    midi.tracks.append(meta)
    track = MidiTrack()
    track.append(Message("note_on", note=metadata.pitch, velocity=metadata.velocity, time=0))
    track.append(
        Message(
            "note_off",
            note=metadata.pitch,
            velocity=0,
            time=round(held_seconds * TICKS_PER_SECOND),
        )
    )
    midi.tracks.append(track)
    output = BytesIO()
    midi.save(file=output)
    return output.getvalue()


def select_nsynth_samples(
    archive: tarfile.TarFile,
    *,
    families: tuple[str, ...],
    samples_per_family: int,
    minimum_pitch: int,
    maximum_pitch: int,
) -> tuple[list[SelectedNsynthSample], int]:
    selected: dict[str, list[SelectedNsynthSample]] = {family: [] for family in families}
    selected_pitches: dict[str, set[int]] = {family: set() for family in families}
    inspected_wavs = 0

    for member in archive:
        if not member.isfile() or not member.name.lower().endswith(".wav"):
            continue
        inspected_wavs += 1
        filename = PurePosixPath(member.name).name
        try:
            metadata = parse_nsynth_filename(filename)
        except ValueError:
            continue
        family_samples = selected.get(metadata.family)
        if (
            family_samples is None
            or metadata.source != "acoustic"
            or not minimum_pitch <= metadata.pitch <= maximum_pitch
            or len(family_samples) >= samples_per_family
            or metadata.pitch in selected_pitches[metadata.family]
        ):
            continue
        extracted = archive.extractfile(member)
        if extracted is None:
            raise RuntimeError(f"could not read NSynth archive member: {member.name}")
        family_samples.append(
            SelectedNsynthSample(
                source_member=member.name,
                metadata=metadata,
                source_wav=extracted.read(),
            )
        )
        selected_pitches[metadata.family].add(metadata.pitch)
        if all(len(samples) == samples_per_family for samples in selected.values()):
            break

    missing = {
        family: samples_per_family - len(samples)
        for family, samples in selected.items()
        if len(samples) < samples_per_family
    }
    if missing:
        raise RuntimeError(
            "NSynth archive did not satisfy requested family quotas: "
            + ", ".join(f"{family} missing {count}" for family, count in missing.items())
        )
    return (
        [sample for family in families for sample in selected[family]],
        inspected_wavs,
    )


def write_nsynth_subset(
    output_directory: Path,
    *,
    samples: list[SelectedNsynthSample],
    archive_url: str,
    archive_etag: str,
) -> Path:
    if output_directory.exists() and any(output_directory.iterdir()):
        raise RuntimeError(f"output directory is not empty: {output_directory.resolve()}")

    rendered: list[tuple[SelectedNsynthSample, bytes, bytes]] = []
    for sample in samples:
        normalized_wav = normalize_nsynth_wav(sample.source_wav)
        reference_midi = build_nsynth_reference_midi(sample.metadata)
        rendered.append((sample, normalized_wav, reference_midi))

    audio_directory = output_directory / "audio"
    midi_directory = output_directory / "midi"
    audio_directory.mkdir(parents=True, exist_ok=False)
    midi_directory.mkdir(parents=True, exist_ok=False)
    manifest_samples: list[dict[str, object]] = []
    for sample, normalized_wav, reference_midi in rendered:
        sample_id = sample.metadata.sample_id
        audio_path = audio_directory / f"{sample_id}.wav"
        midi_path = midi_directory / f"{sample_id}.mid"
        audio_path.write_bytes(normalized_wav)
        midi_path.write_bytes(reference_midi)
        manifest_samples.append(
            {
                "id": sample_id,
                "category": sample.metadata.category,
                "audio_path": f"audio/{sample_id}.wav",
                "reference_midi_path": f"midi/{sample_id}.mid",
                "audio_sha256": sha256(normalized_wav).hexdigest(),
                "reference_midi_sha256": sha256(reference_midi).hexdigest(),
                "source_member": sample.source_member,
                "source_audio_sha256": sha256(sample.source_wav).hexdigest(),
            }
        )

    manifest = {
        "schema_version": 1,
        "dataset": {
            "name": "NSynth test acoustic subset",
            "version": f"test-etag-{archive_etag}",
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "source_url": archive_url,
            "reference_policy": (
                "Pitch and velocity come from each NSynth filename; onset is 0 seconds and "
                "offset is 3 seconds, matching the official NSynth note-generation contract "
                "documented at https://magenta.tensorflow.org/datasets/nsynth."
            ),
            "source_archive_etag": archive_etag,
            "synthetic": False,
        },
        "onset_tolerance_seconds": 0.1,
        "offset_tolerance_seconds": 0.2,
        "offset_tolerance_ratio": 0.25,
        "provider_params": {},
        "samples": manifest_samples,
        "thresholds": {},
    }
    manifest_path = output_directory / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path

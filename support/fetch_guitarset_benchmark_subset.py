"""Range-extract a pinned GuitarSet phrase subset for audio-to-MIDI benchmarking."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from abachiwave.evaluations.guitarset_benchmark import (
    GUITARSET_KNOWN_BAD_STEMS,
    GuitarSetSourceArtifact,
    SelectedGuitarSetSample,
    build_selected_guitarset_sample,
    parse_guitarset_stem,
    validate_guitarset_zenodo_record,
    write_guitarset_subset,
)
from abachiwave.evaluations.remote_zip import HttpsRangeReader

GUITARSET_RECORD_API_URL = "https://zenodo.org/api/records/3371780"
GUITARSET_RECORD_PAGE_URL = "https://zenodo.org/records/3371780"
DEFAULT_STEMS = (
    "03_Rock2-142-D_solo",
    "05_BN3-119-G_solo",
    "03_SS3-98-C_comp",
    "05_Jazz3-150-C_comp",
)


def fetch_guitarset_record() -> dict[str, GuitarSetSourceArtifact]:
    request = Request(
        GUITARSET_RECORD_API_URL,
        headers={"Accept": "application/json", "User-Agent": "AbachiWave-benchmark/1"},
    )
    with urlopen(request, timeout=120) as response:  # noqa: S310 - fixed HTTPS URL
        payload = json.loads(response.read())
    return validate_guitarset_zenodo_record(payload)


def fetch_guitarset_samples(
    artifacts: dict[str, GuitarSetSourceArtifact],
    stems: tuple[str, ...],
) -> list[SelectedGuitarSetSample]:
    annotation_artifact = artifacts["annotation.zip"]
    audio_artifact = artifacts["audio_mono-mic.zip"]
    samples: list[SelectedGuitarSetSample] = []
    with (
        HttpsRangeReader(
            annotation_artifact.content_url,
            size=annotation_artifact.size,
        ) as annotation_reader,
        zipfile.ZipFile(annotation_reader) as annotation_archive,
        HttpsRangeReader(audio_artifact.content_url, size=audio_artifact.size) as audio_reader,
        zipfile.ZipFile(audio_reader) as audio_archive,
    ):
        for stem in stems:
            if stem in GUITARSET_KNOWN_BAD_STEMS:
                raise ValueError(f"GuitarSet stem has a documented annotation issue: {stem}")
            metadata = parse_guitarset_stem(stem)
            annotation = annotation_archive.read(metadata.annotation_member)
            audio = audio_archive.read(metadata.audio_member)
            samples.append(
                build_selected_guitarset_sample(
                    metadata,
                    source_audio_wav=audio,
                    source_annotation_jams=annotation,
                )
            )
    return samples


def _parse_stems(value: str) -> tuple[str, ...]:
    stems = tuple(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))
    if not stems:
        raise argparse.ArgumentTypeError("at least one GuitarSet stem is required")
    for stem in stems:
        if stem in GUITARSET_KNOWN_BAD_STEMS:
            raise argparse.ArgumentTypeError(f"known-bad GuitarSet stem is not allowed: {stem}")
        try:
            parse_guitarset_stem(stem)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(str(exc)) from exc
    return stems


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument(
        "--stems",
        type=_parse_stems,
        default=DEFAULT_STEMS,
        help="Comma-separated GuitarSet stems; defaults to two solo and two comp excerpts.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        artifacts = fetch_guitarset_record()
        samples = fetch_guitarset_samples(artifacts, args.stems)
        manifest = write_guitarset_subset(
            args.output_directory,
            samples=samples,
            source_url=GUITARSET_RECORD_PAGE_URL,
            source_artifact_checksums={
                name: artifact.checksum for name, artifact in artifacts.items()
            },
        )
    except (
        HTTPError,
        URLError,
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        zipfile.BadZipFile,
    ) as exc:
        print(f"GuitarSet subset acquisition failed: {exc}", file=sys.stderr)
        return 1
    note_count = sum(len(sample.notes) for sample in samples)
    print(
        f"Wrote {len(samples)} GuitarSet excerpts / {note_count} reference notes: "
        f"{manifest.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

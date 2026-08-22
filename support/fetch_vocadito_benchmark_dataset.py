"""Fetch and convert the complete dual-annotator Vocadito vocal benchmark."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from hashlib import md5
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

from abachiwave.evaluations.vocadito_benchmark import (
    SelectedVocaditoSample,
    VocaditoSourceArtifact,
    build_selected_vocadito_sample,
    parse_vocadito_metadata,
    validate_vocadito_zenodo_record,
    write_vocadito_dataset,
)

VOCADITO_RECORD_API_URL = "https://zenodo.org/api/records/5557945"
VOCADITO_RECORD_PAGE_URL = "https://zenodo.org/records/5557945"
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


def fetch_vocadito_record() -> VocaditoSourceArtifact:
    request = Request(
        VOCADITO_RECORD_API_URL,
        headers={"Accept": "application/json", "User-Agent": "AbachiWave-benchmark/1"},
    )
    with urlopen(request, timeout=120) as response:  # noqa: S310 - fixed HTTPS URL
        payload = json.loads(response.read())
    return validate_vocadito_zenodo_record(payload)


def download_verified_archive(artifact: VocaditoSourceArtifact) -> bytes:
    if not artifact.content_url.startswith("https://"):
        raise ValueError("Vocadito archive URL must use HTTPS")
    request = Request(
        artifact.content_url,
        headers={"Accept-Encoding": "identity", "User-Agent": "AbachiWave-benchmark/1"},
    )
    data = bytearray()
    digest = md5(usedforsecurity=False)
    with urlopen(request, timeout=120) as response:  # noqa: S310 - validated HTTPS URL
        while chunk := response.read(DOWNLOAD_CHUNK_SIZE):
            data.extend(chunk)
            digest.update(chunk)
            if len(data) > artifact.size:
                raise OSError("Vocadito archive exceeds pinned size")
    if len(data) != artifact.size:
        raise OSError(
            f"Vocadito archive size mismatch: expected {artifact.size}, received {len(data)}"
        )
    actual_checksum = f"md5:{digest.hexdigest()}"
    if actual_checksum != artifact.checksum:
        raise OSError(
            "Vocadito archive checksum mismatch: "
            f"expected {artifact.checksum}, received {actual_checksum}"
        )
    return bytes(data)


def build_vocadito_samples(archive_data: bytes) -> list[SelectedVocaditoSample]:
    samples: list[SelectedVocaditoSample] = []
    with zipfile.ZipFile(BytesIO(archive_data)) as archive:
        tracks = parse_vocadito_metadata(archive.read("vocadito_metadata.csv"))
        for metadata in tracks:
            samples.append(
                build_selected_vocadito_sample(
                    metadata,
                    source_audio_wav=archive.read(metadata.audio_member),
                    source_annotator_1_csv=archive.read(metadata.annotation_member(1)),
                    source_annotator_2_csv=archive.read(metadata.annotation_member(2)),
                )
            )
    return samples


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        artifact = fetch_vocadito_record()
        archive_data = download_verified_archive(artifact)
        samples = build_vocadito_samples(archive_data)
        manifest = write_vocadito_dataset(
            args.output_directory,
            samples=samples,
            source_url=VOCADITO_RECORD_PAGE_URL,
            source_artifact_checksum=artifact.checksum,
        )
    except (OSError, RuntimeError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f"Vocadito dataset acquisition failed: {exc}", file=sys.stderr)
        return 1
    annotator_1_notes = sum(len(sample.annotator_1_notes) for sample in samples)
    annotator_2_notes = sum(len(sample.annotator_2_notes) for sample in samples)
    print(
        f"Wrote 40 Vocadito tracks / A1 {annotator_1_notes} notes / "
        f"A2 {annotator_2_notes} notes: {manifest.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Stream a small, reproducible acoustic NSynth subset for MIDI benchmarking."""

from __future__ import annotations

import argparse
import sys
import tarfile
from pathlib import Path
from urllib.request import Request, urlopen

from abachiwave.evaluations.nsynth_benchmark import (
    SelectedNsynthSample,
    select_nsynth_samples,
    write_nsynth_subset,
)

NSYNTH_TEST_ARCHIVE_URL = (
    "https://storage.googleapis.com/download.magenta.tensorflow.org/"
    "datasets/nsynth/nsynth-test.jsonwav.tar.gz"
)
NSYNTH_TEST_ARCHIVE_ETAG = "5e6f8719bf7e16ad0a00d518b78af77d"
DEFAULT_FAMILIES = ("guitar", "string", "brass", "reed", "flute", "keyboard", "vocal")

def fetch_nsynth_samples(
    *,
    archive_url: str,
    expected_etag: str,
    families: tuple[str, ...],
    samples_per_family: int,
    minimum_pitch: int,
    maximum_pitch: int,
) -> tuple[list[SelectedNsynthSample], int, str]:
    if not archive_url.startswith("https://"):
        raise ValueError("NSynth archive URL must use HTTPS")
    request = Request(archive_url, headers={"User-Agent": "AbachiWave-benchmark/1"})
    with urlopen(request, timeout=120) as response:  # noqa: S310 - fixed HTTPS default
        actual_etag = (response.headers.get("ETag") or "").strip('"')
        if actual_etag != expected_etag:
            raise RuntimeError(
                "NSynth archive ETag mismatch: "
                f"expected {expected_etag}, received {actual_etag or '<missing>'}"
            )
        with tarfile.open(fileobj=response, mode="r|gz") as archive:
            samples, inspected = select_nsynth_samples(
                archive,
                families=families,
                samples_per_family=samples_per_family,
                minimum_pitch=minimum_pitch,
                maximum_pitch=maximum_pitch,
            )
    return samples, inspected, actual_etag


def _parse_families(value: str) -> tuple[str, ...]:
    families = tuple(
        dict.fromkeys(item.strip().lower() for item in value.split(",") if item.strip())
    )
    if not families:
        raise argparse.ArgumentTypeError("at least one NSynth family is required")
    return families


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--families", type=_parse_families, default=DEFAULT_FAMILIES)
    parser.add_argument("--samples-per-family", type=int, default=2)
    parser.add_argument("--minimum-pitch", type=int, default=48)
    parser.add_argument("--maximum-pitch", type=int, default=84)
    parser.add_argument("--archive-url", default=NSYNTH_TEST_ARCHIVE_URL)
    parser.add_argument("--expected-etag", default=NSYNTH_TEST_ARCHIVE_ETAG)
    args = parser.parse_args()
    if args.samples_per_family <= 0:
        parser.error("--samples-per-family must be positive")
    if not 0 <= args.minimum_pitch <= args.maximum_pitch <= 127:
        parser.error("pitch range must satisfy 0 <= minimum <= maximum <= 127")
    return args


def main() -> int:
    args = parse_args()
    try:
        samples, inspected, archive_etag = fetch_nsynth_samples(
            archive_url=args.archive_url,
            expected_etag=args.expected_etag,
            families=args.families,
            samples_per_family=args.samples_per_family,
            minimum_pitch=args.minimum_pitch,
            maximum_pitch=args.maximum_pitch,
        )
        manifest = write_nsynth_subset(
            args.output_directory,
            samples=samples,
            archive_url=args.archive_url,
            archive_etag=archive_etag,
        )
    except (OSError, RuntimeError, tarfile.TarError, ValueError) as exc:
        print(f"NSynth subset acquisition failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Wrote {len(samples)} samples after inspecting {inspected} WAV members: "
        f"{manifest.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

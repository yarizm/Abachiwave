"""Create a deterministic synthetic WAV/MIDI dataset for benchmark pipeline smoke tests."""

from __future__ import annotations

import argparse
from pathlib import Path

from abachiwave.evaluations.audio_to_midi_fixtures import create_smoke_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_directory", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = create_smoke_dataset(args.output_directory.resolve())
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

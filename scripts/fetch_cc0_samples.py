"""Fetch CC0 drum samples into src/abachiwave/services/audio_assets/.

Source: EwonRael/BushDrum (https://github.com/EwonRael/BushDrum), which ships a
CC0 1.0 Universal license at
https://raw.githubusercontent.com/EwonRael/BushDrum/main/LICENSE.

Idempotent: files that already exist are skipped. Every download is validated
as a readable RIFF/WAVE file before being written.
"""

from __future__ import annotations

import argparse
import io
import wave
from pathlib import Path
from urllib.request import urlopen

# Logical sample name -> raw file URL on GitHub. License: CC0 1.0 Universal.
_SOURCES: dict[str, str] = {
    "kick": "https://raw.githubusercontent.com/EwonRael/BushDrum/main/kick.wav",
    "snare": "https://raw.githubusercontent.com/EwonRael/BushDrum/main/snare-m.wav",
    "closed_hat": "https://raw.githubusercontent.com/EwonRael/BushDrum/main/hihat-closed.wav",
    "open_hat": "https://raw.githubusercontent.com/EwonRael/BushDrum/main/hihat-open.wav",
}

_TARGET_DIR = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "abachiwave"
    / "services"
    / "audio_assets"
)


def _is_wav(data: bytes) -> bool:
    """Return True if data looks like a RIFF/WAVE container."""
    if len(data) < 12:
        return False
    return data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def _validate_wav(data: bytes) -> None:
    """Raise ValueError if data is not a readable WAV file."""
    if not _is_wav(data):
        raise ValueError("download is not a RIFF/WAVE file")
    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            w.getnframes()
    except (wave.Error, EOFError, ValueError) as exc:
        raise ValueError(f"download is not a readable WAV file: {exc}") from exc


def fetch(name: str, url: str) -> Path:
    """Download one sample to audio_assets/{name}.wav (skips if present)."""
    target = _TARGET_DIR / f"{name}.wav"
    if target.exists():
        print(f"skip (exists): {target}")
        return target
    with urlopen(url, timeout=30) as response:
        data = response.read()
    _validate_wav(data)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    print(f"wrote: {target} ({len(data)} bytes)")
    return target


def verify() -> int:
    """Confirm all expected samples exist and are readable WAVs. Returns total bytes."""
    total = 0
    for name in _SOURCES:
        path = _TARGET_DIR / f"{name}.wav"
        with wave.open(str(path), "rb") as w:
            print(f"ok: {path} ({path.stat().st_size} bytes, {w.getnframes()} frames)")
        total += path.stat().st_size
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch CC0 drum samples into audio_assets")
    parser.add_argument("--dry-run", action="store_true", help="print URLs without downloading")
    args = parser.parse_args()
    for name, url in _SOURCES.items():
        if args.dry_run:
            print(f"would fetch {name}: {url}")
        else:
            fetch(name, url)
    if not args.dry_run:
        total = verify()
        print(f"total: {total} bytes")


if __name__ == "__main__":
    main()

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest

from abachiwave.evaluations.remote_zip import HttpsRangeReader


def test_https_range_reader_supports_seek_read_and_cache() -> None:
    data = bytes(range(32))
    calls: list[tuple[int, int]] = []

    def fetcher(_url: str, start: int, end: int, _timeout: float, _agent: str) -> bytes:
        calls.append((start, end))
        return data[start : end + 1]

    reader = HttpsRangeReader(
        "https://example.test/archive.zip",
        size=len(data),
        chunk_size=8,
        fetcher=fetcher,
    )

    reader.seek(5)
    assert reader.read(6) == data[5:11]
    reader.seek(-3, 1)
    assert reader.read(2) == data[8:10]
    reader.seek(-2, 2)
    assert reader.read() == data[-2:]
    assert calls == [(0, 7), (8, 15), (24, 31)]


def test_https_range_reader_is_compatible_with_zipfile() -> None:
    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("fixture/one.txt", b"one" * 100)
        archive.writestr("fixture/two.txt", b"two" * 100)
    data = output.getvalue()

    def fetcher(_url: str, start: int, end: int, _timeout: float, _agent: str) -> bytes:
        return data[start : end + 1]

    reader = HttpsRangeReader(
        "https://example.test/archive.zip",
        size=len(data),
        chunk_size=64,
        fetcher=fetcher,
    )
    with zipfile.ZipFile(reader) as archive:
        assert archive.read("fixture/two.txt") == b"two" * 100


def test_https_range_reader_rejects_insecure_or_invalid_sources() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        HttpsRangeReader("http://example.test/archive.zip", size=10)
    with pytest.raises(ValueError, match="positive"):
        HttpsRangeReader("https://example.test/archive.zip", size=0)


def test_https_range_reader_rejects_short_range_response() -> None:
    reader = HttpsRangeReader(
        "https://example.test/archive.zip",
        size=10,
        chunk_size=5,
        fetcher=lambda *_args: b"short"[:4],
    )

    with pytest.raises(OSError, match="length mismatch"):
        reader.read(1)

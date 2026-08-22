from __future__ import annotations

import io
from collections.abc import Callable
from urllib.request import Request, urlopen

RangeFetcher = Callable[[str, int, int, float, str], bytes]


class HttpsRangeReader(io.RawIOBase):
    """Seekable, cached reader backed by strict HTTPS byte-range requests."""

    def __init__(
        self,
        url: str,
        *,
        size: int,
        timeout_seconds: float = 120,
        chunk_size: int = 4 * 1024 * 1024,
        user_agent: str = "AbachiWave-benchmark/1",
        fetcher: RangeFetcher | None = None,
    ) -> None:
        super().__init__()
        if not url.startswith("https://"):
            raise ValueError("range reader URL must use HTTPS")
        if size <= 0:
            raise ValueError("range reader size must be positive")
        if chunk_size <= 0:
            raise ValueError("range reader chunk size must be positive")
        self.url = url
        self.size = size
        self.timeout_seconds = timeout_seconds
        self.chunk_size = chunk_size
        self.user_agent = user_agent
        self._fetcher = fetcher or _fetch_https_range
        self._position = 0
        self._cache_start = 0
        self._cache = b""

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_CUR:
            target = self._position + offset
        elif whence == io.SEEK_END:
            target = self.size + offset
        elif whence == io.SEEK_SET:
            target = offset
        else:
            raise ValueError(f"unsupported seek mode: {whence}")
        if not 0 <= target <= self.size:
            raise ValueError(f"range reader seek outside file: {target}")
        self._position = target
        return target

    def read(self, size: int = -1) -> bytes:
        if self.closed:
            raise ValueError("I/O operation on closed range reader")
        remaining = self.size - self._position
        requested = remaining if size is None or size < 0 else min(size, remaining)
        if requested <= 0:
            return b""

        output = bytearray()
        while len(output) < requested:
            if not self._cache_contains(self._position):
                self._load_cache(self._position)
            cache_offset = self._position - self._cache_start
            available = min(len(self._cache) - cache_offset, requested - len(output))
            if available <= 0:
                raise OSError("HTTPS range reader returned an empty cache chunk")
            output.extend(self._cache[cache_offset : cache_offset + available])
            self._position += available
        return bytes(output)

    def _cache_contains(self, position: int) -> bool:
        return self._cache_start <= position < self._cache_start + len(self._cache)

    def _load_cache(self, position: int) -> None:
        start = position // self.chunk_size * self.chunk_size
        end = min(self.size - 1, start + self.chunk_size - 1)
        self._cache = self._fetcher(
            self.url,
            start,
            end,
            self.timeout_seconds,
            self.user_agent,
        )
        expected_length = end - start + 1
        if len(self._cache) != expected_length:
            raise OSError(
                "HTTPS range length mismatch: "
                f"expected {expected_length}, received {len(self._cache)}"
            )
        self._cache_start = start


def _fetch_https_range(
    url: str,
    start: int,
    end: int,
    timeout_seconds: float,
    user_agent: str,
) -> bytes:
    request = Request(
        url,
        headers={
            "Accept-Encoding": "identity",
            "Range": f"bytes={start}-{end}",
            "User-Agent": user_agent,
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        status = getattr(response, "status", None)
        content_range = response.headers.get("Content-Range") or ""
        if status != 206 or not content_range.startswith(f"bytes {start}-{end}/"):
            raise OSError(
                "server did not honor HTTPS range request: "
                f"status={status}, content-range={content_range or '<missing>'}"
            )
        return bytes(response.read())

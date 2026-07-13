from io import BytesIO
from typing import Any

from abachiwave.core.config import Settings
from abachiwave.services.storage import S3ObjectStorage, iter_storage_bytes, put_storage_file


class FakeBody:
    def __init__(self, data: bytes) -> None:
        self._buffer = BytesIO(data)
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)

    def close(self) -> None:
        self.closed = True


class FakeS3Client:
    def __init__(self, data: bytes) -> None:
        self.body = FakeBody(data)
        self.uploaded = b""

    def get_object(self, **_kwargs: Any) -> dict[str, FakeBody]:
        return {"Body": self.body}

    def upload_fileobj(
        self,
        fileobj: BytesIO,
        _bucket: str,
        _key: str,
        *,
        ExtraArgs: dict[str, str],
    ) -> None:
        assert ExtraArgs["ContentType"] == "application/octet-stream"
        self.uploaded = fileobj.read()


def test_s3_storage_streams_downloads_and_file_uploads() -> None:
    client = FakeS3Client(b"abcdefgh")
    storage = S3ObjectStorage(Settings(), client=client)

    assert list(iter_storage_bytes(storage, "asset", chunk_size=3)) == [b"abc", b"def", b"gh"]
    assert client.body.closed is True

    put_storage_file(storage, "uploaded", BytesIO(b"payload"), "application/octet-stream")
    assert client.uploaded == b"payload"


def test_s3_storage_closes_regular_download_body() -> None:
    client = FakeS3Client(b"payload")
    storage = S3ObjectStorage(Settings(), client=client)

    assert storage.get_bytes("asset") == b"payload"
    assert client.body.closed is True

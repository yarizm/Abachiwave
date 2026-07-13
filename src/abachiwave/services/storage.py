from collections.abc import Iterator
from functools import lru_cache
from typing import IO, Any, Protocol, runtime_checkable

import boto3

from abachiwave.core.config import Settings, get_settings


class ObjectStorage(Protocol):
    def put_bytes(self, key: str, data: bytes, content_type: str) -> None: ...

    def get_bytes(self, key: str) -> bytes: ...

    def delete_bytes(self, key: str) -> None: ...


@runtime_checkable
class StreamingObjectStorage(Protocol):
    def iter_bytes(self, key: str, chunk_size: int = 64 * 1024) -> Iterator[bytes]: ...

    def put_fileobj(self, key: str, fileobj: IO[bytes], content_type: str) -> None: ...


@runtime_checkable
class InventoryObjectStorage(Protocol):
    def list_keys(self, prefix: str) -> Iterator[str]: ...

    def delete_bytes(self, key: str) -> None: ...


class S3ObjectStorage:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self._bucket = settings.s3_bucket
        self._client = client or boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def get_bytes(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        body = response["Body"]
        try:
            return bytes(body.read())
        finally:
            body.close()

    def iter_bytes(self, key: str, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return _iter_streaming_body(response["Body"], chunk_size)

    def put_fileobj(self, key: str, fileobj: IO[bytes], content_type: str) -> None:
        fileobj.seek(0)
        self._client.upload_fileobj(
            fileobj,
            self._bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    def delete_bytes(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def close(self) -> None:
        self._client.close()

    def list_keys(self, prefix: str) -> Iterator[str]:
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for item in page.get("Contents", []):
                key = item.get("Key")
                if isinstance(key, str):
                    yield key


@lru_cache
def _get_s3_storage() -> S3ObjectStorage:
    return S3ObjectStorage(get_settings())


def get_object_storage() -> ObjectStorage:
    return _get_s3_storage()


def close_object_storage() -> None:
    if _get_s3_storage.cache_info().currsize:
        _get_s3_storage().close()
        _get_s3_storage.cache_clear()


def iter_storage_bytes(
    storage: ObjectStorage,
    key: str,
    chunk_size: int = 64 * 1024,
) -> Iterator[bytes]:
    if isinstance(storage, StreamingObjectStorage):
        return storage.iter_bytes(key, chunk_size)
    return iter((storage.get_bytes(key),))


def put_storage_file(
    storage: ObjectStorage,
    key: str,
    fileobj: IO[bytes],
    content_type: str,
) -> None:
    fileobj.seek(0)
    if isinstance(storage, StreamingObjectStorage):
        storage.put_fileobj(key, fileobj, content_type)
        return
    storage.put_bytes(key, fileobj.read(), content_type)


def _iter_streaming_body(body: Any, chunk_size: int) -> Iterator[bytes]:
    try:
        while chunk := body.read(chunk_size):
            yield bytes(chunk)
    finally:
        body.close()

from functools import lru_cache
from typing import Any, Protocol

import boto3

from abachiwave.core.config import Settings, get_settings


class ObjectStorage(Protocol):
    def put_bytes(self, key: str, data: bytes, content_type: str) -> None: ...

    def get_bytes(self, key: str) -> bytes: ...

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
        return bytes(body.read())

    def delete_bytes(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


@lru_cache
def _get_s3_storage() -> S3ObjectStorage:
    return S3ObjectStorage(get_settings())


def get_object_storage() -> ObjectStorage:
    return _get_s3_storage()

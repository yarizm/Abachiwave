from __future__ import annotations

import time

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from abachiwave.core.config import get_settings

WAIT_TIMEOUT_SECONDS = 60


def main() -> None:
    settings = get_settings()
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
    )
    deadline = time.monotonic() + WAIT_TIMEOUT_SECONDS
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            client.head_bucket(Bucket=settings.s3_bucket)
            print(f"Bucket {settings.s3_bucket} is ready.")
            return
        except ClientError as error:
            last_error = error
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status == 404:
                client.create_bucket(Bucket=settings.s3_bucket)
                print(f"Created bucket {settings.s3_bucket}.")
                return
        except BotoCoreError as error:
            last_error = error
        time.sleep(1)

    raise RuntimeError(
        f"Object storage did not become ready within {WAIT_TIMEOUT_SECONDS} seconds"
    ) from last_error


if __name__ == "__main__":
    main()

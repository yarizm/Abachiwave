from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import boto3
import structlog
from sqlalchemy import text

from abachiwave.core.config import Settings, get_settings
from abachiwave.core.database import engine
from abachiwave.schemas.health import DependencyReadiness, DependencyState
from abachiwave.services.task_queue import get_arq_task_queue

DependencyCheck = Callable[[], Awaitable[None]]


class ReadinessService(Protocol):
    async def check(self) -> DependencyReadiness: ...


class SystemReadinessService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def check(self) -> DependencyReadiness:
        database, redis, storage = await asyncio.gather(
            self._check_dependency("database", self._check_database),
            self._check_dependency("redis", self._check_redis),
            self._check_dependency("storage", self._check_storage),
        )
        return DependencyReadiness(database=database, redis=redis, storage=storage)

    async def _check_dependency(
        self,
        name: str,
        check: DependencyCheck,
    ) -> DependencyState:
        try:
            await asyncio.wait_for(check(), timeout=self._settings.readiness_timeout_seconds)
        except Exception as error:
            structlog.get_logger(__name__).warning(
                "readiness_dependency_unavailable",
                dependency=name,
                error_type=type(error).__name__,
            )
            return "unavailable"
        return "ok"

    async def _check_database(self) -> None:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def _check_redis(self) -> None:
        await get_arq_task_queue().ping()

    async def _check_storage(self) -> None:
        await asyncio.to_thread(self._head_bucket)

    def _head_bucket(self) -> None:
        client: Any = boto3.client(
            "s3",
            endpoint_url=self._settings.s3_endpoint_url,
            aws_access_key_id=self._settings.s3_access_key_id,
            aws_secret_access_key=self._settings.s3_secret_access_key,
        )
        try:
            client.head_bucket(Bucket=self._settings.s3_bucket)
        finally:
            client.close()


def get_readiness_service() -> ReadinessService:
    return SystemReadinessService(get_settings())

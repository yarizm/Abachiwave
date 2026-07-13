from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.models.audio import AudioUpload
from abachiwave.models.composition import ExportBundle, MidiAssetVersion
from abachiwave.models.demo import AudioDemoVersion
from abachiwave.services.storage import InventoryObjectStorage


@dataclass(frozen=True)
class StorageAuditReport:
    known_count: int
    stored_count: int
    missing_keys: list[str]
    orphan_keys: list[str]
    deleted_orphan_count: int = 0


async def audit_storage(
    session: AsyncSession,
    storage: InventoryObjectStorage,
    *,
    project_id: UUID | None = None,
    delete_orphans: bool = False,
) -> StorageAuditReport:
    known_keys = await _known_storage_keys(session, project_id)
    prefix = f"projects/{project_id}/" if project_id else "projects/"
    stored_keys = set(storage.list_keys(prefix))
    missing_keys = sorted(known_keys - stored_keys)
    orphan_keys = sorted(stored_keys - known_keys)

    deleted = 0
    if delete_orphans:
        for key in orphan_keys:
            storage.delete_bytes(key)
            deleted += 1

    return StorageAuditReport(
        known_count=len(known_keys),
        stored_count=len(stored_keys),
        missing_keys=missing_keys,
        orphan_keys=orphan_keys,
        deleted_orphan_count=deleted,
    )


async def _known_storage_keys(session: AsyncSession, project_id: UUID | None) -> set[str]:
    keys: set[str] = set()
    for model in (MidiAssetVersion, AudioDemoVersion, AudioUpload, ExportBundle):
        statement: Select[tuple[str | None]] = select(model.storage_key)
        if project_id is not None:
            statement = statement.where(model.project_id == str(project_id))
        result = await session.execute(statement)
        keys.update(key for key in result.scalars() if key)
    return keys

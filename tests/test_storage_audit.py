from collections.abc import Iterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.models.audio import AudioUpload, AudioUploadKind
from abachiwave.models.project import Project
from abachiwave.services.storage_audit import audit_storage


class InventoryStorage:
    def __init__(self, keys: set[str]) -> None:
        self.keys = keys
        self.deleted: list[str] = []

    def list_keys(self, prefix: str) -> Iterator[str]:
        return iter(sorted(key for key in self.keys if key.startswith(prefix)))

    def delete_bytes(self, key: str) -> None:
        self.deleted.append(key)
        self.keys.discard(key)


@pytest.mark.asyncio
async def test_storage_audit_reports_and_optionally_deletes_orphans(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    known_key = "projects/project/audio-uploads/known.wav"
    orphan_key = "projects/project/audio-uploads/orphan.wav"
    async with session_factory() as session:
        project = Project(id="project", name="Storage audit")
        session.add(project)
        session.add(
            AudioUpload(
                id="upload",
                project_id=project.id,
                kind=AudioUploadKind.humming,
                storage_key=known_key,
                filename="known.wav",
                content_type="audio/wav",
                size_bytes=4,
                checksum="checksum",
                duration_seconds=1,
                sample_rate=8000,
                channels=1,
                waveform_peaks=[],
            )
        )
        await session.commit()

        storage = InventoryStorage({orphan_key})
        report = await audit_storage(session, storage)
        delete_report = await audit_storage(session, storage, delete_orphans=True)

    assert report.missing_keys == [known_key]
    assert report.orphan_keys == [orphan_key]
    assert storage.deleted == [orphan_key]
    assert delete_report.deleted_orphan_count == 1

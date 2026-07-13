import argparse
import asyncio
import json
from dataclasses import asdict
from uuid import UUID

from abachiwave.core.database import AsyncSessionLocal, engine
from abachiwave.services.storage import InventoryObjectStorage, get_object_storage
from abachiwave.services.storage_audit import audit_storage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit database and object-storage consistency")
    parser.add_argument("--project-id", type=UUID)
    parser.add_argument("--delete-orphans", action="store_true")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    storage = get_object_storage()
    if not isinstance(storage, InventoryObjectStorage):
        raise RuntimeError("Configured object storage does not support inventory listing")
    try:
        async with AsyncSessionLocal() as session:
            report = await audit_storage(
                session,
                storage,
                project_id=args.project_id,
                delete_orphans=args.delete_orphans,
            )
        print(json.dumps(asdict(report), ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

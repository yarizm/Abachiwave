import argparse
import asyncio
import json
from collections.abc import Sequence
from uuid import UUID

from abachiwave.core.database import AsyncSessionLocal, engine
from abachiwave.services.provenance_audit import audit_asset_provenance


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit historical asset SongSpec provenance")
    parser.add_argument("--project-id", type=UUID)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    return asyncio.run(_run(project_id=args.project_id, apply=args.apply))


async def _run(*, project_id: UUID | None, apply: bool) -> int:
    try:
        async with AsyncSessionLocal() as session:
            report = await audit_asset_provenance(
                session,
                project_id=project_id,
                apply=apply,
            )
        print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
        remaining = report.unresolved if apply else len(report.findings)
        return 2 if remaining else 0
    finally:
        await engine.dispose()

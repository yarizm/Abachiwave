from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from abachiwave.schemas.health import ReadinessRead
from abachiwave.services.readiness import ReadinessService, get_readiness_service

router = APIRouter()
ReadinessDependency = Annotated[ReadinessService, Depends(get_readiness_service)]


@router.get("")
@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready", response_model=ReadinessRead)
async def readiness(
    response: Response,
    service: ReadinessDependency,
) -> ReadinessRead:
    dependencies = await service.check()
    is_ready = all(value == "ok" for value in dependencies.model_dump().values())
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessRead(
        status="ready" if is_ready else "not_ready",
        dependencies=dependencies,
    )

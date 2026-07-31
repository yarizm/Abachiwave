from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.core.database import get_session
from abachiwave.schemas.structure import StructureChangeRead, StructureChangeRequest
from abachiwave.services.structure import (
    StructureConflictError,
    StructureResourceNotFoundError,
    change_project_structure,
)

router = APIRouter()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]


@router.patch("/{project_id}/structure", response_model=StructureChangeRead)
async def change_project_structure_endpoint(
    project_id: UUID,
    payload: StructureChangeRequest,
    session: SessionDependency,
) -> StructureChangeRead:
    try:
        return await change_project_structure(session, project_id, payload)
    except StructureResourceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except StructureConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

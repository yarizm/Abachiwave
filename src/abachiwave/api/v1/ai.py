from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.api.pagination import PageDependency
from abachiwave.core.database import get_session
from abachiwave.models.ai import TextWorkflow
from abachiwave.schemas.ai import (
    CandidateGenerateRequest,
    CandidateSelectionRead,
    EvaluationHumanScoreCreate,
    EvaluationRunCreate,
    EvaluationRunRead,
    EvaluationSampleSetRead,
    GenerationCandidateRead,
    ProviderCapabilityRead,
)
from abachiwave.schemas.demo import GenerationRunRead
from abachiwave.services.ai_generation import (
    create_candidate_generation_run,
    list_generation_candidates,
    list_provider_capabilities,
    select_generation_candidate,
)
from abachiwave.services.demo import generation_run_to_read
from abachiwave.services.evaluations import (
    add_evaluation_human_scores,
    create_evaluation_run,
    evaluation_run_to_read,
    get_evaluation_run,
    list_evaluation_runs,
    list_evaluation_sample_sets,
)
from abachiwave.services.song_specs import project_exists
from abachiwave.services.task_queue import (
    TextEvaluationTaskQueue,
    TextGenerationTaskQueue,
    get_text_evaluation_task_queue,
    get_text_generation_task_queue,
)

router = APIRouter()
providers_router = APIRouter()
evaluations_router = APIRouter()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
QueueDependency = Annotated[TextGenerationTaskQueue, Depends(get_text_generation_task_queue)]
EvaluationQueueDependency = Annotated[
    TextEvaluationTaskQueue,
    Depends(get_text_evaluation_task_queue),
]


@providers_router.get("/capabilities", response_model=list[ProviderCapabilityRead])
async def provider_capabilities_endpoint(
    session: SessionDependency,
) -> list[ProviderCapabilityRead]:
    return await list_provider_capabilities(session)


@router.post(
    "/{project_id}/candidates/generate",
    response_model=GenerationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_candidates_endpoint(
    project_id: UUID,
    payload: CandidateGenerateRequest,
    session: SessionDependency,
    queue: QueueDependency,
) -> GenerationRunRead:
    return await enqueue_candidate_generation_or_raise(
        session=session,
        project_id=project_id,
        payload=payload,
        queue=queue,
    )


async def enqueue_candidate_generation_or_raise(
    *,
    session: AsyncSession,
    project_id: UUID,
    payload: CandidateGenerateRequest,
    queue: TextGenerationTaskQueue,
) -> GenerationRunRead:
    result = await create_candidate_generation_run(
        session=session,
        project_id=project_id,
        payload=payload,
        queue=queue,
    )
    if result.not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.not_found)
    if result.conflict or result.run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.conflict or "Candidate generation could not start",
        )
    return await generation_run_to_read(session, result.run)


@router.get("/{project_id}/candidates", response_model=list[GenerationCandidateRead])
async def list_candidates_endpoint(
    project_id: UUID,
    session: SessionDependency,
    page: PageDependency,
    workflow: Annotated[TextWorkflow | None, Query()] = None,
) -> list[GenerationCandidateRead]:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return await list_generation_candidates(
        session,
        project_id,
        workflow=workflow,
        limit=page.limit,
        offset=page.offset,
    )


@router.post(
    "/{project_id}/candidates/{candidate_id}/select",
    response_model=CandidateSelectionRead,
)
async def select_candidate_endpoint(
    project_id: UUID,
    candidate_id: UUID,
    session: SessionDependency,
) -> CandidateSelectionRead:
    result = await select_generation_candidate(session, project_id, candidate_id)
    if result.not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.not_found)
    if result.conflict or result.selection is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.conflict or "Candidate could not be selected",
        )
    return result.selection


@evaluations_router.get("/sample-sets", response_model=list[EvaluationSampleSetRead])
async def list_evaluation_sample_sets_endpoint() -> list[EvaluationSampleSetRead]:
    return list_evaluation_sample_sets()


@evaluations_router.post(
    "",
    response_model=EvaluationRunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_evaluation_run_endpoint(
    payload: EvaluationRunCreate,
    session: SessionDependency,
    queue: EvaluationQueueDependency,
) -> EvaluationRunRead:
    result = await create_evaluation_run(session=session, payload=payload, queue=queue)
    if result.not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.not_found)
    if result.conflict or result.run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.conflict or "EvaluationRun could not start",
        )
    return evaluation_run_to_read(result.run)


@evaluations_router.get("", response_model=list[EvaluationRunRead])
async def list_evaluation_runs_endpoint(
    session: SessionDependency,
    page: PageDependency,
) -> list[EvaluationRunRead]:
    return await list_evaluation_runs(session, limit=page.limit, offset=page.offset)


@evaluations_router.get("/{evaluation_run_id}", response_model=EvaluationRunRead)
async def get_evaluation_run_endpoint(
    evaluation_run_id: UUID,
    session: SessionDependency,
) -> EvaluationRunRead:
    run = await get_evaluation_run(session, evaluation_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="EvaluationRun not found")
    return evaluation_run_to_read(run)


@evaluations_router.post(
    "/{evaluation_run_id}/human-scores",
    response_model=EvaluationRunRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_evaluation_human_scores_endpoint(
    evaluation_run_id: UUID,
    payload: EvaluationHumanScoreCreate,
    session: SessionDependency,
) -> EvaluationRunRead:
    result = await add_evaluation_human_scores(session, evaluation_run_id, payload)
    if result.not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result.not_found)
    if result.conflict or result.run is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result.conflict or "Evaluation scores could not be recorded",
        )
    return evaluation_run_to_read(result.run)

from fastapi import APIRouter

from abachiwave.api.health import router as health_router
from abachiwave.api.v1.ai import evaluations_router, providers_router
from abachiwave.api.v1.ai import router as ai_router
from abachiwave.api.v1.audio import router as audio_router
from abachiwave.api.v1.comments import router as comments_router
from abachiwave.api.v1.composition import export_router
from abachiwave.api.v1.composition import router as composition_router
from abachiwave.api.v1.demo import router as demo_router
from abachiwave.api.v1.demo import tasks_router
from abachiwave.api.v1.projects import router as projects_router
from abachiwave.api.v1.revisions import router as revisions_router
from abachiwave.api.v1.structure import router as structure_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(projects_router, prefix="/api/v1/projects", tags=["projects"])
api_router.include_router(ai_router, prefix="/api/v1/projects", tags=["AI candidates"])
api_router.include_router(providers_router, prefix="/api/v1/providers", tags=["providers"])
api_router.include_router(
    evaluations_router,
    prefix="/api/v1/evaluations",
    tags=["evaluations"],
)
api_router.include_router(audio_router, prefix="/api/v1/projects", tags=["audio"])
api_router.include_router(comments_router, prefix="/api/v1/projects", tags=["comments"])
api_router.include_router(composition_router, prefix="/api/v1/projects", tags=["composition"])
api_router.include_router(demo_router, prefix="/api/v1/projects", tags=["demo"])
api_router.include_router(revisions_router, prefix="/api/v1/projects", tags=["revisions"])
api_router.include_router(structure_router, prefix="/api/v1/projects", tags=["structure"])
api_router.include_router(export_router, prefix="/api/v1/exports", tags=["exports"])
api_router.include_router(tasks_router, prefix="/api/v1/tasks", tags=["tasks"])

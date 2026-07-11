from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.models.project import Project
from abachiwave.schemas.projects import ProjectCreate, ProjectUpdate
from abachiwave.services.events import add_project_event


async def create_project(session: AsyncSession, payload: ProjectCreate) -> Project:
    project = Project(name=payload.name, description=payload.description)
    session.add(project)
    await session.flush()
    add_project_event(
        session,
        project_id=UUID(project.id),
        event_type="project.created",
        payload={"name": project.name, "status": str(project.status)},
    )
    await session.commit()
    await session.refresh(project)
    return project


async def list_projects(session: AsyncSession) -> list[Project]:
    statement: Select[tuple[Project]] = select(Project).order_by(Project.created_at.desc())
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_project(session: AsyncSession, project_id: UUID) -> Project | None:
    return await session.get(Project, str(project_id))


async def update_project(
    session: AsyncSession,
    project_id: UUID,
    payload: ProjectUpdate,
) -> Project | None:
    project = await get_project(session, project_id)
    if project is None:
        return None

    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(project, key, value)

    if updates:
        add_project_event(
            session,
            project_id=project_id,
            event_type="project.updated",
            payload={"updated_fields": sorted(updates)},
        )

    await session.commit()
    await session.refresh(project)
    return project

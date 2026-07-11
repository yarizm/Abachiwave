from pydantic import ValidationError

from abachiwave.models.project import ProjectStatus
from abachiwave.schemas.projects import ProjectCreate, ProjectUpdate


def test_project_create_normalizes_input() -> None:
    payload = ProjectCreate(name="  Demo  ", description="  ")

    assert payload.name == "Demo"
    assert payload.description is None


def test_project_create_rejects_blank_name() -> None:
    try:
        ProjectCreate(name=" ")
    except ValidationError as exc:
        assert "name must not be blank" in str(exc)
    else:
        raise AssertionError("blank project name should fail validation")


def test_project_update_accepts_archive_status() -> None:
    payload = ProjectUpdate(status=ProjectStatus.archived)

    assert payload.status == ProjectStatus.archived

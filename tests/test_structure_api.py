from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from abachiwave.models.composition import LyricsVersion
from abachiwave.schemas.structure import StructureSectionInput
from abachiwave.services.storage import get_object_storage
from abachiwave.services.structure import _remap_lyrics


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(self, key: str, data: bytes, _content_type: str) -> None:
        self.objects[key] = data

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def delete_bytes(self, key: str) -> None:
        self.objects.pop(key, None)


@pytest_asyncio.fixture
async def structure_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    storage = MemoryStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.pop(get_object_storage, None)


async def _create_complete_asset_chain(client: AsyncClient) -> tuple[str, dict[str, Any]]:
    project_response = await client.post("/api/v1/projects", json={"name": "Timeline Project"})
    assert project_response.status_code == 201
    project_id = str(UUID(project_response.json()["id"]))
    intake_response = await client.post(
        f"/api/v1/projects/{project_id}/intake",
        json={
            "idea": (
                "Chinese indie rock song about riding home late at night. "
                "Verse restrained and lonely, chorus lifting and hopeful. "
                "128 BPM, E major, 4/4, 3:30, standard structure."
            )
        },
    )
    song_spec_response = await client.post(
        f"/api/v1/projects/{project_id}/song-spec/generate",
        json={"intake_id": intake_response.json()["intake_id"]},
    )
    approve_response = await client.post(
        f"/api/v1/projects/{project_id}/song-specs/{song_spec_response.json()['id']}/approve"
    )
    assert approve_response.status_code == 200
    song_spec = approve_response.json()

    lyrics_response = await client.post(
        f"/api/v1/projects/{project_id}/lyrics/generate",
        json={"song_spec_id": song_spec["id"]},
    )
    assert lyrics_response.status_code == 201
    lyrics = lyrics_response.json()
    chords_response = await client.post(
        f"/api/v1/projects/{project_id}/chords/generate",
        json={"song_spec_id": song_spec["id"], "lyrics_version_id": lyrics["id"]},
    )
    assert chords_response.status_code == 201
    chords = chords_response.json()
    midi_response = await client.post(
        f"/api/v1/projects/{project_id}/midi/generate",
        json={
            "song_spec_id": song_spec["id"],
            "lyrics_version_id": lyrics["id"],
            "chord_version_id": chords["id"],
        },
    )
    assert midi_response.status_code == 201
    arrangement_response = await client.post(
        f"/api/v1/projects/{project_id}/arrangement/generate",
        json={
            "song_spec_id": song_spec["id"],
            "lyrics_version_id": lyrics["id"],
            "chord_version_id": chords["id"],
            "midi_asset_ids": [asset["id"] for asset in midi_response.json()],
        },
    )
    assert arrangement_response.status_code == 201
    return project_id, song_spec


@pytest.mark.asyncio
async def test_structure_preview_and_apply_propagates_stable_section_ids(
    structure_client: AsyncClient,
) -> None:
    project_id, song_spec = await _create_complete_asset_chain(structure_client)
    original_sections = song_spec["song_spec"]["structure_sections"]
    assert len(original_sections) >= 3
    proposed = [
        original_sections[1],
        {
            "section_id": original_sections[0]["section_id"],
            "label": "Cold Open",
        },
        {
            "section_id": "lift-copy",
            "label": "Lift",
            "source_section_id": original_sections[1]["section_id"],
        },
        *original_sections[2:-1],
    ]
    request = {"source_song_spec_id": song_spec["id"], "sections": proposed}

    before = {
        "song_specs": len(
            (await structure_client.get(f"/api/v1/projects/{project_id}/song-specs")).json()
        ),
        "lyrics": len((await structure_client.get(f"/api/v1/projects/{project_id}/lyrics")).json()),
        "chords": len((await structure_client.get(f"/api/v1/projects/{project_id}/chords")).json()),
        "arrangements": len(
            (await structure_client.get(f"/api/v1/projects/{project_id}/arrangements")).json()
        ),
    }
    preview_response = await structure_client.patch(
        f"/api/v1/projects/{project_id}/structure",
        json=request,
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["status"] == "preview"
    assert preview["created_versions"] == []
    assert preview["impact"]["reordered"] is True
    assert preview["impact"]["requires_midi_regeneration"] is True
    assert {item["section_id"] for item in preview["impact"]["added_sections"]} == {"lift-copy"}
    assert preview["impact"]["renamed_sections"][0]["after"] == "Cold Open"

    after_preview = {
        "song_specs": len(
            (await structure_client.get(f"/api/v1/projects/{project_id}/song-specs")).json()
        ),
        "lyrics": len((await structure_client.get(f"/api/v1/projects/{project_id}/lyrics")).json()),
        "chords": len((await structure_client.get(f"/api/v1/projects/{project_id}/chords")).json()),
        "arrangements": len(
            (await structure_client.get(f"/api/v1/projects/{project_id}/arrangements")).json()
        ),
    }
    assert after_preview == before

    apply_response = await structure_client.patch(
        f"/api/v1/projects/{project_id}/structure",
        json={**request, "preview_id": preview["preview_id"]},
    )
    assert apply_response.status_code == 200
    applied = apply_response.json()
    assert applied["status"] == "applied"
    assert {item["asset_type"] for item in applied["created_versions"]} == {
        "song_spec",
        "lyrics",
        "chords",
        "arrangement",
    }

    expected_ids = [section["section_id"] for section in proposed]
    song_specs = (await structure_client.get(f"/api/v1/projects/{project_id}/song-specs")).json()
    assert song_specs[0]["status"] == "approved"
    assert song_specs[1]["status"] == "superseded"
    assert [
        section["section_id"] for section in song_specs[0]["song_spec"]["structure_sections"]
    ] == expected_ids
    for endpoint, key in (
        ("lyrics", "sections"),
        ("chords", "sections"),
        ("arrangements", "arrangement_plan"),
    ):
        versions = (await structure_client.get(f"/api/v1/projects/{project_id}/{endpoint}")).json()
        sections = versions[0][key]
        if endpoint == "arrangements":
            sections = sections["sections"]
        assert [section["section_id"] for section in sections] == expected_ids
        assert versions[0]["parent_version_id"] == versions[1]["id"]

    midi_assets = (await structure_client.get(f"/api/v1/projects/{project_id}/midi-assets")).json()
    assert len(midi_assets) == 3
    second_apply = await structure_client.patch(
        f"/api/v1/projects/{project_id}/structure",
        json={**request, "preview_id": preview["preview_id"]},
    )
    assert second_apply.status_code == 409

    stale_tree = (await structure_client.get(f"/api/v1/projects/{project_id}/assets")).json()
    assert set(stale_tree["missing_prerequisites"]) == {
        "midi_chord",
        "midi_melody",
        "midi_hook",
        "arrangement",
    }
    blocked_export = await structure_client.post(
        f"/api/v1/projects/{project_id}/exports",
        json={},
    )
    assert blocked_export.status_code == 409
    assert set(blocked_export.json()["detail"]["missing"]) == {
        "midi_chord",
        "midi_melody",
        "midi_hook",
        "arrangement",
    }
    blocked_demo = await structure_client.post(
        f"/api/v1/projects/{project_id}/demo/generate",
        json={},
    )
    assert blocked_demo.status_code == 409

    current_song_spec = song_specs[0]
    current_lyrics = (await structure_client.get(f"/api/v1/projects/{project_id}/lyrics")).json()[0]
    current_chords = (await structure_client.get(f"/api/v1/projects/{project_id}/chords")).json()[0]
    regenerated_midi_response = await structure_client.post(
        f"/api/v1/projects/{project_id}/midi/generate",
        json={
            "song_spec_id": current_song_spec["id"],
            "lyrics_version_id": current_lyrics["id"],
            "chord_version_id": current_chords["id"],
        },
    )
    assert regenerated_midi_response.status_code == 201
    regenerated_midi = regenerated_midi_response.json()
    midi_ready_tree = (await structure_client.get(f"/api/v1/projects/{project_id}/assets")).json()
    assert midi_ready_tree["missing_prerequisites"] == ["arrangement"]

    regenerated_arrangement_response = await structure_client.post(
        f"/api/v1/projects/{project_id}/arrangement/generate",
        json={
            "song_spec_id": current_song_spec["id"],
            "lyrics_version_id": current_lyrics["id"],
            "chord_version_id": current_chords["id"],
            "midi_asset_ids": [asset["id"] for asset in regenerated_midi],
        },
    )
    assert regenerated_arrangement_response.status_code == 201
    ready_tree = (await structure_client.get(f"/api/v1/projects/{project_id}/assets")).json()
    assert ready_tree["missing_prerequisites"] == []
    export_response = await structure_client.post(
        f"/api/v1/projects/{project_id}/exports",
        json={},
    )
    assert export_response.status_code == 201


@pytest.mark.asyncio
async def test_structure_requires_current_approved_song_spec(
    structure_client: AsyncClient,
) -> None:
    project_response = await structure_client.post(
        "/api/v1/projects", json={"name": "No Approved Spec"}
    )
    project_id = project_response.json()["id"]
    response = await structure_client.patch(
        f"/api/v1/projects/{project_id}/structure",
        json={
            "source_song_spec_id": "00000000-0000-0000-0000-000000000000",
            "sections": [{"section_id": "verse", "label": "Verse"}],
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_structure_rejects_noop_preview(structure_client: AsyncClient) -> None:
    project_id, song_spec = await _create_complete_asset_chain(structure_client)
    response = await structure_client.patch(
        f"/api/v1/projects/{project_id}/structure",
        json={
            "source_song_spec_id": song_spec["id"],
            "sections": song_spec["song_spec"]["structure_sections"],
        },
    )
    assert response.status_code == 409
    versions = (await structure_client.get(f"/api/v1/projects/{project_id}/song-specs")).json()
    assert len(versions) == 1


def test_remap_lyrics_matches_legacy_underscore_section_ids() -> None:
    """Legacy sections slugged with underscores must still match hyphen targets
    from build_structure_sections when the structure change is applied."""
    version = LyricsVersion(
        id=str(uuid4()),
        project_id=str(uuid4()),
        song_spec_id=str(uuid4()),
        version_number=1,
        sections=[
            {
                "section_id": "pre_chorus",
                "label": "Pre Chorus",
                "text": "hello",
                "lines": [{"line_id": "line-1", "text": "hello", "rhyme_label": None}],
            }
        ],
        hook_candidates=[],
    )
    targets = [StructureSectionInput(section_id="pre-chorus", label="Pre-Chorus")]

    remapped = _remap_lyrics(version, targets)

    assert remapped[0].section_id == "pre-chorus"
    assert remapped[0].text == "hello"
    assert "Draft pending" not in remapped[0].text

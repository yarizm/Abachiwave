from collections.abc import AsyncIterator
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from abachiwave.schemas.composition import LyricSection, LyricsUpdate


@pytest_asyncio.fixture
async def lyrics_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def _create_approved_song_spec(client: AsyncClient) -> tuple[str, dict[str, object]]:
    project_response = await client.post(
        "/api/v1/projects",
        json={"name": "Structured Lyrics"},
    )
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
    return project_id, approve_response.json()


def test_legacy_lyric_text_builds_stable_lines_and_metrics() -> None:
    first = LyricSection(
        section_id="verse",
        label="Verse",
        text="We carry fire\n夜色落下",
    )
    second = LyricSection(
        section_id="verse",
        label="Verse",
        text="We carry fire\n夜色落下",
    )

    assert [line.line_id for line in first.lines] == [line.line_id for line in second.lines]
    assert first.lines[0].character_count == 11
    assert first.lines[0].syllable_count == 4
    assert first.lines[0].rhyme_key == "ire"
    assert first.lines[1].syllable_count == 4
    assert first.lines[1].rhyme_key == "下"
    assert first.lines[1].stress_positions == [1, 3]


def test_structured_lyric_lines_are_authoritative_over_legacy_text() -> None:
    section = LyricSection.model_validate(
        {
            "section_id": "chorus",
            "label": "Chorus",
            "text": "stale compatibility text",
            "lines": [
                {"line_id": "chorus-line-1", "text": "Current controlled line"},
                {"line_id": "chorus-line-2", "text": "Second controlled line"},
            ],
        }
    )

    assert section.text == "Current controlled line\nSecond controlled line"
    assert [line.line_id for line in section.lines] == [
        "chorus-line-1",
        "chorus-line-2",
    ]


def test_lyrics_update_rejects_duplicate_line_ids() -> None:
    with pytest.raises(ValidationError, match="line IDs must be unique"):
        LyricsUpdate.model_validate(
            {
                "sections": [
                    {
                        "section_id": "verse",
                        "label": "Verse",
                        "text": "One",
                        "lines": [{"line_id": "same", "text": "One"}],
                    },
                    {
                        "section_id": "chorus",
                        "label": "Chorus",
                        "text": "Two",
                        "lines": [{"line_id": "same", "text": "Two"}],
                    },
                ]
            }
        )


@pytest.mark.asyncio
async def test_rewrite_preview_then_accept_line_creates_one_new_version(
    lyrics_client: AsyncClient,
) -> None:
    project_id, song_spec = await _create_approved_song_spec(lyrics_client)
    generated_response = await lyrics_client.post(
        f"/api/v1/projects/{project_id}/lyrics/generate",
        json={"song_spec_id": song_spec["id"]},
    )
    assert generated_response.status_code == 201
    generated = generated_response.json()
    assert generated["schema_version"] == 2
    assert all(section["lines"] for section in generated["sections"])
    source_line = generated["sections"][0]["lines"][0]

    preview_response = await lyrics_client.post(
        f"/api/v1/projects/{project_id}/lyrics/{generated['id']}/rewrite",
        json={
            "scope": "line",
            "action": "expand",
            "line_id": source_line["line_id"],
            "instruction": "bring the streetlights closer",
            "banned_phrases": ["trace"],
            "preferred_terms": ["follow"],
        },
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["source_lyrics_id"] == generated["id"]
    assert len(preview["changes"]) == 1
    change = preview["changes"][0]
    assert change["line_id"] == source_line["line_id"]
    assert change["after"]["line_id"] == source_line["line_id"]
    assert "trace" in preview["detected_banned_phrases"]
    assert {segment["kind"] for segment in change["diff"]} >= {"delete", "insert"}

    versions_before_accept = (
        await lyrics_client.get(f"/api/v1/projects/{project_id}/lyrics")
    ).json()
    assert len(versions_before_accept) == 1

    accepted_response = await lyrics_client.patch(
        f"/api/v1/projects/{project_id}/lyrics/{generated['id']}",
        json={
            "sections": preview["candidate_sections"],
            "hook_candidates": generated["hook_candidates"],
        },
    )
    assert accepted_response.status_code == 200
    accepted = accepted_response.json()
    assert accepted["version_number"] == 2
    assert accepted["parent_version_id"] == generated["id"]
    assert accepted["sections"][0]["lines"][0]["line_id"] == source_line["line_id"]
    assert "bring the streetlights closer" in accepted["sections"][0]["text"]


@pytest.mark.asyncio
async def test_rewrite_validates_targets_without_creating_versions(
    lyrics_client: AsyncClient,
) -> None:
    project_id, song_spec = await _create_approved_song_spec(lyrics_client)
    generated = (
        await lyrics_client.post(
            f"/api/v1/projects/{project_id}/lyrics/generate",
            json={"song_spec_id": song_spec["id"]},
        )
    ).json()

    missing_line_response = await lyrics_client.post(
        f"/api/v1/projects/{project_id}/lyrics/{generated['id']}/rewrite",
        json={
            "scope": "line",
            "action": "rewrite",
            "line_id": "missing-line",
        },
    )
    assert missing_line_response.status_code == 404

    section_response = await lyrics_client.post(
        f"/api/v1/projects/{project_id}/lyrics/{generated['id']}/rewrite",
        json={
            "scope": "section",
            "action": "change_rhyme",
            "section_id": generated["sections"][0]["section_id"],
            "rhyme_ending": "home",
            "rhyme_label": "A",
        },
    )
    assert section_response.status_code == 200
    section_preview = section_response.json()
    assert len(section_preview["changes"]) == len(generated["sections"][0]["lines"])
    assert all(change["after"]["rhyme_label"] == "A" for change in section_preview["changes"])
    versions = (await lyrics_client.get(f"/api/v1/projects/{project_id}/lyrics")).json()
    assert len(versions) == 1

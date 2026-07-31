from collections.abc import AsyncIterator
from io import BytesIO
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from mido import MidiFile

from abachiwave.services import composition as composition_service
from abachiwave.services.storage import get_object_storage


class MemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data
        self.content_types[key] = content_type

    def get_bytes(self, key: str) -> bytes:
        return self.objects[key]

    def delete_bytes(self, key: str) -> None:
        self.objects.pop(key, None)
        self.content_types.pop(key, None)


@pytest_asyncio.fixture
async def client_with_storage(app: FastAPI) -> AsyncIterator[tuple[AsyncClient, MemoryStorage]]:
    storage = MemoryStorage()
    app.dependency_overrides[get_object_storage] = lambda: storage
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client, storage
    app.dependency_overrides.pop(get_object_storage, None)


async def _create_project(client: AsyncClient) -> str:
    response = await client.post("/api/v1/projects", json={"name": "Composition Project"})
    assert response.status_code == 201
    return str(UUID(response.json()["id"]))


async def _create_song_spec(client: AsyncClient, *, approve: bool) -> tuple[str, dict[str, object]]:
    project_id = await _create_project(client)
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
    assert intake_response.status_code == 201
    generate_response = await client.post(
        f"/api/v1/projects/{project_id}/song-spec/generate",
        json={"intake_id": intake_response.json()["intake_id"]},
    )
    assert generate_response.status_code == 200
    song_spec = generate_response.json()
    if approve:
        approve_response = await client.post(
            f"/api/v1/projects/{project_id}/song-specs/{song_spec['id']}/approve"
        )
        assert approve_response.status_code == 200
        song_spec = approve_response.json()
    return project_id, song_spec


@pytest.mark.asyncio
async def test_unapproved_song_spec_cannot_generate_lyrics(
    client_with_storage: tuple[AsyncClient, MemoryStorage],
) -> None:
    client, _storage = client_with_storage
    project_id, song_spec = await _create_song_spec(client, approve=False)

    response = await client.post(
        f"/api/v1/projects/{project_id}/lyrics/generate",
        json={"song_spec_id": song_spec["id"]},
    )

    assert response.status_code == 409
    assert response.headers["X-Error-Code"] == "song_spec_not_approved"
    assert response.headers["X-Error-Hint"] == "approve_song_spec"


@pytest.mark.asyncio
async def test_lyrics_and_chords_create_editable_versions(
    client_with_storage: tuple[AsyncClient, MemoryStorage],
) -> None:
    client, _storage = client_with_storage
    project_id, song_spec = await _create_song_spec(client, approve=True)

    lyrics_response = await client.post(
        f"/api/v1/projects/{project_id}/lyrics/generate",
        json={"song_spec_id": song_spec["id"]},
    )
    assert lyrics_response.status_code == 201
    lyrics = lyrics_response.json()
    assert lyrics["version_number"] == 1
    assert len(lyrics["sections"]) >= 3
    assert lyrics["hook_candidates"]

    edited_lyrics_response = await client.patch(
        f"/api/v1/projects/{project_id}/lyrics/{lyrics['id']}",
        json={
            "sections": [
                {
                    **lyrics["sections"][0],
                    "text": "A revised opening line\nA revised second line",
                }
            ],
            "hook_candidates": lyrics["hook_candidates"],
        },
    )
    assert edited_lyrics_response.status_code == 200
    edited_lyrics = edited_lyrics_response.json()
    assert edited_lyrics["version_number"] == 2
    assert edited_lyrics["parent_version_id"] == lyrics["id"]

    chords_response = await client.post(
        f"/api/v1/projects/{project_id}/chords/generate",
        json={"song_spec_id": song_spec["id"], "lyrics_version_id": edited_lyrics["id"]},
    )
    assert chords_response.status_code == 201
    chords = chords_response.json()
    assert chords["schema_version"] == 2
    assert chords["sections"][0]["chords"] == ["E", "B", "C#m", "A"]
    first_event = chords["sections"][0]["measures"][0]["events"][0]
    assert first_event["symbol"] == "E"
    assert first_event["roman_numeral"] == "I"
    assert first_event["nashville_number"] == "1"
    assert first_event["midi_notes"]

    second_chords_response = await client.post(
        f"/api/v1/projects/{project_id}/chords/generate",
        json={"song_spec_id": song_spec["id"], "lyrics_version_id": edited_lyrics["id"]},
    )
    assert second_chords_response.status_code == 201
    assert second_chords_response.json()["sections"] == chords["sections"]

    edited_chords_response = await client.patch(
        f"/api/v1/projects/{project_id}/chords/{chords['id']}",
        json={
            "sections": [
                {
                    "section_id": "verse",
                    "label": "Verse",
                    "bars": 4,
                    "chords": ["E", "A", "B", "E"],
                }
            ]
        },
    )
    assert edited_chords_response.status_code == 200
    edited_chords = edited_chords_response.json()
    assert edited_chords["version_number"] == 3
    assert edited_chords["parent_version_id"] == chords["id"]

    lyrics_list_response = await client.get(f"/api/v1/projects/{project_id}/lyrics")
    chords_list_response = await client.get(f"/api/v1/projects/{project_id}/chords")
    assert [item["version_number"] for item in lyrics_list_response.json()] == [2, 1]
    assert [item["version_number"] for item in chords_list_response.json()] == [3, 2, 1]

    events_response = await client.get(f"/api/v1/projects/{project_id}/events")
    assert events_response.status_code == 200
    event_types = {event["event_type"] for event in events_response.json()}
    assert {
        "lyrics.generated",
        "lyrics.edited",
        "chords.generated",
        "chords.edited",
    }.issubset(event_types)


@pytest.mark.asyncio
async def test_structured_chords_support_positions_inversions_and_transpose(
    client_with_storage: tuple[AsyncClient, MemoryStorage],
) -> None:
    client, _storage = client_with_storage
    project_id, song_spec = await _create_song_spec(client, approve=True)
    generated_response = await client.post(
        f"/api/v1/projects/{project_id}/chords/generate",
        json={"song_spec_id": song_spec["id"]},
    )
    assert generated_response.status_code == 201
    generated = generated_response.json()
    original_event_id = generated["sections"][0]["measures"][0]["events"][0]["event_id"]

    edit_response = await client.patch(
        f"/api/v1/projects/{project_id}/chords/{generated['id']}",
        json={
            "sections": [
                {
                    "section_id": "verse",
                    "label": "Verse",
                    "measures": [
                        {
                            "measure_number": 1,
                            "events": [
                                {
                                    "event_id": original_event_id,
                                    "measure": 1,
                                    "beat": 1,
                                    "duration_beats": 2,
                                    "symbol": "Emaj7",
                                    "inversion": 1,
                                },
                                {
                                    "event_id": "verse-measure-1-event-2",
                                    "measure": 1,
                                    "beat": 3,
                                    "duration_beats": 2,
                                    "symbol": "Aadd9",
                                },
                            ],
                        }
                    ],
                }
            ]
        },
    )
    assert edit_response.status_code == 200
    edited = edit_response.json()
    events = edited["sections"][0]["measures"][0]["events"]
    assert edited["sections"][0]["chords"] == ["Emaj7", "Aadd9"]
    assert events[0]["beat"] == 1
    assert events[0]["bass"] == "G#"
    assert events[0]["inversion"] == 1
    assert events[0]["extensions"] == ["7"]
    assert events[1]["beat"] == 3

    transpose_response = await client.post(
        f"/api/v1/projects/{project_id}/chords/{edited['id']}/transpose",
        json={"semitones": 2},
    )
    assert transpose_response.status_code == 201
    transposed = transpose_response.json()
    transposed_events = transposed["sections"][0]["measures"][0]["events"]
    assert transposed["parent_version_id"] == edited["id"]
    assert transposed["key"] == "F# major"
    assert transposed_events[0]["event_id"] == original_event_id
    assert transposed_events[0]["symbol"] == "F#maj7"
    assert transposed_events[0]["root"] == "F#"
    assert transposed_events[0]["roman_numeral"] == "I65"

    selected_response = await client.post(
        f"/api/v1/projects/{project_id}/chords/{transposed['id']}/transpose",
        json={"semitones": -1, "section_ids": ["verse"]},
    )
    assert selected_response.status_code == 201
    selected = selected_response.json()
    assert selected["key"] == "F# major"
    assert selected["sections"][0]["measures"][0]["events"][0]["root"] == "F"

    events_response = await client.get(f"/api/v1/projects/{project_id}/events")
    assert events_response.status_code == 200
    assert any(event["event_type"] == "chords.transposed" for event in events_response.json())


@pytest.mark.asyncio
async def test_invalid_chord_symbol_and_overlapping_events_return_422(
    client_with_storage: tuple[AsyncClient, MemoryStorage],
) -> None:
    client, _storage = client_with_storage
    project_id, song_spec = await _create_song_spec(client, approve=True)
    generated = (
        await client.post(
            f"/api/v1/projects/{project_id}/chords/generate",
            json={"song_spec_id": song_spec["id"]},
        )
    ).json()
    base_event = generated["sections"][0]["measures"][0]["events"][0]

    invalid_symbol = await client.patch(
        f"/api/v1/projects/{project_id}/chords/{generated['id']}",
        json={
            "sections": [
                {
                    "section_id": "verse",
                    "label": "Verse",
                    "measures": [
                        {
                            "measure_number": 1,
                            "events": [{**base_event, "symbol": "H13"}],
                        }
                    ],
                }
            ]
        },
    )
    assert invalid_symbol.status_code == 422
    assert invalid_symbol.json()["detail"] == "Unsupported chord symbol: H13"
    assert invalid_symbol.headers["X-Error-Code"] == "chord_theory_error"
    assert invalid_symbol.headers["X-Error-Hint"] == "check_chord_symbol"

    overlap = await client.patch(
        f"/api/v1/projects/{project_id}/chords/{generated['id']}",
        json={
            "sections": [
                {
                    "section_id": "verse",
                    "label": "Verse",
                    "measures": [
                        {
                            "measure_number": 1,
                            "events": [
                                {**base_event, "duration_beats": 3},
                                {
                                    **base_event,
                                    "event_id": "overlap-event",
                                    "beat": 2,
                                    "duration_beats": 2,
                                    "symbol": "A",
                                },
                            ],
                        }
                    ],
                }
            ]
        },
    )
    assert overlap.status_code == 422
    assert "overlap" in overlap.json()["detail"].lower()
    assert overlap.headers["X-Error-Code"] == "chord_theory_error"


@pytest.mark.asyncio
async def test_lyrics_version_conflict_returns_409_without_dirty_version(
    client_with_storage: tuple[AsyncClient, MemoryStorage],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _storage = client_with_storage
    project_id, song_spec = await _create_song_spec(client, approve=True)
    lyrics_response = await client.post(
        f"/api/v1/projects/{project_id}/lyrics/generate",
        json={"song_spec_id": song_spec["id"]},
    )
    assert lyrics_response.status_code == 201
    lyrics = lyrics_response.json()

    async def stale_version_number(_session: object, _project_id: object) -> int:
        return 1

    monkeypatch.setattr(
        composition_service,
        "_next_lyrics_version_number",
        stale_version_number,
    )
    conflict_response = await client.patch(
        f"/api/v1/projects/{project_id}/lyrics/{lyrics['id']}",
        headers={"X-Request-ID": "lyrics-conflict-1"},
        json={
            "sections": lyrics["sections"],
            "hook_candidates": lyrics["hook_candidates"],
        },
    )

    assert conflict_response.status_code == 409
    assert conflict_response.json() == {
        "detail": "Asset version changed concurrently; retry the request"
    }
    assert conflict_response.headers["X-Request-ID"] == "lyrics-conflict-1"
    versions_response = await client.get(f"/api/v1/projects/{project_id}/lyrics")
    assert versions_response.status_code == 200
    assert [version["version_number"] for version in versions_response.json()] == [1]


@pytest.mark.asyncio
async def test_midi_generation_listing_and_download(
    client_with_storage: tuple[AsyncClient, MemoryStorage],
) -> None:
    client, storage = client_with_storage
    project_id, song_spec = await _create_song_spec(client, approve=True)
    lyrics = (
        await client.post(
            f"/api/v1/projects/{project_id}/lyrics/generate",
            json={"song_spec_id": song_spec["id"]},
        )
    ).json()
    chords = (
        await client.post(
            f"/api/v1/projects/{project_id}/chords/generate",
            json={"song_spec_id": song_spec["id"], "lyrics_version_id": lyrics["id"]},
        )
    ).json()

    midi_response = await client.post(
        f"/api/v1/projects/{project_id}/midi/generate",
        json={
            "song_spec_id": song_spec["id"],
            "lyrics_version_id": lyrics["id"],
            "chord_version_id": chords["id"],
        },
    )

    assert midi_response.status_code == 201
    assets = midi_response.json()
    assert {asset["kind"] for asset in assets} == {"chord", "melody", "hook"}
    assert len(storage.objects) == 3
    assert all(asset["checksum"] for asset in assets)
    assert all(asset["size_bytes"] > 0 for asset in assets)

    download_response = await client.get(
        f"/api/v1/projects/{project_id}/midi-assets/{assets[0]['id']}/download"
    )
    assert download_response.status_code == 200
    assert download_response.content.startswith(b"MThd")
    MidiFile(file=BytesIO(download_response.content))

    list_response = await client.get(f"/api/v1/projects/{project_id}/midi-assets")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 3

    events_response = await client.get(f"/api/v1/projects/{project_id}/events")
    assert events_response.status_code == 200
    midi_events = [
        event for event in events_response.json() if event["event_type"] == "midi.generated"
    ]
    assert len(midi_events) == 3
    assert {event["payload"]["kind"] for event in midi_events} == {"chord", "melody", "hook"}


@pytest.mark.asyncio
async def test_composition_missing_resources_return_404(
    client_with_storage: tuple[AsyncClient, MemoryStorage],
) -> None:
    client, _storage = client_with_storage
    project_id = await _create_project(client)

    response = await client.post(
        f"/api/v1/projects/{project_id}/lyrics/generate",
        json={"song_spec_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 404

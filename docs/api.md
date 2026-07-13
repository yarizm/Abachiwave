# Abachiwave API

The API is served by FastAPI. The interactive OpenAPI document is available at `/docs`, and the machine-readable schema is available at `/openapi.json`.

## Common behavior

- Base URL: `/api/v1`
- Identifiers are UUID strings.
- JSON is used unless an endpoint explicitly accepts multipart data or returns a file.
- Every response returns `X-Request-ID`. A valid caller-provided `X-Request-ID` is preserved.
- Validation errors return `422`; missing resources return `404`; incomplete asset chains and invalid state transitions return `409`.
- Collection endpoints accept `limit` (default `50`, maximum `200`) and zero-based `offset` query parameters.

## Health

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Compatibility health check |
| GET | `/health/live` | Process liveness |
| GET | `/health/ready` | PostgreSQL, Redis, and object-storage readiness |

## Projects and SongSpec

| Method | Path | Description |
|---|---|---|
| GET, POST | `/api/v1/projects` | List or create projects |
| GET, PATCH | `/api/v1/projects/{project_id}` | Read or update a project |
| GET | `/api/v1/projects/{project_id}/review` | Read the deterministic project review |
| GET | `/api/v1/projects/{project_id}/handoff` | Read the project handoff summary |
| POST | `/api/v1/projects/{project_id}/intake` | Submit an idea and clarification answers |
| GET | `/api/v1/projects/{project_id}/intake/latest` | Read the latest intake |
| POST | `/api/v1/projects/{project_id}/song-spec/generate` | Generate a SongSpec draft |
| GET | `/api/v1/projects/{project_id}/song-specs` | List SongSpec versions |
| PATCH | `/api/v1/projects/{project_id}/song-specs/{song_spec_id}` | Create an edited SongSpec version |
| POST | `/api/v1/projects/{project_id}/song-specs/{song_spec_id}/approve` | Approve a SongSpec version |

## Composition and delivery

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/projects/{project_id}/lyrics/generate` | Generate lyrics |
| GET | `/api/v1/projects/{project_id}/lyrics` | List lyrics versions |
| PATCH | `/api/v1/projects/{project_id}/lyrics/{lyrics_version_id}` | Create an edited lyrics version |
| POST | `/api/v1/projects/{project_id}/chords/generate` | Generate a chord progression |
| GET | `/api/v1/projects/{project_id}/chords` | List chord progression versions |
| PATCH | `/api/v1/projects/{project_id}/chords/{chord_version_id}` | Create an edited chord version |
| POST | `/api/v1/projects/{project_id}/midi/generate` | Generate MIDI assets |
| GET | `/api/v1/projects/{project_id}/midi-assets` | List MIDI assets |
| GET | `/api/v1/projects/{project_id}/midi-assets/{midi_asset_id}/download` | Download MIDI |
| POST | `/api/v1/projects/{project_id}/arrangement/generate` | Generate an arrangement |
| GET | `/api/v1/projects/{project_id}/arrangements` | List arrangement versions |
| PATCH | `/api/v1/projects/{project_id}/arrangements/{arrangement_id}` | Create an edited arrangement |
| GET | `/api/v1/projects/{project_id}/assets` | Read current assets and timeline |
| POST, GET | `/api/v1/projects/{project_id}/exports` | Create or list export bundles |
| GET | `/api/v1/projects/{project_id}/exports/{export_id}` | Read an export record |
| GET | `/api/v1/exports/{export_id}/download?token=...` | Download an export ZIP |

## Demo and tasks

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/projects/{project_id}/demo/generate` | Queue Demo generation |
| GET | `/api/v1/projects/{project_id}/demos` | List Demo versions |
| GET | `/api/v1/projects/{project_id}/demos/{demo_id}` | Read Demo metadata |
| GET | `/api/v1/projects/{project_id}/demos/{demo_id}/download` | Stream WAV audio |
| GET | `/api/v1/projects/{project_id}/runs` | List project generation runs |
| GET | `/api/v1/tasks/{task_id}` | Read task state |
| POST | `/api/v1/tasks/{task_id}/retry` | Retry a failed task |
| POST | `/api/v1/tasks/{task_id}/cancel` | Cancel a queued or running task |

## Audio uploads

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/projects/{project_id}/audio-uploads` | Upload WAV multipart data |
| GET | `/api/v1/projects/{project_id}/audio-uploads` | List audio uploads |
| GET, PATCH | `/api/v1/projects/{project_id}/audio-uploads/{audio_upload_id}` | Read or update upload metadata |
| GET | `/api/v1/projects/{project_id}/audio-uploads/{audio_upload_id}/download` | Stream uploaded audio |
| POST | `/api/v1/projects/{project_id}/audio-uploads/{audio_upload_id}/extract-midi` | Queue melody MIDI extraction |

## Revisions and collaboration

| Method | Path | Description |
|---|---|---|
| POST, GET | `/api/v1/projects/{project_id}/revisions` | Plan or list revisions |
| GET | `/api/v1/projects/{project_id}/revisions/{revision_id}` | Read a revision |
| POST | `/api/v1/projects/{project_id}/revisions/{revision_id}/apply` | Apply supported revision tasks |
| POST | `/api/v1/projects/{project_id}/revisions/{revision_id}/reject` | Reject a revision |
| GET | `/api/v1/projects/{project_id}/versions/diff` | Compare two asset versions |
| POST | `/api/v1/projects/{project_id}/versions/restore` | Restore an asset as a new version |
| GET | `/api/v1/projects/{project_id}/events` | List project events |
| POST, GET | `/api/v1/projects/{project_id}/comments` | Create or list comments |
| PATCH | `/api/v1/projects/{project_id}/comments/{comment_id}` | Update comment status |

Request and response schemas remain authoritative in `/openapi.json` and the Pydantic models under `src/abachiwave/schemas`.

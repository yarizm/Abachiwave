# Abachiwave API

The API is served by FastAPI. The interactive OpenAPI document is available at `/docs`, and the machine-readable schema is available at `/openapi.json`.

## Common behavior

- Base URL: `/api/v1`
- Identifiers are UUID strings.
- JSON is used unless an endpoint explicitly accepts multipart data or returns a file.
- Every response returns `X-Request-ID`. A valid caller-provided `X-Request-ID` is preserved.
- Validation errors return `422`; missing resources return `404`; incomplete asset chains and invalid state transitions return `409`.
- Collection endpoints accept `limit` (default `50`, maximum `200`) and zero-based `offset` query parameters.

## Error response structure

Every migrated error response includes the `X-Error-Code` header with a stable machine-readable identifier (e.g. `prerequisites_missing`, `validation_failed`). When guidance is available, `X-Error-Hint` provides an actionable suggestion key (e.g. `approve_song_spec`, `retry`).

The response body follows one of two shapes:

**String detail** -- 404, 403, 413, 415, and most 409, 422 errors carry the human-readable message in a top-level `detail` string:

```json
{"detail": "Project not found"}
```

**Dict detail** -- 409 conflict errors with missing prerequisites and 422 SongSpec validation errors carry structured fields alongside the message:

```json
{
  "detail": {
    "message": "Arrangement prerequisites are missing",
    "missing": ["MIDI: chord", "MIDI: melody"],
    "error_code": "prerequisites_missing",
    "hint": "check_prerequisites"
  }
}
```

`error_code` is always present inside dict-detail bodies and as `X-Error-Code` in every migrated error response. `hint` is present only when actionable guidance applies.

**422 validation fields** -- request validation errors return a `fields` object mapping request field paths to validation messages. Field nesting uses dot notation.

```json
{
  "detail": "Validation failed",
  "error_code": "validation_failed",
  "fields": {"name": "field required", "limit": "Input should be less than or equal to 200"}
}
```

Error responses not yet migrated emit no `X-Error-Code` header; clients fall back to status-code-based handling.

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
| PATCH | `/api/v1/projects/{project_id}/structure` | Preview or apply a stable section-timeline change |

`PATCH /structure` is a two-step write. The first request supplies the current approved
`source_song_spec_id` and the complete ordered `sections` array; it stores an impact preview but
does not create asset versions. Repeating the same request with the returned `preview_id` applies
the change atomically. Apply creates a new approved SongSpec plus new lyrics, chord, and arrangement
versions when those assets exist. Existing MIDI and Demo versions remain historical and are marked
in the impact response as requiring regeneration. A stale source, changed asset set, altered
preview payload, or reused preview returns `409`.

After apply, the asset tree treats MIDI and arrangements sourced from the superseded SongSpec as
missing prerequisites. Arrangement generation, Demo generation, and ZIP export return `409` until
the required MIDI assets and arrangement have been regenerated for the new approved SongSpec.

Each section has a stable `section_id` and editable `label`. A newly duplicated section can include
`source_section_id` so copied lyrics, chords, and arrangement data follow it into the new versions.

## AI providers and candidates

Text generation is asynchronous. Creating a candidate run does not create an asset version.
Exactly one candidate from a run can be selected; selection materializes the corresponding
SongSpec, lyrics, arrangement, or revision record in one transaction.

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/providers/capabilities` | List enabled server-side Provider profiles and supported workflows |
| POST | `/api/v1/projects/{project_id}/candidates/generate` | Queue 1-3 structured candidates |
| GET | `/api/v1/projects/{project_id}/candidates` | List candidates, optionally filtered by `workflow` |
| POST | `/api/v1/projects/{project_id}/candidates/{candidate_id}/select` | Select and materialize one candidate |

Candidate workflows are `song_spec`, `lyrics`, `arrangement`, and `revision`. The request supplies
the source identifiers required by its workflow, a `provider_profile_id`, and `candidate_count`.
Provider credentials are environment-only and are never returned by the API.

The existing SongSpec, lyrics, arrangement, and revision creation endpoints remain backward
compatible. Without candidate options they return the deterministic asset immediately. When a
request explicitly includes `provider_profile_id` or `candidate_count`, it returns `202` with a
`GenerationRun`; the caller then lists and selects a candidate through the endpoints above.

## Text provider evaluations

The bundled `creative-briefs-v1` set contains 32 fixed cases across all four text workflows. It
covers Chinese Indie Rock, English Pop, instrumental soundtrack, existing-lyrics continuation,
incomplete input, and additional language/genre combinations. Evaluation work runs in Arq and
stores schema validity, constraint adherence, section completeness, duplicate ratio, Provider
usage, and anonymous A/B pairs. Private A/B assignments are not returned by the API.

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/evaluations/sample-sets` | List fixed evaluation sets and coverage |
| POST | `/api/v1/evaluations` | Queue a Provider/Prompt evaluation for one workflow |
| GET | `/api/v1/evaluations` | List evaluation runs |
| GET | `/api/v1/evaluations/{evaluation_run_id}` | Read metrics and anonymous A/B pairs |
| POST | `/api/v1/evaluations/{evaluation_run_id}/human-scores` | Record blind theme/editability ratings |

## Composition and delivery

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/projects/{project_id}/lyrics/generate` | Generate lyrics |
| GET | `/api/v1/projects/{project_id}/lyrics` | List lyrics versions |
| PATCH | `/api/v1/projects/{project_id}/lyrics/{lyrics_version_id}` | Create an edited lyrics version |
| POST | `/api/v1/projects/{project_id}/lyrics/{lyrics_version_id}/rewrite` | Preview a deterministic line, section, or full-lyrics rewrite |
| POST | `/api/v1/projects/{project_id}/chords/generate` | Generate a chord progression |
| GET | `/api/v1/projects/{project_id}/chords` | List chord progression versions |
| PATCH | `/api/v1/projects/{project_id}/chords/{chord_version_id}` | Create an edited chord version |
| POST | `/api/v1/projects/{project_id}/chords/{chord_version_id}/preview` | Validate an unsaved progression and return theory/playback data without creating a version |
| POST | `/api/v1/projects/{project_id}/chords/{chord_version_id}/transpose` | Create a transposed full-song or selected-section version |
| POST | `/api/v1/projects/{project_id}/midi/generate` | Generate MIDI assets |
| POST | `/api/v1/projects/{project_id}/midi/transform` | Create a transformed MIDI version |
| GET | `/api/v1/projects/{project_id}/midi-assets` | List MIDI assets |
| PATCH | `/api/v1/projects/{project_id}/midi-assets/{midi_asset_id}` | Save edited notes as a new MIDI version |
| GET | `/api/v1/projects/{project_id}/midi-assets/{midi_asset_id}/download` | Download MIDI |
| POST | `/api/v1/projects/{project_id}/arrangement/generate` | Generate an arrangement |
| GET | `/api/v1/projects/{project_id}/arrangements` | List arrangement versions |
| PATCH | `/api/v1/projects/{project_id}/arrangements/{arrangement_id}` | Create an edited arrangement |
| GET | `/api/v1/projects/{project_id}/assets` | Read current assets and timeline |
| POST, GET | `/api/v1/projects/{project_id}/exports` | Create or list export bundles |
| GET | `/api/v1/projects/{project_id}/exports/{export_id}` | Read an export record |
| GET | `/api/v1/exports/{export_id}/download?token=...` | Download an export ZIP |

Lyrics schema version 2 stores each section as controlled `lines` with a stable `line_id`, text,
optional `rhyme_label`, and computed character, word, syllable, rhyme, and stress hints. The legacy
section `text` field remains synchronized for existing clients and exports.

`POST /lyrics/{lyrics_version_id}/rewrite` is preview-only and never creates or mutates a version.
The request selects `line`, `section`, or `all` scope and one of `rewrite`, `expand`, `compress`,
`change_rhyme`, or `adjust_tone`; it may also submit the current unsaved `sections`, avoided
phrases, and preferred vocabulary. The response returns candidate sections, changed-line records,
token-level diff segments, and warnings. A client accepts any subset into its local draft, then
uses the existing `PATCH` endpoint to create the next immutable lyrics version.

Chord schema version 2 stores `sections -> measures -> events`. Each event has a stable `event_id`,
measure/beat position, duration, chord symbol, inversion, normalized root/bass/quality, extensions,
pitch classes, MIDI playback notes, Roman numeral, Nashville number, and borrowed-chord flag. Legacy
`bars` and `chords` remain synchronized for existing exports and clients. `music21` is the only
authority for symbol validity and theory data; the browser does not parse chord text.

`POST /chords/{chord_version_id}/preview` accepts the current unsaved `sections`, validates event
bounds and overlap, and returns normalized theory data without a database write. The transpose
endpoint accepts `{ "semitones": -11..11, "section_ids"?: string[] }`; omitting `section_ids`
transposes the key and complete progression, while a selection keeps the project key and analyzes
the moved section as modal/borrowed harmony. Both save and transpose preserve immutable history.

MIDI schema version 2 stores stable `note_events`, a `tempo_map`, and a
`time_signature_map` beside the binary object. Each note includes `note_id`, optional
`section_id`, pitch, start/duration in quarter-note beats, velocity, and channel. `PATCH` accepts
the complete edited note set and creates a child version; it never mutates the source row.
`POST /midi/transform` accepts a source `midi_asset_id`, an operation (`quantize`, `transpose`,
`velocity`, `legato`, `humanize`, or `scale_snap`), and optional selected `note_ids`. Transform
results are also immutable child versions, and their downloaded MIDI file is deterministically
rebuilt from the structured data. Pre-v2 MIDI remains downloadable but has no editable piano-roll
data until regenerated or restored through a v2 editing workflow.

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

Generation runs include `provider_usage` and a stable `error_code`. Run types currently include
`demo_generation`, `audio_to_midi`, and `text_generation`. Text evaluations use their dedicated
`EvaluationRun` state rather than a project-scoped `GenerationRun`.

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

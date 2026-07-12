# Abachiwave

[![CI](https://github.com/yarizm/Abachiwave/actions/workflows/ci.yml/badge.svg)](https://github.com/yarizm/Abachiwave/actions/workflows/ci.yml)

[中文](README.md) | [English](README.en.md)

Abachiwave is an AI-assisted music creation workspace for turning rough ideas, lyrics, hummed melodies, and reference directions into editable, traceable, exportable song assets.

The repository now supports the local MVP loop:

1. Create a project and capture a song idea.
2. Clarify requirements into a structured `SongSpec`.
3. Generate and edit lyrics, chords, MIDI, and arrangement plans.
4. Generate a listenable WAV demo through the task queue.
5. Use natural-language revision requests to create local versions, compare, and restore.
6. Upload WAV humming/reference audio, view basic waveform peaks, and extract draft melody MIDI.
7. Generate a project handoff summary and export a ZIP bundle containing current assets, demos, and uploaded audio.

See [abachiwave_development_plan.md](abachiwave_development_plan.md) for the product plan and [milestone_7_development_plan.md](milestone_7_development_plan.md) for the next stabilization milestone.

## Status

Milestones 0-6 are implemented for local MVP use, and Milestone 7 engineering stabilization, real-dependency CI, browser acceptance coverage, security scans, and operations documentation are in place. The public repository protects `main` and requires Backend, Frontend, Security, Integration, and Browser checks before merging.

- FastAPI API, Pydantic v2, SQLAlchemy 2.x, and Alembic.
- Docker Compose stack with PostgreSQL, Redis, MinIO, API, worker, and web.
- Next.js + TypeScript frontend workspace.
- Persistent English/Chinese UI language setting covering navigation, forms, statuses, errors, empty states, and system-generated guidance while preserving product terms such as SongSpec, MIDI, and Demo.
- Idea Intake, clarification questions, SongSpec drafting, editing, approval, and versioning.
- Lyrics, chords, chord/melody/hook MIDI generation, editing, and download.
- Arrangement plans, asset tree, version timeline, Demo/uploaded audio, ZIP export with handoff/comments/review/events, and download tokens.
- Async demo generation, polling, retry, cancellation, waveform peaks, and browser playback.
- Revision Planner, impact preview, local apply, diff, restore, and event records.
- WAV upload, waveform peaks, playback, download, and deterministic monophonic audio-to-MIDI extraction.
- Audio upload metadata editing with kind/notes updates and archive/restore status.
- Project Review with deterministic completeness scoring, checklist items, and next actions.
- Lightweight project comments that can target the project or current assets, with open/resolved state.
- Project Handoff summary that aggregates current assets, readiness, open comments, recent activity, and Markdown notes.
- Project workspace settings for editing local metadata and archiving or restoring projects.
- Project list filtering and search for active, archived, or all local projects.
- Domain-based workspace components and Playwright coverage for desktop, mobile, transient failure recovery, and the complete browser MVP flow.
- Live/ready health checks, request IDs, structured logs, concurrent version protection, task timeouts, and orphan-object cleanup.

Generation remains deterministic and local-first: no real LLM, external music model, GPU, or ffmpeg is required.

## Requirements

- Python `>=3.12`
- `uv`
- Node.js `22+`
- Docker Desktop

## Getting Started

### Install backend dependencies

```bash
uv sync --all-groups
```

### Install frontend dependencies

```bash
cd web
npm install
```

### Run the full local stack

```bash
docker compose up -d --build
docker compose ps
```

Local services:

- API: <http://localhost:8000>
- Web: <http://localhost:3000>
- MinIO Console: <http://localhost:9001>

### Run the automated MVP smoke test

After Docker Compose is running:

```bash
uv run python scripts/smoke_mvp.py
```

The script validates the real HTTP API flow: project creation, SongSpec, lyrics/chords/MIDI, arrangement, handoff summary, export, demo waveform metadata, revision, comments, WAV upload, audio-to-melody-MIDI extraction, and readable ZIP/WAV/MIDI outputs; ZIP exports include the handoff summary, comments, Project Review, Activity events, Demo WAV, and uploaded WAV files.

To target a different API base URL:

```bash
ABACHIWAVE_API_BASE_URL=http://localhost:8000 uv run python scripts/smoke_mvp.py
```

## Common Checks

Backend:

```bash
uv run ruff check .
uv run mypy
uv run pytest
```

Frontend:

```bash
cd web
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
```

`test:e2e` expects the Docker Compose stack to be running. Restart the Web container after a host production build because the bind-mounted development server shares the `.next` directory.

## Current Limitations

- Anonymous single-user mode with no production authentication or team authorization.
- Local deterministic agents and providers; generated output is draft quality.
- WAV-only analysis with no MP3/M4A decoding, Basic Pitch, stems, or ffmpeg.
- WAV files are limited to 25 MB. `MAX_PROJECT_UPLOADS` defaults to 100 per project.
- Default Compose credentials and development servers are not suitable for public deployment.

## Development and Operations

- [Local runbook and troubleshooting](docs/runbook.md)
- [Architecture and data flows](docs/architecture.md)
- [PostgreSQL and MinIO backup/restore](docs/backup-restore.md)

## Core API Overview

- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `POST /api/v1/projects`
- `PATCH /api/v1/projects/{project_id}`
- `POST /api/v1/projects/{project_id}/intake`
- `POST /api/v1/projects/{project_id}/song-spec/generate`
- `POST /api/v1/projects/{project_id}/lyrics/generate`
- `POST /api/v1/projects/{project_id}/chords/generate`
- `POST /api/v1/projects/{project_id}/midi/generate`
- `POST /api/v1/projects/{project_id}/arrangement/generate`
- `POST /api/v1/projects/{project_id}/demo/generate`
- `POST /api/v1/projects/{project_id}/audio-uploads`
- `PATCH /api/v1/projects/{project_id}/audio-uploads/{audio_upload_id}`
- `POST /api/v1/projects/{project_id}/audio-uploads/{audio_upload_id}/extract-midi`
- `POST /api/v1/projects/{project_id}/revisions`
- `POST /api/v1/projects/{project_id}/comments`
- `POST /api/v1/projects/{project_id}/exports`
- `GET /api/v1/projects/{project_id}/review`
- `GET /api/v1/projects/{project_id}/handoff`
- `GET /api/v1/tasks/{task_id}`

The API accepts or generates `X-Request-ID` and returns it in the response headers. `/health/ready` checks PostgreSQL, Redis, and MinIO so process liveness and dependency readiness remain distinct.

## Stack

- Backend: FastAPI, Pydantic, SQLAlchemy, Alembic
- Agent/workflow: LangGraph
- Storage: PostgreSQL and MinIO/S3-compatible object storage
- Async jobs: Redis and Arq worker
- Music tooling: mido and local deterministic WAV/MIDI providers
- Frontend: Next.js, React, TypeScript

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

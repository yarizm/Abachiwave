from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.api.pagination import PageDependency
from abachiwave.core.database import get_session
from abachiwave.models.song_spec import SongSpecStatus, SongSpecVersion
from abachiwave.schemas.composition import (
    ArrangementGenerateRequest,
    ArrangementPlanVersionRead,
    ArrangementUpdate,
    AssetTreeRead,
    ChordGenerateRequest,
    ChordProgressionVersionRead,
    ChordUpdate,
    ExportBundleRead,
    ExportCreateRequest,
    LyricsGenerateRequest,
    LyricsUpdate,
    LyricsVersionRead,
    MidiAssetVersionRead,
    MidiGenerateRequest,
)
from abachiwave.services.composition import (
    chord_progression_to_read,
    edit_chord_progression_version,
    edit_lyrics_version,
    generate_chord_progression_version,
    generate_lyrics_version,
    generate_midi_asset_versions,
    get_chord_progression_version,
    get_lyrics_version,
    get_midi_asset_version,
    list_chord_progression_versions,
    list_lyrics_versions,
    list_midi_asset_versions,
    lyrics_version_to_read,
    midi_asset_to_read,
)
from abachiwave.services.delivery import (
    arrangement_plan_to_read,
    build_asset_tree,
    create_export_bundle,
    edit_arrangement_plan_version,
    export_bundle_to_read,
    generate_arrangement_plan_version,
    get_export_bundle_by_id,
    get_project_export_bundle,
    list_arrangement_plan_versions,
    list_export_bundles,
    resolve_arrangement_inputs,
    validate_export_download_token,
)
from abachiwave.services.song_specs import get_song_spec_version, project_exists
from abachiwave.services.storage import ObjectStorage, get_object_storage, iter_storage_bytes

router = APIRouter()
export_router = APIRouter()
SessionDependency = Annotated[AsyncSession, Depends(get_session)]
StorageDependency = Annotated[ObjectStorage, Depends(get_object_storage)]


@router.post(
    "/{project_id}/lyrics/generate",
    response_model=LyricsVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_lyrics_endpoint(
    project_id: UUID,
    payload: LyricsGenerateRequest,
    session: SessionDependency,
) -> LyricsVersionRead:
    song_spec = await _get_approved_song_spec_or_raise(session, project_id, payload.song_spec_id)
    version = await generate_lyrics_version(session, project_id, song_spec)
    return lyrics_version_to_read(version)


@router.get("/{project_id}/lyrics", response_model=list[LyricsVersionRead])
async def list_lyrics_endpoint(
    project_id: UUID,
    session: SessionDependency,
    page: PageDependency,
) -> list[LyricsVersionRead]:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    versions = await list_lyrics_versions(
        session,
        project_id,
        limit=page.limit,
        offset=page.offset,
    )
    return [lyrics_version_to_read(version) for version in versions]


@router.patch("/{project_id}/lyrics/{lyrics_version_id}", response_model=LyricsVersionRead)
async def edit_lyrics_endpoint(
    project_id: UUID,
    lyrics_version_id: UUID,
    payload: LyricsUpdate,
    session: SessionDependency,
) -> LyricsVersionRead:
    version = await edit_lyrics_version(session, project_id, lyrics_version_id, payload)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LyricsVersion not found")
    return lyrics_version_to_read(version)


@router.post(
    "/{project_id}/chords/generate",
    response_model=ChordProgressionVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_chords_endpoint(
    project_id: UUID,
    payload: ChordGenerateRequest,
    session: SessionDependency,
) -> ChordProgressionVersionRead:
    song_spec = await _get_approved_song_spec_or_raise(session, project_id, payload.song_spec_id)
    lyrics_version = None
    if payload.lyrics_version_id is not None:
        lyrics_version = await get_lyrics_version(session, project_id, payload.lyrics_version_id)
        if lyrics_version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="LyricsVersion not found",
            )
    version = await generate_chord_progression_version(
        session,
        project_id,
        song_spec,
        lyrics_version,
    )
    return chord_progression_to_read(version)


@router.get("/{project_id}/chords", response_model=list[ChordProgressionVersionRead])
async def list_chords_endpoint(
    project_id: UUID,
    session: SessionDependency,
    page: PageDependency,
) -> list[ChordProgressionVersionRead]:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    versions = await list_chord_progression_versions(
        session,
        project_id,
        limit=page.limit,
        offset=page.offset,
    )
    return [chord_progression_to_read(version) for version in versions]


@router.patch(
    "/{project_id}/chords/{chord_version_id}",
    response_model=ChordProgressionVersionRead,
)
async def edit_chords_endpoint(
    project_id: UUID,
    chord_version_id: UUID,
    payload: ChordUpdate,
    session: SessionDependency,
) -> ChordProgressionVersionRead:
    version = await edit_chord_progression_version(session, project_id, chord_version_id, payload)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ChordProgressionVersion not found",
        )
    return chord_progression_to_read(version)


@router.post(
    "/{project_id}/midi/generate",
    response_model=list[MidiAssetVersionRead],
    status_code=status.HTTP_201_CREATED,
)
async def generate_midi_endpoint(
    project_id: UUID,
    payload: MidiGenerateRequest,
    session: SessionDependency,
    storage: StorageDependency,
) -> list[MidiAssetVersionRead]:
    song_spec = await _get_approved_song_spec_or_raise(session, project_id, payload.song_spec_id)
    lyrics_version = None
    chord_version = None
    if payload.lyrics_version_id is not None:
        lyrics_version = await get_lyrics_version(session, project_id, payload.lyrics_version_id)
        if lyrics_version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="LyricsVersion not found",
            )
    if payload.chord_version_id is not None:
        chord_version = await get_chord_progression_version(
            session,
            project_id,
            payload.chord_version_id,
        )
        if chord_version is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ChordProgressionVersion not found",
            )
    versions = await generate_midi_asset_versions(
        session=session,
        project_id=project_id,
        song_spec=song_spec,
        lyrics_version=lyrics_version,
        chord_version=chord_version,
        kinds=payload.kinds,
        storage=storage,
    )
    return [midi_asset_to_read(version) for version in versions]


@router.get("/{project_id}/midi-assets", response_model=list[MidiAssetVersionRead])
async def list_midi_assets_endpoint(
    project_id: UUID,
    session: SessionDependency,
    page: PageDependency,
) -> list[MidiAssetVersionRead]:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    versions = await list_midi_asset_versions(
        session,
        project_id,
        limit=page.limit,
        offset=page.offset,
    )
    return [midi_asset_to_read(version) for version in versions]


@router.get("/{project_id}/midi-assets/{midi_asset_id}/download")
async def download_midi_asset_endpoint(
    project_id: UUID,
    midi_asset_id: UUID,
    session: SessionDependency,
    storage: StorageDependency,
) -> StreamingResponse:
    version = await get_midi_asset_version(session, project_id, midi_asset_id)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MidiAssetVersion not found",
        )
    try:
        data = iter_storage_bytes(storage, version.storage_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MIDI asset file not found",
        ) from exc
    return StreamingResponse(
        data,
        media_type=version.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{version.filename}"',
            "Content-Length": str(version.size_bytes),
        },
    )


async def _get_approved_song_spec_or_raise(
    session: AsyncSession,
    project_id: UUID,
    song_spec_id: UUID,
) -> SongSpecVersion:
    song_spec = await get_song_spec_version(session, project_id, song_spec_id)
    if song_spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SongSpec not found")
    if song_spec.status != SongSpecStatus.approved:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SongSpec must be approved before composition generation",
        )
    return song_spec


@router.post(
    "/{project_id}/arrangement/generate",
    response_model=ArrangementPlanVersionRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_arrangement_endpoint(
    project_id: UUID,
    payload: ArrangementGenerateRequest,
    session: SessionDependency,
) -> ArrangementPlanVersionRead:
    song_spec = await _get_approved_song_spec_or_raise(session, project_id, payload.song_spec_id)
    inputs, missing, not_found = await resolve_arrangement_inputs(
        session,
        project_id,
        song_spec,
        payload.lyrics_version_id,
        payload.chord_version_id,
        payload.midi_asset_ids,
    )
    if not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found)
    if missing or inputs is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Arrangement prerequisites are missing", "missing": missing},
        )
    version = await generate_arrangement_plan_version(session, project_id, inputs)
    return arrangement_plan_to_read(version)


@router.get("/{project_id}/arrangements", response_model=list[ArrangementPlanVersionRead])
async def list_arrangements_endpoint(
    project_id: UUID,
    session: SessionDependency,
    page: PageDependency,
) -> list[ArrangementPlanVersionRead]:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    versions = await list_arrangement_plan_versions(
        session,
        project_id,
        limit=page.limit,
        offset=page.offset,
    )
    return [arrangement_plan_to_read(version) for version in versions]


@router.patch(
    "/{project_id}/arrangements/{arrangement_id}",
    response_model=ArrangementPlanVersionRead,
)
async def edit_arrangement_endpoint(
    project_id: UUID,
    arrangement_id: UUID,
    payload: ArrangementUpdate,
    session: SessionDependency,
) -> ArrangementPlanVersionRead:
    version = await edit_arrangement_plan_version(session, project_id, arrangement_id, payload)
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ArrangementPlanVersion not found",
        )
    return arrangement_plan_to_read(version)


@router.get("/{project_id}/assets", response_model=AssetTreeRead)
async def get_asset_tree_endpoint(
    project_id: UUID,
    session: SessionDependency,
) -> AssetTreeRead:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return await build_asset_tree(session, project_id)


@router.post(
    "/{project_id}/exports",
    response_model=ExportBundleRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_export_endpoint(
    project_id: UUID,
    payload: ExportCreateRequest,
    session: SessionDependency,
    storage: StorageDependency,
) -> ExportBundleRead:
    bundle, missing, not_found = await create_export_bundle(
        session=session,
        project_id=project_id,
        arrangement_plan_id=payload.arrangement_plan_id,
        storage=storage,
    )
    if not_found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found)
    if missing or bundle is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": "Export prerequisites are missing", "missing": missing},
        )
    return export_bundle_to_read(bundle)


@router.get("/{project_id}/exports", response_model=list[ExportBundleRead])
async def list_exports_endpoint(
    project_id: UUID,
    session: SessionDependency,
    page: PageDependency,
) -> list[ExportBundleRead]:
    if not await project_exists(session, project_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    bundles = await list_export_bundles(
        session,
        project_id,
        limit=page.limit,
        offset=page.offset,
    )
    return [export_bundle_to_read(bundle) for bundle in bundles]


@router.get("/{project_id}/exports/{export_id}", response_model=ExportBundleRead)
async def get_export_endpoint(
    project_id: UUID,
    export_id: UUID,
    session: SessionDependency,
) -> ExportBundleRead:
    bundle = await get_project_export_bundle(session, project_id, export_id)
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ExportBundle not found")
    return export_bundle_to_read(bundle)


@export_router.get("/{export_id}/download")
async def download_export_endpoint(
    export_id: UUID,
    token: str,
    session: SessionDependency,
    storage: StorageDependency,
) -> StreamingResponse:
    bundle = await get_export_bundle_by_id(session, export_id)
    if bundle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ExportBundle not found")
    if not validate_export_download_token(bundle, token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid export token")
    if not bundle.storage_key or not bundle.filename:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export file not found")
    try:
        data = iter_storage_bytes(storage, bundle.storage_key)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Export file not found",
        ) from exc
    return StreamingResponse(
        data,
        media_type=bundle.content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{bundle.filename}"',
            "Content-Length": str(bundle.size_bytes or 0),
        },
    )

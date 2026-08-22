from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from abachiwave.models.audio import AudioMarker, AudioUpload
from abachiwave.schemas.audio import AudioMarkerCreate, AudioMarkerRead, AudioMarkerUpdate
from abachiwave.services.events import add_project_event


class AudioMarkerPositionError(ValueError):
    pass


def audio_marker_to_read(marker: AudioMarker) -> AudioMarkerRead:
    return AudioMarkerRead(
        id=UUID(marker.id),
        project_id=UUID(marker.project_id),
        audio_upload_id=UUID(marker.audio_upload_id),
        position_seconds=marker.position_seconds,
        label=marker.label,
        section_id=marker.section_id,
        notes=marker.notes,
        created_at=marker.created_at,
        updated_at=marker.updated_at,
    )


async def create_audio_marker(
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
    payload: AudioMarkerCreate,
) -> AudioMarker | None:
    upload = await _get_audio_upload(session, project_id, audio_upload_id)
    if upload is None:
        return None
    _validate_position(payload.position_seconds, upload.duration_seconds)
    marker = AudioMarker(
        project_id=str(project_id),
        audio_upload_id=str(audio_upload_id),
        position_seconds=payload.position_seconds,
        label=payload.label,
        section_id=payload.section_id,
        notes=payload.notes,
    )
    session.add(marker)
    await session.flush()
    add_project_event(
        session,
        project_id=project_id,
        event_type="audio.marker.created",
        payload={
            "audio_marker_id": marker.id,
            "audio_upload_id": marker.audio_upload_id,
            "position_seconds": marker.position_seconds,
        },
    )
    await session.commit()
    await session.refresh(marker)
    return marker


async def list_audio_markers(
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[AudioMarker] | None:
    upload = await _get_audio_upload(session, project_id, audio_upload_id)
    if upload is None:
        return None
    statement: Select[tuple[AudioMarker]] = (
        select(AudioMarker)
        .where(
            AudioMarker.project_id == str(project_id),
            AudioMarker.audio_upload_id == str(audio_upload_id),
        )
        .order_by(AudioMarker.position_seconds.asc(), AudioMarker.id.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_audio_marker(
    session: AsyncSession,
    project_id: UUID,
    marker_id: UUID,
) -> AudioMarker | None:
    statement: Select[tuple[AudioMarker]] = select(AudioMarker).where(
        AudioMarker.id == str(marker_id),
        AudioMarker.project_id == str(project_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def update_audio_marker(
    session: AsyncSession,
    project_id: UUID,
    marker_id: UUID,
    payload: AudioMarkerUpdate,
) -> AudioMarker | None:
    marker = await get_audio_marker(session, project_id, marker_id)
    if marker is None:
        return None
    upload = await _get_audio_upload(session, project_id, UUID(marker.audio_upload_id))
    if upload is None:
        return None

    changed_fields: set[str] = set()
    if payload.position_seconds is not None:
        _validate_position(payload.position_seconds, upload.duration_seconds)
        marker.position_seconds = payload.position_seconds
        changed_fields.add("position_seconds")
    if payload.label is not None:
        marker.label = payload.label
        changed_fields.add("label")
    if "section_id" in payload.model_fields_set:
        marker.section_id = payload.section_id
        changed_fields.add("section_id")
    if "notes" in payload.model_fields_set:
        marker.notes = payload.notes
        changed_fields.add("notes")

    if changed_fields:
        add_project_event(
            session,
            project_id=project_id,
            event_type="audio.marker.updated",
            payload={
                "audio_marker_id": marker.id,
                "audio_upload_id": marker.audio_upload_id,
                "updated_fields": sorted(changed_fields),
            },
        )
    await session.commit()
    await session.refresh(marker)
    return marker


async def delete_audio_marker(
    session: AsyncSession,
    project_id: UUID,
    marker_id: UUID,
) -> bool:
    marker = await get_audio_marker(session, project_id, marker_id)
    if marker is None:
        return False
    add_project_event(
        session,
        project_id=project_id,
        event_type="audio.marker.deleted",
        payload={
            "audio_marker_id": marker.id,
            "audio_upload_id": marker.audio_upload_id,
            "position_seconds": marker.position_seconds,
        },
    )
    await session.delete(marker)
    await session.commit()
    return True


async def _get_audio_upload(
    session: AsyncSession,
    project_id: UUID,
    audio_upload_id: UUID,
) -> AudioUpload | None:
    statement: Select[tuple[AudioUpload]] = select(AudioUpload).where(
        AudioUpload.id == str(audio_upload_id),
        AudioUpload.project_id == str(project_id),
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


def _validate_position(position_seconds: float, duration_seconds: float | None) -> None:
    if duration_seconds is None:
        raise AudioMarkerPositionError(
            "Audio duration is unavailable until normalization completes"
        )
    if position_seconds > duration_seconds + 1e-6:
        raise AudioMarkerPositionError(
            f"Marker position exceeds audio duration ({duration_seconds:.3f} seconds)"
        )

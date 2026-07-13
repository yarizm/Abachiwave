import json
from hashlib import sha256
from typing import IO
from zipfile import ZIP_DEFLATED, ZipFile

from abachiwave.models.composition import MidiAssetVersion
from abachiwave.models.project import Project
from abachiwave.schemas.composition import (
    ArrangementPlanVersionRead,
    ChordProgressionVersionRead,
    LyricsVersionRead,
)
from abachiwave.schemas.song_specs import SongSpecVersionRead
from abachiwave.services.storage import ObjectStorage, iter_storage_bytes


def write_export_archive(
    buffer: IO[bytes],
    *,
    project: Project,
    song_spec: SongSpecVersionRead,
    lyrics: LyricsVersionRead,
    chords: ChordProgressionVersionRead,
    arrangement: ArrangementPlanVersionRead,
    midi_assets: list[MidiAssetVersion],
    manifest: dict[str, object],
    storage: ObjectStorage,
) -> None:
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("README.md", _build_export_readme(project, manifest))
        archive.writestr("manifest.json", _json_text(manifest))
        archive.writestr("song-spec.json", _json_text(song_spec.model_dump(mode="json")))
        archive.writestr("lyrics.json", _json_text(lyrics.model_dump(mode="json")))
        archive.writestr("lyrics.md", _lyrics_markdown(lyrics))
        archive.writestr("chords.json", _json_text(chords.model_dump(mode="json")))
        archive.writestr("chords.md", _chords_markdown(chords))
        archive.writestr("arrangement.json", _json_text(arrangement.model_dump(mode="json")))
        archive.writestr("arrangement.md", _arrangement_markdown(arrangement))
        archive.writestr("review.json", _json_text(manifest.get("review")))
        archive.writestr("comments.json", _json_text(manifest.get("comments", [])))
        archive.writestr("comments.md", _comments_markdown(manifest.get("comments", [])))
        archive.writestr("events.json", _json_text(manifest.get("events", [])))
        archive.writestr("handoff.json", _json_text(manifest.get("handoff")))
        archive.writestr("handoff.md", _handoff_markdown(manifest))
        archive.writestr("demos.json", _json_text(manifest.get("demos", [])))
        archive.writestr("audio-uploads.json", _json_text(manifest.get("audio_uploads", [])))
        for asset in midi_assets:
            _write_storage_object(archive, f"midi/{asset.filename}", storage, asset.storage_key)
        for item in _manifest_items(manifest.get("demos", [])):
            _write_manifest_object(archive, item, storage)
        for item in _manifest_items(manifest.get("audio_uploads", [])):
            _write_manifest_object(archive, item, storage)
    buffer.seek(0)


def file_size_and_checksum(fileobj: IO[bytes]) -> tuple[int, str]:
    fileobj.seek(0)
    digest = sha256()
    size = 0
    while chunk := fileobj.read(1024 * 1024):
        size += len(chunk)
        digest.update(chunk)
    fileobj.seek(0)
    return size, digest.hexdigest()


def export_source_size(
    midi_assets: list[MidiAssetVersion],
    manifest: dict[str, object],
) -> int:
    total = sum(asset.size_bytes for asset in midi_assets)
    for key in ("demos", "audio_uploads"):
        for item in _manifest_items(manifest.get(key, [])):
            size = item.get("size_bytes")
            if isinstance(size, int):
                total += size
    return total


def _write_manifest_object(
    archive: ZipFile,
    item: dict[str, object],
    storage: ObjectStorage,
) -> None:
    archive_path = _manifest_string(item, "archive_path")
    storage_key = _manifest_string(item, "storage_key")
    if archive_path and storage_key:
        _write_storage_object(archive, archive_path, storage, storage_key)


def _write_storage_object(
    archive: ZipFile,
    archive_path: str,
    storage: ObjectStorage,
    storage_key: str,
) -> None:
    with archive.open(archive_path, mode="w") as target:
        for chunk in iter_storage_bytes(storage, storage_key):
            target.write(chunk)


def _build_export_readme(project: Project, manifest: dict[str, object]) -> str:
    exported_at = manifest.get("exported_at", "")
    return "\n".join(
        [
            f"# {project.name}",
            "",
            "Abachiwave project export.",
            "",
            f"- Project ID: `{project.id}`",
            f"- Exported at: `{exported_at}`",
            "",
            "## Contents",
            "",
            "- `song-spec.json`",
            "- `lyrics.md` / `lyrics.json`",
            "- `chords.md` / `chords.json`",
            "- `arrangement.md` / `arrangement.json`",
            "- `comments.md` / `comments.json`",
            "- `handoff.md` / `handoff.json`",
            "- `review.json`",
            "- `events.json`",
            "- `demos.json` / `demos/*.wav`",
            "- `audio-uploads.json` / `audio-uploads/*.wav`",
            "- `midi/*.mid`",
            "- `manifest.json`",
            "",
        ]
    )


def _handoff_markdown(manifest: dict[str, object]) -> str:
    handoff = manifest.get("handoff")
    if not isinstance(handoff, dict):
        return "# Handoff\n\nNo handoff summary available.\n"
    markdown = handoff.get("handoff_markdown")
    return str(markdown) if markdown else "# Handoff\n\nNo handoff summary available.\n"


def _lyrics_markdown(version: LyricsVersionRead) -> str:
    lines = [f"# Lyrics v{version.version_number}", ""]
    for section in version.sections:
        lines.extend([f"## {section.label}", "", section.text, ""])
    if version.hook_candidates:
        lines.extend(["## Hook candidates", ""])
        lines.extend([f"- {candidate.text}" for candidate in version.hook_candidates])
        lines.append("")
    return "\n".join(lines)


def _chords_markdown(version: ChordProgressionVersionRead) -> str:
    lines = [f"# Chords v{version.version_number}", ""]
    for section in version.sections:
        lines.extend(
            [
                f"## {section.label}",
                "",
                f"- Bars: {section.bars}",
                f"- Chords: {' | '.join(section.chords)}",
                "",
            ]
        )
    return "\n".join(lines)


def _arrangement_markdown(version: ArrangementPlanVersionRead) -> str:
    plan = version.arrangement_plan
    lines = [f"# Arrangement v{version.version_number}", "", plan.overview, ""]
    for section in plan.sections:
        lines.extend(
            [
                f"## {section.label}",
                "",
                f"- Energy: {section.energy_level}/10",
                f"- Instruments: {', '.join(section.instruments)}",
                f"- Notes: {section.production_notes}",
                "",
            ]
        )
    lines.extend(
        ["## Mix notes", "", plan.mix_notes, "", "## Reference notes", "", plan.reference_notes, ""]
    )
    return "\n".join(lines)


def _comments_markdown(value: object) -> str:
    comments = value if isinstance(value, list) else []
    lines = ["# Comments", ""]
    if not comments:
        lines.extend(["No comments recorded.", ""])
        return "\n".join(lines)
    for raw_comment in comments:
        if not isinstance(raw_comment, dict):
            continue
        author = raw_comment.get("author_name", "Unknown")
        status = raw_comment.get("status", "unknown")
        target_type = raw_comment.get("target_type", "project")
        target_id = raw_comment.get("target_id") or "project"
        created_at = raw_comment.get("created_at", "")
        body = raw_comment.get("body", "")
        lines.extend(
            [
                f"## {author} - {status}",
                "",
                f"- Target: `{target_type}` `{target_id}`",
                f"- Created: `{created_at}`",
                "",
                str(body),
                "",
            ]
        )
    return "\n".join(lines)


def _manifest_items(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _manifest_string(item: dict[str, object], key: str) -> str | None:
    value = item.get(key)
    return value if isinstance(value, str) else None


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)

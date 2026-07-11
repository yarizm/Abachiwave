from datetime import datetime

from abachiwave.schemas.comments import ProjectCommentRead
from abachiwave.schemas.composition import AssetReference, AssetTreeRead
from abachiwave.schemas.projects import ProjectRead
from abachiwave.schemas.review import ProjectReviewRead
from abachiwave.schemas.revisions import ProjectEventRead


def build_handoff_next_actions(
    review: ProjectReviewRead,
    open_comments: list[ProjectCommentRead],
) -> list[str]:
    actions = list(review.next_actions)
    if open_comments:
        actions.insert(0, f"Resolve {len(open_comments)} open project comment(s).")
    return actions[:8]


def build_handoff_markdown(
    *,
    project: ProjectRead,
    review: ProjectReviewRead,
    asset_tree: AssetTreeRead,
    open_comments: list[ProjectCommentRead],
    recent_events: list[ProjectEventRead],
    next_actions: list[str],
    generated_at: datetime,
) -> str:
    lines = [
        f"# {project.name} Handoff",
        "",
        f"- Project status: {project.status.value}",
        f"- Review: {review.status} ({review.score}/100)",
        f"- Generated: {generated_at.isoformat()}",
        "",
        "## Current Assets",
        _asset_line("SongSpec", asset_tree.current.song_spec),
        _asset_line("Lyrics", asset_tree.current.lyrics),
        _asset_line("Chords", asset_tree.current.chords),
        _asset_line("Arrangement", asset_tree.current.arrangement),
        _midi_line(asset_tree.current.midi_assets),
        "",
        "## Missing Prerequisites",
    ]
    if asset_tree.missing_prerequisites:
        lines.extend(f"- {item.replace('_', ' ')}" for item in asset_tree.missing_prerequisites)
    else:
        lines.append("- None")

    lines.extend(["", "## Next Actions"])
    if next_actions:
        lines.extend(f"- {action}" for action in next_actions)
    else:
        lines.append("- None")

    lines.extend(["", "## Open Comments"])
    if open_comments:
        lines.extend(
            f"- [{comment.target_type.value}] {comment.body} ({comment.author_name})"
            for comment in open_comments[:10]
        )
    else:
        lines.append("- None")

    lines.extend(["", "## Recent Activity"])
    if recent_events:
        lines.extend(
            f"- {event.created_at.isoformat()} - {event.event_type}" for event in recent_events[:12]
        )
    else:
        lines.append("- None")

    return "\n".join(lines)


def _asset_line(label: str, asset: AssetReference | None) -> str:
    if asset is None:
        return f"- {label}: missing"
    suffix = f" ({asset.kind})" if asset.kind else ""
    return f"- {label}: {asset.label}{suffix} [{asset.id}]"


def _midi_line(assets: list[AssetReference]) -> str:
    if not assets:
        return "- MIDI: missing"
    parts = [
        f"{asset.label}{f' ({asset.kind})' if asset.kind else ''} [{asset.id}]"
        for asset in assets
    ]
    return f"- MIDI: {', '.join(parts)}"

"""Unified error response contract for the API.

Provides a single ``ProblemError`` exception plus the ``ErrorCode`` and
``ErrorHint`` enumerations used by the global exception handlers in
``abachiwave.main``.

Design (see docs/plans/04-ux-improvement.md, Phase 0):

* String-detail responses keep the body ``{"detail": "<string>"}`` unchanged and
  surface ``error_code`` / ``hint`` via the ``X-Error-Code`` / ``X-Error-Hint``
  response headers. This preserves the exact-match test assertions on those
  bodies.
* Dict-detail responses add ``error_code`` and ``hint`` as sibling keys inside
  the existing ``detail`` dict, leaving the original ``message`` / ``missing``
  / ``missing_required_fields`` keys untouched.
* 422 validation errors expose a ``fields`` map (field path -> message) instead
  of the FastAPI default ``loc`` array.

The enumeration *values* are part of the public API contract: once released they
must not change. Add new members at the end only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Stable machine-readable error codes.

    The string value is what appears in the ``X-Error-Code`` response header and
    (for dict-detail bodies) the ``error_code`` key. Coarse-grained by design:
    ordinary 404s fall back to ``RESOURCE_NOT_FOUND``; precise codes exist only
    where the frontend must distinguish the next action.
    """

    RESOURCE_NOT_FOUND = "resource_not_found"
    SONG_SPEC_NOT_APPROVED = "song_spec_not_approved"
    PREREQUISITES_MISSING = "prerequisites_missing"
    ASSET_VERSION_CONFLICT = "asset_version_conflict"
    UPLOAD_TOO_LARGE = "upload_too_large"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    VALIDATION_FAILED = "validation_failed"
    CHORD_THEORY_ERROR = "chord_theory_error"
    SONG_SPEC_INCOMPLETE = "song_spec_incomplete"
    INTERNAL_ERROR = "internal_error"


class ErrorHint(StrEnum):
    """Actionable hint keys the frontend maps to localized guidance and CTAs."""

    RETRY = "retry"
    APPROVE_SONG_SPEC = "approve_song_spec"
    CHECK_PREREQUISITES = "check_prerequisites"
    TRIM_AUDIO_UNDER_25MB = "trim_audio_under_25mb"
    CHECK_FORMAT = "check_format"
    CHECK_REQUIRED_FIELDS = "check_required_fields"
    CHECK_CHORD_SYMBOL = "check_chord_symbol"
    CONTACT_SUPPORT = "contact_support"


@dataclass
class ProblemError(Exception):
    """Exception translated by the global handler into a structured response.

    Attributes:
        status_code: HTTP status code.
        error_code: Stable machine-readable code.
        detail: Human-readable message. A ``str`` keeps the body as
            ``{"detail": str}``; a ``dict`` becomes ``{"detail": {**dict,
            error_code, hint?}}``.
        hint: Optional actionable hint for frontend guidance rendering.
        fields: Field-level error map (422 responses). Keys use dot notation
            for nested paths, e.g. ``sections.0.chords.0``.
        headers: Extra response headers beyond the error-code/hint headers.
    """

    status_code: int
    error_code: ErrorCode
    detail: str | dict[str, Any]
    hint: ErrorHint | None = None
    fields: dict[str, str] | None = None
    headers: dict[str, str] = field(default_factory=dict)


__all__ = ["ErrorCode", "ErrorHint", "ProblemError"]

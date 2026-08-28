from __future__ import annotations

import json
import re
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from statistics import median
from typing import Literal

from mido import MidiFile, merge_tracks, tick2second
from pydantic import BaseModel, Field, field_validator, model_validator


@dataclass(frozen=True)
class TimedMidiNote:
    pitch: int
    onset_seconds: float
    offset_seconds: float
    velocity: int

    @property
    def duration_seconds(self) -> float:
        return self.offset_seconds - self.onset_seconds


@dataclass(frozen=True)
class NoteMatchMetrics:
    reference_notes: int
    predicted_notes: int
    onset_pitch_matches: int
    onset_pitch_offset_matches: int
    onset_aligned_matches: int
    onset_pitch_precision: float
    onset_pitch_recall: float
    onset_pitch_f1: float
    onset_pitch_offset_precision: float
    onset_pitch_offset_recall: float
    onset_pitch_offset_f1: float
    onset_mae_ms: float | None
    duration_mae_ms: float | None
    velocity_mae: float | None
    onset_aligned_pitch_mae_semitones: float | None


@dataclass(frozen=True)
class NoteTimingError:
    """Signed timing error of one onset+pitch matched note pair.

    ``duration_mae_ms`` in :class:`NoteMatchMetrics` is an absolute mean and cannot
    distinguish a systematic bias from symmetric scatter. These signed samples can.
    """

    reference_duration_seconds: float
    onset_error_seconds: float
    duration_error_seconds: float
    offset_error_seconds: float
    allowed_offset_error_seconds: float

    @property
    def offset_within_tolerance(self) -> bool:
        return abs(self.offset_error_seconds) <= self.allowed_offset_error_seconds


@dataclass(frozen=True)
class MissedNoteBreakdown:
    """Why reference notes had no predicted onset within tolerance.

    Recall alone cannot separate "the transcriber never fired here" from "the
    transcriber held one long note across several reference notes". The two call for
    different fixes, so they are counted separately. A reference note counts as
    ``merged_into_same_pitch`` when some predicted note of the same pitch covers its
    midpoint -- the pitch was found, the re-articulation was not.
    """

    reference_notes: int
    onset_matched: int
    merged_into_same_pitch: int
    covered_by_other_pitch: int
    undetected: int

    @property
    def missed(self) -> int:
        return self.reference_notes - self.onset_matched


@dataclass(frozen=True)
class SampleBenchmarkResult:
    sample_id: str
    category: str
    audio_duration_seconds: float
    latency_seconds: float
    real_time_factor: float
    metrics: NoteMatchMetrics
    reference_id: str = "primary"


@dataclass(frozen=True)
class ResourceMetrics:
    peak_cpu_percent: float | None = None
    peak_memory_mib: float | None = None


@dataclass(frozen=True)
class ThresholdViolation:
    scope: str
    metric: str
    actual: float
    comparator: Literal[">=", "<="]
    threshold: float


class DatasetMetadata(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=100)
    license: str = Field(min_length=1, max_length=200)
    license_url: str | None = Field(default=None, max_length=2000)
    source_url: str | None = Field(default=None, max_length=2000)
    reference_policy: str | None = Field(default=None, max_length=4000)
    source_archive_etag: str | None = Field(default=None, max_length=200)
    source_artifact_checksums: dict[str, str] = Field(default_factory=dict)
    synthetic: bool = False

    @field_validator("source_artifact_checksums")
    @classmethod
    def validate_source_artifact_checksums(cls, checksums: dict[str, str]) -> dict[str, str]:
        for name, checksum in checksums.items():
            if not name or len(name) > 500:
                raise ValueError("source artifact checksum names must be 1-500 characters")
            if re.fullmatch(r"(?:md5:[0-9a-f]{32}|sha256:[0-9a-f]{64})", checksum) is None:
                raise ValueError(f"invalid source artifact checksum for {name}")
        return checksums

    @model_validator(mode="after")
    def require_real_dataset_provenance(self) -> DatasetMetadata:
        if not self.synthetic and (self.license_url is None or self.source_url is None):
            raise ValueError("real datasets require license_url and source_url")
        return self


class BenchmarkReference(BaseModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    midi_path: Path
    midi_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_annotation_member: str | None = Field(default=None, max_length=2000)
    source_annotation_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )


class BenchmarkSample(BaseModel):
    id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9._-]+$")
    category: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    audio_path: Path
    reference_id: str = Field(
        default="primary",
        min_length=1,
        max_length=100,
        pattern=r"^[A-Za-z0-9._-]+$",
    )
    reference_midi_path: Path
    audio_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reference_midi_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_member: str | None = Field(default=None, max_length=2000)
    source_audio_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_annotation_member: str | None = Field(default=None, max_length=2000)
    source_annotation_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    alternative_references: list[BenchmarkReference] = Field(default_factory=list)
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_unique_reference_ids(self) -> BenchmarkSample:
        reference_ids = [self.reference_id, *(item.id for item in self.alternative_references)]
        if len(reference_ids) != len(set(reference_ids)):
            raise ValueError("reference ids must be unique within each sample")
        return self


class MetricThresholds(BaseModel):
    onset_pitch_f1_min: float | None = Field(default=None, ge=0, le=1)
    onset_pitch_offset_f1_min: float | None = Field(default=None, ge=0, le=1)
    macro_onset_pitch_f1_min: float | None = Field(default=None, ge=0, le=1)
    macro_onset_pitch_offset_f1_min: float | None = Field(default=None, ge=0, le=1)
    mean_onset_mae_ms_max: float | None = Field(default=None, ge=0)
    mean_duration_mae_ms_max: float | None = Field(default=None, ge=0)
    mean_velocity_mae_max: float | None = Field(default=None, ge=0)
    mean_onset_aligned_pitch_mae_semitones_max: float | None = Field(
        default=None,
        ge=0,
    )
    empty_result_rate_max: float | None = Field(default=None, ge=0, le=1)
    median_real_time_factor_max: float | None = Field(default=None, gt=0)
    p95_latency_seconds_max: float | None = Field(default=None, gt=0)
    peak_cpu_percent_max: float | None = Field(default=None, gt=0)
    peak_memory_mib_max: float | None = Field(default=None, gt=0)


class AudioToMidiBenchmarkManifest(BaseModel):
    schema_version: Literal[1]
    dataset: DatasetMetadata
    onset_tolerance_seconds: float = Field(default=0.05, gt=0, le=1)
    offset_tolerance_seconds: float = Field(default=0.05, gt=0, le=2)
    offset_tolerance_ratio: float = Field(default=0.2, ge=0, le=1)
    reference_selection_policy: Literal[
        "primary",
        "best_onset_pitch_offset_f1",
    ] = "primary"
    provider_params: dict[str, bool | float] = Field(default_factory=dict)
    samples: list[BenchmarkSample] = Field(min_length=1)
    thresholds: dict[str, MetricThresholds] = Field(default_factory=dict)

    @field_validator("samples")
    @classmethod
    def require_unique_sample_ids(
        cls,
        samples: list[BenchmarkSample],
    ) -> list[BenchmarkSample]:
        ids = [sample.id for sample in samples]
        if len(ids) != len(set(ids)):
            raise ValueError("sample ids must be unique")
        return samples

    @model_validator(mode="after")
    def require_known_threshold_scopes(self) -> AudioToMidiBenchmarkManifest:
        categories = {sample.category for sample in self.samples}
        unknown = set(self.thresholds) - {"overall", *categories}
        if unknown:
            raise ValueError(f"threshold scopes do not match sample categories: {sorted(unknown)}")
        category_resource_thresholds = [
            scope
            for scope, thresholds in self.thresholds.items()
            if scope != "overall"
            and (
                thresholds.peak_cpu_percent_max is not None
                or thresholds.peak_memory_mib_max is not None
            )
        ]
        if category_resource_thresholds:
            raise ValueError("container resource thresholds are only valid for the overall scope")
        return self


def load_benchmark_manifest(path: Path) -> AudioToMidiBenchmarkManifest:
    manifest_path = path.resolve()
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = AudioToMidiBenchmarkManifest.model_validate(payload)
    base_directory = manifest_path.parent
    resolved_samples = [
        sample.model_copy(
            update={
                "audio_path": _resolve_verified_file(
                    base_directory,
                    sample.audio_path,
                    sample.audio_sha256,
                ),
                "reference_midi_path": _resolve_verified_file(
                    base_directory,
                    sample.reference_midi_path,
                    sample.reference_midi_sha256,
                ),
                "alternative_references": [
                    reference.model_copy(
                        update={
                            "midi_path": _resolve_verified_file(
                                base_directory,
                                reference.midi_path,
                                reference.midi_sha256,
                            )
                        }
                    )
                    for reference in sample.alternative_references
                ],
            }
        )
        for sample in manifest.samples
    ]
    return manifest.model_copy(update={"samples": resolved_samples})


def parse_timed_midi_notes(
    data: bytes,
    *,
    programs: frozenset[int] | None = None,
) -> list[TimedMidiNote]:
    """Parse note events with absolute times, optionally keeping only some programs.

    ``programs`` filters on the MIDI program in effect on the note's channel when it
    started. Multi-instrument transcribers emit one program per detected instrument, so
    this is how a single part is isolated. The default keeps every note.
    """
    from io import BytesIO

    midi = MidiFile(file=BytesIO(data))
    ticks_per_beat = midi.ticks_per_beat or 480
    tempo = 500_000
    current_seconds = 0.0
    program: dict[int, int] = defaultdict(int)
    active: dict[tuple[int, int], list[tuple[float, int, int]]] = defaultdict(list)
    notes: list[TimedMidiNote] = []

    for message in merge_tracks(midi.tracks):
        current_seconds += tick2second(int(message.time), ticks_per_beat, tempo)
        if message.type == "set_tempo":
            tempo = int(message.tempo)
            continue
        if message.type == "program_change":
            program[message.channel] = int(message.program)
            continue
        if message.type == "note_on" and message.velocity > 0:
            active[(message.channel, message.note)].append(
                (current_seconds, message.velocity, program[message.channel])
            )
            continue
        if message.type not in {"note_off", "note_on"}:
            continue
        key = (message.channel, message.note)
        if not active[key]:
            continue
        onset_seconds, velocity, note_program = active[key].pop(0)
        if programs is not None and note_program not in programs:
            continue
        notes.append(
            TimedMidiNote(
                pitch=message.note,
                onset_seconds=onset_seconds,
                offset_seconds=max(current_seconds, onset_seconds),
                velocity=velocity,
            )
        )

    return sorted(notes, key=lambda note: (note.onset_seconds, note.pitch, note.offset_seconds))


def count_notes_by_program(data: bytes) -> dict[int, int]:
    """Count note-on events per MIDI program, for checking what a transcriber emitted."""
    from io import BytesIO

    midi = MidiFile(file=BytesIO(data))
    program: dict[int, int] = defaultdict(int)
    counts: dict[int, int] = defaultdict(int)
    for message in merge_tracks(midi.tracks):
        if message.type == "program_change":
            program[message.channel] = int(message.program)
        elif message.type == "note_on" and message.velocity > 0:
            counts[program[message.channel]] += 1
    return dict(counts)


def compare_note_sequences(
    reference: list[TimedMidiNote],
    predicted: list[TimedMidiNote],
    *,
    onset_tolerance_seconds: float = 0.05,
    offset_tolerance_seconds: float = 0.05,
    offset_tolerance_ratio: float = 0.2,
) -> NoteMatchMetrics:
    onset_pitch_pairs = _match_notes(
        reference,
        predicted,
        onset_tolerance_seconds=onset_tolerance_seconds,
        require_pitch=True,
        require_offset=False,
        offset_tolerance_seconds=offset_tolerance_seconds,
        offset_tolerance_ratio=offset_tolerance_ratio,
    )
    onset_pitch_offset_pairs = _match_notes(
        reference,
        predicted,
        onset_tolerance_seconds=onset_tolerance_seconds,
        require_pitch=True,
        require_offset=True,
        offset_tolerance_seconds=offset_tolerance_seconds,
        offset_tolerance_ratio=offset_tolerance_ratio,
    )
    onset_aligned_pairs = _match_notes(
        reference,
        predicted,
        onset_tolerance_seconds=onset_tolerance_seconds,
        require_pitch=False,
        require_offset=False,
        offset_tolerance_seconds=offset_tolerance_seconds,
        offset_tolerance_ratio=offset_tolerance_ratio,
    )
    onset_precision, onset_recall, onset_f1 = _precision_recall_f1(
        len(onset_pitch_pairs),
        len(reference),
        len(predicted),
    )
    offset_precision, offset_recall, offset_f1 = _precision_recall_f1(
        len(onset_pitch_offset_pairs),
        len(reference),
        len(predicted),
    )
    return NoteMatchMetrics(
        reference_notes=len(reference),
        predicted_notes=len(predicted),
        onset_pitch_matches=len(onset_pitch_pairs),
        onset_pitch_offset_matches=len(onset_pitch_offset_pairs),
        onset_aligned_matches=len(onset_aligned_pairs),
        onset_pitch_precision=onset_precision,
        onset_pitch_recall=onset_recall,
        onset_pitch_f1=onset_f1,
        onset_pitch_offset_precision=offset_precision,
        onset_pitch_offset_recall=offset_recall,
        onset_pitch_offset_f1=offset_f1,
        onset_mae_ms=_mean_or_none(
            [
                abs(reference[i].onset_seconds - predicted[j].onset_seconds) * 1000
                for i, j in onset_pitch_pairs
            ]
        ),
        duration_mae_ms=_mean_or_none(
            [
                abs(reference[i].duration_seconds - predicted[j].duration_seconds) * 1000
                for i, j in onset_pitch_pairs
            ]
        ),
        velocity_mae=_mean_or_none(
            [abs(reference[i].velocity - predicted[j].velocity) for i, j in onset_pitch_pairs]
        ),
        onset_aligned_pitch_mae_semitones=_mean_or_none(
            [abs(reference[i].pitch - predicted[j].pitch) for i, j in onset_aligned_pairs]
        ),
    )


def collect_note_timing_errors(
    reference: list[TimedMidiNote],
    predicted: list[TimedMidiNote],
    *,
    onset_tolerance_seconds: float = 0.05,
    offset_tolerance_seconds: float = 0.05,
    offset_tolerance_ratio: float = 0.2,
) -> list[NoteTimingError]:
    """Return signed timing errors for every onset+pitch matched pair.

    Errors are ``predicted - reference``, so a positive duration error means the
    prediction held the note too long. Unmatched reference or predicted notes are
    excluded: they are counted by recall and precision, not by timing accuracy.
    """
    pairs = _match_notes(
        reference,
        predicted,
        onset_tolerance_seconds=onset_tolerance_seconds,
        require_pitch=True,
        require_offset=False,
        offset_tolerance_seconds=offset_tolerance_seconds,
        offset_tolerance_ratio=offset_tolerance_ratio,
    )
    errors: list[NoteTimingError] = []
    for reference_index, predicted_index in pairs:
        expected = reference[reference_index]
        actual = predicted[predicted_index]
        errors.append(
            NoteTimingError(
                reference_duration_seconds=expected.duration_seconds,
                onset_error_seconds=actual.onset_seconds - expected.onset_seconds,
                duration_error_seconds=actual.duration_seconds - expected.duration_seconds,
                offset_error_seconds=actual.offset_seconds - expected.offset_seconds,
                allowed_offset_error_seconds=max(
                    offset_tolerance_seconds,
                    expected.duration_seconds * offset_tolerance_ratio,
                ),
            )
        )
    return errors


def classify_missed_reference_notes(
    reference: list[TimedMidiNote],
    predicted: list[TimedMidiNote],
    *,
    onset_tolerance_seconds: float = 0.05,
    offset_tolerance_seconds: float = 0.05,
    offset_tolerance_ratio: float = 0.2,
) -> MissedNoteBreakdown:
    """Split the recall loss into under-segmentation and outright misses.

    Onset matching here ignores pitch, so a reference note counts as matched whenever
    any predicted note starts close enough to it. The remainder are classified by what,
    if anything, covers their midpoint.
    """
    matched = {
        reference_index
        for reference_index, _predicted_index in _match_notes(
            reference,
            predicted,
            onset_tolerance_seconds=onset_tolerance_seconds,
            require_pitch=False,
            require_offset=False,
            offset_tolerance_seconds=offset_tolerance_seconds,
            offset_tolerance_ratio=offset_tolerance_ratio,
        )
    }
    merged = covered = undetected = 0
    for reference_index, expected in enumerate(reference):
        if reference_index in matched:
            continue
        midpoint = (expected.onset_seconds + expected.offset_seconds) / 2
        covering = [
            actual
            for actual in predicted
            if actual.onset_seconds <= midpoint <= actual.offset_seconds
        ]
        if not covering:
            undetected += 1
        elif any(actual.pitch == expected.pitch for actual in covering):
            merged += 1
        else:
            covered += 1
    return MissedNoteBreakdown(
        reference_notes=len(reference),
        onset_matched=len(matched),
        merged_into_same_pitch=merged,
        covered_by_other_pitch=covered,
        undetected=undetected,
    )


def compare_reference_candidates(
    references: list[tuple[str, list[TimedMidiNote]]],
    predicted: list[TimedMidiNote],
    *,
    selection_policy: Literal["primary", "best_onset_pitch_offset_f1"],
    onset_tolerance_seconds: float = 0.05,
    offset_tolerance_seconds: float = 0.05,
    offset_tolerance_ratio: float = 0.2,
) -> tuple[str, NoteMatchMetrics]:
    if not references:
        raise ValueError("at least one reference candidate is required")
    comparisons = [
        compare_note_sequences(
            reference,
            predicted,
            onset_tolerance_seconds=onset_tolerance_seconds,
            offset_tolerance_seconds=offset_tolerance_seconds,
            offset_tolerance_ratio=offset_tolerance_ratio,
        )
        for _reference_id, reference in references
    ]
    selected_index = 0
    if selection_policy == "best_onset_pitch_offset_f1":
        selected_index = max(
            range(len(comparisons)),
            key=lambda index: (
                comparisons[index].onset_pitch_offset_f1,
                comparisons[index].onset_pitch_f1,
                -index,
            ),
        )
    return references[selected_index][0], comparisons[selected_index]


def aggregate_benchmark_results(
    results: list[SampleBenchmarkResult],
    *,
    resources: ResourceMetrics | None = None,
) -> dict[str, object]:
    if not results:
        raise ValueError("at least one benchmark result is required")
    aggregate = _aggregate_scope(results)
    categories = {
        category: _aggregate_scope([result for result in results if result.category == category])
        for category in sorted({result.category for result in results})
    }
    return {
        "overall": aggregate,
        "categories": categories,
        "resources": asdict(resources or ResourceMetrics()),
        "samples": [asdict(result) for result in results],
    }


def evaluate_thresholds(
    report: dict[str, object],
    thresholds: dict[str, MetricThresholds],
) -> list[ThresholdViolation]:
    violations: list[ThresholdViolation] = []
    for scope, selected_thresholds in thresholds.items():
        metrics = _report_scope(report, scope)
        checks: list[
            tuple[str, float | None, Literal[">=", "<="]]
        ] = [
            ("onset_pitch_f1", selected_thresholds.onset_pitch_f1_min, ">="),
            (
                "onset_pitch_offset_f1",
                selected_thresholds.onset_pitch_offset_f1_min,
                ">=",
            ),
            (
                "macro_onset_pitch_f1",
                selected_thresholds.macro_onset_pitch_f1_min,
                ">=",
            ),
            (
                "macro_onset_pitch_offset_f1",
                selected_thresholds.macro_onset_pitch_offset_f1_min,
                ">=",
            ),
            ("mean_onset_mae_ms", selected_thresholds.mean_onset_mae_ms_max, "<="),
            (
                "mean_duration_mae_ms",
                selected_thresholds.mean_duration_mae_ms_max,
                "<=",
            ),
            ("mean_velocity_mae", selected_thresholds.mean_velocity_mae_max, "<="),
            (
                "mean_onset_aligned_pitch_mae_semitones",
                selected_thresholds.mean_onset_aligned_pitch_mae_semitones_max,
                "<=",
            ),
            ("empty_result_rate", selected_thresholds.empty_result_rate_max, "<="),
            (
                "median_real_time_factor",
                selected_thresholds.median_real_time_factor_max,
                "<=",
            ),
            ("p95_latency_seconds", selected_thresholds.p95_latency_seconds_max, "<="),
        ]
        for metric, threshold, comparator in checks:
            if threshold is None:
                continue
            raw_actual = metrics[metric]
            if not isinstance(raw_actual, int | float):
                raise ValueError(f"benchmark metric {scope}.{metric} is not numeric")
            actual = float(raw_actual)
            if (comparator == ">=" and actual < threshold) or (
                comparator == "<=" and actual > threshold
            ):
                violations.append(
                    ThresholdViolation(
                        scope=scope,
                        metric=metric,
                        actual=actual,
                        comparator=comparator,
                        threshold=threshold,
                    )
                )
        resource_checks = [
            ("peak_cpu_percent", selected_thresholds.peak_cpu_percent_max),
            ("peak_memory_mib", selected_thresholds.peak_memory_mib_max),
        ]
        for resource_name, resource_threshold in resource_checks:
            if resource_threshold is None:
                continue
            resources = report.get("resources")
            if not isinstance(resources, dict):
                raise ValueError("benchmark report does not contain resource metrics")
            raw_resource = resources.get(resource_name)
            if not isinstance(raw_resource, int | float):
                raise ValueError(
                    f"{resource_name} threshold requires container resource sampling"
                )
            actual_resource = float(raw_resource)
            if actual_resource > resource_threshold:
                violations.append(
                    ThresholdViolation(
                        scope=scope,
                        metric=resource_name,
                        actual=actual_resource,
                        comparator="<=",
                        threshold=resource_threshold,
                    )
                )
    return violations


def _match_notes(
    reference: list[TimedMidiNote],
    predicted: list[TimedMidiNote],
    *,
    onset_tolerance_seconds: float,
    require_pitch: bool,
    require_offset: bool,
    offset_tolerance_seconds: float,
    offset_tolerance_ratio: float,
) -> list[tuple[int, int]]:
    candidates: dict[int, list[tuple[float, int, float, int]]] = defaultdict(list)
    for reference_index, expected in enumerate(reference):
        for predicted_index, actual in enumerate(predicted):
            if require_pitch and expected.pitch != actual.pitch:
                continue
            onset_error = abs(expected.onset_seconds - actual.onset_seconds)
            if onset_error > onset_tolerance_seconds:
                continue
            offset_error = abs(expected.offset_seconds - actual.offset_seconds)
            allowed_offset_error = max(
                offset_tolerance_seconds,
                expected.duration_seconds * offset_tolerance_ratio,
            )
            if require_offset and offset_error > allowed_offset_error:
                continue
            pitch_error = abs(expected.pitch - actual.pitch)
            candidates[reference_index].append(
                (onset_error, pitch_error, offset_error, predicted_index)
            )
    for choices in candidates.values():
        choices.sort()

    reference_to_predicted: dict[int, int] = {}
    predicted_to_reference: dict[int, int] = {}
    for start_reference in range(len(reference)):
        if start_reference in reference_to_predicted or not candidates[start_reference]:
            continue
        queue = deque([start_reference])
        visited_references = {start_reference}
        visited_predictions: set[int] = set()
        prediction_parent: dict[int, int] = {}
        free_prediction: int | None = None
        while queue and free_prediction is None:
            reference_index = queue.popleft()
            for _onset, _pitch, _offset, predicted_index in candidates[reference_index]:
                if predicted_index in visited_predictions:
                    continue
                visited_predictions.add(predicted_index)
                prediction_parent[predicted_index] = reference_index
                matched_reference = predicted_to_reference.get(predicted_index)
                if matched_reference is None:
                    free_prediction = predicted_index
                    break
                if matched_reference not in visited_references:
                    visited_references.add(matched_reference)
                    queue.append(matched_reference)
        if free_prediction is None:
            continue
        predicted_index = free_prediction
        while True:
            reference_index = prediction_parent[predicted_index]
            previous_prediction = reference_to_predicted.get(reference_index)
            reference_to_predicted[reference_index] = predicted_index
            predicted_to_reference[predicted_index] = reference_index
            if previous_prediction is None:
                break
            predicted_index = previous_prediction
    return sorted(reference_to_predicted.items())


def _precision_recall_f1(
    matches: int,
    reference_count: int,
    predicted_count: int,
) -> tuple[float, float, float]:
    precision = matches / predicted_count if predicted_count else 0.0
    recall = matches / reference_count if reference_count else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def _aggregate_scope(results: list[SampleBenchmarkResult]) -> dict[str, float | int | None]:
    reference_count = sum(result.metrics.reference_notes for result in results)
    predicted_count = sum(result.metrics.predicted_notes for result in results)
    onset_matches = sum(result.metrics.onset_pitch_matches for result in results)
    offset_matches = sum(result.metrics.onset_pitch_offset_matches for result in results)
    onset_precision, onset_recall, onset_f1 = _precision_recall_f1(
        onset_matches,
        reference_count,
        predicted_count,
    )
    offset_precision, offset_recall, offset_f1 = _precision_recall_f1(
        offset_matches,
        reference_count,
        predicted_count,
    )
    latencies = sorted(result.latency_seconds for result in results)
    return {
        "sample_count": len(results),
        "reference_notes": reference_count,
        "predicted_notes": predicted_count,
        "onset_pitch_precision": onset_precision,
        "onset_pitch_recall": onset_recall,
        "onset_pitch_f1": onset_f1,
        "onset_pitch_offset_precision": offset_precision,
        "onset_pitch_offset_recall": offset_recall,
        "onset_pitch_offset_f1": offset_f1,
        "macro_onset_pitch_f1": _mean_or_none(
            [result.metrics.onset_pitch_f1 for result in results]
        ),
        "macro_onset_pitch_offset_f1": _mean_or_none(
            [result.metrics.onset_pitch_offset_f1 for result in results]
        ),
        "empty_result_rate": sum(result.metrics.predicted_notes == 0 for result in results)
        / len(results),
        "median_latency_seconds": median(latencies),
        "p95_latency_seconds": _percentile(latencies, 0.95),
        "median_real_time_factor": median(result.real_time_factor for result in results),
        "mean_onset_mae_ms": _weighted_mean(
            results,
            "onset_mae_ms",
            "onset_pitch_matches",
        ),
        "mean_duration_mae_ms": _weighted_mean(
            results,
            "duration_mae_ms",
            "onset_pitch_matches",
        ),
        "mean_velocity_mae": _weighted_mean(
            results,
            "velocity_mae",
            "onset_pitch_matches",
        ),
        "mean_onset_aligned_pitch_mae_semitones": _weighted_mean(
            results,
            "onset_aligned_pitch_mae_semitones",
            "onset_aligned_matches",
        ),
    }


def _weighted_mean(
    results: list[SampleBenchmarkResult],
    metric_name: str,
    weight_name: str,
) -> float | None:
    weighted_total = 0.0
    total_weight = 0
    for result in results:
        value = getattr(result.metrics, metric_name)
        weight = int(getattr(result.metrics, weight_name))
        if value is None or weight == 0:
            continue
        weighted_total += float(value) * weight
        total_weight += weight
    return weighted_total / total_weight if total_weight else None


def _report_scope(report: dict[str, object], scope: str) -> dict[str, object]:
    if scope == "overall":
        selected = report.get("overall")
    else:
        categories = report.get("categories")
        selected = categories.get(scope) if isinstance(categories, dict) else None
    if not isinstance(selected, dict):
        raise ValueError(f"benchmark report does not contain threshold scope {scope}")
    return selected


def _resolve_verified_file(base_directory: Path, path: Path, expected_sha256: str) -> Path:
    resolved = path if path.is_absolute() else base_directory / path
    resolved = resolved.resolve()
    if not resolved.is_file():
        raise ValueError(f"benchmark input file does not exist: {resolved}")
    actual_sha256 = sha256(resolved.read_bytes()).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError(
            f"benchmark input checksum mismatch: {resolved} "
            f"(expected {expected_sha256}, got {actual_sha256})"
        )
    return resolved


def _percentile(values: list[float], percentile: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * percentile
    lower = int(position)
    upper = min(len(values) - 1, lower + 1)
    fraction = position - lower
    return values[lower] + (values[upper] - values[lower]) * fraction


def _mean_or_none(values: list[float | int]) -> float | None:
    return sum(values) / len(values) if values else None


def parse_docker_memory_mib(value: str) -> float:
    matched = re.fullmatch(r"\s*([0-9.]+)\s*([KMGT]?i?B)\s*", value, flags=re.IGNORECASE)
    if matched is None:
        raise ValueError(f"unsupported Docker memory value: {value}")
    amount = float(matched.group(1))
    unit = matched.group(2).lower()
    factors = {
        "b": 1 / (1024 * 1024),
        "kb": 1000 / (1024 * 1024),
        "kib": 1 / 1024,
        "mb": 1_000_000 / (1024 * 1024),
        "mib": 1,
        "gb": 1_000_000_000 / (1024 * 1024),
        "gib": 1024,
        "tb": 1_000_000_000_000 / (1024 * 1024),
        "tib": 1024 * 1024,
    }
    return amount * factors[unit]

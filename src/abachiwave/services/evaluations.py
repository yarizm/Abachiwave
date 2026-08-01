from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.core.config import Settings, get_settings
from abachiwave.core.database import AsyncSessionLocal
from abachiwave.evaluations.samples import (
    EvaluationSample,
    load_sample_set,
    lyric_lines,
    sample_set_summary,
)
from abachiwave.models.ai import (
    EvaluationRun,
    EvaluationRunStatus,
    PromptTemplateVersion,
    ProviderProfile,
    TextWorkflow,
)
from abachiwave.schemas.ai import (
    EvaluationHumanScoreCreate,
    EvaluationRunCreate,
    EvaluationRunRead,
    EvaluationSampleSetRead,
    LyricsCandidateContent,
    RevisionCandidateContent,
)
from abachiwave.schemas.composition import ArrangementPlan
from abachiwave.schemas.song_specs import SongSpecData
from abachiwave.services.ai_generation import (
    build_text_provider,
    get_active_prompt,
    select_provider_profile,
)
from abachiwave.services.task_queue import TextEvaluationTaskQueue
from abachiwave.services.text_provider import (
    TextGenerationProvider,
    TextGenerationRequest,
    TextProviderError,
)


@dataclass(frozen=True)
class EvaluationCreateResult:
    run: EvaluationRun | None
    not_found: str | None = None
    conflict: str | None = None


@dataclass(frozen=True)
class HumanScoreResult:
    run: EvaluationRun | None
    not_found: str | None = None
    conflict: str | None = None


def list_evaluation_sample_sets() -> list[EvaluationSampleSetRead]:
    return [EvaluationSampleSetRead.model_validate(sample_set_summary())]


async def create_evaluation_run(
    *,
    session: AsyncSession,
    payload: EvaluationRunCreate,
    queue: TextEvaluationTaskQueue,
) -> EvaluationCreateResult:
    try:
        samples = [
            sample
            for sample in load_sample_set(payload.sample_set)
            if sample.workflow == payload.workflow
        ]
    except KeyError:
        return EvaluationCreateResult(None, not_found="Evaluation sample set not found")
    if not samples:
        return EvaluationCreateResult(None, conflict="Sample set has no samples for workflow")
    profile = await select_provider_profile(
        session,
        payload.provider_profile_id,
        payload.workflow,
    )
    if profile is None:
        return EvaluationCreateResult(None, not_found="ProviderProfile not found")
    prompt = await get_active_prompt(session, payload.workflow)
    if prompt is None:
        return EvaluationCreateResult(None, conflict="No active prompt template is configured")
    run = EvaluationRun(
        sample_set=payload.sample_set,
        workflow=payload.workflow,
        status=EvaluationRunStatus.queued,
        sample_count=len(samples),
        provider_profile_id=profile.id,
        prompt_template_version_id=prompt.id,
        metrics={},
        human_scores={"submissions": [], "aggregate": {}},
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    try:
        run.arq_job_id = await queue.enqueue_text_evaluation(UUID(run.id))
    except Exception as error:
        run.status = EvaluationRunStatus.failed
        run.error_code = "queue_enqueue_failed"
        run.error_message = str(error)[:4000]
        run.completed_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(run)
        return EvaluationCreateResult(run)
    await session.commit()
    await session.refresh(run)
    return EvaluationCreateResult(run)


async def execute_text_evaluation(
    evaluation_run_id: UUID,
    *,
    provider: TextGenerationProvider | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    settings: Settings | None = None,
) -> EvaluationRun | None:
    selected_session_factory = session_factory or AsyncSessionLocal
    selected_settings = settings or get_settings()
    async with selected_session_factory() as session:
        run = await session.get(EvaluationRun, str(evaluation_run_id))
        if run is None:
            return None
        if run.status not in {EvaluationRunStatus.queued, EvaluationRunStatus.running}:
            return run
        run.status = EvaluationRunStatus.running
        run.started_at = datetime.now(UTC)
        run.error_code = None
        run.error_message = None
        await session.commit()
        await session.refresh(run)

        profile = (
            await session.get(ProviderProfile, run.provider_profile_id)
            if run.provider_profile_id
            else None
        )
        prompt = (
            await session.get(PromptTemplateVersion, run.prompt_template_version_id)
            if run.prompt_template_version_id
            else None
        )
        if profile is None or not profile.enabled:
            return await _fail_evaluation(
                session,
                run,
                "provider_unavailable",
                "Provider profile is unavailable",
            )
        if prompt is None or not prompt.active:
            return await _fail_evaluation(
                session,
                run,
                "invalid_prompt_template",
                "Prompt template is unavailable",
            )
        try:
            samples = [
                sample
                for sample in load_sample_set(run.sample_set)
                if sample.workflow == TextWorkflow(run.workflow)
            ]
        except KeyError:
            return await _fail_evaluation(
                session,
                run,
                "sample_set_not_found",
                "Evaluation sample set is unavailable",
            )

        results: list[dict[str, object]] = []
        blind_pairs: list[dict[str, object]] = []
        blind_assignments: dict[str, str] = {}
        total_usage: dict[str, int] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }
        for sample in samples:
            output_model = type(sample.fallback)
            try:
                selected_provider = provider or build_text_provider(
                    profile,
                    sample.fallback,
                    selected_settings,
                )
                generated = await selected_provider.generate(
                    TextGenerationRequest(
                        system_prompt=prompt.template_body,
                        user_prompt=_json_context(sample.context),
                        output_model=output_model,
                        schema_name=f"abachiwave_{sample.workflow.value}_evaluation_v1",
                        candidate_count=1,
                        params=profile.default_params,
                    )
                )
                content = output_model.model_validate(generated.candidates[0])
                _merge_usage(total_usage, generated.usage)
                constraint_pass = _constraints_pass(sample, content)
                section_complete = _section_complete(sample, content)
                duplicate_ratio = _duplicate_ratio(content)
                output = content.model_dump(mode="json")
                results.append(
                    {
                        "sample_id": sample.id,
                        "category": sample.category,
                        "schema_valid": True,
                        "constraint_pass": constraint_pass,
                        "section_complete": section_complete,
                        "duplicate_ratio": duplicate_ratio,
                        "error_code": None,
                    }
                )
                provider_label = _provider_label(run.id, sample.id)
                blind_assignments[sample.id] = provider_label
                blind_pairs.append(
                    {
                        "sample_id": sample.id,
                        "category": sample.category,
                        "output_a": (
                            output
                            if provider_label == "A"
                            else sample.fallback.model_dump(mode="json")
                        ),
                        "output_b": (
                            output
                            if provider_label == "B"
                            else sample.fallback.model_dump(mode="json")
                        ),
                    }
                )
            except TextProviderError as error:
                results.append(_failed_sample_result(sample, error.code))
            except Exception:
                results.append(_failed_sample_result(sample, "evaluation_sample_failed"))

        metrics = _build_metrics(
            run=run,
            results=results,
            blind_pairs=blind_pairs,
            blind_assignments=blind_assignments,
            provider_usage=total_usage,
        )
        run.metrics = metrics
        run.completed_at = datetime.now(UTC)
        raw_valid_count = metrics["schema_valid_count"]
        valid_count = raw_valid_count if isinstance(raw_valid_count, int) else 0
        if valid_count == 0:
            run.status = EvaluationRunStatus.failed
            run.error_code = "evaluation_no_valid_outputs"
            run.error_message = "Provider did not return any schema-valid evaluation output"
        else:
            run.status = EvaluationRunStatus.succeeded
        await session.commit()
        await session.refresh(run)
        return run


async def list_evaluation_runs(
    session: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[EvaluationRunRead]:
    statement: Select[tuple[EvaluationRun]] = (
        select(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(limit).offset(offset)
    )
    runs = list((await session.execute(statement)).scalars().all())
    return [evaluation_run_to_read(run) for run in runs]


async def get_evaluation_run(
    session: AsyncSession,
    evaluation_run_id: UUID,
) -> EvaluationRun | None:
    return await session.get(EvaluationRun, str(evaluation_run_id))


async def mark_text_evaluation_failed(
    evaluation_run_id: UUID,
    error_code: str,
    error_message: str,
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> EvaluationRun | None:
    selected_session_factory = session_factory or AsyncSessionLocal
    async with selected_session_factory() as session:
        run = await session.get(EvaluationRun, str(evaluation_run_id))
        if run is None:
            return None
        return await _fail_evaluation(session, run, error_code, error_message)


def evaluation_run_lock_statement(run_id: UUID) -> Select[tuple[EvaluationRun]]:
    """Row lock for the human_scores read-modify-write; concurrent submissions
    must serialize on PostgreSQL or the second commit overwrites the first."""
    return (
        select(EvaluationRun)
        .where(EvaluationRun.id == str(run_id))
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def add_evaluation_human_scores(
    session: AsyncSession,
    evaluation_run_id: UUID,
    payload: EvaluationHumanScoreCreate,
) -> HumanScoreResult:
    run = (
        await session.execute(evaluation_run_lock_statement(evaluation_run_id))
    ).scalar_one_or_none()
    if run is None:
        return HumanScoreResult(None, not_found="EvaluationRun not found")
    if run.status != EvaluationRunStatus.succeeded:
        return HumanScoreResult(None, conflict="EvaluationRun is not ready for scoring")
    assignments = run.metrics.get("_blind_assignments")
    if not isinstance(assignments, dict):
        return HumanScoreResult(None, conflict="EvaluationRun has no blind comparison data")
    known_sample_ids = {key for key in assignments if isinstance(key, str)}
    submitted_sample_ids = {rating.sample_id for rating in payload.ratings}
    if not submitted_sample_ids.issubset(known_sample_ids):
        return HumanScoreResult(None, conflict="Rating contains an unknown sample_id")

    current = run.human_scores if isinstance(run.human_scores, dict) else {}
    raw_submissions = current.get("submissions", [])
    submissions = list(raw_submissions) if isinstance(raw_submissions, list) else []
    submissions.append(
        {
            "evaluator_alias": payload.evaluator_alias,
            "ratings": [rating.model_dump(mode="json") for rating in payload.ratings],
            "notes": payload.notes,
            "submitted_at": datetime.now(UTC).isoformat(),
        }
    )
    run.human_scores = {
        "submissions": submissions,
        "aggregate": _aggregate_human_scores(submissions, assignments),
    }
    await session.commit()
    await session.refresh(run)
    return HumanScoreResult(run)


def evaluation_run_to_read(run: EvaluationRun) -> EvaluationRunRead:
    public_metrics = {key: value for key, value in run.metrics.items() if not key.startswith("_")}
    return EvaluationRunRead(
        id=UUID(run.id),
        sample_set=run.sample_set,
        workflow=run.workflow,
        status=run.status,
        arq_job_id=run.arq_job_id,
        sample_count=run.sample_count,
        provider_profile_id=UUID(run.provider_profile_id) if run.provider_profile_id else None,
        prompt_template_version_id=(
            UUID(run.prompt_template_version_id) if run.prompt_template_version_id else None
        ),
        metrics=public_metrics,
        human_scores=run.human_scores,
        error_code=run.error_code,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


async def _fail_evaluation(
    session: AsyncSession,
    run: EvaluationRun,
    error_code: str,
    error_message: str,
) -> EvaluationRun:
    run.status = EvaluationRunStatus.failed
    run.error_code = error_code
    run.error_message = error_message[:4000]
    run.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(run)
    return run


def _json_context(context: dict[str, object]) -> str:
    import json

    return json.dumps(context, ensure_ascii=False, separators=(",", ":"), default=str)


def _constraints_pass(sample: EvaluationSample, content: BaseModel) -> bool:
    if sample.workflow == TextWorkflow.song_spec:
        actual = SongSpecData.model_validate(content.model_dump()).model_dump(mode="json")
        exact_fields = sample.expectations.get("exact_fields")
        if isinstance(exact_fields, dict) and any(
            actual.get(field) != expected
            for field, expected in exact_fields.items()
            if isinstance(field, str)
        ):
            return False
        null_fields = sample.expectations.get("null_fields")
        return not isinstance(null_fields, list) or all(
            actual.get(field) is None for field in null_fields if isinstance(field, str)
        )
    if sample.workflow == TextWorkflow.lyrics:
        lyrics = LyricsCandidateContent.model_validate(content.model_dump())
        expected_ids = _expected_strings(sample, "section_ids")
        minimum_hooks = sample.expectations.get("minimum_hook_count", 0)
        return expected_ids.issubset({section.section_id for section in lyrics.sections}) and len(
            lyrics.hook_candidates
        ) >= (minimum_hooks if isinstance(minimum_hooks, int) else 0)
    if sample.workflow == TextWorkflow.arrangement:
        arrangement = ArrangementPlan.model_validate(content.model_dump())
        return _expected_strings(sample, "section_ids").issubset(
            {section.section_id for section in arrangement.sections}
        )
    revision = RevisionCandidateContent.model_validate(content.model_dump())
    return _expected_strings(sample, "targets").issubset(
        {task.target.value for task in revision.tasks}
    )


def _section_complete(sample: EvaluationSample, content: BaseModel) -> bool | None:
    expected_ids = _expected_strings(sample, "section_ids")
    if not expected_ids:
        return None
    if sample.workflow == TextWorkflow.lyrics:
        actual = {
            section.section_id
            for section in LyricsCandidateContent.model_validate(content.model_dump()).sections
        }
    elif sample.workflow == TextWorkflow.arrangement:
        actual = {
            section.section_id
            for section in ArrangementPlan.model_validate(content.model_dump()).sections
        }
    else:
        return None
    return expected_ids.issubset(actual)


def _duplicate_ratio(content: BaseModel) -> float:
    values: list[str]
    if isinstance(content, LyricsCandidateContent):
        values = lyric_lines(content) + [hook.text.casefold() for hook in content.hook_candidates]
    elif isinstance(content, ArrangementPlan):
        values = [section.production_notes.casefold() for section in content.sections]
    elif isinstance(content, RevisionCandidateContent):
        values = [task.summary.casefold() for task in content.tasks]
    else:
        spec = SongSpecData.model_validate(content.model_dump())
        values = [item.casefold() for item in (spec.song_structure or [])]
    if not values:
        return 0.0
    return round(1 - len(set(values)) / len(values), 4)


def _build_metrics(
    *,
    run: EvaluationRun,
    results: list[dict[str, object]],
    blind_pairs: list[dict[str, object]],
    blind_assignments: dict[str, str],
    provider_usage: dict[str, int],
) -> dict[str, object]:
    total = len(results)
    schema_count = sum(result["schema_valid"] is True for result in results)
    constraint_count = sum(result["constraint_pass"] is True for result in results)
    section_results = [
        result for result in results if isinstance(result.get("section_complete"), bool)
    ]
    section_count = sum(result["section_complete"] is True for result in section_results)
    duplicate_values = [
        value
        for result in results
        for value in [result.get("duplicate_ratio")]
        if isinstance(value, float)
    ]
    errors = Counter(
        value
        for result in results
        for value in [result.get("error_code")]
        if isinstance(value, str)
    )
    schema_rate = schema_count / total if total else 0.0
    return {
        "sample_set": run.sample_set,
        "workflow": TextWorkflow(run.workflow).value,
        "total_samples": total,
        "schema_valid_count": schema_count,
        "schema_valid_rate": round(schema_rate, 4),
        "passes_schema_target": schema_rate >= 0.98,
        "constraint_pass_count": constraint_count,
        "constraint_adherence_rate": round(constraint_count / total, 4) if total else 0.0,
        "section_complete_count": section_count,
        "section_completeness_rate": (
            round(section_count / len(section_results), 4) if section_results else None
        ),
        "average_duplicate_ratio": (
            round(sum(duplicate_values) / len(duplicate_values), 4) if duplicate_values else 0.0
        ),
        "error_counts": dict(errors),
        "provider_usage": provider_usage,
        "sample_results": results,
        "blind_pairs": blind_pairs,
        "_blind_assignments": blind_assignments,
    }


def _failed_sample_result(sample: EvaluationSample, error_code: str) -> dict[str, object]:
    return {
        "sample_id": sample.id,
        "category": sample.category,
        "schema_valid": False,
        "constraint_pass": False,
        "section_complete": None,
        "duplicate_ratio": None,
        "error_code": error_code,
    }


def _provider_label(run_id: str, sample_id: str) -> str:
    digest = sha256(f"{run_id}:{sample_id}".encode()).digest()
    return "A" if digest[0] % 2 == 0 else "B"


def _expected_strings(sample: EvaluationSample, key: str) -> set[str]:
    value = sample.expectations.get(key)
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _merge_usage(total: dict[str, int], usage: dict[str, object]) -> None:
    for key in total:
        value = usage.get(key)
        if isinstance(value, int):
            total[key] += value


def _aggregate_human_scores(
    submissions: list[object],
    assignments: dict[object, object],
) -> dict[str, object]:
    provider_theme: list[int] = []
    provider_editability: list[int] = []
    baseline_theme: list[int] = []
    baseline_editability: list[int] = []
    provider_preferences = 0
    baseline_preferences = 0
    ties = 0
    rating_count = 0
    for submission in submissions:
        if not isinstance(submission, dict) or not isinstance(submission.get("ratings"), list):
            continue
        for raw_rating in submission["ratings"]:
            if not isinstance(raw_rating, dict):
                continue
            sample_id = raw_rating.get("sample_id")
            provider_label = assignments.get(sample_id)
            if provider_label not in {"A", "B"}:
                continue
            baseline_label = "B" if provider_label == "A" else "A"
            provider_theme.append(_rating_value(raw_rating, provider_label, "theme_consistency"))
            provider_editability.append(_rating_value(raw_rating, provider_label, "editability"))
            baseline_theme.append(_rating_value(raw_rating, baseline_label, "theme_consistency"))
            baseline_editability.append(_rating_value(raw_rating, baseline_label, "editability"))
            preferred = raw_rating.get("preferred_output")
            if preferred == provider_label:
                provider_preferences += 1
            elif preferred == baseline_label:
                baseline_preferences += 1
            else:
                ties += 1
            rating_count += 1
    return {
        "submission_count": len(submissions),
        "rating_count": rating_count,
        "provider_theme_consistency": _average(provider_theme),
        "provider_editability": _average(provider_editability),
        "baseline_theme_consistency": _average(baseline_theme),
        "baseline_editability": _average(baseline_editability),
        "provider_preference_rate": (
            round(provider_preferences / rating_count, 4) if rating_count else None
        ),
        "baseline_preference_rate": (
            round(baseline_preferences / rating_count, 4) if rating_count else None
        ),
        "tie_rate": round(ties / rating_count, 4) if rating_count else None,
    }


def _rating_value(rating: dict[object, object], label: str, metric: str) -> int:
    value = rating.get(f"output_{label.lower()}_{metric}")
    return value if isinstance(value, int) else 0


def _average(values: list[int]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from abachiwave.agents.composition import (
    build_arrangement_from_assets,
    build_lyrics_from_song_spec,
)
from abachiwave.agents.prompts import TEXT_PROMPT_TEMPLATES
from abachiwave.agents.song_spec import build_song_spec_from_input
from abachiwave.core.config import Settings, get_settings
from abachiwave.core.database import AsyncSessionLocal
from abachiwave.models.ai import (
    GenerationCandidate,
    GenerationCandidateStatus,
    PromptTemplateVersion,
    ProviderProfile,
    TextWorkflow,
)
from abachiwave.models.composition import MidiAssetKind
from abachiwave.models.demo import GenerationRun, GenerationRunStatus, GenerationRunType
from abachiwave.models.project import Project
from abachiwave.models.revision import RevisionRequest
from abachiwave.models.song_spec import IdeaIntakeStatus, SongSpecStatus, SongSpecVersion
from abachiwave.schemas.ai import (
    CandidateGenerateRequest,
    CandidateSelectionRead,
    GenerationCandidateRead,
    LyricsCandidateContent,
    ProviderCapabilityRead,
    RevisionCandidateContent,
)
from abachiwave.schemas.composition import ArrangementPlan, ChordSection, LyricSection
from abachiwave.schemas.song_specs import SongSpecData
from abachiwave.services.composition import _create_lyrics_version
from abachiwave.services.delivery import (
    _create_arrangement_plan_version,
    resolve_arrangement_inputs,
)
from abachiwave.services.events import add_project_event
from abachiwave.services.generation_runs import lock_generation_run
from abachiwave.services.revisions import plan_revision_tasks
from abachiwave.services.song_specs import (
    _create_song_spec_version,
    get_idea_intake,
    get_song_spec_version,
    song_spec_to_data,
)
from abachiwave.services.task_queue import TextGenerationTaskQueue
from abachiwave.services.text_provider import (
    InvalidProviderOutputError,
    LocalDeterministicTextProvider,
    OpenAICompatibleTextProvider,
    TextGenerationProvider,
    TextGenerationRequest,
    TextProviderError,
    TextProviderUnavailableError,
)

ALL_TEXT_CAPABILITIES = [workflow.value for workflow in TextWorkflow]
DEFAULT_PROVIDER_PARAMS: dict[str, object] = {"temperature": 0.7}


@dataclass(frozen=True)
class CandidateRunCreateResult:
    run: GenerationRun | None
    not_found: str | None = None
    conflict: str | None = None


@dataclass(frozen=True)
class CandidateSelectResult:
    selection: CandidateSelectionRead | None
    not_found: str | None = None
    conflict: str | None = None


@dataclass(frozen=True)
class PreparedCandidate:
    output_model: type[BaseModel]
    context: dict[str, object]
    fallback: BaseModel
    source_asset_ids: dict[str, object]


async def ensure_ai_catalog(
    session: AsyncSession,
    *,
    settings: Settings | None = None,
) -> None:
    selected_settings = settings or get_settings()
    external_enabled = all(
        _present(value)
        for value in (
            selected_settings.text_provider_api_base_url,
            selected_settings.text_provider_api_key,
            selected_settings.text_provider_model,
        )
    )
    await _upsert_profile(
        session,
        profile_key="local-deterministic",
        provider_name="local_deterministic",
        display_name="Local deterministic",
        model=None,
        default_params={"temperature": 0},
        enabled=True,
        is_default=not external_enabled,
    )
    if external_enabled:
        await _upsert_profile(
            session,
            profile_key="server-text-provider",
            provider_name="openai_compatible",
            display_name="Server text provider",
            model=selected_settings.text_provider_model,
            default_params=DEFAULT_PROVIDER_PARAMS,
            enabled=True,
            is_default=True,
        )
    else:
        await _disable_profile_if_present(session, "server-text-provider")
    for workflow in TextWorkflow:
        statement: Select[tuple[PromptTemplateVersion]] = select(PromptTemplateVersion).where(
            PromptTemplateVersion.workflow == workflow,
            PromptTemplateVersion.version_number == 1,
        )
        if (await session.execute(statement)).scalar_one_or_none() is None:
            session.add(
                PromptTemplateVersion(
                    workflow=workflow,
                    version_number=1,
                    template_body=TEXT_PROMPT_TEMPLATES[workflow.value],
                    output_schema_version="1",
                    change_summary="Initial structured generation contract",
                    active=True,
                )
            )
    await session.commit()


async def list_provider_capabilities(
    session: AsyncSession,
    *,
    settings: Settings | None = None,
) -> list[ProviderCapabilityRead]:
    await ensure_ai_catalog(session, settings=settings)
    statement: Select[tuple[ProviderProfile]] = (
        select(ProviderProfile)
        .where(ProviderProfile.enabled.is_(True))
        .order_by(ProviderProfile.is_default.desc(), ProviderProfile.display_name)
    )
    profiles = list((await session.execute(statement)).scalars().all())
    return [
        ProviderCapabilityRead(
            id=UUID(profile.id),
            provider_name=profile.provider_name,
            display_name=profile.display_name,
            capabilities=[TextWorkflow(item) for item in profile.capabilities],
            model=profile.model,
            default_params=profile.default_params,
            enabled=profile.enabled,
            is_default=profile.is_default,
        )
        for profile in profiles
    ]


async def create_candidate_generation_run(
    *,
    session: AsyncSession,
    project_id: UUID,
    payload: CandidateGenerateRequest,
    queue: TextGenerationTaskQueue,
) -> CandidateRunCreateResult:
    await ensure_ai_catalog(session)
    prepared, not_found, conflict = await _prepare_candidate(session, project_id, payload)
    if prepared is None:
        return CandidateRunCreateResult(None, not_found=not_found, conflict=conflict)
    profile = await select_provider_profile(session, payload.provider_profile_id, payload.workflow)
    if profile is None:
        return CandidateRunCreateResult(None, not_found="ProviderProfile not found")
    prompt = await get_active_prompt(session, payload.workflow)
    if prompt is None:
        return CandidateRunCreateResult(None, conflict="No active prompt template is configured")

    manifest_payload = payload.model_dump(mode="json", exclude_none=True)
    run = GenerationRun(
        project_id=str(project_id),
        run_type=GenerationRunType.text_generation,
        input_manifest={
            "workflow": payload.workflow.value,
            "candidate_count": payload.candidate_count,
            "provider_profile_id": profile.id,
            "prompt_template_version_id": prompt.id,
            "payload": manifest_payload,
        },
        provider_name=profile.provider_name,
        provider_version=profile.model or "1",
        provider_params=profile.default_params,
        provider_usage={},
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    try:
        run.arq_job_id = await queue.enqueue_text_generation(UUID(run.id))
    except Exception as error:
        run.status = GenerationRunStatus.failed
        run.error_code = "queue_enqueue_failed"
        run.error_message = str(error)
        run.completed_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(run)
        raise
    await session.commit()
    await session.refresh(run)
    return CandidateRunCreateResult(run)


async def execute_candidate_generation(
    run_id: UUID,
    *,
    provider: TextGenerationProvider | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    settings: Settings | None = None,
) -> GenerationRun | None:
    selected_session_factory = session_factory or AsyncSessionLocal
    selected_settings = settings or get_settings()
    async with selected_session_factory() as session:
        run = await session.get(GenerationRun, str(run_id))
        if run is None:
            return None
        if run.run_type != GenerationRunType.text_generation:
            return run
        if run.status == GenerationRunStatus.cancelled:
            return run
        run.status = GenerationRunStatus.running
        run.started_at = datetime.now(UTC)
        run.error_code = None
        run.error_message = None
        await session.commit()
        await session.refresh(run)
        try:
            payload = _payload_from_manifest(run.input_manifest)
            workflow = payload.workflow
            prepared, not_found, conflict = await _prepare_candidate(
                session,
                UUID(run.project_id),
                payload,
            )
            if prepared is None:
                raise InvalidProviderOutputError(
                    not_found or conflict or "Candidate inputs invalid"
                )
            profile = await session.get(
                ProviderProfile,
                _manifest_string(run.input_manifest, "provider_profile_id"),
            )
            prompt = await session.get(
                PromptTemplateVersion,
                _manifest_string(run.input_manifest, "prompt_template_version_id"),
            )
            if profile is None or not profile.enabled:
                raise TextProviderUnavailableError("Provider profile is unavailable")
            if prompt is None or not prompt.active:
                raise InvalidProviderOutputError("Prompt template is unavailable")
            selected_provider = provider or build_text_provider(
                profile,
                prepared.fallback,
                selected_settings,
            )
            result = await selected_provider.generate(
                TextGenerationRequest(
                    system_prompt=prompt.template_body,
                    user_prompt=json.dumps(prepared.context, ensure_ascii=False, default=str),
                    output_model=prepared.output_model,
                    schema_name=f"abachiwave_{workflow.value}_v1",
                    candidate_count=payload.candidate_count,
                    params=run.provider_params,
                )
            )
            locked_run = await lock_generation_run(session, run_id)
            if locked_run is None:
                return None
            run = locked_run
            if run.status == GenerationRunStatus.cancelled:
                await session.commit()
                await session.refresh(run)
                return run
            for index, content in enumerate(result.candidates, start=1):
                validated = prepared.output_model.model_validate(content)
                session.add(
                    GenerationCandidate(
                        project_id=run.project_id,
                        run_id=run.id,
                        provider_profile_id=profile.id,
                        prompt_template_version_id=prompt.id,
                        workflow=workflow,
                        candidate_index=index,
                        content=validated.model_dump(mode="json"),
                        score=_candidate_score(workflow, validated),
                        source_asset_ids=prepared.source_asset_ids,
                        generation_params=run.provider_params,
                        provider_usage=result.usage,
                    )
                )
            run.provider_usage = result.usage
            run.status = GenerationRunStatus.succeeded
            run.completed_at = datetime.now(UTC)
            add_project_event(
                session,
                project_id=UUID(run.project_id),
                event_type="candidate.generated",
                payload={
                    "workflow": workflow.value,
                    "candidate_count": len(result.candidates),
                    "provider_name": run.provider_name,
                },
                generation_run_id=run_id,
            )
            await session.commit()
            await session.refresh(run)
            return run
        except TextProviderError as error:
            await _fail_run(session, run, error.code, str(error))
            return run
        except Exception as error:
            await _fail_run(session, run, "candidate_generation_failed", str(error))
            return run


async def list_generation_candidates(
    session: AsyncSession,
    project_id: UUID,
    *,
    workflow: TextWorkflow | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[GenerationCandidateRead]:
    statement: Select[tuple[GenerationCandidate]] = select(GenerationCandidate).where(
        GenerationCandidate.project_id == str(project_id)
    )
    if workflow is not None:
        statement = statement.where(GenerationCandidate.workflow == workflow)
    statement = (
        statement.order_by(GenerationCandidate.created_at.desc()).limit(limit).offset(offset)
    )
    candidates = list((await session.execute(statement)).scalars().all())
    return [generation_candidate_to_read(candidate) for candidate in candidates]


async def select_generation_candidate(
    session: AsyncSession,
    project_id: UUID,
    candidate_id: UUID,
) -> CandidateSelectResult:
    statement: Select[tuple[GenerationCandidate]] = (
        select(GenerationCandidate)
        .where(
            GenerationCandidate.id == str(candidate_id),
            GenerationCandidate.project_id == str(project_id),
        )
        .with_for_update()
    )
    candidate = (await session.execute(statement)).scalar_one_or_none()
    if candidate is None:
        return CandidateSelectResult(None, not_found="GenerationCandidate not found")
    if candidate.status == GenerationCandidateStatus.selected:
        if candidate.selected_asset_type and candidate.selected_asset_id:
            return CandidateSelectResult(
                CandidateSelectionRead(
                    candidate=generation_candidate_to_read(candidate),
                    asset_type=candidate.selected_asset_type,
                    asset_id=UUID(candidate.selected_asset_id),
                )
            )
        return CandidateSelectResult(None, conflict="Candidate is already selected")
    await lock_generation_run(session, UUID(candidate.run_id))
    selected_in_run = (
        await session.execute(
            select(GenerationCandidate).where(
                GenerationCandidate.run_id == candidate.run_id,
                GenerationCandidate.status == GenerationCandidateStatus.selected,
            )
        )
    ).scalar_one_or_none()
    if selected_in_run is not None:
        return CandidateSelectResult(None, conflict="Another candidate from this run is selected")

    asset_type, asset_id = await _materialize_candidate(session, project_id, candidate)
    candidate.status = GenerationCandidateStatus.selected
    candidate.selected_asset_type = asset_type
    candidate.selected_asset_id = str(asset_id)
    candidate.selected_at = datetime.now(UTC)
    add_project_event(
        session,
        project_id=project_id,
        event_type="candidate.selected",
        payload={
            "candidate_id": candidate.id,
            "workflow": TextWorkflow(candidate.workflow).value,
            "asset_type": asset_type,
            "asset_id": str(asset_id),
        },
        generation_run_id=UUID(candidate.run_id),
        artifact_version_id=asset_id,
    )
    await session.commit()
    await session.refresh(candidate)
    return CandidateSelectResult(
        CandidateSelectionRead(
            candidate=generation_candidate_to_read(candidate),
            asset_type=asset_type,
            asset_id=asset_id,
        )
    )


def generation_candidate_to_read(candidate: GenerationCandidate) -> GenerationCandidateRead:
    return GenerationCandidateRead(
        id=UUID(candidate.id),
        project_id=UUID(candidate.project_id),
        run_id=UUID(candidate.run_id),
        provider_profile_id=(
            UUID(candidate.provider_profile_id) if candidate.provider_profile_id else None
        ),
        prompt_template_version_id=(
            UUID(candidate.prompt_template_version_id)
            if candidate.prompt_template_version_id
            else None
        ),
        workflow=candidate.workflow,
        candidate_index=candidate.candidate_index,
        status=candidate.status,
        content=candidate.content,
        score=candidate.score,
        source_asset_ids=candidate.source_asset_ids,
        generation_params=candidate.generation_params,
        provider_usage=candidate.provider_usage,
        selected_asset_type=candidate.selected_asset_type,
        selected_asset_id=(
            UUID(candidate.selected_asset_id) if candidate.selected_asset_id else None
        ),
        selected_at=candidate.selected_at,
        created_at=candidate.created_at,
    )


async def _prepare_candidate(
    session: AsyncSession,
    project_id: UUID,
    payload: CandidateGenerateRequest,
) -> tuple[PreparedCandidate | None, str | None, str | None]:
    if await session.get(Project, str(project_id)) is None:
        return None, "Project not found", None
    if payload.workflow == TextWorkflow.song_spec:
        if payload.intake_id is None:
            return None, None, "SongSpec candidate requires intake"
        intake = await get_idea_intake(session, project_id, payload.intake_id)
        if intake is None:
            return None, "IdeaIntake not found", None
        data = build_song_spec_from_input(intake.idea, intake.answers)
        return (
            PreparedCandidate(
                output_model=SongSpecData,
                context={"idea": intake.idea, "answers": intake.answers},
                fallback=data,
                source_asset_ids={"intake_id": intake.id},
            ),
            None,
            None,
        )
    if payload.workflow == TextWorkflow.lyrics:
        song_spec, error = await _approved_song_spec(session, project_id, payload.song_spec_id)
        if song_spec is None:
            return None, error if error and "not found" in error.lower() else None, error
        data = song_spec_to_data(song_spec)
        sections, hooks = build_lyrics_from_song_spec(data)
        return (
            PreparedCandidate(
                output_model=LyricsCandidateContent,
                context={"song_spec": data.model_dump(mode="json")},
                fallback=LyricsCandidateContent(sections=sections, hook_candidates=hooks),
                source_asset_ids={"song_spec_id": song_spec.id},
            ),
            None,
            None,
        )
    if payload.workflow == TextWorkflow.arrangement:
        song_spec, error = await _approved_song_spec(session, project_id, payload.song_spec_id)
        if song_spec is None:
            return None, error if error and "not found" in error.lower() else None, error
        inputs, missing, not_found = await resolve_arrangement_inputs(
            session,
            project_id,
            song_spec,
            payload.lyrics_version_id,
            payload.chord_version_id,
            payload.midi_asset_ids,
        )
        if not_found:
            return None, not_found, None
        if inputs is None:
            return None, None, f"Arrangement prerequisites are missing: {', '.join(missing)}"
        song_spec_data = song_spec_to_data(inputs.song_spec)
        lyric_sections = [LyricSection.model_validate(item) for item in inputs.lyrics.sections]
        chord_sections = [ChordSection.model_validate(item) for item in inputs.chords.sections]
        plan = build_arrangement_from_assets(
            song_spec=song_spec_data,
            lyric_sections=lyric_sections,
            chord_sections=chord_sections,
            midi_kinds=[MidiAssetKind(asset.kind) for asset in inputs.midi_assets],
        )
        source_ids: dict[str, object] = {
            "song_spec_id": inputs.song_spec.id,
            "lyrics_version_id": inputs.lyrics.id,
            "chord_version_id": inputs.chords.id,
            "midi_asset_ids": [asset.id for asset in inputs.midi_assets],
        }
        return (
            PreparedCandidate(
                output_model=ArrangementPlan,
                context={
                    "song_spec": song_spec_data.model_dump(mode="json"),
                    "lyrics": [item.model_dump(mode="json") for item in lyric_sections],
                    "chords": [item.model_dump(mode="json") for item in chord_sections],
                    "midi_kinds": [MidiAssetKind(asset.kind).value for asset in inputs.midi_assets],
                },
                fallback=plan,
                source_asset_ids=source_ids,
            ),
            None,
            None,
        )
    feedback = payload.feedback or ""
    tasks = await plan_revision_tasks(session, project_id, feedback)
    revision_content = RevisionCandidateContent(feedback=feedback, tasks=tasks)
    return (
        PreparedCandidate(
            output_model=RevisionCandidateContent,
            context={"feedback": feedback, "available_targets": ALL_TEXT_CAPABILITIES[1:]},
            fallback=revision_content,
            source_asset_ids={
                "affected_asset_ids": sorted(
                    {str(asset_id) for task in tasks for asset_id in task.affected_asset_ids}
                )
            },
        ),
        None,
        None,
    )


async def _materialize_candidate(
    session: AsyncSession,
    project_id: UUID,
    candidate: GenerationCandidate,
) -> tuple[str, UUID]:
    if candidate.workflow == TextWorkflow.song_spec:
        song_spec_content = SongSpecData.model_validate(candidate.content)
        intake_id = _source_uuid(candidate.source_asset_ids, "intake_id")
        song_spec_version = await _create_song_spec_version(
            session=session,
            project_id=project_id,
            intake_id=intake_id,
            data=song_spec_content,
            parent_version_id=None,
            commit=False,
        )
        intake = await get_idea_intake(session, project_id, intake_id)
        if intake is not None:
            intake.status = IdeaIntakeStatus.generated
        return "song_spec", UUID(song_spec_version.id)
    if candidate.workflow == TextWorkflow.lyrics:
        lyrics_content = LyricsCandidateContent.model_validate(candidate.content)
        lyrics_version = await _create_lyrics_version(
            session=session,
            project_id=project_id,
            song_spec_id=_source_uuid(candidate.source_asset_ids, "song_spec_id"),
            sections=lyrics_content.sections,
            hook_candidates=lyrics_content.hook_candidates,
            parent_version_id=None,
            commit=False,
        )
        return "lyrics", UUID(lyrics_version.id)
    if candidate.workflow == TextWorkflow.arrangement:
        arrangement_content = ArrangementPlan.model_validate(candidate.content)
        arrangement_version = await _create_arrangement_plan_version(
            session=session,
            project_id=project_id,
            song_spec_id=_source_uuid(candidate.source_asset_ids, "song_spec_id"),
            lyrics_version_id=_source_uuid(candidate.source_asset_ids, "lyrics_version_id"),
            chord_version_id=_source_uuid(candidate.source_asset_ids, "chord_version_id"),
            midi_asset_ids=_source_uuid_list(candidate.source_asset_ids, "midi_asset_ids"),
            plan=arrangement_content,
            parent_version_id=None,
            commit=False,
        )
        return "arrangement", UUID(arrangement_version.id)
    revision_content = RevisionCandidateContent.model_validate(candidate.content)
    revision = RevisionRequest(
        project_id=str(project_id),
        feedback=revision_content.feedback,
        tasks=[task.model_dump(mode="json") for task in revision_content.tasks],
        created_versions=[],
    )
    session.add(revision)
    await session.flush()
    add_project_event(
        session,
        project_id=project_id,
        event_type="revision.planned",
        payload={
            "feedback": revision_content.feedback,
            "task_count": len(revision_content.tasks),
        },
        revision_request_id=UUID(revision.id),
    )
    return "revision", UUID(revision.id)


async def _approved_song_spec(
    session: AsyncSession,
    project_id: UUID,
    song_spec_id: UUID | None,
) -> tuple[SongSpecVersion | None, str | None]:
    if song_spec_id is None:
        return None, "SongSpec not found"
    song_spec = await get_song_spec_version(session, project_id, song_spec_id)
    if song_spec is None:
        return None, "SongSpec not found"
    if song_spec.status != SongSpecStatus.approved:
        return None, "SongSpec must be approved before candidate generation"
    return song_spec, None


async def select_provider_profile(
    session: AsyncSession,
    profile_id: UUID | None,
    workflow: TextWorkflow,
) -> ProviderProfile | None:
    if profile_id is not None:
        profile = await session.get(ProviderProfile, str(profile_id))
        if profile is None or not profile.enabled or workflow.value not in profile.capabilities:
            return None
        return profile
    statement: Select[tuple[ProviderProfile]] = (
        select(ProviderProfile)
        .where(ProviderProfile.enabled.is_(True))
        .order_by(ProviderProfile.is_default.desc(), ProviderProfile.created_at)
    )
    profiles = list((await session.execute(statement)).scalars().all())
    return next((profile for profile in profiles if workflow.value in profile.capabilities), None)


async def get_active_prompt(
    session: AsyncSession,
    workflow: TextWorkflow,
) -> PromptTemplateVersion | None:
    statement: Select[tuple[PromptTemplateVersion]] = (
        select(PromptTemplateVersion)
        .where(
            PromptTemplateVersion.workflow == workflow,
            PromptTemplateVersion.active.is_(True),
        )
        .order_by(PromptTemplateVersion.version_number.desc())
        .limit(1)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def _upsert_profile(
    session: AsyncSession,
    *,
    profile_key: str,
    provider_name: str,
    display_name: str,
    model: str | None,
    default_params: dict[str, object],
    enabled: bool,
    is_default: bool,
) -> None:
    statement: Select[tuple[ProviderProfile]] = select(ProviderProfile).where(
        ProviderProfile.profile_key == profile_key
    )
    profile = (await session.execute(statement)).scalar_one_or_none()
    if profile is None:
        session.add(
            ProviderProfile(
                profile_key=profile_key,
                provider_name=provider_name,
                display_name=display_name,
                capabilities=ALL_TEXT_CAPABILITIES,
                model=model,
                default_params=default_params,
                enabled=enabled,
                is_default=is_default,
            )
        )
        return
    profile.provider_name = provider_name
    profile.display_name = display_name
    profile.capabilities = ALL_TEXT_CAPABILITIES
    profile.model = model
    profile.default_params = default_params
    profile.enabled = enabled
    profile.is_default = is_default


async def _disable_profile_if_present(session: AsyncSession, profile_key: str) -> None:
    statement: Select[tuple[ProviderProfile]] = select(ProviderProfile).where(
        ProviderProfile.profile_key == profile_key
    )
    profile = (await session.execute(statement)).scalar_one_or_none()
    if profile is not None:
        profile.enabled = False
        profile.is_default = False


def build_text_provider(
    profile: ProviderProfile,
    fallback: BaseModel,
    settings: Settings,
) -> TextGenerationProvider:
    if profile.provider_name == "local_deterministic":
        return LocalDeterministicTextProvider([fallback])
    if profile.provider_name == "openai_compatible":
        if not all(
            _present(value)
            for value in (
                settings.text_provider_api_base_url,
                settings.text_provider_api_key,
                settings.text_provider_model,
            )
        ):
            raise TextProviderUnavailableError("Server text provider is not configured")
        return OpenAICompatibleTextProvider(
            api_base_url=settings.text_provider_api_base_url or "",
            api_key=settings.text_provider_api_key or "",
            model=settings.text_provider_model or "",
            timeout_seconds=settings.text_provider_timeout_seconds,
        )
    raise TextProviderUnavailableError(f"Unsupported text provider: {profile.provider_name}")


async def _fail_run(
    session: AsyncSession,
    run: GenerationRun,
    error_code: str,
    error_message: str,
) -> None:
    run.status = GenerationRunStatus.failed
    run.error_code = error_code
    run.error_message = error_message[:4000]
    run.completed_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(run)


def _candidate_score(workflow: TextWorkflow, content: BaseModel) -> float:
    if workflow == TextWorkflow.song_spec:
        song_spec_data = SongSpecData.model_validate(content.model_dump())
        return round(1 - len(song_spec_data.missing_required_fields()) / 9, 4)
    if workflow == TextWorkflow.revision:
        revision_data = RevisionCandidateContent.model_validate(content.model_dump())
        return round(
            sum(task.supported for task in revision_data.tasks) / len(revision_data.tasks),
            4,
        )
    return 1.0


def _payload_from_manifest(manifest: dict[str, object]) -> CandidateGenerateRequest:
    payload = manifest.get("payload")
    if not isinstance(payload, dict):
        raise InvalidProviderOutputError("Generation run payload is missing")
    return CandidateGenerateRequest.model_validate(payload)


def _manifest_string(manifest: dict[str, object], key: str) -> str:
    value = manifest.get(key)
    if not isinstance(value, str):
        raise InvalidProviderOutputError(f"Generation run {key} is missing")
    return value


def _source_uuid(source: dict[str, object], key: str) -> UUID:
    value = source.get(key)
    if not isinstance(value, str):
        raise InvalidProviderOutputError(f"Candidate source {key} is missing")
    return UUID(value)


def _source_uuid_list(source: dict[str, object], key: str) -> list[UUID]:
    value = source.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise InvalidProviderOutputError(f"Candidate source {key} is missing")
    return [UUID(item) for item in value]


def _present(value: str | None) -> bool:
    return bool(value and value.strip())

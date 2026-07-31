"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { useParams } from "next/navigation";

import { useWorkspaceData } from "./hooks/use-workspace-data";
import { usePendingActions } from "./hooks/use-pending-actions";

import {
  CollaborationWorkspace,
  buildCommentTargets,
  makeCommentTargetValue,
  parseCommentTarget,
} from "@/components/workspace/collaboration-workspace";
import type { AudioUploadUpdatePayload } from "@/components/workspace/audio-workspace";
import {
  DeliveryWorkspace,
  emptyArrangementPlan,
} from "@/components/workspace/delivery-workspace";
import { ProjectOverview } from "@/components/workspace/project-overview";
import { StructureWorkspace } from "@/components/workspace/structure-workspace";
import {
  SongSpecDraftForm,
  SongSpecVersionsPanel,
  SongSpecWorkspace,
} from "@/components/workspace/song-spec-workspace";
import { useLocale } from "@/i18n/locale-provider";
import { fetchJson } from "@/lib/api-client";
import {
  CandidateGeneratePayload,
  CandidateSelection,
  TextWorkflow,
  candidateGenerateEndpoint,
  candidateSelectEndpoint,
  textGenerationRuns,
} from "@/lib/ai-generation";
import {
  LyricsRewritePayload,
  LyricsRewritePreview,
  lyricsRewriteEndpoint,
} from "@/lib/lyrics-editor";

import {
  ArrangementPlan,
  AudioUpload,
  AudioUploadKind,
  ChordPreview,
  ChordProgressionVersion,
  ChordSection,
  GenerationRun,
  HookCandidate,
  LyricSection,
  LyricsVersion,
  MidiAssetVersion,
  ProjectComment,
  RevisionApplyResponse,
  RevisionRequest,
  RestoreAssetType,
  VersionAssetType,
  VersionDiff,
  audioExtractMidiEndpoint,
  audioUploadEndpoint,
  audioUploadsEndpoint,
  arrangementGenerateEndpoint,
  arrangementVersionEndpoint,
  canCreateExport,
  canGenerateDemo,
  canGenerateArrangement,
  canGenerateComposition,
  chordVersionEndpoint,
  chordPreviewEndpoint,
  chordTransposeEndpoint,
  chordsGenerateEndpoint,
  demoGenerateEndpoint,
  exportsEndpoint,
  isRunActive,
  latestApprovedSongSpec,
  lyricsGenerateEndpoint,
  lyricsVersionEndpoint,
  midiGenerateEndpoint,
  projectCommentEndpoint,
  projectCommentsEndpoint,
  revisionApplyEndpoint,
  revisionRejectEndpoint,
  revisionsEndpoint,
  sortArrangementVersions,
  sortAudioUploads,
  sortChordVersions,
  sortDemoVersions,
  sortExportBundles,
  sortGenerationRuns,
  sortLyricsVersions,
  sortMidiAssets,
  sortProjectComments,
  sortProjectEvents,
  sortRevisionRequests,
  taskCancelEndpoint,
  taskRetryEndpoint,
  validateArrangementPlan,
  validateAudioUploadFile,
  validateAudioUploadNotes,
  validateChordSections,
  validateCommentBody,
  validateLyricSections,
  validateRevisionFeedback,
  versionDiffEndpoint,
  versionRestoreEndpoint,
} from "@/lib/composition";
import { deriveCreationStage } from "@/lib/creation-stage";
import {
  Project,
  normalizeApiBaseUrl,
  projectDetailEndpoint,
  validateProjectDescription,
  validateProjectName,
} from "@/lib/projects";
import {
  IdeaIntake,
  SongSpec,
  SongSpecVersion,
  intakeEndpoint,
  songSpecApproveEndpoint,
  songSpecGenerateEndpoint,
  songSpecVersionEndpoint,
  sortSongSpecVersions,
  validateIdea,
  workspaceState,
} from "@/lib/song-specs";
import {
  StructureChange,
  StructureChangeRequest,
  structureEndpoint,
} from "@/lib/structure";

const workspaceLoading = () => <div className="workspace-panel-loading" aria-hidden="true" />;
const AudioWorkspace = dynamic(
  () => import("@/components/workspace/audio-workspace").then((module) => module.AudioWorkspace),
  { loading: workspaceLoading },
);
const CompositionWorkspace = dynamic(
  () =>
    import("@/components/workspace/composition-workspace").then(
      (module) => module.CompositionWorkspace,
    ),
  { loading: workspaceLoading },
);
const DemoWorkspace = dynamic(
  () => import("@/components/workspace/demo-workspace").then((module) => module.DemoWorkspace),
  { loading: workspaceLoading },
);
const RevisionWorkspace = dynamic(
  () =>
    import("@/components/workspace/revision-workspace").then(
      (module) => module.RevisionWorkspace,
    ),
  { loading: workspaceLoading },
);
const CandidateWorkspace = dynamic(
  () =>
    import("@/components/workspace/candidate-workspace").then(
      (module) => module.CandidateWorkspace,
    ),
  { loading: workspaceLoading },
);
const CreationChainProgress = dynamic(
  () =>
    import("@/components/workspace/creation-chain-progress").then(
      (module) => module.CreationChainProgress,
    ),
  { loading: workspaceLoading },
);

const apiBaseUrl = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL);

export default function ProjectWorkspaceClient() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
  const { errorMessage, locale, t, text } = useLocale();
  function handleApiError(e: unknown, fallback: string) {
    let hint: string | null = null;
    if (
      typeof e === "object" &&
      e !== null &&
      "hint" in e &&
      typeof (e as { hint: unknown }).hint === "string"
    ) {
      hint = (e as { hint: string }).hint;
    }
    setError(errorMessage(e, fallback as never));
    setErrorHint(hint);
  }
  const {
    project,
    setProject,
    latestIntake,
    setLatestIntake,
    versions,
    setVersions,
    lyricsVersions,
    setLyricsVersions,
    chordVersions,
    setChordVersions,
    midiAssets,
    setMidiAssets,
    arrangementVersions,
    assetTree,
    exportBundles,
    demoVersions,
    generationRuns,
    setGenerationRuns,
    revisionRequests,
    setRevisionRequests,
    projectComments,
    setProjectComments,
    projectEvents,
    projectHandoff,
    projectReview,
    audioUploads,
    setAudioUploads,
    providerProfiles,
    candidates,
    isLoading,
    error,
    setError,
    loadWorkspace,
  } = useWorkspaceData(apiBaseUrl, projectId);
  const [errorHint, setErrorHint] = useState<string | null>(null);
  const [idea, setIdea] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [draftForm, setDraftForm] = useState<SongSpecDraftForm>(() => emptyDraftForm());
  const [arrangementDraft, setArrangementDraft] = useState<ArrangementPlan>(() => emptyArrangementPlan());
  const [revisionFeedback, setRevisionFeedback] = useState("");
  const [commentBody, setCommentBody] = useState("");
  const [commentAuthor, setCommentAuthor] = useState(() => t("Local collaborator"));
  const [commentTargetValue, setCommentTargetValue] = useState(
    makeCommentTargetValue("project", null),
  );
  const [versionDiff, setVersionDiff] = useState<VersionDiff | null>(null);
  const [audioUploadFile, setAudioUploadFile] = useState<File | null>(null);
  const [audioUploadKind, setAudioUploadKind] = useState<AudioUploadKind>("humming");
  const [audioUploadNotes, setAudioUploadNotes] = useState("");
  const [projectNameDraft, setProjectNameDraft] = useState("");
  const [projectDescriptionDraft, setProjectDescriptionDraft] = useState("");
  const pendingActions = usePendingActions();

  const sortedVersions = useMemo(() => sortSongSpecVersions(versions), [versions]);
  const sortedLyrics = useMemo(() => sortLyricsVersions(lyricsVersions), [lyricsVersions]);
  const sortedChords = useMemo(() => sortChordVersions(chordVersions), [chordVersions]);
  const sortedMidiAssets = useMemo(() => sortMidiAssets(midiAssets), [midiAssets]);
  const sortedArrangements = useMemo(
    () => sortArrangementVersions(arrangementVersions),
    [arrangementVersions],
  );
  const sortedExports = useMemo(() => sortExportBundles(exportBundles), [exportBundles]);
  const sortedDemos = useMemo(() => sortDemoVersions(demoVersions), [demoVersions]);
  const sortedRuns = useMemo(() => sortGenerationRuns(generationRuns), [generationRuns]);
  const sortedRevisions = useMemo(() => sortRevisionRequests(revisionRequests), [revisionRequests]);
  const sortedComments = useMemo(() => sortProjectComments(projectComments), [projectComments]);
  const sortedProjectEvents = useMemo(() => sortProjectEvents(projectEvents), [projectEvents]);
  const sortedAudioUploads = useMemo(() => sortAudioUploads(audioUploads), [audioUploads]);
  const demoRuns = useMemo(
    () => sortedRuns.filter((run) => run.run_type === "demo_generation"),
    [sortedRuns],
  );
  const audioRuns = useMemo(
    () => sortedRuns.filter((run) => run.run_type === "audio_to_midi"),
    [sortedRuns],
  );
  const textRuns = useMemo(() => textGenerationRuns(sortedRuns), [sortedRuns]);
  const melodyAssets = useMemo(
    () => sortedMidiAssets.filter((asset) => asset.kind === "melody"),
    [sortedMidiAssets],
  );
  const activeVersion = sortedVersions[0] ?? null;
  const approvedVersion = useMemo(() => latestApprovedSongSpec(sortedVersions), [sortedVersions]);
  const activeLyrics = sortedLyrics[0] ?? null;
  const activeChords = sortedChords[0] ?? null;
  const activeArrangement = sortedArrangements[0] ?? null;
  const state = workspaceState({ isLoading, latestIntake, versions: sortedVersions });
  const canGenerateAssets = canGenerateComposition(sortedVersions);
  const canGenerateArrangementPlan = canGenerateArrangement(assetTree);
  const canExportProject = canCreateExport(assetTree);
  const hasActiveDemoRun = demoRuns.some(isRunActive);
  const canGenerateDemoVersion = canGenerateDemo(assetTree) && !hasActiveDemoRun;
  const creationStage = useMemo(
    () =>
      deriveCreationStage({
        latestIntake,
        versions: sortedVersions,
        lyricsVersions: sortedLyrics,
        chordVersions: sortedChords,
        midiAssets: sortedMidiAssets,
        arrangementVersions: sortedArrangements,
        assetTree,
        demoVersions: sortedDemos,
        exportBundles: sortedExports,
      }),
    [
      latestIntake,
      sortedVersions,
      sortedLyrics,
      sortedChords,
      sortedMidiAssets,
      sortedArrangements,
      assetTree,
      sortedDemos,
      sortedExports,
    ],
  );
  const commentTargets = useMemo(
    () =>
      buildCommentTargets({
        assetTree,
        demos: sortedDemos,
        exports: sortedExports,
        uploads: sortedAudioUploads,
        revisions: sortedRevisions,
      }, locale),
    [assetTree, locale, sortedDemos, sortedExports, sortedAudioUploads, sortedRevisions],
  );

  useEffect(() => {
    setCommentAuthor((current) =>
      current === "Local collaborator" || current === "本地协作者"
        ? t("Local collaborator")
        : current,
    );
  }, [t]);

  useEffect(() => {
    setIdea(latestIntake?.idea ?? "");
    setAnswers(latestIntake?.answers ?? {});
  }, [latestIntake]);

  useEffect(() => {
    setProjectNameDraft(project?.name ?? "");
    setProjectDescriptionDraft(project?.description ?? "");
  }, [project]);

  useEffect(() => {
    setDraftForm(activeVersion ? draftFormFromSongSpec(activeVersion.song_spec) : emptyDraftForm());
  }, [activeVersion]);

  useEffect(() => {
    setArrangementDraft(activeArrangement?.arrangement_plan ?? emptyArrangementPlan());
  }, [activeArrangement]);

  async function handleIntakeSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateIdea(idea);
    if (validationError) {
      setError(text(validationError));
      return;
    }
    pendingActions.begin("songSpec");
    setError(null);
    setErrorHint(null);
    try {
      const intake = await fetchJson<IdeaIntake>(intakeEndpoint(apiBaseUrl, projectId), "Idea intake", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idea, answers }),
      });
      setLatestIntake(intake);
      setAnswers(intake.answers);
      await loadWorkspace();
    } catch (submitError) {
      handleApiError(submitError, "Failed to save intake");
    } finally {
      pendingActions.end("songSpec");
    }
  }

  async function handleGenerateDraft() {
    if (!latestIntake) {
      setError(t("Create an idea intake before generating a SongSpec."));
      return;
    }
    pendingActions.begin("songSpec");
    setError(null);
    setErrorHint(null);
    try {
      const generated = await fetchJson<SongSpecVersion>(
        songSpecGenerateEndpoint(apiBaseUrl, projectId),
        "SongSpec generate",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ intake_id: latestIntake.intake_id }),
        },
      );
      setVersions((current) => sortSongSpecVersions([generated, ...current]));
      await loadWorkspace();
    } catch (generateError) {
      handleApiError(generateError, "Failed to generate SongSpec");
    } finally {
      pendingActions.end("songSpec");
    }
  }

  async function handleGenerateCandidates(input: {
    workflow: TextWorkflow;
    providerProfileId: string;
    candidateCount: number;
    feedback: string;
  }) {
    const payload: CandidateGeneratePayload = {
      workflow: input.workflow,
      provider_profile_id: input.providerProfileId,
      candidate_count: input.candidateCount,
    };
    if (input.workflow === "song_spec" && latestIntake) {
      payload.intake_id = latestIntake.intake_id;
    }
    if (input.workflow === "lyrics" || input.workflow === "arrangement") {
      if (!approvedVersion) {
        setError(t("Approve a SongSpec first."));
        return;
      }
      payload.song_spec_id = approvedVersion.id;
    }
    if (input.workflow === "revision") {
      payload.feedback = input.feedback;
    }
    pendingActions.begin("ai");
    setError(null);
    setErrorHint(null);
    try {
      const run = await fetchJson<GenerationRun>(
        candidateGenerateEndpoint(apiBaseUrl, projectId),
        "Candidate generation",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      setGenerationRuns((current) => sortGenerationRuns([run, ...current]));
      await loadWorkspace();
    } catch (candidateError) {
      handleApiError(candidateError, "Failed to generate candidates");
    } finally {
      pendingActions.end("ai");
    }
  }

  async function handleSelectCandidate(candidateId: string) {
    pendingActions.begin("ai");
    setError(null);
    setErrorHint(null);
    try {
      await fetchJson<CandidateSelection>(
        candidateSelectEndpoint(apiBaseUrl, projectId, candidateId),
        "Candidate selection",
        { method: "POST" },
      );
      await loadWorkspace();
    } catch (candidateError) {
      handleApiError(candidateError, "Failed to select candidate");
    } finally {
      pendingActions.end("ai");
    }
  }

  async function handleSongSpecSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeVersion) {
      return;
    }
    const payload = parseDraftForm(draftForm);
    if (payload instanceof Error) {
      setError(text(payload.message));
      return;
    }
    pendingActions.begin("songSpec");
    setError(null);
    setErrorHint(null);
    try {
      const edited = await fetchJson<SongSpecVersion>(
        songSpecVersionEndpoint(apiBaseUrl, projectId, activeVersion.id),
        "SongSpec edit",
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      setVersions((current) => sortSongSpecVersions([edited, ...current]));
      await loadWorkspace();
    } catch (editError) {
      handleApiError(editError, "Failed to edit SongSpec");
    } finally {
      pendingActions.end("songSpec");
    }
  }

  async function handleApprove() {
    if (!activeVersion) {
      return;
    }
    pendingActions.begin("songSpec");
    setError(null);
    setErrorHint(null);
    try {
      await fetchJson<SongSpecVersion>(
        songSpecApproveEndpoint(apiBaseUrl, projectId, activeVersion.id),
        "SongSpec approve",
        { method: "POST" },
      );
      await loadWorkspace();
    } catch (approveError) {
      handleApiError(approveError, "Failed to approve SongSpec");
    } finally {
      pendingActions.end("songSpec");
    }
  }

  async function handleStructureChange(
    payload: StructureChangeRequest,
  ): Promise<StructureChange> {
    pendingActions.begin("structure");
    setError(null);
    setErrorHint(null);
    try {
      const result = await fetchJson<StructureChange>(
        structureEndpoint(apiBaseUrl, projectId),
        "Structure change",
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      if (result.status === "applied") {
        await loadWorkspace();
      }
      return result;
    } catch (structureError) {
      handleApiError(structureError, "Failed to update song structure");
      throw structureError;
    } finally {
      pendingActions.end("structure");
    }
  }

  async function handleGenerateLyrics() {
    if (!approvedVersion) {
      setError(t("Approve a SongSpec before generating lyrics."));
      return;
    }
    pendingActions.begin("composition");
    setError(null);
    setErrorHint(null);
    try {
      const generated = await fetchJson<LyricsVersion>(
        lyricsGenerateEndpoint(apiBaseUrl, projectId),
        "Lyrics generate",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ song_spec_id: approvedVersion.id }),
        },
      );
      setLyricsVersions((current) => sortLyricsVersions([generated, ...current]));
      await loadWorkspace();
    } catch (lyricsError) {
      handleApiError(lyricsError, "Failed to generate lyrics");
    } finally {
      pendingActions.end("composition");
    }
  }

  async function handleLyricsSave(
    sections: LyricSection[],
    hookCandidates: HookCandidate[],
  ) {
    if (!activeLyrics) {
      return;
    }
    const validationError = validateLyricSections(sections);
    if (validationError) {
      setError(text(validationError));
      return;
    }
    pendingActions.begin("lyrics");
    setError(null);
    setErrorHint(null);
    try {
      const edited = await fetchJson<LyricsVersion>(
        lyricsVersionEndpoint(apiBaseUrl, projectId, activeLyrics.id),
        "Lyrics edit",
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            sections,
            hook_candidates: normalizeHookDraft(hookCandidates),
          }),
        },
      );
      setLyricsVersions((current) => sortLyricsVersions([edited, ...current]));
      await loadWorkspace();
    } catch (lyricsError) {
      handleApiError(lyricsError, "Failed to edit lyrics");
    } finally {
      pendingActions.end("lyrics");
    }
  }

  async function handleLyricsRewrite(
    payload: LyricsRewritePayload,
  ): Promise<LyricsRewritePreview> {
    if (!activeLyrics) {
      throw new Error("LyricsVersion not found");
    }
    pendingActions.begin("lyricsRewrite");
    setError(null);
    setErrorHint(null);
    try {
      return await fetchJson<LyricsRewritePreview>(
        lyricsRewriteEndpoint(apiBaseUrl, projectId, activeLyrics.id),
        "Lyrics rewrite",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
    } catch (lyricsError) {
      handleApiError(lyricsError, "Failed to preview lyrics rewrite");
      throw lyricsError;
    } finally {
      pendingActions.end("lyricsRewrite");
    }
  }

  async function handleGenerateChords() {
    if (!approvedVersion) {
      setError(t("Approve a SongSpec before generating chords."));
      return;
    }
    pendingActions.begin("chords");
    setError(null);
    setErrorHint(null);
    try {
      const generated = await fetchJson<ChordProgressionVersion>(
        chordsGenerateEndpoint(apiBaseUrl, projectId),
        "Chords generate",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            song_spec_id: approvedVersion.id,
            lyrics_version_id: activeLyrics?.id,
          }),
        },
      );
      setChordVersions((current) => sortChordVersions([generated, ...current]));
      await loadWorkspace();
    } catch (chordsError) {
      handleApiError(chordsError, "Failed to generate chords");
    } finally {
      pendingActions.end("chords");
    }
  }

  async function handleChordsSave(sections: ChordSection[]) {
    if (!activeChords) {
      return;
    }
    const validationError = validateChordSections(sections, activeChords.time_signature);
    if (validationError) {
      setError(text(validationError));
      return;
    }
    pendingActions.begin("chords");
    setError(null);
    setErrorHint(null);
    try {
      const edited = await fetchJson<ChordProgressionVersion>(
        chordVersionEndpoint(apiBaseUrl, projectId, activeChords.id),
        "Chords edit",
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sections }),
        },
      );
      setChordVersions((current) => sortChordVersions([edited, ...current]));
      await loadWorkspace();
    } catch (chordsError) {
      handleApiError(chordsError, "Failed to edit chords");
    } finally {
      pendingActions.end("chords");
    }
  }

  async function handleChordsPreview(sections: ChordSection[]): Promise<ChordPreview> {
    if (!activeChords) {
      throw new Error("ChordProgressionVersion not found");
    }
    const validationError = validateChordSections(sections, activeChords.time_signature);
    if (validationError) {
      const validation = new Error(text(validationError));
      setError(validation.message);
      throw validation;
    }
    pendingActions.begin("chordsPreview");
    setError(null);
    setErrorHint(null);
    try {
      return await fetchJson<ChordPreview>(
        chordPreviewEndpoint(apiBaseUrl, projectId, activeChords.id),
        "Chords preview",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sections }),
        },
      );
    } catch (chordsError) {
      handleApiError(chordsError, "Failed to validate chords");
      throw chordsError;
    } finally {
      pendingActions.end("chordsPreview");
    }
  }

  async function handleChordsTranspose(semitones: number, sectionIds: string[] | null) {
    if (!activeChords) {
      return;
    }
    pendingActions.begin("chordsTranspose");
    setError(null);
    setErrorHint(null);
    try {
      const transposed = await fetchJson<ChordProgressionVersion>(
        chordTransposeEndpoint(apiBaseUrl, projectId, activeChords.id),
        "Chords transpose",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            semitones,
            section_ids: sectionIds,
          }),
        },
      );
      setChordVersions((current) => sortChordVersions([transposed, ...current]));
      await loadWorkspace();
    } catch (chordsError) {
      handleApiError(chordsError, "Failed to transpose chords");
    } finally {
      pendingActions.end("chordsTranspose");
    }
  }

  async function handleGenerateMidi() {
    if (!approvedVersion) {
      setError(t("Approve a SongSpec before generating MIDI."));
      return;
    }
    pendingActions.begin("composition");
    setError(null);
    setErrorHint(null);
    try {
      const generated = await fetchJson<MidiAssetVersion[]>(
        midiGenerateEndpoint(apiBaseUrl, projectId),
        "MIDI generate",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            song_spec_id: approvedVersion.id,
            lyrics_version_id: activeLyrics?.id,
            chord_version_id: activeChords?.id,
          }),
        },
      );
      setMidiAssets((current) => sortMidiAssets([...generated, ...current]));
      await loadWorkspace();
    } catch (midiError) {
      handleApiError(midiError, "Failed to generate MIDI");
    } finally {
      pendingActions.end("composition");
    }
  }

  async function handleAudioUploadSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateAudioUploadFile(audioUploadFile);
    if (validationError) {
      setError(text(validationError));
      return;
    }
    if (!audioUploadFile) {
      return;
    }
    pendingActions.begin("audio");
    setError(null);
    setErrorHint(null);
    try {
      const formData = new FormData();
      formData.append("file", audioUploadFile);
      formData.append("kind", audioUploadKind);
      if (audioUploadNotes.trim()) {
        formData.append("notes", audioUploadNotes.trim());
      }
      const upload = await fetchJson<AudioUpload>(audioUploadsEndpoint(apiBaseUrl, projectId), "Audio upload", {
        method: "POST",
        body: formData,
      });
      setAudioUploads((current) => sortAudioUploads([upload, ...current]));
      setAudioUploadFile(null);
      setAudioUploadNotes("");
      await loadWorkspace();
    } catch (uploadError) {
      handleApiError(uploadError, "Failed to upload audio");
    } finally {
      pendingActions.end("audio");
    }
  }

  async function handleUpdateAudioUpload(
    audioUploadId: string,
    payload: AudioUploadUpdatePayload,
  ) {
    if (payload.notes !== undefined) {
      const notesError = validateAudioUploadNotes(payload.notes ?? "");
      if (notesError) {
        setError(text(notesError));
        return;
      }
    }

    pendingActions.begin("audio");
    setError(null);
    setErrorHint(null);
    try {
      const updatedUpload = await fetchJson<AudioUpload>(
        audioUploadEndpoint(apiBaseUrl, projectId, audioUploadId),
        "Audio upload update",
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
      setAudioUploads((current) =>
        sortAudioUploads(
          current.map((upload) => (upload.id === updatedUpload.id ? updatedUpload : upload)),
        ),
      );
      await loadWorkspace();
    } catch (updateError) {
      handleApiError(updateError, "Failed to update audio");
    } finally {
      pendingActions.end("audio");
    }
  }

  async function handleExtractAudioMidi(audioUploadId: string) {
    if (!approvedVersion) {
      setError(t("Approve a SongSpec before extracting melody MIDI."));
      return;
    }
    pendingActions.begin("audio");
    setError(null);
    setErrorHint(null);
    try {
      const run = await fetchJson<GenerationRun>(
        audioExtractMidiEndpoint(apiBaseUrl, projectId, audioUploadId),
        "Audio-to-MIDI extraction",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ song_spec_id: approvedVersion.id, target_kind: "melody" }),
        },
      );
      setGenerationRuns((current) => sortGenerationRuns([run, ...current]));
      await loadWorkspace();
    } catch (extractError) {
      handleApiError(extractError, "Failed to extract melody MIDI");
    } finally {
      pendingActions.end("audio");
    }
  }

  async function handleGenerateArrangement() {
    if (!approvedVersion) {
      setError(t("Approve a SongSpec before generating an arrangement."));
      return;
    }
    pendingActions.begin("delivery");
    setError(null);
    setErrorHint(null);
    try {
      await fetchJson<unknown>(
        arrangementGenerateEndpoint(apiBaseUrl, projectId),
        "Arrangement generate",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ song_spec_id: approvedVersion.id }),
        },
      );
      await loadWorkspace();
    } catch (arrangementError) {
      handleApiError(arrangementError, "Failed to generate arrangement");
    } finally {
      pendingActions.end("delivery");
    }
  }

  async function handleArrangementSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeArrangement) {
      return;
    }
    const validationError = validateArrangementPlan(arrangementDraft);
    if (validationError) {
      setError(text(validationError));
      return;
    }
    pendingActions.begin("delivery");
    setError(null);
    setErrorHint(null);
    try {
      await fetchJson<unknown>(
        arrangementVersionEndpoint(apiBaseUrl, projectId, activeArrangement.id),
        "Arrangement edit",
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(arrangementDraft),
        },
      );
      await loadWorkspace();
    } catch (arrangementError) {
      handleApiError(arrangementError, "Failed to edit arrangement");
    } finally {
      pendingActions.end("delivery");
    }
  }

  async function handleCreateExport() {
    pendingActions.begin("delivery");
    setError(null);
    setErrorHint(null);
    try {
      await fetchJson<unknown>(exportsEndpoint(apiBaseUrl, projectId), "Project export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ arrangement_plan_id: activeArrangement?.id ?? null }),
      });
      await loadWorkspace();
    } catch (exportError) {
      handleApiError(exportError, "Failed to export project");
    } finally {
      pendingActions.end("delivery");
    }
  }

  async function handleGenerateDemo() {
    pendingActions.begin("demo");
    setError(null);
    setErrorHint(null);
    try {
      const run = await fetchJson<GenerationRun>(
        demoGenerateEndpoint(apiBaseUrl, projectId),
        "Demo generation",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ arrangement_plan_id: activeArrangement?.id ?? null }),
        },
      );
      setGenerationRuns((current) => sortGenerationRuns([run, ...current]));
      await loadWorkspace();
    } catch (demoError) {
      handleApiError(demoError, "Failed to generate demo");
    } finally {
      pendingActions.end("demo");
    }
  }

  async function handleRetryRun(runId: string) {
    pendingActions.begin("tasks");
    setError(null);
    setErrorHint(null);
    try {
      const run = await fetchJson<GenerationRun>(
        taskRetryEndpoint(apiBaseUrl, runId),
        "Demo retry",
        { method: "POST" },
      );
      setGenerationRuns((current) => sortGenerationRuns([run, ...current]));
      await loadWorkspace();
    } catch (retryError) {
      handleApiError(retryError, "Failed to retry demo");
    } finally {
      pendingActions.end("tasks");
    }
  }

  async function handleCancelRun(runId: string) {
    pendingActions.begin("tasks");
    setError(null);
    setErrorHint(null);
    try {
      const run = await fetchJson<GenerationRun>(
        taskCancelEndpoint(apiBaseUrl, runId),
        "Demo cancel",
        { method: "POST" },
      );
      setGenerationRuns((current) =>
        sortGenerationRuns(current.map((item) => (item.id === run.id ? run : item))),
      );
      await loadWorkspace();
    } catch (cancelError) {
      handleApiError(cancelError, "Failed to cancel task");
    } finally {
      pendingActions.end("tasks");
    }
  }

  async function handleCreateRevision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateRevisionFeedback(revisionFeedback);
    if (validationError) {
      setError(text(validationError));
      return;
    }
    pendingActions.begin("revision");
    setError(null);
    setErrorHint(null);
    try {
      const revision = await fetchJson<RevisionRequest>(
        revisionsEndpoint(apiBaseUrl, projectId),
        "Revision plan",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ feedback: revisionFeedback }),
        },
      );
      setRevisionRequests((current) => sortRevisionRequests([revision, ...current]));
      setRevisionFeedback("");
      await loadWorkspace();
    } catch (revisionError) {
      handleApiError(revisionError, "Failed to plan revision");
    } finally {
      pendingActions.end("revision");
    }
  }

  async function handleApplyRevision(revisionId: string, regenerateDemo: boolean) {
    pendingActions.begin("revision");
    setError(null);
    setErrorHint(null);
    try {
      const result = await fetchJson<RevisionApplyResponse>(
        revisionApplyEndpoint(apiBaseUrl, projectId, revisionId),
        "Revision apply",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ regenerate_demo: regenerateDemo }),
        },
      );
      setRevisionRequests((current) =>
        sortRevisionRequests(current.map((item) => (item.id === result.revision.id ? result.revision : item))),
      );
      await loadWorkspace();
    } catch (applyError) {
      handleApiError(applyError, "Failed to apply revision");
    } finally {
      pendingActions.end("revision");
    }
  }

  async function handleRejectRevision(revisionId: string) {
    pendingActions.begin("revision");
    setError(null);
    setErrorHint(null);
    try {
      const revision = await fetchJson<RevisionRequest>(
        revisionRejectEndpoint(apiBaseUrl, projectId, revisionId),
        "Revision reject",
        { method: "POST" },
      );
      setRevisionRequests((current) =>
        sortRevisionRequests(current.map((item) => (item.id === revision.id ? revision : item))),
      );
      await loadWorkspace();
    } catch (rejectError) {
      handleApiError(rejectError, "Failed to reject revision");
    } finally {
      pendingActions.end("revision");
    }
  }

  async function handleCreateComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateCommentBody(commentBody);
    if (validationError) {
      setError(text(validationError));
      return;
    }
    pendingActions.begin("collaboration");
    setError(null);
    setErrorHint(null);
    try {
      const target = parseCommentTarget(commentTargetValue);
      const comment = await fetchJson<ProjectComment>(
        projectCommentsEndpoint(apiBaseUrl, projectId),
        "Comment create",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            body: commentBody,
            author_name: commentAuthor.trim() || t("Local collaborator"),
            target_type: target.target_type,
            target_id: target.target_id,
          }),
        },
      );
      setProjectComments((current) => sortProjectComments([comment, ...current]));
      setCommentBody("");
      await loadWorkspace();
    } catch (commentError) {
      handleApiError(commentError, "Failed to create comment");
    } finally {
      pendingActions.end("collaboration");
    }
  }

  async function handleUpdateComment(commentId: string, status: ProjectComment["status"]) {
    pendingActions.begin("collaboration");
    setError(null);
    setErrorHint(null);
    try {
      const comment = await fetchJson<ProjectComment>(
        projectCommentEndpoint(apiBaseUrl, projectId, commentId),
        "Comment update",
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status }),
        },
      );
      setProjectComments((current) =>
        sortProjectComments(current.map((item) => (item.id === comment.id ? comment : item))),
      );
      await loadWorkspace();
    } catch (commentError) {
      handleApiError(commentError, "Failed to update comment");
    } finally {
      pendingActions.end("collaboration");
    }
  }

  async function handleCompareVersions(
    assetType: VersionAssetType,
    leftId: string,
    rightId: string,
  ) {
    pendingActions.begin("revision");
    setError(null);
    setErrorHint(null);
    try {
      const diff = await fetchJson<VersionDiff>(
        versionDiffEndpoint(apiBaseUrl, projectId, assetType, leftId, rightId),
        "Version diff",
      );
      setVersionDiff(diff);
    } catch (diffError) {
      handleApiError(diffError, "Failed to compare versions");
    } finally {
      pendingActions.end("revision");
    }
  }

  async function handleRestoreVersion(assetType: RestoreAssetType, versionId: string) {
    pendingActions.begin("revision");
    setError(null);
    setErrorHint(null);
    try {
      await fetchJson<unknown>(versionRestoreEndpoint(apiBaseUrl, projectId), "Version restore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_type: assetType, version_id: versionId }),
      });
      await loadWorkspace();
    } catch (restoreError) {
      handleApiError(restoreError, "Failed to restore version");
    } finally {
      pendingActions.end("revision");
    }
  }

  async function handleProjectSettingsSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nameError = validateProjectName(projectNameDraft);
    if (nameError) {
      setError(text(nameError));
      return;
    }
    const descriptionError = validateProjectDescription(projectDescriptionDraft);
    if (descriptionError) {
      setError(text(descriptionError));
      return;
    }

    pendingActions.begin("project");
    setError(null);
    setErrorHint(null);
    try {
      const updatedProject = await fetchJson<Project>(
        projectDetailEndpoint(apiBaseUrl, projectId),
        "Project update",
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: projectNameDraft.trim(),
            description: projectDescriptionDraft.trim() || null,
          }),
        },
      );
      setProject(updatedProject);
    } catch (updateError) {
      handleApiError(updateError, "Failed to update project");
    } finally {
      pendingActions.end("project");
    }
  }

  async function handleProjectStatusToggle() {
    if (!project) {
      return;
    }

    pendingActions.begin("project");
    setError(null);
    setErrorHint(null);
    try {
      const updatedProject = await fetchJson<Project>(
        projectDetailEndpoint(apiBaseUrl, projectId),
        "Project status update",
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: project.status === "archived" ? "active" : "archived" }),
        },
      );
      setProject(updatedProject);
    } catch (statusError) {
      handleApiError(statusError, "Failed to update project status");
    } finally {
      pendingActions.end("project");
    }
  }

  return (
    <div className="workspace">
      <ProjectOverview
        description={projectDescriptionDraft}
        error={error}
        errorHint={errorHint}
        handoff={projectHandoff}
        isLoading={isLoading}
        isSaving={pendingActions.isPending("project")}
        name={projectNameDraft}
        onDescriptionChange={setProjectDescriptionDraft}
        onErrorHintAction={loadWorkspace}
        onNameChange={setProjectNameDraft}
        onRefresh={loadWorkspace}
        onStatusToggle={handleProjectStatusToggle}
        onSubmit={handleProjectSettingsSubmit}
        project={project}
        review={projectReview}
      />

      {!isLoading ? <CreationChainProgress stage={creationStage} /> : null}

      <div id="song-spec-panel" className="workspace-anchor" tabIndex={-1}>
      <SongSpecWorkspace
        activeVersion={activeVersion}
        answers={answers}
        draftForm={draftForm}
        idea={idea}
        isSaving={pendingActions.isPending("songSpec")}
        latestIntake={latestIntake}
        onAnswersChange={setAnswers}
        onApprove={handleApprove}
        onDraftChange={setDraftForm}
        onGenerateDraft={handleGenerateDraft}
        onIdeaChange={setIdea}
        onIntakeSubmit={handleIntakeSubmit}
        onSongSpecSubmit={handleSongSpecSubmit}
        state={state}
      />
      </div>

      <StructureWorkspace
        isSaving={pendingActions.isPending("structure")}
        onChange={handleStructureChange}
        projectId={projectId}
        sourceVersion={approvedVersion}
      />

      <CandidateWorkspace
        approvedSongSpecId={approvedVersion?.id ?? null}
        canGenerateArrangement={canGenerateArrangementPlan}
        candidates={candidates}
        isSaving={pendingActions.isPending("ai", "tasks")}
        latestIntakeId={latestIntake?.intake_id ?? null}
        onCancel={handleCancelRun}
        onGenerate={handleGenerateCandidates}
        onSelect={handleSelectCandidate}
        providers={providerProfiles}
        runs={textRuns}
      />

      <div id="composition-panel" className="asset-grid workspace-anchor" tabIndex={-1}>
        <AudioWorkspace
          approvedSongSpecId={approvedVersion?.id ?? null}
          file={audioUploadFile}
          isSaving={pendingActions.isPending("audio", "tasks")}
          kind={audioUploadKind}
          notes={audioUploadNotes}
          onCancel={handleCancelRun}
          onExtract={handleExtractAudioMidi}
          onFileChange={setAudioUploadFile}
          onKindChange={setAudioUploadKind}
          onNotesChange={setAudioUploadNotes}
          onUpdateUpload={handleUpdateAudioUpload}
          onUpload={handleAudioUploadSubmit}
          projectId={projectId}
          runs={audioRuns}
          uploads={sortedAudioUploads}
        />
        <CompositionWorkspace
          activeChords={activeChords}
          activeLyrics={activeLyrics}
          canGenerate={canGenerateAssets}
          isGeneratingChords={pendingActions.isPending("chords")}
          isGeneratingLyrics={pendingActions.isPending("composition")}
          isPreviewingChords={pendingActions.isPending("chordsPreview")}
          isRewritingLyrics={pendingActions.isPending("lyricsRewrite")}
          isSavingComposition={pendingActions.isPending("composition")}
          isSavingChords={pendingActions.isPending("chords")}
          isSavingLyrics={pendingActions.isPending("lyrics")}
          isTransposingChords={pendingActions.isPending("chordsTranspose")}
          midiAssets={sortedMidiAssets}
          onGenerateChords={handleGenerateChords}
          onGenerateLyrics={handleGenerateLyrics}
          onGenerateMidi={handleGenerateMidi}
          onChordsPreview={handleChordsPreview}
          onChordsSave={handleChordsSave}
          onChordsTranspose={handleChordsTranspose}
          onLyricsRewrite={handleLyricsRewrite}
          onLyricsSave={handleLyricsSave}
          projectId={projectId}
        />
      </div>

      <div id="delivery-panel" className="delivery-grid workspace-anchor" tabIndex={-1}>
        <DeliveryWorkspace
          activeArrangement={activeArrangement}
          arrangementPlan={arrangementDraft}
          assetTree={assetTree}
          canExport={canExportProject}
          canGenerateArrangement={canGenerateArrangementPlan}
          exports={sortedExports}
          isSaving={pendingActions.isPending("delivery")}
          onArrangementChange={setArrangementDraft}
          onArrangementSubmit={handleArrangementSubmit}
          onCreateExport={handleCreateExport}
          onGenerateArrangement={handleGenerateArrangement}
        />
        <div id="demo-panel" className="workspace-anchor" tabIndex={-1}>
        <DemoWorkspace
          assetTree={assetTree}
          canGenerate={canGenerateDemoVersion}
          demos={sortedDemos}
          isSaving={pendingActions.isPending("demo", "tasks")}
          onGenerate={handleGenerateDemo}
          onCancel={handleCancelRun}
          onRetry={handleRetryRun}
          projectId={projectId}
          runs={demoRuns}
        />
        </div>
      </div>

      <RevisionWorkspace
        arrangements={sortedArrangements}
        demos={sortedDemos}
        feedback={revisionFeedback}
        isSaving={pendingActions.isPending("revision")}
        lyrics={sortedLyrics}
        melodyAssets={melodyAssets}
        onApply={handleApplyRevision}
        onCompare={handleCompareVersions}
        onFeedbackChange={setRevisionFeedback}
        onPlan={handleCreateRevision}
        onReject={handleRejectRevision}
        onRestore={handleRestoreVersion}
        revisions={sortedRevisions}
        versionDiff={versionDiff}
      />

      <CollaborationWorkspace
        author={commentAuthor}
        body={commentBody}
        comments={sortedComments}
        events={sortedProjectEvents}
        isSaving={pendingActions.isPending("collaboration")}
        onAuthorChange={setCommentAuthor}
        onBodyChange={setCommentBody}
        onSubmit={handleCreateComment}
        onTargetChange={setCommentTargetValue}
        onUpdateStatus={handleUpdateComment}
        targetOptions={commentTargets}
        targetValue={commentTargetValue}
      />

      <SongSpecVersionsPanel versions={sortedVersions} />
    </div>
  );
}

function emptyDraftForm(): SongSpecDraftForm {
  return {
    theme: "",
    genre: "",
    language: "",
    tempo_bpm: "",
    key: "",
    time_signature: "",
    target_duration_seconds: "",
    mood_curve: "",
    song_structure: "",
  };
}

function draftFormFromSongSpec(songSpec: SongSpec): SongSpecDraftForm {
  return {
    theme: songSpec.theme ?? "",
    genre: songSpec.genre?.join(", ") ?? "",
    language: songSpec.language ?? "",
    tempo_bpm: songSpec.tempo_bpm?.toString() ?? "",
    key: songSpec.key ?? "",
    time_signature: songSpec.time_signature ?? "",
    target_duration_seconds: songSpec.target_duration_seconds?.toString() ?? "",
    mood_curve: songSpec.mood_curve ? JSON.stringify(songSpec.mood_curve, null, 2) : "",
    song_structure: songSpec.song_structure?.join("\n") ?? "",
  };
}

function parseDraftForm(form: SongSpecDraftForm): SongSpec | Error {
  try {
    return {
      theme: form.theme.trim() || null,
      genre: splitList(form.genre),
      language: form.language.trim() || null,
      tempo_bpm: parseOptionalNumber(form.tempo_bpm),
      key: form.key.trim() || null,
      time_signature: form.time_signature.trim() || null,
      target_duration_seconds: parseOptionalNumber(form.target_duration_seconds),
      mood_curve: form.mood_curve.trim() ? JSON.parse(form.mood_curve) : null,
      song_structure: splitLines(form.song_structure),
    };
  } catch {
    return new Error("Mood curve must be valid JSON.");
  }
}

function splitList(value: string): string[] | null {
  const items = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return items.length ? items : null;
}

function splitLines(value: string): string[] | null {
  const items = value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
  return items.length ? items : null;
}

function parseOptionalNumber(value: string): number | null {
  const normalized = value.trim();
  return normalized ? Number(normalized) : null;
}

function normalizeHookDraft(hooks: HookCandidate[]): HookCandidate[] {
  return hooks
    .map((hook, index) => ({
      id: hook.id.trim() || `hook_${index + 1}`,
      text: hook.text.trim(),
    }))
    .filter((hook) => hook.text);
}

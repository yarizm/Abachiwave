"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { useWorkspaceData } from "./hooks/use-workspace-data";

import {
  CollaborationWorkspace,
  buildCommentTargets,
  makeCommentTargetValue,
  parseCommentTarget,
} from "@/components/workspace/collaboration-workspace";
import {
  AudioUploadUpdatePayload,
  AudioWorkspace,
} from "@/components/workspace/audio-workspace";
import { CompositionWorkspace } from "@/components/workspace/composition-workspace";
import {
  DeliveryWorkspace,
  emptyArrangementPlan,
} from "@/components/workspace/delivery-workspace";
import { DemoWorkspace } from "@/components/workspace/demo-workspace";
import { ProjectOverview } from "@/components/workspace/project-overview";
import { RevisionWorkspace } from "@/components/workspace/revision-workspace";
import {
  SongSpecDraftForm,
  SongSpecVersionsPanel,
  SongSpecWorkspace,
} from "@/components/workspace/song-spec-workspace";
import { ensureOk } from "@/lib/api-client";

import {
  ArrangementPlan,
  AudioUpload,
  AudioUploadKind,
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

const apiBaseUrl = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL);

export default function ProjectWorkspaceClient() {
  const params = useParams<{ projectId: string }>();
  const projectId = params.projectId;
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
    isLoading,
    error,
    setError,
    loadWorkspace,
  } = useWorkspaceData(apiBaseUrl, projectId);
  const [idea, setIdea] = useState("");
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [draftForm, setDraftForm] = useState<SongSpecDraftForm>(() => emptyDraftForm());
  const [lyricDraft, setLyricDraft] = useState<LyricSection[]>([]);
  const [hookDraft, setHookDraft] = useState<HookCandidate[]>([]);
  const [chordDraft, setChordDraft] = useState<ChordSection[]>([]);
  const [arrangementDraft, setArrangementDraft] = useState<ArrangementPlan>(() => emptyArrangementPlan());
  const [revisionFeedback, setRevisionFeedback] = useState("");
  const [commentBody, setCommentBody] = useState("");
  const [commentAuthor, setCommentAuthor] = useState("Local collaborator");
  const [commentTargetValue, setCommentTargetValue] = useState(
    makeCommentTargetValue("project", null),
  );
  const [versionDiff, setVersionDiff] = useState<VersionDiff | null>(null);
  const [audioUploadFile, setAudioUploadFile] = useState<File | null>(null);
  const [audioUploadKind, setAudioUploadKind] = useState<AudioUploadKind>("humming");
  const [audioUploadNotes, setAudioUploadNotes] = useState("");
  const [projectNameDraft, setProjectNameDraft] = useState("");
  const [projectDescriptionDraft, setProjectDescriptionDraft] = useState("");
  const [isSaving, setIsSaving] = useState(false);

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
  const hasActiveRun = sortedRuns.some(isRunActive);
  const hasActiveDemoRun = demoRuns.some(isRunActive);
  const canGenerateDemoVersion = canGenerateDemo(assetTree) && !hasActiveDemoRun;
  const commentTargets = useMemo(
    () =>
      buildCommentTargets({
        assetTree,
        demos: sortedDemos,
        exports: sortedExports,
        uploads: sortedAudioUploads,
        revisions: sortedRevisions,
      }),
    [assetTree, sortedDemos, sortedExports, sortedAudioUploads, sortedRevisions],
  );

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  useEffect(() => {
    setIdea(latestIntake?.idea ?? "");
    setAnswers(latestIntake?.answers ?? {});
  }, [latestIntake]);

  useEffect(() => {
    setProjectNameDraft(project?.name ?? "");
    setProjectDescriptionDraft(project?.description ?? "");
  }, [project]);

  useEffect(() => {
    if (!hasActiveRun) {
      return;
    }
    const intervalId = window.setInterval(() => {
      void loadWorkspace();
    }, 2500);
    return () => window.clearInterval(intervalId);
  }, [hasActiveRun, loadWorkspace]);

  useEffect(() => {
    setDraftForm(activeVersion ? draftFormFromSongSpec(activeVersion.song_spec) : emptyDraftForm());
  }, [activeVersion]);

  useEffect(() => {
    setLyricDraft(activeLyrics?.sections ?? []);
    setHookDraft(activeLyrics?.hook_candidates ?? []);
  }, [activeLyrics]);

  useEffect(() => {
    setChordDraft(activeChords?.sections ?? []);
  }, [activeChords]);

  useEffect(() => {
    setArrangementDraft(activeArrangement?.arrangement_plan ?? emptyArrangementPlan());
  }, [activeArrangement]);

  async function handleIntakeSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateIdea(idea);
    if (validationError) {
      setError(validationError);
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(intakeEndpoint(apiBaseUrl, projectId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ idea, answers }),
      });
      ensureOk(response, "Idea intake");
      const intake = (await response.json()) as IdeaIntake;
      setLatestIntake(intake);
      setAnswers(intake.answers);
      await loadWorkspace();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to save intake");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleGenerateDraft() {
    if (!latestIntake) {
      setError("Create an idea intake before generating a SongSpec.");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(songSpecGenerateEndpoint(apiBaseUrl, projectId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ intake_id: latestIntake.intake_id }),
      });
      ensureOk(response, "SongSpec generate");
      const generated = (await response.json()) as SongSpecVersion;
      setVersions((current) => sortSongSpecVersions([generated, ...current]));
      await loadWorkspace();
    } catch (generateError) {
      setError(
        generateError instanceof Error ? generateError.message : "Failed to generate SongSpec",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSongSpecSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeVersion) {
      return;
    }
    const payload = parseDraftForm(draftForm);
    if (payload instanceof Error) {
      setError(payload.message);
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(songSpecVersionEndpoint(apiBaseUrl, projectId, activeVersion.id), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      ensureOk(response, "SongSpec edit");
      const edited = (await response.json()) as SongSpecVersion;
      setVersions((current) => sortSongSpecVersions([edited, ...current]));
      await loadWorkspace();
    } catch (editError) {
      setError(editError instanceof Error ? editError.message : "Failed to edit SongSpec");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleApprove() {
    if (!activeVersion) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(songSpecApproveEndpoint(apiBaseUrl, projectId, activeVersion.id), {
        method: "POST",
      });
      ensureOk(response, "SongSpec approve");
      await loadWorkspace();
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : "Failed to approve SongSpec");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleGenerateLyrics() {
    if (!approvedVersion) {
      setError("Approve a SongSpec before generating lyrics.");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(lyricsGenerateEndpoint(apiBaseUrl, projectId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ song_spec_id: approvedVersion.id }),
      });
      ensureOk(response, "Lyrics generate");
      const generated = (await response.json()) as LyricsVersion;
      setLyricsVersions((current) => sortLyricsVersions([generated, ...current]));
      await loadWorkspace();
    } catch (lyricsError) {
      setError(lyricsError instanceof Error ? lyricsError.message : "Failed to generate lyrics");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleLyricsSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeLyrics) {
      return;
    }
    const validationError = validateLyricSections(lyricDraft);
    if (validationError) {
      setError(validationError);
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(lyricsVersionEndpoint(apiBaseUrl, projectId, activeLyrics.id), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sections: lyricDraft,
          hook_candidates: normalizeHookDraft(hookDraft),
        }),
      });
      ensureOk(response, "Lyrics edit");
      const edited = (await response.json()) as LyricsVersion;
      setLyricsVersions((current) => sortLyricsVersions([edited, ...current]));
      await loadWorkspace();
    } catch (lyricsError) {
      setError(lyricsError instanceof Error ? lyricsError.message : "Failed to edit lyrics");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleGenerateChords() {
    if (!approvedVersion) {
      setError("Approve a SongSpec before generating chords.");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(chordsGenerateEndpoint(apiBaseUrl, projectId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          song_spec_id: approvedVersion.id,
          lyrics_version_id: activeLyrics?.id,
        }),
      });
      ensureOk(response, "Chords generate");
      const generated = (await response.json()) as ChordProgressionVersion;
      setChordVersions((current) => sortChordVersions([generated, ...current]));
      await loadWorkspace();
    } catch (chordsError) {
      setError(chordsError instanceof Error ? chordsError.message : "Failed to generate chords");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleChordsSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeChords) {
      return;
    }
    const validationError = validateChordSections(chordDraft);
    if (validationError) {
      setError(validationError);
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(chordVersionEndpoint(apiBaseUrl, projectId, activeChords.id), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sections: chordDraft }),
      });
      ensureOk(response, "Chords edit");
      const edited = (await response.json()) as ChordProgressionVersion;
      setChordVersions((current) => sortChordVersions([edited, ...current]));
      await loadWorkspace();
    } catch (chordsError) {
      setError(chordsError instanceof Error ? chordsError.message : "Failed to edit chords");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleGenerateMidi() {
    if (!approvedVersion) {
      setError("Approve a SongSpec before generating MIDI.");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(midiGenerateEndpoint(apiBaseUrl, projectId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          song_spec_id: approvedVersion.id,
          lyrics_version_id: activeLyrics?.id,
          chord_version_id: activeChords?.id,
        }),
      });
      ensureOk(response, "MIDI generate");
      const generated = (await response.json()) as MidiAssetVersion[];
      setMidiAssets((current) => sortMidiAssets([...generated, ...current]));
      await loadWorkspace();
    } catch (midiError) {
      setError(midiError instanceof Error ? midiError.message : "Failed to generate MIDI");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleAudioUploadSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateAudioUploadFile(audioUploadFile);
    if (validationError) {
      setError(validationError);
      return;
    }
    if (!audioUploadFile) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", audioUploadFile);
      formData.append("kind", audioUploadKind);
      if (audioUploadNotes.trim()) {
        formData.append("notes", audioUploadNotes.trim());
      }
      const response = await fetch(audioUploadsEndpoint(apiBaseUrl, projectId), {
        method: "POST",
        body: formData,
      });
      ensureOk(response, "Audio upload");
      const upload = (await response.json()) as AudioUpload;
      setAudioUploads((current) => sortAudioUploads([upload, ...current]));
      setAudioUploadFile(null);
      setAudioUploadNotes("");
      await loadWorkspace();
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Failed to upload audio");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleUpdateAudioUpload(
    audioUploadId: string,
    payload: AudioUploadUpdatePayload,
  ) {
    if (payload.notes !== undefined) {
      const notesError = validateAudioUploadNotes(payload.notes ?? "");
      if (notesError) {
        setError(notesError);
        return;
      }
    }

    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(audioUploadEndpoint(apiBaseUrl, projectId, audioUploadId), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      ensureOk(response, "Audio upload update");
      const updatedUpload = (await response.json()) as AudioUpload;
      setAudioUploads((current) =>
        sortAudioUploads(
          current.map((upload) => (upload.id === updatedUpload.id ? updatedUpload : upload)),
        ),
      );
      await loadWorkspace();
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Failed to update audio");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleExtractAudioMidi(audioUploadId: string) {
    if (!approvedVersion) {
      setError("Approve a SongSpec before extracting melody MIDI.");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(
        audioExtractMidiEndpoint(apiBaseUrl, projectId, audioUploadId),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ song_spec_id: approvedVersion.id, target_kind: "melody" }),
        },
      );
      ensureOk(response, "Audio-to-MIDI extraction");
      const run = (await response.json()) as GenerationRun;
      setGenerationRuns((current) => sortGenerationRuns([run, ...current]));
      await loadWorkspace();
    } catch (extractError) {
      setError(
        extractError instanceof Error ? extractError.message : "Failed to extract melody MIDI",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function handleGenerateArrangement() {
    if (!approvedVersion) {
      setError("Approve a SongSpec before generating an arrangement.");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(arrangementGenerateEndpoint(apiBaseUrl, projectId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ song_spec_id: approvedVersion.id }),
      });
      ensureOk(response, "Arrangement generate");
      await loadWorkspace();
    } catch (arrangementError) {
      setError(
        arrangementError instanceof Error
          ? arrangementError.message
          : "Failed to generate arrangement",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function handleArrangementSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeArrangement) {
      return;
    }
    const validationError = validateArrangementPlan(arrangementDraft);
    if (validationError) {
      setError(validationError);
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(
        arrangementVersionEndpoint(apiBaseUrl, projectId, activeArrangement.id),
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(arrangementDraft),
        },
      );
      ensureOk(response, "Arrangement edit");
      await loadWorkspace();
    } catch (arrangementError) {
      setError(
        arrangementError instanceof Error ? arrangementError.message : "Failed to edit arrangement",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function handleCreateExport() {
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(exportsEndpoint(apiBaseUrl, projectId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ arrangement_plan_id: activeArrangement?.id ?? null }),
      });
      ensureOk(response, "Project export");
      await loadWorkspace();
    } catch (exportError) {
      setError(exportError instanceof Error ? exportError.message : "Failed to export project");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleGenerateDemo() {
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(demoGenerateEndpoint(apiBaseUrl, projectId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ arrangement_plan_id: activeArrangement?.id ?? null }),
      });
      ensureOk(response, "Demo generation");
      const run = (await response.json()) as GenerationRun;
      setGenerationRuns((current) => sortGenerationRuns([run, ...current]));
      await loadWorkspace();
    } catch (demoError) {
      setError(demoError instanceof Error ? demoError.message : "Failed to generate demo");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleRetryRun(runId: string) {
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(taskRetryEndpoint(apiBaseUrl, runId), { method: "POST" });
      ensureOk(response, "Demo retry");
      const run = (await response.json()) as GenerationRun;
      setGenerationRuns((current) => sortGenerationRuns([run, ...current]));
      await loadWorkspace();
    } catch (retryError) {
      setError(retryError instanceof Error ? retryError.message : "Failed to retry demo");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleCancelRun(runId: string) {
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(taskCancelEndpoint(apiBaseUrl, runId), { method: "POST" });
      ensureOk(response, "Demo cancel");
      const run = (await response.json()) as GenerationRun;
      setGenerationRuns((current) =>
        sortGenerationRuns(current.map((item) => (item.id === run.id ? run : item))),
      );
      await loadWorkspace();
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "Failed to cancel demo");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleCreateRevision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateRevisionFeedback(revisionFeedback);
    if (validationError) {
      setError(validationError);
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(revisionsEndpoint(apiBaseUrl, projectId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback: revisionFeedback }),
      });
      ensureOk(response, "Revision plan");
      const revision = (await response.json()) as RevisionRequest;
      setRevisionRequests((current) => sortRevisionRequests([revision, ...current]));
      setRevisionFeedback("");
      await loadWorkspace();
    } catch (revisionError) {
      setError(
        revisionError instanceof Error ? revisionError.message : "Failed to plan revision",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function handleApplyRevision(revisionId: string, regenerateDemo: boolean) {
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(revisionApplyEndpoint(apiBaseUrl, projectId, revisionId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ regenerate_demo: regenerateDemo }),
      });
      ensureOk(response, "Revision apply");
      const result = (await response.json()) as RevisionApplyResponse;
      setRevisionRequests((current) =>
        sortRevisionRequests(current.map((item) => (item.id === result.revision.id ? result.revision : item))),
      );
      await loadWorkspace();
    } catch (applyError) {
      setError(applyError instanceof Error ? applyError.message : "Failed to apply revision");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleRejectRevision(revisionId: string) {
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(revisionRejectEndpoint(apiBaseUrl, projectId, revisionId), {
        method: "POST",
      });
      ensureOk(response, "Revision reject");
      const revision = (await response.json()) as RevisionRequest;
      setRevisionRequests((current) =>
        sortRevisionRequests(current.map((item) => (item.id === revision.id ? revision : item))),
      );
      await loadWorkspace();
    } catch (rejectError) {
      setError(rejectError instanceof Error ? rejectError.message : "Failed to reject revision");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleCreateComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateCommentBody(commentBody);
    if (validationError) {
      setError(validationError);
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const target = parseCommentTarget(commentTargetValue);
      const response = await fetch(projectCommentsEndpoint(apiBaseUrl, projectId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          body: commentBody,
          author_name: commentAuthor.trim() || "Local collaborator",
          target_type: target.target_type,
          target_id: target.target_id,
        }),
      });
      ensureOk(response, "Comment create");
      const comment = (await response.json()) as ProjectComment;
      setProjectComments((current) => sortProjectComments([comment, ...current]));
      setCommentBody("");
      await loadWorkspace();
    } catch (commentError) {
      setError(commentError instanceof Error ? commentError.message : "Failed to create comment");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleUpdateComment(commentId: string, status: ProjectComment["status"]) {
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(projectCommentEndpoint(apiBaseUrl, projectId, commentId), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      ensureOk(response, "Comment update");
      const comment = (await response.json()) as ProjectComment;
      setProjectComments((current) =>
        sortProjectComments(current.map((item) => (item.id === comment.id ? comment : item))),
      );
      await loadWorkspace();
    } catch (commentError) {
      setError(commentError instanceof Error ? commentError.message : "Failed to update comment");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleCompareVersions(
    assetType: VersionAssetType,
    leftId: string,
    rightId: string,
  ) {
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(
        versionDiffEndpoint(apiBaseUrl, projectId, assetType, leftId, rightId),
      );
      ensureOk(response, "Version diff");
      setVersionDiff((await response.json()) as VersionDiff);
    } catch (diffError) {
      setError(diffError instanceof Error ? diffError.message : "Failed to compare versions");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleRestoreVersion(assetType: RestoreAssetType, versionId: string) {
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(versionRestoreEndpoint(apiBaseUrl, projectId), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ asset_type: assetType, version_id: versionId }),
      });
      ensureOk(response, "Version restore");
      await loadWorkspace();
    } catch (restoreError) {
      setError(restoreError instanceof Error ? restoreError.message : "Failed to restore version");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleProjectSettingsSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nameError = validateProjectName(projectNameDraft);
    if (nameError) {
      setError(nameError);
      return;
    }
    const descriptionError = validateProjectDescription(projectDescriptionDraft);
    if (descriptionError) {
      setError(descriptionError);
      return;
    }

    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(projectDetailEndpoint(apiBaseUrl, projectId), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: projectNameDraft.trim(),
          description: projectDescriptionDraft.trim() || null,
        }),
      });
      ensureOk(response, "Project update");
      const updatedProject = (await response.json()) as Project;
      setProject(updatedProject);
    } catch (updateError) {
      setError(updateError instanceof Error ? updateError.message : "Failed to update project");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleProjectStatusToggle() {
    if (!project) {
      return;
    }

    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(projectDetailEndpoint(apiBaseUrl, projectId), {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: project.status === "archived" ? "active" : "archived" }),
      });
      ensureOk(response, "Project status update");
      const updatedProject = (await response.json()) as Project;
      setProject(updatedProject);
    } catch (statusError) {
      setError(
        statusError instanceof Error ? statusError.message : "Failed to update project status",
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="workspace">
      <ProjectOverview
        description={projectDescriptionDraft}
        error={error}
        handoff={projectHandoff}
        isLoading={isLoading}
        isSaving={isSaving}
        name={projectNameDraft}
        onDescriptionChange={setProjectDescriptionDraft}
        onNameChange={setProjectNameDraft}
        onRefresh={loadWorkspace}
        onStatusToggle={handleProjectStatusToggle}
        onSubmit={handleProjectSettingsSubmit}
        project={project}
        review={projectReview}
      />

      <SongSpecWorkspace
        activeVersion={activeVersion}
        answers={answers}
        draftForm={draftForm}
        idea={idea}
        isSaving={isSaving}
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

      <div className="asset-grid">
        <AudioWorkspace
          approvedSongSpecId={approvedVersion?.id ?? null}
          file={audioUploadFile}
          isSaving={isSaving}
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
          chordDraft={chordDraft}
          hookDraft={hookDraft}
          isSaving={isSaving}
          lyricDraft={lyricDraft}
          midiAssets={sortedMidiAssets}
          onChordBarsChange={(index, bars) => {
            setChordDraft((current) =>
              current.map((section, sectionIndex) =>
                sectionIndex === index ? { ...section, bars } : section,
              ),
            );
          }}
          onChordsChange={(index, chords) => {
            setChordDraft((current) =>
              current.map((section, sectionIndex) =>
                sectionIndex === index ? { ...section, chords } : section,
              ),
            );
          }}
          onChordsSubmit={handleChordsSubmit}
          onGenerateChords={handleGenerateChords}
          onGenerateLyrics={handleGenerateLyrics}
          onGenerateMidi={handleGenerateMidi}
          onHookChange={(index, text) => {
            setHookDraft((current) =>
              current.map((hook, hookIndex) => (hookIndex === index ? { ...hook, text } : hook)),
            );
          }}
          onLyricsSubmit={handleLyricsSubmit}
          onLyricSectionChange={(index, text) => {
            setLyricDraft((current) =>
              current.map((section, sectionIndex) =>
                sectionIndex === index ? { ...section, text } : section,
              ),
            );
          }}
          projectId={projectId}
        />
      </div>

      <div className="delivery-grid">
        <DeliveryWorkspace
          activeArrangement={activeArrangement}
          arrangementPlan={arrangementDraft}
          assetTree={assetTree}
          canExport={canExportProject}
          canGenerateArrangement={canGenerateArrangementPlan}
          exports={sortedExports}
          isSaving={isSaving}
          onArrangementChange={setArrangementDraft}
          onArrangementSubmit={handleArrangementSubmit}
          onCreateExport={handleCreateExport}
          onGenerateArrangement={handleGenerateArrangement}
        />
        <DemoWorkspace
          assetTree={assetTree}
          canGenerate={canGenerateDemoVersion}
          demos={sortedDemos}
          isSaving={isSaving}
          onGenerate={handleGenerateDemo}
          onCancel={handleCancelRun}
          onRetry={handleRetryRun}
          projectId={projectId}
          runs={demoRuns}
        />
      </div>

      <RevisionWorkspace
        arrangements={sortedArrangements}
        demos={sortedDemos}
        feedback={revisionFeedback}
        isSaving={isSaving}
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
        isSaving={isSaving}
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

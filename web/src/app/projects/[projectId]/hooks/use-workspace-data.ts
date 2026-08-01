"use client";

import { useCallback, useEffect, useState } from "react";

import { useGenerationRunPolling } from "./use-generation-run-polling";

import { useLocale } from "@/i18n/locale-provider";
import type { GenerationCandidate, ProviderCapability } from "@/lib/ai-generation";
import {
  ArrangementPlanVersion,
  AudioDemoVersion,
  AudioUpload,
  AssetTree,
  ChordProgressionVersion,
  ExportBundle,
  GenerationRun,
  LyricsVersion,
  MidiAssetVersion,
  ProjectComment,
  ProjectEvent,
  ProjectHandoff,
  ProjectReview,
  RevisionRequest,
} from "@/lib/composition";
import { Project } from "@/lib/projects";
import { IdeaIntake, SongSpecVersion } from "@/lib/song-specs";
import { loadWorkspaceSnapshot } from "@/lib/workspace-api";

export function useWorkspaceData(apiBaseUrl: string, projectId: string) {
  const { errorMessage } = useLocale();
  const [project, setProject] = useState<Project | null>(null);
  const [latestIntake, setLatestIntake] = useState<IdeaIntake | null>(null);
  const [versions, setVersions] = useState<SongSpecVersion[]>([]);
  const [lyricsVersions, setLyricsVersions] = useState<LyricsVersion[]>([]);
  const [chordVersions, setChordVersions] = useState<ChordProgressionVersion[]>([]);
  const [midiAssets, setMidiAssets] = useState<MidiAssetVersion[]>([]);
  const [arrangementVersions, setArrangementVersions] = useState<ArrangementPlanVersion[]>([]);
  const [assetTree, setAssetTree] = useState<AssetTree | null>(null);
  const [exportBundles, setExportBundles] = useState<ExportBundle[]>([]);
  const [demoVersions, setDemoVersions] = useState<AudioDemoVersion[]>([]);
  const [generationRuns, setGenerationRuns] = useState<GenerationRun[]>([]);
  const [revisionRequests, setRevisionRequests] = useState<RevisionRequest[]>([]);
  const [projectComments, setProjectComments] = useState<ProjectComment[]>([]);
  const [projectEvents, setProjectEvents] = useState<ProjectEvent[]>([]);
  const [projectHandoff, setProjectHandoff] = useState<ProjectHandoff | null>(null);
  const [projectReview, setProjectReview] = useState<ProjectReview | null>(null);
  const [audioUploads, setAudioUploads] = useState<AudioUpload[]>([]);
  const [providerProfiles, setProviderProfiles] = useState<ProviderCapability[]>([]);
  const [candidates, setCandidates] = useState<GenerationCandidate[]>([]);
  const [optionalErrors, setOptionalErrors] = useState({
    providers: null as string | null,
    candidates: null as string | null,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadWorkspace = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const snapshot = await loadWorkspaceSnapshot(apiBaseUrl, projectId);
      setProject(snapshot.project);
      setLatestIntake(snapshot.latestIntake);
      setVersions(snapshot.versions);
      setLyricsVersions(snapshot.lyricsVersions);
      setChordVersions(snapshot.chordVersions);
      setMidiAssets(snapshot.midiAssets);
      setArrangementVersions(snapshot.arrangementVersions);
      setAssetTree(snapshot.assetTree);
      setExportBundles(snapshot.exportBundles);
      setDemoVersions(snapshot.demoVersions);
      setGenerationRuns(snapshot.generationRuns);
      setRevisionRequests(snapshot.revisionRequests);
      setProjectComments(snapshot.projectComments);
      setProjectEvents(snapshot.projectEvents);
      setProjectHandoff(snapshot.projectHandoff);
      setProjectReview(snapshot.projectReview);
      setAudioUploads(snapshot.audioUploads);
      setProviderProfiles(snapshot.providerProfiles);
      setCandidates(snapshot.candidates);
      setOptionalErrors(snapshot.optionalErrors);
    } catch (loadError) {
      setError(errorMessage(loadError, "Failed to load workspace"));
    } finally {
      setIsLoading(false);
    }
  }, [apiBaseUrl, errorMessage, projectId]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  const handlePollingError = useCallback(
    (pollError: unknown) => {
      setError(errorMessage(pollError, "Failed to refresh task status"));
    },
    [errorMessage],
  );
  useGenerationRunPolling({
    apiBaseUrl,
    runs: generationRuns,
    setRuns: setGenerationRuns,
    onTerminal: loadWorkspace,
    onError: handlePollingError,
  });

  return {
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
    setArrangementVersions,
    assetTree,
    setAssetTree,
    exportBundles,
    setExportBundles,
    demoVersions,
    setDemoVersions,
    generationRuns,
    setGenerationRuns,
    revisionRequests,
    setRevisionRequests,
    projectComments,
    setProjectComments,
    projectEvents,
    setProjectEvents,
    projectHandoff,
    setProjectHandoff,
    projectReview,
    setProjectReview,
    audioUploads,
    setAudioUploads,
    providerProfiles,
    setProviderProfiles,
    candidates,
    setCandidates,
    optionalErrors,
    isLoading,
    error,
    setError,
    loadWorkspace,
  };
}

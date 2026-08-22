import { fetchJson } from "@/lib/api-client";
import {
  GenerationCandidate,
  ProviderCapability,
  candidatesEndpoint,
  providerCapabilitiesEndpoint,
  sortGenerationCandidates,
} from "@/lib/ai-generation";
import {
  ArrangementPlanVersion,
  AudioDemoVersion,
  AudioDerivative,
  AudioMarker,
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
  ReferenceAnalysis,
  RevisionRequest,
  arrangementsEndpoint,
  assetTreeEndpoint,
  audioDerivativesEndpoint,
  audioMarkersEndpoint,
  audioAnalysesEndpoint,
  audioUploadsEndpoint,
  chordsEndpoint,
  demosEndpoint,
  exportsEndpoint,
  lyricsEndpoint,
  midiAssetsEndpoint,
  projectCommentsEndpoint,
  projectEventsEndpoint,
  projectHandoffEndpoint,
  projectReviewEndpoint,
  projectRunsEndpoint,
  revisionsEndpoint,
  sortArrangementVersions,
  sortAudioDerivatives,
  sortAudioMarkers,
  sortAudioUploads,
  sortChordVersions,
  sortDemoVersions,
  sortExportBundles,
  sortGenerationRuns,
  sortLyricsVersions,
  sortMidiAssets,
  sortProjectComments,
  sortProjectEvents,
  sortReferenceAnalyses,
  sortRevisionRequests,
} from "@/lib/composition";
import { Project, projectDetailEndpoint } from "@/lib/projects";
import {
  IdeaIntake,
  SongSpecVersion,
  latestIntakeEndpoint,
  songSpecsEndpoint,
  sortSongSpecVersions,
} from "@/lib/song-specs";

export type WorkspaceSnapshot = {
  project: Project;
  latestIntake: IdeaIntake | null;
  versions: SongSpecVersion[];
  lyricsVersions: LyricsVersion[];
  chordVersions: ChordProgressionVersion[];
  midiAssets: MidiAssetVersion[];
  arrangementVersions: ArrangementPlanVersion[];
  assetTree: AssetTree;
  exportBundles: ExportBundle[];
  demoVersions: AudioDemoVersion[];
  generationRuns: GenerationRun[];
  revisionRequests: RevisionRequest[];
  projectComments: ProjectComment[];
  projectEvents: ProjectEvent[];
  projectHandoff: ProjectHandoff;
  projectReview: ProjectReview;
  audioUploads: AudioUpload[];
  audioDerivatives: AudioDerivative[];
  audioMarkers: AudioMarker[];
  referenceAnalyses: ReferenceAnalysis[];
  providerProfiles: ProviderCapability[];
  candidates: GenerationCandidate[];
  optionalErrors: {
    providers: string | null;
    candidates: string | null;
  };
};

type OptionalWorkspaceData = Pick<
  WorkspaceSnapshot,
  "providerProfiles" | "candidates" | "optionalErrors"
>;

export async function loadWorkspaceSnapshot(
  apiBaseUrl: string,
  projectId: string,
): Promise<WorkspaceSnapshot> {
  const audioUploadsPromise = fetchJson<AudioUpload[]>(
    audioUploadsEndpoint(apiBaseUrl, projectId),
    "Audio upload list",
  );
  const audioDerivativesPromise = audioUploadsPromise.then(async (uploads) =>
    sortAudioDerivatives(
      (
        await Promise.all(
          uploads.map((upload) =>
            fetchJson<AudioDerivative[]>(
              audioDerivativesEndpoint(apiBaseUrl, projectId, upload.id),
              "Audio derivative list",
            ),
          ),
        )
      ).flat(),
    ),
  );
  const audioMarkersPromise = audioUploadsPromise.then(async (uploads) =>
    sortAudioMarkers(
      (
        await Promise.all(
          uploads.map((upload) =>
            fetchJson<AudioMarker[]>(
              audioMarkersEndpoint(apiBaseUrl, projectId, upload.id),
              "Audio marker list",
            ),
          ),
        )
      ).flat(),
    ),
  );
  const referenceAnalysesPromise = audioUploadsPromise.then(async (uploads) =>
    sortReferenceAnalyses(
      (
        await Promise.all(
          uploads.map((upload) =>
            fetchJson<ReferenceAnalysis[]>(
              audioAnalysesEndpoint(apiBaseUrl, projectId, upload.id),
              "Reference analysis list",
            ),
          ),
        )
      ).flat(),
    ),
  );
  const corePromise = Promise.all([
    fetchJson<Project>(projectDetailEndpoint(apiBaseUrl, projectId), "Project"),
    fetchJson<IdeaIntake | null>(latestIntakeEndpoint(apiBaseUrl, projectId), "Latest intake"),
    fetchJson<SongSpecVersion[]>(songSpecsEndpoint(apiBaseUrl, projectId), "SongSpec list"),
    fetchJson<LyricsVersion[]>(lyricsEndpoint(apiBaseUrl, projectId), "Lyrics list"),
    fetchJson<ChordProgressionVersion[]>(chordsEndpoint(apiBaseUrl, projectId), "Chords list"),
    fetchJson<MidiAssetVersion[]>(midiAssetsEndpoint(apiBaseUrl, projectId), "MIDI asset list"),
    fetchJson<ArrangementPlanVersion[]>(
      arrangementsEndpoint(apiBaseUrl, projectId),
      "Arrangement list",
    ),
    fetchJson<AssetTree>(assetTreeEndpoint(apiBaseUrl, projectId), "Asset tree"),
    fetchJson<ExportBundle[]>(exportsEndpoint(apiBaseUrl, projectId), "Export list"),
    fetchJson<AudioDemoVersion[]>(demosEndpoint(apiBaseUrl, projectId), "Demo list"),
    fetchJson<GenerationRun[]>(projectRunsEndpoint(apiBaseUrl, projectId), "Generation run list"),
    fetchJson<RevisionRequest[]>(revisionsEndpoint(apiBaseUrl, projectId), "Revision list"),
    fetchJson<ProjectComment[]>(projectCommentsEndpoint(apiBaseUrl, projectId), "Comment list"),
    fetchJson<ProjectEvent[]>(projectEventsEndpoint(apiBaseUrl, projectId), "Project event list"),
    fetchJson<ProjectHandoff>(projectHandoffEndpoint(apiBaseUrl, projectId), "Project handoff"),
    fetchJson<ProjectReview>(projectReviewEndpoint(apiBaseUrl, projectId), "Project review"),
    audioUploadsPromise,
    audioDerivativesPromise,
    audioMarkersPromise,
    referenceAnalysesPromise,
  ]);
  const optionalPromise = loadOptionalWorkspaceData(
    fetchJson<ProviderCapability[]>(providerCapabilitiesEndpoint(apiBaseUrl), "Provider list"),
    fetchJson<GenerationCandidate[]>(candidatesEndpoint(apiBaseUrl, projectId), "Candidate list"),
  );
  const [[
    project,
    latestIntake,
    versions,
    lyricsVersions,
    chordVersions,
    midiAssets,
    arrangementVersions,
    assetTree,
    exportBundles,
    demoVersions,
    generationRuns,
    revisionRequests,
    projectComments,
    projectEvents,
    projectHandoff,
    projectReview,
    audioUploads,
    audioDerivatives,
    audioMarkers,
    referenceAnalyses,
  ], optional] = await Promise.all([corePromise, optionalPromise]);

  return {
    project,
    latestIntake,
    versions: sortSongSpecVersions(versions),
    lyricsVersions: sortLyricsVersions(lyricsVersions),
    chordVersions: sortChordVersions(chordVersions),
    midiAssets: sortMidiAssets(midiAssets),
    arrangementVersions: sortArrangementVersions(arrangementVersions),
    assetTree,
    exportBundles: sortExportBundles(exportBundles),
    demoVersions: sortDemoVersions(demoVersions),
    generationRuns: sortGenerationRuns(generationRuns),
    revisionRequests: sortRevisionRequests(revisionRequests),
    projectComments: sortProjectComments(projectComments),
    projectEvents: sortProjectEvents(projectEvents),
    projectHandoff,
    projectReview,
    audioUploads: sortAudioUploads(audioUploads),
    audioDerivatives,
    audioMarkers,
    referenceAnalyses,
    providerProfiles: optional.providerProfiles,
    candidates: optional.candidates,
    optionalErrors: optional.optionalErrors,
  };
}

export async function loadOptionalWorkspaceData(
  providersPromise: Promise<ProviderCapability[]>,
  candidatesPromise: Promise<GenerationCandidate[]>,
): Promise<OptionalWorkspaceData> {
  const [providers, candidates] = await Promise.allSettled([
    providersPromise,
    candidatesPromise,
  ]);
  return {
    providerProfiles: providers.status === "fulfilled" ? providers.value : [],
    candidates:
      candidates.status === "fulfilled" ? sortGenerationCandidates(candidates.value) : [],
    optionalErrors: {
      providers: providers.status === "rejected" ? optionalErrorMessage(providers.reason) : null,
      candidates:
        candidates.status === "rejected" ? optionalErrorMessage(candidates.reason) : null,
    },
  };
}

function optionalErrorMessage(reason: unknown): string {
  return reason instanceof Error ? reason.message : "Optional workspace data is unavailable";
}

import { fetchJson } from "@/lib/api-client";
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
  arrangementsEndpoint,
  assetTreeEndpoint,
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
};

export async function loadWorkspaceSnapshot(
  apiBaseUrl: string,
  projectId: string,
): Promise<WorkspaceSnapshot> {
  const [
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
  ] = await Promise.all([
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
    fetchJson<GenerationRun[]>(
      projectRunsEndpoint(apiBaseUrl, projectId),
      "Generation run list",
    ),
    fetchJson<RevisionRequest[]>(revisionsEndpoint(apiBaseUrl, projectId), "Revision list"),
    fetchJson<ProjectComment[]>(
      projectCommentsEndpoint(apiBaseUrl, projectId),
      "Comment list",
    ),
    fetchJson<ProjectEvent[]>(projectEventsEndpoint(apiBaseUrl, projectId), "Project event list"),
    fetchJson<ProjectHandoff>(projectHandoffEndpoint(apiBaseUrl, projectId), "Project handoff"),
    fetchJson<ProjectReview>(projectReviewEndpoint(apiBaseUrl, projectId), "Project review"),
    fetchJson<AudioUpload[]>(audioUploadsEndpoint(apiBaseUrl, projectId), "Audio upload list"),
  ]);

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
  };
}

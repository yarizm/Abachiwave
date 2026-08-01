import type { Project } from "./projects";
import { SongSpecVersion } from "./song-specs";

export type MidiAssetKind = "chord" | "melody" | "hook";
export type MidiTransformOperation =
  | "quantize"
  | "transpose"
  | "velocity"
  | "legato"
  | "humanize"
  | "scale_snap";
export type ExportBundleStatus = "ready" | "failed";
export type GenerationRunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type GenerationRunType = "demo_generation" | "audio_to_midi" | "text_generation";
export type RevisionRequestStatus = "planned" | "applied" | "rejected";
export type RevisionTaskTarget = "lyrics" | "midi_melody" | "arrangement";
export type VersionAssetType = "lyrics" | "midi_melody" | "arrangement" | "demo";
export type RestoreAssetType = "lyrics" | "midi_melody" | "arrangement";
export type AudioUploadKind = "humming" | "reference" | "scratch" | "other";
export type AudioUploadStatus = "available" | "archived";
export type ProjectReviewStatus = "ready" | "needs_work" | "blocked";
export type ProjectReviewItemStatus = "pass" | "warning" | "fail";
export type ProjectCommentStatus = "open" | "resolved";
export type ProjectCommentTargetType =
  | "project"
  | "song_spec"
  | "lyrics"
  | "chords"
  | "midi"
  | "arrangement"
  | "demo"
  | "audio_upload"
  | "export"
  | "revision";

export type ProjectEvent = {
  id: string;
  project_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  revision_request_id: string | null;
  generation_run_id: string | null;
  artifact_version_id: string | null;
  created_at: string;
};

export type ProjectReviewItem = {
  id: string;
  label: string;
  status: ProjectReviewItemStatus;
  detail: string;
  weight: number;
};

export type ProjectReview = {
  project_id: string;
  status: ProjectReviewStatus;
  score: number;
  items: ProjectReviewItem[];
  next_actions: string[];
  generated_at: string;
};

export type ProjectComment = {
  id: string;
  project_id: string;
  author_name: string;
  body: string;
  status: ProjectCommentStatus;
  target_type: ProjectCommentTargetType;
  target_id: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ProjectHandoff = {
  project: Project;
  review: ProjectReview;
  current_assets: CurrentAssets;
  missing_prerequisites: string[];
  open_comments: ProjectComment[];
  recent_events: ProjectEvent[];
  next_actions: string[];
  handoff_markdown: string;
  generated_at: string;
};

export type LyricLine = {
  line_id: string;
  text: string;
  rhyme_label: string | null;
  character_count: number;
  word_count: number;
  syllable_count: number;
  rhyme_key: string | null;
  stress_positions: number[];
};

export type LyricSection = {
  section_id: string;
  label: string;
  text: string;
  lines: LyricLine[];
};

export type HookCandidate = {
  id: string;
  text: string;
};

export type LyricsVersion = {
  id: string;
  project_id: string;
  song_spec_id: string;
  version_number: number;
  parent_version_id: string | null;
  source_revision_request_id: string | null;
  schema_version: number;
  sections: LyricSection[];
  hook_candidates: HookCandidate[];
  created_at: string;
  updated_at: string;
};

export type ChordEvent = {
  event_id: string;
  measure: number;
  beat: number;
  duration_beats: number;
  symbol: string;
  inversion: number | null;
  root: string | null;
  bass: string | null;
  quality: string | null;
  extensions: string[];
  pitch_classes: number[];
  midi_notes: number[];
  roman_numeral: string | null;
  nashville_number: string | null;
  borrowed: boolean;
};

export type ChordMeasure = {
  measure_number: number;
  events: ChordEvent[];
};

export type ChordSection = {
  section_id: string;
  label: string;
  bars: number;
  chords: string[];
  measures: ChordMeasure[];
};

export type ChordProgressionVersion = {
  id: string;
  project_id: string;
  song_spec_id: string;
  lyrics_version_id: string | null;
  version_number: number;
  parent_version_id: string | null;
  schema_version: number;
  key: string;
  tempo_bpm: number;
  time_signature: string;
  sections: ChordSection[];
  created_at: string;
  updated_at: string;
};

export type ChordPreview = {
  source_chord_id: string;
  key: string;
  tempo_bpm: number;
  time_signature: string;
  sections: ChordSection[];
};

export type MidiAssetVersion = {
  id: string;
  project_id: string;
  song_spec_id: string;
  lyrics_version_id: string | null;
  chord_version_id: string | null;
  parent_version_id: string | null;
  version_number: number;
  kind: MidiAssetKind;
  schema_version: number;
  note_events: MidiNoteEvent[];
  tempo_map: MidiTempoEvent[];
  time_signature_map: MidiTimeSignatureEvent[];
  source_revision_request_id: string | null;
  source_audio_upload_id: string | null;
  filename: string;
  content_type: string;
  size_bytes: number;
  checksum: string;
  created_at: string;
};

export type MidiNoteEvent = {
  note_id: string;
  section_id: string | null;
  pitch: number;
  start_beat: number;
  duration_beats: number;
  velocity: number;
  channel: number;
};

export type MidiTempoEvent = {
  beat: number;
  bpm: number;
};

export type MidiTimeSignatureEvent = {
  beat: number;
  numerator: number;
  denominator: number;
};

export type MidiAssetUpdatePayload = {
  note_events: MidiNoteEvent[];
  tempo_map?: MidiTempoEvent[];
  time_signature_map?: MidiTimeSignatureEvent[];
};

export type MidiTransformPayload = {
  midi_asset_id: string;
  operation: MidiTransformOperation;
  note_ids?: string[];
  grid_beats?: number;
  semitones?: number;
  velocity_delta?: number;
  legato_gap_beats?: number;
  humanize_beats?: number;
};

export type ArrangementSection = {
  section_id: string;
  label: string;
  instruments: string[];
  energy_level: number;
  production_notes: string;
};

export type ArrangementPlan = {
  overview: string;
  sections: ArrangementSection[];
  mix_notes: string;
  reference_notes: string;
};

export type ArrangementPlanVersion = {
  id: string;
  project_id: string;
  song_spec_id: string;
  lyrics_version_id: string;
  chord_version_id: string;
  midi_asset_ids: string[];
  version_number: number;
  parent_version_id: string | null;
  source_revision_request_id: string | null;
  arrangement_plan: ArrangementPlan;
  created_at: string;
  updated_at: string;
};

export type AssetReference = {
  asset_type: string;
  id: string;
  label: string;
  version_number: number;
  created_at: string;
  status: string | null;
  kind: string | null;
};

export type CurrentAssets = {
  song_spec: AssetReference | null;
  lyrics: AssetReference | null;
  chords: AssetReference | null;
  midi_assets: AssetReference[];
  arrangement: AssetReference | null;
};

export type AssetTree = {
  current: CurrentAssets;
  timeline: AssetReference[];
  missing_prerequisites: string[];
};

export type ExportBundle = {
  id: string;
  project_id: string;
  arrangement_plan_id: string | null;
  status: ExportBundleStatus;
  manifest: Record<string, unknown>;
  filename: string | null;
  content_type: string;
  size_bytes: number | null;
  checksum: string | null;
  download_url: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type GenerationRun = {
  id: string;
  project_id: string;
  run_type: GenerationRunType;
  status: GenerationRunStatus;
  arq_job_id: string | null;
  input_manifest: Record<string, unknown>;
  provider_name: string;
  provider_version: string;
  provider_params: Record<string, unknown>;
  provider_usage: Record<string, unknown>;
  error_code: string | null;
  error_message: string | null;
  retry_of_run_id: string | null;
  result_midi_asset_id: string | null;
  demo_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AudioUpload = {
  id: string;
  project_id: string;
  kind: AudioUploadKind;
  status: AudioUploadStatus;
  filename: string;
  content_type: string;
  size_bytes: number;
  checksum: string;
  duration_seconds: number;
  sample_rate: number;
  channels: number;
  waveform_peaks: number[];
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type AudioDemoVersion = {
  id: string;
  project_id: string;
  run_id: string;
  song_spec_id: string;
  lyrics_version_id: string;
  chord_version_id: string;
  arrangement_plan_id: string;
  midi_asset_ids: string[];
  version_number: number;
  filename: string;
  content_type: string;
  size_bytes: number;
  checksum: string;
  duration_seconds: number;
  waveform_peaks: number[];
  provider_name: string;
  provider_version: string;
  provider_params: Record<string, unknown>;
  download_url: string;
  created_at: string;
};

export type RevisionTask = {
  id: string;
  target: RevisionTaskTarget;
  target_section_id: string | null;
  action: string;
  summary: string;
  affected_asset_ids: string[];
  requires_demo_regeneration: boolean;
  supported: boolean;
};

export type VersionReference = {
  asset_type: RestoreAssetType;
  id: string;
  label: string;
  version_number: number;
  parent_version_id: string | null;
  source_revision_request_id: string | null;
};

export type RevisionRequest = {
  id: string;
  project_id: string;
  feedback: string;
  status: RevisionRequestStatus;
  tasks: RevisionTask[];
  created_versions: VersionReference[];
  applied_at: string | null;
  rejected_at: string | null;
  created_at: string;
  updated_at: string;
};

export type RevisionApplyResponse = {
  revision: RevisionRequest;
  created_versions: VersionReference[];
  demo_run: GenerationRun | null;
};

export type VersionDiffChange = {
  field: string;
  label: string;
  left: string | null;
  right: string | null;
  summary: string;
};

export type VersionEndpointReference = {
  id: string;
  label: string;
  version_number: number;
  created_at: string;
};

export type VersionDiff = {
  asset_type: VersionAssetType;
  left: VersionEndpointReference;
  right: VersionEndpointReference;
  summary: string;
  changes: VersionDiffChange[];
};

export function lyricsGenerateEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/lyrics/generate`;
}

export function lyricsEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/lyrics`;
}

export function lyricsVersionEndpoint(
  apiBaseUrl: string,
  projectId: string,
  lyricsVersionId: string,
): string {
  return `${lyricsEndpoint(apiBaseUrl, projectId)}/${lyricsVersionId}`;
}

export function chordsGenerateEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/chords/generate`;
}

export function chordsEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/chords`;
}

export function chordVersionEndpoint(
  apiBaseUrl: string,
  projectId: string,
  chordVersionId: string,
): string {
  return `${chordsEndpoint(apiBaseUrl, projectId)}/${chordVersionId}`;
}

export function chordPreviewEndpoint(
  apiBaseUrl: string,
  projectId: string,
  chordVersionId: string,
): string {
  return `${chordVersionEndpoint(apiBaseUrl, projectId, chordVersionId)}/preview`;
}

export function chordTransposeEndpoint(
  apiBaseUrl: string,
  projectId: string,
  chordVersionId: string,
): string {
  return `${chordVersionEndpoint(apiBaseUrl, projectId, chordVersionId)}/transpose`;
}

export function midiGenerateEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/midi/generate`;
}

export function midiAssetsEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/midi-assets`;
}

export function midiAssetEndpoint(
  apiBaseUrl: string,
  projectId: string,
  midiAssetId: string,
): string {
  return `${midiAssetsEndpoint(apiBaseUrl, projectId)}/${midiAssetId}`;
}

export function midiTransformEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/midi/transform`;
}

export function midiAssetDownloadEndpoint(
  apiBaseUrl: string,
  projectId: string,
  midiAssetId: string,
): string {
  return `${midiAssetEndpoint(apiBaseUrl, projectId, midiAssetId)}/download`;
}

export function audioUploadsEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/audio-uploads`;
}

export function audioUploadEndpoint(
  apiBaseUrl: string,
  projectId: string,
  audioUploadId: string,
): string {
  return `${audioUploadsEndpoint(apiBaseUrl, projectId)}/${audioUploadId}`;
}

export function audioUploadDownloadEndpoint(
  apiBaseUrl: string,
  projectId: string,
  audioUploadId: string,
): string {
  return `${audioUploadEndpoint(apiBaseUrl, projectId, audioUploadId)}/download`;
}

export function audioExtractMidiEndpoint(
  apiBaseUrl: string,
  projectId: string,
  audioUploadId: string,
): string {
  return `${audioUploadEndpoint(apiBaseUrl, projectId, audioUploadId)}/extract-midi`;
}

export function audioUploadStatusActionLabel(status: AudioUploadStatus): string {
  return status === "archived" ? "Restore upload" : "Archive upload";
}

export function arrangementGenerateEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/arrangement/generate`;
}

export function arrangementsEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/arrangements`;
}

export function arrangementVersionEndpoint(
  apiBaseUrl: string,
  projectId: string,
  arrangementId: string,
): string {
  return `${arrangementsEndpoint(apiBaseUrl, projectId)}/${arrangementId}`;
}

export function assetTreeEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/assets`;
}

export function projectReviewEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/review`;
}

export function projectHandoffEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/handoff`;
}

export function exportsEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/exports`;
}

export function exportEndpoint(apiBaseUrl: string, projectId: string, exportId: string): string {
  return `${exportsEndpoint(apiBaseUrl, projectId)}/${exportId}`;
}

export function exportDownloadEndpoint(apiBaseUrl: string, downloadUrl: string): string {
  if (downloadUrl.startsWith("http")) {
    return downloadUrl;
  }
  return `${apiBaseUrl}${downloadUrl}`;
}

export function demoGenerateEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/demo/generate`;
}

export function demosEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/demos`;
}

export function demoEndpoint(apiBaseUrl: string, projectId: string, demoId: string): string {
  return `${demosEndpoint(apiBaseUrl, projectId)}/${demoId}`;
}

export function demoDownloadEndpoint(apiBaseUrl: string, projectId: string, demoId: string): string {
  return `${demoEndpoint(apiBaseUrl, projectId, demoId)}/download`;
}

export function projectRunsEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/runs`;
}

export function taskEndpoint(apiBaseUrl: string, taskId: string): string {
  return `${apiBaseUrl}/api/v1/tasks/${taskId}`;
}

export function taskRetryEndpoint(apiBaseUrl: string, taskId: string): string {
  return `${taskEndpoint(apiBaseUrl, taskId)}/retry`;
}

export function taskCancelEndpoint(apiBaseUrl: string, taskId: string): string {
  return `${taskEndpoint(apiBaseUrl, taskId)}/cancel`;
}

export function revisionsEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/revisions`;
}

export function projectEventsEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/events`;
}

export function projectCommentsEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/comments`;
}

export function projectCommentEndpoint(
  apiBaseUrl: string,
  projectId: string,
  commentId: string,
): string {
  return `${projectCommentsEndpoint(apiBaseUrl, projectId)}/${commentId}`;
}

export function revisionEndpoint(
  apiBaseUrl: string,
  projectId: string,
  revisionId: string,
): string {
  return `${revisionsEndpoint(apiBaseUrl, projectId)}/${revisionId}`;
}

export function revisionApplyEndpoint(
  apiBaseUrl: string,
  projectId: string,
  revisionId: string,
): string {
  return `${revisionEndpoint(apiBaseUrl, projectId, revisionId)}/apply`;
}

export function revisionRejectEndpoint(
  apiBaseUrl: string,
  projectId: string,
  revisionId: string,
): string {
  return `${revisionEndpoint(apiBaseUrl, projectId, revisionId)}/reject`;
}

export function versionDiffEndpoint(
  apiBaseUrl: string,
  projectId: string,
  assetType: VersionAssetType,
  leftId: string,
  rightId: string,
): string {
  const params = new URLSearchParams({
    asset_type: assetType,
    left_id: leftId,
    right_id: rightId,
  });
  return `${apiBaseUrl}/api/v1/projects/${projectId}/versions/diff?${params.toString()}`;
}

export function versionRestoreEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/versions/restore`;
}

export function latestApprovedSongSpec(versions: SongSpecVersion[]): SongSpecVersion | null {
  return versions.find((version) => version.status === "approved") ?? null;
}

export function canGenerateComposition(versions: SongSpecVersion[]): boolean {
  return latestApprovedSongSpec(versions) !== null;
}

export function sortLyricsVersions(versions: LyricsVersion[]): LyricsVersion[] {
  return [...versions].sort((left, right) => right.version_number - left.version_number);
}

export function sortChordVersions(
  versions: ChordProgressionVersion[],
): ChordProgressionVersion[] {
  return [...versions].sort((left, right) => right.version_number - left.version_number);
}

export function sortMidiAssets(versions: MidiAssetVersion[]): MidiAssetVersion[] {
  return [...versions].sort((left, right) => {
    const createdDifference = Date.parse(right.created_at) - Date.parse(left.created_at);
    return createdDifference || right.version_number - left.version_number;
  });
}

export function sortAudioUploads(uploads: AudioUpload[]): AudioUpload[] {
  return [...uploads].sort(
    (left, right) => Date.parse(right.created_at) - Date.parse(left.created_at),
  );
}

export function sortArrangementVersions(
  versions: ArrangementPlanVersion[],
): ArrangementPlanVersion[] {
  return [...versions].sort((left, right) => right.version_number - left.version_number);
}

export function sortExportBundles(versions: ExportBundle[]): ExportBundle[] {
  return [...versions].sort(
    (left, right) => Date.parse(right.created_at) - Date.parse(left.created_at),
  );
}

export function sortDemoVersions(versions: AudioDemoVersion[]): AudioDemoVersion[] {
  return [...versions].sort(
    (left, right) =>
      Date.parse(right.created_at) - Date.parse(left.created_at) ||
      right.version_number - left.version_number,
  );
}

export function sortGenerationRuns(versions: GenerationRun[]): GenerationRun[] {
  return [...versions].sort(
    (left, right) => Date.parse(right.created_at) - Date.parse(left.created_at),
  );
}

export function sortRevisionRequests(versions: RevisionRequest[]): RevisionRequest[] {
  return [...versions].sort(
    (left, right) => Date.parse(right.created_at) - Date.parse(left.created_at),
  );
}

export function sortProjectEvents(events: ProjectEvent[]): ProjectEvent[] {
  return [...events].sort(
    (left, right) => Date.parse(right.created_at) - Date.parse(left.created_at),
  );
}

export function sortProjectComments(comments: ProjectComment[]): ProjectComment[] {
  return [...comments].sort(
    (left, right) => Date.parse(right.created_at) - Date.parse(left.created_at),
  );
}

export function canGenerateArrangement(assetTree: AssetTree | null): boolean {
  if (!assetTree) {
    return false;
  }
  const blocking = new Set([
    "approved_song_spec",
    "lyrics",
    "chords",
    "midi_chord",
    "midi_melody",
    "midi_hook",
  ]);
  return !assetTree.missing_prerequisites.some((item) => blocking.has(item));
}

export function canCreateExport(assetTree: AssetTree | null): boolean {
  return Boolean(assetTree && assetTree.missing_prerequisites.length === 0);
}

export function canGenerateDemo(assetTree: AssetTree | null): boolean {
  return canCreateExport(assetTree);
}

export function isRunActive(run: GenerationRun): boolean {
  return run.status === "queued" || run.status === "running";
}

export function canRetryRun(run: GenerationRun): boolean {
  return run.run_type === "demo_generation" && run.status === "failed";
}

export function canCancelRun(run: GenerationRun): boolean {
  return run.status === "queued" || run.status === "running";
}

/**
 * A short, present-tense label describing a run's lifecycle phase, suitable for
 * surfacing next to a pulse indicator so users can tell a long task is still
 * progressing rather than stuck. Returns null for terminal states (no pulse).
 * The literal values double as translation keys in i18n.
 */
export function runProgressHint(
  status: GenerationRunStatus,
): "Task is queued, will start shortly" | "Task is running, status refreshes automatically" | null {
  switch (status) {
    case "queued":
      return "Task is queued, will start shortly";
    case "running":
      return "Task is running, status refreshes automatically";
    default:
      return null;
  }
}

/** Whether a run status warrants an animated "in progress" pulse indicator. */
export function isRunInProgress(run: GenerationRun): boolean {
  return run.status === "queued" || run.status === "running";
}

export function validateRevisionFeedback(value: string): string | null {
  if (!value.trim()) {
    return "Revision feedback is required.";
  }
  return null;
}

export function validateCommentBody(value: string): string | null {
  if (!value.trim()) {
    return "Comment text is required.";
  }
  return null;
}

export function canApplyRevision(revision: RevisionRequest): boolean {
  return revision.status === "planned" && revision.tasks.some((task) => task.supported);
}

export function validateAudioUploadFile(file: File | null): string | null {
  if (!file) {
    return "Choose a WAV file to upload.";
  }
  if (!["audio/wav", "audio/x-wav", "audio/wave"].includes(file.type)) {
    return "Only WAV uploads are supported.";
  }
  return null;
}

export function validateAudioUploadNotes(value: string): string | null {
  if (value.trim().length > 2000) {
    return "Audio notes must be 2000 characters or fewer.";
  }
  return null;
}

export function validateLyricSections(sections: LyricSection[]): string | null {
  if (sections.length === 0) {
    return "At least one lyric section is required.";
  }
  if (sections.some((section) => section.lines.length === 0)) {
    return "Each lyric section needs at least one line.";
  }
  if (sections.some((section) => section.lines.some((line) => !line.text.trim()))) {
    return "Lyric lines must not be empty.";
  }
  const lineIds = sections.flatMap((section) => section.lines.map((line) => line.line_id));
  if (new Set(lineIds).size !== lineIds.length) {
    return "Lyric line IDs must be unique.";
  }
  if (sections.some((section) => !section.text.trim())) {
    return "Lyric section text must not be empty.";
  }
  return null;
}

export function validateChordSections(
  sections: ChordSection[],
  timeSignature = "4/4",
): string | null {
  if (sections.length === 0) {
    return "At least one chord section is required.";
  }
  if (
    sections.some(
      (section) =>
        section.bars < 1 ||
        section.chords.length === 0 ||
        section.measures.length === 0 ||
        section.measures.some((measure) => measure.events.length === 0),
    )
  ) {
    return "Chord sections need at least one bar and one chord.";
  }
  if (sections.some((section) => section.chords.some((chord) => !chord.trim()))) {
    return "Chord names must not be empty.";
  }
  const beatsPerMeasure = Number(timeSignature.split("/")[0]) || 4;
  for (const section of sections) {
    for (const measure of section.measures) {
      const events = [...measure.events].sort((left, right) => left.beat - right.beat);
      let previousEnd = 0;
      for (const event of events) {
        const eventEnd = event.beat - 1 + event.duration_beats;
        if (
          !event.symbol.trim() ||
          event.beat < 1 ||
          event.duration_beats <= 0 ||
          eventEnd > beatsPerMeasure
        ) {
          return "Chord positions must fit within their measure.";
        }
        if (event.beat - 1 < previousEnd) {
          return "Chord events must not overlap.";
        }
        previousEnd = eventEnd;
      }
    }
  }
  return null;
}

export function validateArrangementPlan(plan: ArrangementPlan): string | null {
  if (!plan.overview.trim()) {
    return "Arrangement overview is required.";
  }
  if (plan.sections.length === 0) {
    return "At least one arrangement section is required.";
  }
  if (
    plan.sections.some(
      (section) =>
        section.energy_level < 1 ||
        section.energy_level > 10 ||
        section.instruments.length === 0 ||
        !section.production_notes.trim(),
    )
  ) {
    return "Arrangement sections need instruments, notes, and energy from 1 to 10.";
  }
  if (!plan.mix_notes.trim() || !plan.reference_notes.trim()) {
    return "Mix notes and reference notes are required.";
  }
  return null;
}

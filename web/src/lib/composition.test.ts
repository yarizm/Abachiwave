import assert from "node:assert/strict";
import test from "node:test";

import {
  audioExtractMidiEndpoint,
  audioUploadStatusActionLabel,
  audioUploadDownloadEndpoint,
  audioUploadEndpoint,
  audioUploadsEndpoint,
  arrangementGenerateEndpoint,
  arrangementVersionEndpoint,
  arrangementsEndpoint,
  assetTreeEndpoint,
  canCreateExport,
  canApplyRevision,
  canCancelRun,
  canGenerateDemo,
  canGenerateArrangement,
  canGenerateComposition,
  canRetryRun,
  chordPreviewEndpoint,
  chordTransposeEndpoint,
  chordVersionEndpoint,
  chordsEndpoint,
  chordsGenerateEndpoint,
  demoDownloadEndpoint,
  demoEndpoint,
  demoGenerateEndpoint,
  demosEndpoint,
  exportDownloadEndpoint,
  exportEndpoint,
  exportsEndpoint,
  isRunActive,
  latestApprovedSongSpec,
  lyricsEndpoint,
  lyricsGenerateEndpoint,
  lyricsVersionEndpoint,
  midiAssetDownloadEndpoint,
  midiAssetsEndpoint,
  midiGenerateEndpoint,
  projectRunsEndpoint,
  projectCommentEndpoint,
  projectCommentsEndpoint,
  projectEventsEndpoint,
  projectHandoffEndpoint,
  projectReviewEndpoint,
  revisionApplyEndpoint,
  revisionEndpoint,
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
  taskEndpoint,
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
  type ArrangementPlan,
  type ArrangementPlanVersion,
  type AudioUpload,
  type AudioDemoVersion,
  type AssetTree,
  type ChordProgressionVersion,
  type ExportBundle,
  type GenerationRun,
  type LyricsVersion,
  type MidiAssetVersion,
  type ProjectComment,
  type ProjectEvent,
  type RevisionRequest,
} from "./composition";
import { type SongSpecVersion } from "./song-specs";

function songSpec(versionNumber: number, status: SongSpecVersion["status"]): SongSpecVersion {
  return {
    id: `song-spec-${versionNumber}`,
    project_id: "project-1",
    intake_id: null,
    version_number: versionNumber,
    status,
    parent_version_id: null,
    approved_at: status === "approved" ? "2026-07-08T00:00:00Z" : null,
    song_spec: {
      theme: "Late ride home",
      genre: ["indie rock"],
      language: "zh-CN",
      tempo_bpm: 128,
      key: "E major",
      time_signature: "4/4",
      target_duration_seconds: 210,
      mood_curve: { verse: "restrained" },
      song_structure: ["verse", "chorus"],
    },
    missing_required_fields: [],
    created_at: "2026-07-08T00:00:00Z",
    updated_at: "2026-07-08T00:00:00Z",
  };
}

function lyrics(versionNumber: number): LyricsVersion {
  return {
    id: `lyrics-${versionNumber}`,
    project_id: "project-1",
    song_spec_id: "song-spec-1",
    version_number: versionNumber,
    parent_version_id: null,
    source_revision_request_id: null,
    schema_version: 2,
    sections: [
      {
        section_id: "verse",
        label: "Verse",
        text: "Line one",
        lines: [
          {
            line_id: "line-1",
            text: "Line one",
            rhyme_label: null,
            character_count: 7,
            word_count: 2,
            syllable_count: 2,
            rhyme_key: "one",
            stress_positions: [1],
          },
        ],
      },
    ],
    hook_candidates: [],
    created_at: "2026-07-08T00:00:00Z",
    updated_at: "2026-07-08T00:00:00Z",
  };
}

function chords(versionNumber: number): ChordProgressionVersion {
  return {
    id: `chords-${versionNumber}`,
    project_id: "project-1",
    song_spec_id: "song-spec-1",
    lyrics_version_id: null,
    version_number: versionNumber,
    parent_version_id: null,
    schema_version: 2,
    key: "E major",
    tempo_bpm: 128,
    time_signature: "4/4",
    sections: [
      {
        section_id: "verse",
        label: "Verse",
        bars: 4,
        chords: ["E", "B", "C#m", "A"],
        measures: ["E", "B", "C#m", "A"].map((symbol, index) => ({
          measure_number: index + 1,
          events: [
            {
              event_id: `event-${index + 1}`,
              measure: index + 1,
              beat: 1,
              duration_beats: 4,
              symbol,
              inversion: 0,
              root: symbol.replace("m", ""),
              bass: symbol.replace("m", ""),
              quality: symbol.endsWith("m") ? "minor" : "major",
              extensions: [],
              pitch_classes: [],
              midi_notes: [60, 64, 67],
              roman_numeral: "I",
              nashville_number: "1",
              borrowed: false,
            },
          ],
        })),
      },
    ],
    created_at: "2026-07-08T00:00:00Z",
    updated_at: "2026-07-08T00:00:00Z",
  };
}

function midi(versionNumber: number, createdAt: string): MidiAssetVersion {
  return {
    id: `midi-${versionNumber}`,
    project_id: "project-1",
    song_spec_id: "song-spec-1",
    lyrics_version_id: null,
    chord_version_id: null,
    version_number: versionNumber,
    kind: "melody",
    source_revision_request_id: null,
    source_audio_upload_id: null,
    filename: `melody-v${versionNumber}.mid`,
    content_type: "audio/midi",
    size_bytes: 128,
    checksum: "checksum",
    created_at: createdAt,
  };
}

function arrangement(versionNumber: number): ArrangementPlanVersion {
  return {
    id: `arrangement-${versionNumber}`,
    project_id: "project-1",
    song_spec_id: "song-spec-1",
    lyrics_version_id: "lyrics-1",
    chord_version_id: "chords-1",
    midi_asset_ids: ["midi-1", "midi-2", "midi-3"],
    version_number: versionNumber,
    parent_version_id: null,
    source_revision_request_id: null,
    arrangement_plan: completeArrangement,
    created_at: "2026-07-08T00:00:00Z",
    updated_at: "2026-07-08T00:00:00Z",
  };
}

function revisionRequest(
  status: RevisionRequest["status"],
  createdAt: string,
  supported = true,
): RevisionRequest {
  return {
    id: `revision-${status}-${createdAt}`,
    project_id: "project-1",
    feedback: "Make the chorus lyric stronger.",
    status,
    tasks: [
      {
        id: "lyrics_chorus",
        target: "lyrics",
        target_section_id: "chorus",
        action: "revise_lyrics",
        summary: "Strengthen the chorus lyric.",
        affected_asset_ids: ["lyrics-1"],
        requires_demo_regeneration: true,
        supported,
      },
    ],
    created_versions: [],
    applied_at: status === "applied" ? createdAt : null,
    rejected_at: status === "rejected" ? createdAt : null,
    created_at: createdAt,
    updated_at: createdAt,
  };
}

function exportBundle(versionNumber: number, createdAt: string): ExportBundle {
  return {
    id: `export-${versionNumber}`,
    project_id: "project-1",
    arrangement_plan_id: "arrangement-1",
    status: "ready",
    manifest: {},
    filename: `export-${versionNumber}.zip`,
    content_type: "application/zip",
    size_bytes: 1024,
    checksum: "checksum",
    download_url: `/api/v1/exports/export-${versionNumber}/download?token=t`,
    error_message: null,
    created_at: createdAt,
    updated_at: createdAt,
  };
}

function generationRun(status: GenerationRun["status"], createdAt: string): GenerationRun {
  return {
    id: `run-${status}-${createdAt}`,
    project_id: "project-1",
    run_type: "demo_generation",
    status,
    arq_job_id: "job-1",
    input_manifest: {},
    provider_name: "local_deterministic_wav",
    provider_version: "0.1.0",
    provider_params: {},
    provider_usage: {},
    error_code: null,
    error_message: status === "failed" ? "failed" : null,
    retry_of_run_id: null,
    result_midi_asset_id: null,
    demo_id: status === "succeeded" ? "demo-1" : null,
    started_at: null,
    completed_at: null,
    created_at: createdAt,
    updated_at: createdAt,
  };
}

function audioUpload(versionNumber: number, createdAt: string): AudioUpload {
  return {
    id: `audio-${versionNumber}`,
    project_id: "project-1",
    kind: "humming",
    status: "available",
    filename: `humming-${versionNumber}.wav`,
    content_type: "audio/wav",
    size_bytes: 1024,
    checksum: "checksum",
    duration_seconds: 1,
    sample_rate: 8000,
    channels: 1,
    waveform_peaks: [0, 0.5, 1],
    notes: null,
    created_at: createdAt,
    updated_at: createdAt,
  };
}

function projectEvent(eventType: string, createdAt: string): ProjectEvent {
  return {
    id: `${eventType}-${createdAt}`,
    project_id: "project-1",
    event_type: eventType,
    payload: {},
    revision_request_id: null,
    generation_run_id: null,
    artifact_version_id: null,
    created_at: createdAt,
  };
}

function projectComment(status: ProjectComment["status"], createdAt: string): ProjectComment {
  return {
    id: `comment-${status}-${createdAt}`,
    project_id: "project-1",
    author_name: "Local reviewer",
    body: "Tighten the chorus lift.",
    status,
    target_type: "project",
    target_id: null,
    resolved_at: status === "resolved" ? createdAt : null,
    created_at: createdAt,
    updated_at: createdAt,
  };
}

function demoVersion(versionNumber: number, createdAt: string): AudioDemoVersion {
  return {
    id: `demo-${versionNumber}`,
    project_id: "project-1",
    run_id: "run-1",
    song_spec_id: "song-spec-1",
    lyrics_version_id: "lyrics-1",
    chord_version_id: "chords-1",
    arrangement_plan_id: "arrangement-1",
    midi_asset_ids: ["midi-1", "midi-2", "midi-3"],
    version_number: versionNumber,
    filename: `demo-v${versionNumber}.wav`,
    content_type: "audio/wav",
    size_bytes: 2048,
    checksum: "checksum",
    duration_seconds: 30,
    waveform_peaks: [0, 0.4, 1],
    provider_name: "local_deterministic_wav",
    provider_version: "0.1.0",
    provider_params: {},
    download_url: `/api/v1/projects/project-1/demos/demo-${versionNumber}/download`,
    created_at: createdAt,
  };
}

const completeArrangement: ArrangementPlan = {
  overview: "Build a focused indie rock arrangement.",
  sections: [
    {
      section_id: "verse",
      label: "Verse",
      instruments: ["lead vocal", "guitar"],
      energy_level: 4,
      production_notes: "Keep the verse narrow and dry.",
    },
  ],
  mix_notes: "Keep vocals centered.",
  reference_notes: "Use MIDI as guide parts.",
};

const completeAssetTree: AssetTree = {
  current: {
    song_spec: {
      asset_type: "song_spec",
      id: "song-spec-1",
      label: "SongSpec v1",
      version_number: 1,
      created_at: "2026-07-08T00:00:00Z",
      status: "approved",
      kind: null,
    },
    lyrics: null,
    chords: null,
    midi_assets: [],
    arrangement: null,
  },
  timeline: [],
  missing_prerequisites: [],
};

test("composition endpoints build nested project URLs", () => {
  assert.equal(
    lyricsGenerateEndpoint("http://localhost:8000", "p1"),
    "http://localhost:8000/api/v1/projects/p1/lyrics/generate",
  );
  assert.equal(lyricsEndpoint("http://localhost:8000", "p1"), "http://localhost:8000/api/v1/projects/p1/lyrics");
  assert.equal(
    lyricsVersionEndpoint("http://localhost:8000", "p1", "l1"),
    "http://localhost:8000/api/v1/projects/p1/lyrics/l1",
  );
  assert.equal(
    chordsGenerateEndpoint("http://localhost:8000", "p1"),
    "http://localhost:8000/api/v1/projects/p1/chords/generate",
  );
  assert.equal(chordsEndpoint("http://localhost:8000", "p1"), "http://localhost:8000/api/v1/projects/p1/chords");
  assert.equal(
    chordVersionEndpoint("http://localhost:8000", "p1", "c1"),
    "http://localhost:8000/api/v1/projects/p1/chords/c1",
  );
  assert.equal(
    chordPreviewEndpoint("http://localhost:8000", "p1", "c1"),
    "http://localhost:8000/api/v1/projects/p1/chords/c1/preview",
  );
  assert.equal(
    chordTransposeEndpoint("http://localhost:8000", "p1", "c1"),
    "http://localhost:8000/api/v1/projects/p1/chords/c1/transpose",
  );
  assert.equal(
    midiGenerateEndpoint("http://localhost:8000", "p1"),
    "http://localhost:8000/api/v1/projects/p1/midi/generate",
  );
  assert.equal(
    midiAssetsEndpoint("http://localhost:8000", "p1"),
    "http://localhost:8000/api/v1/projects/p1/midi-assets",
  );
  assert.equal(
    midiAssetDownloadEndpoint("http://localhost:8000", "p1", "m1"),
    "http://localhost:8000/api/v1/projects/p1/midi-assets/m1/download",
  );
  assert.equal(
    audioUploadsEndpoint("http://localhost:8000", "p1"),
    "http://localhost:8000/api/v1/projects/p1/audio-uploads",
  );
  assert.equal(
    audioUploadEndpoint("http://localhost:8000", "p1", "a1"),
    "http://localhost:8000/api/v1/projects/p1/audio-uploads/a1",
  );
  assert.equal(
    audioUploadDownloadEndpoint("http://localhost:8000", "p1", "a1"),
    "http://localhost:8000/api/v1/projects/p1/audio-uploads/a1/download",
  );
  assert.equal(
    audioExtractMidiEndpoint("http://localhost:8000", "p1", "a1"),
    "http://localhost:8000/api/v1/projects/p1/audio-uploads/a1/extract-midi",
  );
  assert.equal(
    arrangementGenerateEndpoint("http://localhost:8000", "p1"),
    "http://localhost:8000/api/v1/projects/p1/arrangement/generate",
  );
  assert.equal(
    arrangementsEndpoint("http://localhost:8000", "p1"),
    "http://localhost:8000/api/v1/projects/p1/arrangements",
  );
  assert.equal(
    arrangementVersionEndpoint("http://localhost:8000", "p1", "a1"),
    "http://localhost:8000/api/v1/projects/p1/arrangements/a1",
  );
  assert.equal(assetTreeEndpoint("http://localhost:8000", "p1"), "http://localhost:8000/api/v1/projects/p1/assets");
  assert.equal(
    projectReviewEndpoint("http://localhost:8000", "p1"),
    "http://localhost:8000/api/v1/projects/p1/review",
  );
  assert.equal(
    projectHandoffEndpoint("http://localhost:8000", "p1"),
    "http://localhost:8000/api/v1/projects/p1/handoff",
  );
  assert.equal(exportsEndpoint("http://localhost:8000", "p1"), "http://localhost:8000/api/v1/projects/p1/exports");
  assert.equal(
    exportEndpoint("http://localhost:8000", "p1", "e1"),
    "http://localhost:8000/api/v1/projects/p1/exports/e1",
  );
  assert.equal(
    exportDownloadEndpoint("http://localhost:8000", "/api/v1/exports/e1/download?token=t"),
    "http://localhost:8000/api/v1/exports/e1/download?token=t",
  );
  assert.equal(
    demoGenerateEndpoint("http://localhost:8000", "p1"),
    "http://localhost:8000/api/v1/projects/p1/demo/generate",
  );
  assert.equal(demosEndpoint("http://localhost:8000", "p1"), "http://localhost:8000/api/v1/projects/p1/demos");
  assert.equal(
    demoEndpoint("http://localhost:8000", "p1", "d1"),
    "http://localhost:8000/api/v1/projects/p1/demos/d1",
  );
  assert.equal(
    demoDownloadEndpoint("http://localhost:8000", "p1", "d1"),
    "http://localhost:8000/api/v1/projects/p1/demos/d1/download",
  );
  assert.equal(projectRunsEndpoint("http://localhost:8000", "p1"), "http://localhost:8000/api/v1/projects/p1/runs");
  assert.equal(taskEndpoint("http://localhost:8000", "r1"), "http://localhost:8000/api/v1/tasks/r1");
  assert.equal(taskRetryEndpoint("http://localhost:8000", "r1"), "http://localhost:8000/api/v1/tasks/r1/retry");
  assert.equal(
    taskCancelEndpoint("http://localhost:8000", "r1"),
    "http://localhost:8000/api/v1/tasks/r1/cancel",
  );
  assert.equal(
    revisionsEndpoint("http://localhost:8000", "p1"),
    "http://localhost:8000/api/v1/projects/p1/revisions",
  );
  assert.equal(
    projectEventsEndpoint("http://localhost:8000", "p1"),
    "http://localhost:8000/api/v1/projects/p1/events",
  );
  assert.equal(
    projectCommentsEndpoint("http://localhost:8000", "p1"),
    "http://localhost:8000/api/v1/projects/p1/comments",
  );
  assert.equal(
    projectCommentEndpoint("http://localhost:8000", "p1", "c1"),
    "http://localhost:8000/api/v1/projects/p1/comments/c1",
  );
  assert.equal(
    revisionEndpoint("http://localhost:8000", "p1", "rv1"),
    "http://localhost:8000/api/v1/projects/p1/revisions/rv1",
  );
  assert.equal(
    revisionApplyEndpoint("http://localhost:8000", "p1", "rv1"),
    "http://localhost:8000/api/v1/projects/p1/revisions/rv1/apply",
  );
  assert.equal(
    revisionRejectEndpoint("http://localhost:8000", "p1", "rv1"),
    "http://localhost:8000/api/v1/projects/p1/revisions/rv1/reject",
  );
  assert.equal(
    versionDiffEndpoint("http://localhost:8000", "p1", "lyrics", "left", "right"),
    "http://localhost:8000/api/v1/projects/p1/versions/diff?asset_type=lyrics&left_id=left&right_id=right",
  );
  assert.equal(
    versionRestoreEndpoint("http://localhost:8000", "p1"),
    "http://localhost:8000/api/v1/projects/p1/versions/restore",
  );
});

test("composition generation requires an approved song spec", () => {
  assert.equal(canGenerateComposition([songSpec(1, "draft")]), false);
  assert.equal(canGenerateComposition([songSpec(2, "approved"), songSpec(1, "draft")]), true);
  assert.equal(latestApprovedSongSpec([songSpec(3, "draft"), songSpec(2, "approved")])?.id, "song-spec-2");
});

test("composition version sorters put newest first", () => {
  assert.deepEqual(sortLyricsVersions([lyrics(1), lyrics(3), lyrics(2)]).map((item) => item.version_number), [3, 2, 1]);
  assert.deepEqual(sortChordVersions([chords(1), chords(2)]).map((item) => item.version_number), [2, 1]);
  assert.deepEqual(
    sortArrangementVersions([arrangement(1), arrangement(3), arrangement(2)]).map(
      (item) => item.version_number,
    ),
    [3, 2, 1],
  );
  assert.deepEqual(
    sortMidiAssets([
      midi(1, "2026-07-08T00:00:00Z"),
      midi(2, "2026-07-08T00:01:00Z"),
    ]).map((item) => item.version_number),
    [2, 1],
  );
  assert.deepEqual(
    sortAudioUploads([
      audioUpload(1, "2026-07-08T00:00:00Z"),
      audioUpload(2, "2026-07-08T00:01:00Z"),
    ]).map((item) => item.id),
    ["audio-2", "audio-1"],
  );
  assert.deepEqual(
    sortExportBundles([
      exportBundle(1, "2026-07-08T00:00:00Z"),
      exportBundle(2, "2026-07-08T00:01:00Z"),
    ]).map((item) => item.id),
    ["export-2", "export-1"],
  );
  assert.deepEqual(
    sortDemoVersions([
      demoVersion(1, "2026-07-08T00:00:00Z"),
      demoVersion(2, "2026-07-08T00:01:00Z"),
    ]).map((item) => item.id),
    ["demo-2", "demo-1"],
  );
  assert.deepEqual(
    sortGenerationRuns([
      generationRun("queued", "2026-07-08T00:00:00Z"),
      generationRun("failed", "2026-07-08T00:01:00Z"),
    ]).map((item) => item.status),
    ["failed", "queued"],
  );
  assert.deepEqual(
    sortRevisionRequests([
      revisionRequest("planned", "2026-07-08T00:00:00Z"),
      revisionRequest("applied", "2026-07-08T00:01:00Z"),
    ]).map((item) => item.status),
    ["applied", "planned"],
  );
  assert.deepEqual(
    sortProjectEvents([
      projectEvent("revision.planned", "2026-07-08T00:00:00Z"),
      projectEvent("demo.generated", "2026-07-08T00:01:00Z"),
    ]).map((item) => item.event_type),
    ["demo.generated", "revision.planned"],
  );
  assert.deepEqual(
    sortProjectComments([
      projectComment("open", "2026-07-08T00:00:00Z"),
      projectComment("resolved", "2026-07-08T00:01:00Z"),
    ]).map((item) => item.status),
    ["resolved", "open"],
  );
});

test("composition form validators reject empty lyric and chord content", () => {
  assert.equal(validateLyricSections([]), "At least one lyric section is required.");
  assert.equal(
    validateLyricSections([
      { section_id: "verse", label: "Verse", text: "", lines: [] },
    ]),
    "Each lyric section needs at least one line.",
  );
  assert.equal(validateLyricSections(lyrics(1).sections), null);
  assert.equal(validateChordSections([]), "At least one chord section is required.");
  assert.equal(
    validateChordSections([
      { section_id: "verse", label: "Verse", bars: 0, chords: [], measures: [] },
    ]),
    "Chord sections need at least one bar and one chord.",
  );
  assert.equal(validateChordSections(chords(1).sections), null);
});

test("asset tree helpers gate arrangement and export actions", () => {
  assert.equal(canGenerateArrangement(null), false);
  assert.equal(canCreateExport(null), false);
  assert.equal(
    canGenerateArrangement({
      ...completeAssetTree,
      missing_prerequisites: ["arrangement"],
    }),
    true,
  );
  assert.equal(
    canCreateExport({
      ...completeAssetTree,
      missing_prerequisites: ["arrangement"],
    }),
    false,
  );
  assert.equal(
    canGenerateArrangement({
      ...completeAssetTree,
      missing_prerequisites: ["lyrics"],
    }),
    false,
  );
  assert.equal(canCreateExport(completeAssetTree), true);
  assert.equal(canGenerateDemo(completeAssetTree), true);
});

test("demo run helpers expose polling and retry states", () => {
  assert.equal(isRunActive(generationRun("queued", "2026-07-08T00:00:00Z")), true);
  assert.equal(isRunActive(generationRun("running", "2026-07-08T00:00:00Z")), true);
  assert.equal(isRunActive(generationRun("succeeded", "2026-07-08T00:00:00Z")), false);
  assert.equal(canCancelRun(generationRun("queued", "2026-07-08T00:00:00Z")), true);
  assert.equal(canCancelRun(generationRun("running", "2026-07-08T00:00:00Z")), true);
  assert.equal(canCancelRun(generationRun("succeeded", "2026-07-08T00:00:00Z")), false);
  assert.equal(canCancelRun(generationRun("cancelled", "2026-07-08T00:00:00Z")), false);
  assert.equal(canRetryRun(generationRun("failed", "2026-07-08T00:00:00Z")), true);
  assert.equal(canRetryRun(generationRun("succeeded", "2026-07-08T00:00:00Z")), false);
  assert.equal(
    canRetryRun({ ...generationRun("failed", "2026-07-08T00:00:00Z"), run_type: "audio_to_midi" }),
    false,
  );
});

test("audio upload validators require WAV files", () => {
  assert.equal(validateAudioUploadFile(null), "Choose a WAV file to upload.");
  assert.equal(
    validateAudioUploadFile(new File(["data"], "humming.mp3", { type: "audio/mpeg" })),
    "Only WAV uploads are supported.",
  );
  assert.equal(
    validateAudioUploadFile(new File(["data"], "humming.wav", { type: "audio/wav" })),
    null,
  );
});

test("audio upload helpers validate notes and status actions", () => {
  assert.equal(validateAudioUploadNotes("Chorus melody sketch"), null);
  assert.equal(
    validateAudioUploadNotes("x".repeat(2001)),
    "Audio notes must be 2000 characters or fewer.",
  );
  assert.equal(audioUploadStatusActionLabel("available"), "Archive upload");
  assert.equal(audioUploadStatusActionLabel("archived"), "Restore upload");
});

test("revision helpers validate feedback and apply state", () => {
  assert.equal(validateRevisionFeedback("  "), "Revision feedback is required.");
  assert.equal(validateRevisionFeedback("Make the chorus lyric stronger."), null);
  assert.equal(validateCommentBody("  "), "Comment text is required.");
  assert.equal(validateCommentBody("Check the hook."), null);
  assert.equal(canApplyRevision(revisionRequest("planned", "2026-07-08T00:00:00Z")), true);
  assert.equal(canApplyRevision(revisionRequest("planned", "2026-07-08T00:00:00Z", false)), false);
  assert.equal(canApplyRevision(revisionRequest("applied", "2026-07-08T00:00:00Z")), false);
});

test("validateArrangementPlan rejects incomplete arrangement content", () => {
  assert.equal(validateArrangementPlan(completeArrangement), null);
  assert.equal(
    validateArrangementPlan({ ...completeArrangement, overview: " " }),
    "Arrangement overview is required.",
  );
  assert.equal(
    validateArrangementPlan({ ...completeArrangement, sections: [] }),
    "At least one arrangement section is required.",
  );
  assert.equal(
    validateArrangementPlan({
      ...completeArrangement,
      sections: [{ ...completeArrangement.sections[0], energy_level: 12 }],
    }),
    "Arrangement sections need instruments, notes, and energy from 1 to 10.",
  );
});

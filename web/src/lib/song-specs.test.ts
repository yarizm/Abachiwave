import assert from "node:assert/strict";
import test from "node:test";

import {
  intakeEndpoint,
  isSongSpecComplete,
  latestIntakeEndpoint,
  missingSongSpecFields,
  songSpecApproveEndpoint,
  songSpecGenerateEndpoint,
  songSpecsEndpoint,
  sortSongSpecVersions,
  validateIdea,
  workspaceState,
  type SongSpec,
  type SongSpecVersion,
} from "./song-specs";

const completeSpec: SongSpec = {
  theme: "Late ride home",
  genre: ["indie rock"],
  language: "zh-CN",
  tempo_bpm: 128,
  key: "E major",
  time_signature: "4/4",
  target_duration_seconds: 210,
  mood_curve: { verse: "restrained", chorus: "lifting" },
  song_structure: ["intro", "verse", "chorus"],
};

function version(versionNumber: number, status: SongSpecVersion["status"]): SongSpecVersion {
  return {
    id: `version-${versionNumber}`,
    project_id: "project-1",
    intake_id: null,
    version_number: versionNumber,
    status,
    parent_version_id: null,
    approved_at: status === "approved" ? "2026-07-08T00:00:00Z" : null,
    song_spec: completeSpec,
    missing_required_fields: [],
    created_at: "2026-07-08T00:00:00Z",
    updated_at: "2026-07-08T00:00:00Z",
  };
}

test("song spec endpoints build nested project URLs", () => {
  assert.equal(intakeEndpoint("http://localhost:8000", "p1"), "http://localhost:8000/api/v1/projects/p1/intake");
  assert.equal(latestIntakeEndpoint("http://localhost:8000", "p1"), "http://localhost:8000/api/v1/projects/p1/intake/latest");
  assert.equal(songSpecGenerateEndpoint("http://localhost:8000", "p1"), "http://localhost:8000/api/v1/projects/p1/song-spec/generate");
  assert.equal(songSpecsEndpoint("http://localhost:8000", "p1"), "http://localhost:8000/api/v1/projects/p1/song-specs");
  assert.equal(songSpecApproveEndpoint("http://localhost:8000", "p1", "s1"), "http://localhost:8000/api/v1/projects/p1/song-specs/s1/approve");
});

test("validateIdea rejects empty ideas", () => {
  assert.equal(validateIdea("  "), "Song idea is required.");
  assert.equal(validateIdea("Late-night indie rock"), null);
});

test("isSongSpecComplete reports missing fields", () => {
  assert.equal(isSongSpecComplete(completeSpec), true);
  assert.deepEqual(missingSongSpecFields({ ...completeSpec, key: null }), ["key"]);
});

test("workspaceState reflects loading, clarification, draft, and approved states", () => {
  assert.equal(workspaceState({ isLoading: true, latestIntake: null, versions: [] }), "loading");
  assert.equal(
    workspaceState({
      isLoading: false,
      latestIntake: {
        intake_id: "i1",
        idea: "idea",
        answers: {},
        status: "needs_clarification",
        questions: [],
        generation_source: "deterministic",
        created_at: "2026-07-08T00:00:00Z",
        updated_at: "2026-07-08T00:00:00Z",
      },
      versions: [],
    }),
    "clarification",
  );
  assert.equal(workspaceState({ isLoading: false, latestIntake: null, versions: [version(1, "draft")] }), "draft");
  assert.equal(workspaceState({ isLoading: false, latestIntake: null, versions: [version(2, "approved")] }), "approved");
});

test("sortSongSpecVersions returns newest version first", () => {
  assert.deepEqual(
    sortSongSpecVersions([version(1, "draft"), version(3, "draft"), version(2, "approved")]).map(
      (item) => item.version_number,
    ),
    [3, 2, 1],
  );
});

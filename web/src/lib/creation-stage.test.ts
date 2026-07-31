import assert from "node:assert/strict";
import test from "node:test";

import { CreationStageInput, deriveCreationStage } from "./creation-stage";
import { AssetTree } from "./composition";
import { IdeaIntake, SongSpecVersion } from "./song-specs";

function buildInput(overrides: Partial<CreationStageInput> = {}): CreationStageInput {
  return {
    latestIntake: null,
    versions: [],
    lyricsVersions: [],
    chordVersions: [],
    midiAssets: [],
    arrangementVersions: [],
    assetTree: null,
    demoVersions: [],
    exportBundles: [],
    ...overrides,
  };
}

function songSpec(overrides: Partial<SongSpecVersion> = {}): SongSpecVersion {
  return {
    id: "spec-1",
    project_id: "p1",
    version_number: 1,
    status: "draft",
    song_spec: {
      title: "Demo",
      genre: "rock",
      tempo_bpm: 120,
      key: "C",
      song_structure: [],
      structure_sections: [],
    },
    source: "manual",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  } as unknown as SongSpecVersion;
}

function intake(overrides: Partial<IdeaIntake> = {}): IdeaIntake {
  return {
    intake_id: "i1",
    idea: "an idea",
    answers: {},
    status: "submitted",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  } as unknown as IdeaIntake;
}

function tree(current: AssetTree["current"]): AssetTree {
  return { current, timeline: [], missing_prerequisites: [] };
}

function statusOf(stage: ReturnType<typeof deriveCreationStage>, id: string) {
  return stage.steps.find((step) => step.id === id)?.status;
}

test("deriveCreationStage: empty project — idea active, rest blocked", () => {
  const stage = deriveCreationStage(buildInput());
  assert.equal(stage.currentIndex, 0);
  assert.equal(stage.complete, false);
  assert.equal(statusOf(stage, "idea"), "active");
  assert.equal(statusOf(stage, "song_spec"), "blocked");
  assert.equal(statusOf(stage, "export"), "blocked");
});

test("deriveCreationStage: intake submitted but no SongSpec — idea done, song_spec active", () => {
  const stage = deriveCreationStage(buildInput({ latestIntake: intake() }));
  assert.equal(statusOf(stage, "idea"), "done");
  assert.equal(statusOf(stage, "song_spec"), "active");
  assert.equal(statusOf(stage, "approve"), "blocked");
});

test("deriveCreationStage: draft SongSpec not approved — approve active", () => {
  const stage = deriveCreationStage(
    buildInput({ latestIntake: intake(), versions: [songSpec()] }),
  );
  assert.equal(statusOf(stage, "idea"), "done");
  assert.equal(statusOf(stage, "song_spec"), "done");
  assert.equal(statusOf(stage, "approve"), "active");
  assert.equal(statusOf(stage, "composition"), "blocked");
});

test("deriveCreationStage: approved SongSpec, no assets — composition active", () => {
  const stage = deriveCreationStage(
    buildInput({ latestIntake: intake(), versions: [songSpec({ status: "approved" })] }),
  );
  assert.equal(statusOf(stage, "approve"), "done");
  assert.equal(statusOf(stage, "composition"), "active");
  assert.equal(statusOf(stage, "arrangement"), "blocked");
});

test("deriveCreationStage: composition present via assetTree — arrangement active", () => {
  const stage = deriveCreationStage(
    buildInput({
      latestIntake: intake(),
      versions: [songSpec({ status: "approved" })],
      assetTree: tree({
        song_spec: null,
        lyrics: { asset_type: "lyrics", id: "l1", label: "Lyrics", version_number: 1, created_at: "2026-01-01T00:00:00Z", status: "ready", kind: null },
        chords: null,
        midi_assets: [],
        arrangement: null,
      }),
    }),
  );
  assert.equal(statusOf(stage, "composition"), "done");
  assert.equal(statusOf(stage, "arrangement"), "active");
});

test("deriveCreationStage: arrangement present — demo active", () => {
  const stage = deriveCreationStage(
    buildInput({
      latestIntake: intake(),
      versions: [songSpec({ status: "approved" })],
      assetTree: tree({
        song_spec: null,
        lyrics: { asset_type: "lyrics", id: "l1", label: "Lyrics", version_number: 1, created_at: "2026-01-01T00:00:00Z", status: "ready", kind: null },
        chords: null,
        midi_assets: [],
        arrangement: null,
      }),
      arrangementVersions: [
        { id: "a1", project_id: "p1", version_number: 1, arrangement_plan: { sections: [] }, source: "manual", created_at: "2026-01-01T00:00:00Z" },
      ] as never,
    }),
  );
  assert.equal(statusOf(stage, "arrangement"), "done");
  assert.equal(statusOf(stage, "demo"), "active");
  assert.equal(statusOf(stage, "export"), "blocked");
});

test("deriveCreationStage: demo present — export active", () => {
  const stage = deriveCreationStage(
    buildInput({
      latestIntake: intake(),
      versions: [songSpec({ status: "approved" })],
      assetTree: tree({
        song_spec: null,
        lyrics: { asset_type: "lyrics", id: "l1", label: "Lyrics", version_number: 1, created_at: "2026-01-01T00:00:00Z", status: "ready", kind: null },
        chords: null,
        midi_assets: [],
        arrangement: null,
      }),
      arrangementVersions: [
        { id: "a1", project_id: "p1", version_number: 1, arrangement_plan: { sections: [] }, source: "manual", created_at: "2026-01-01T00:00:00Z" },
      ] as never,
      demoVersions: [
        { id: "d1", project_id: "p1", version_number: 1, status: "ready", audio_url: "x", duration_seconds: 10, sample_rate: 44100, error_message: null, created_at: "2026-01-01T00:00:00Z" },
      ] as never,
    }),
  );
  assert.equal(statusOf(stage, "demo"), "done");
  assert.equal(statusOf(stage, "export"), "active");
});

test("deriveCreationStage: export present — chain complete, currentIndex -1", () => {
  const stage = deriveCreationStage(
    buildInput({
      latestIntake: intake(),
      versions: [songSpec({ status: "approved" })],
      assetTree: tree({
        song_spec: null,
        lyrics: { asset_type: "lyrics", id: "l1", label: "Lyrics", version_number: 1, created_at: "2026-01-01T00:00:00Z", status: "ready", kind: null },
        chords: null,
        midi_assets: [],
        arrangement: null,
      }),
      arrangementVersions: [{ id: "a1", project_id: "p1", version_number: 1, arrangement_plan: { sections: [] }, source: "manual", created_at: "2026-01-01T00:00:00Z" }] as never,
      demoVersions: [{ id: "d1", project_id: "p1", version_number: 1, status: "ready", audio_url: "x", duration_seconds: 10, sample_rate: 44100, error_message: null, created_at: "2026-01-01T00:00:00Z" }] as never,
      exportBundles: [{ id: "e1", project_id: "p1", arrangement_plan_id: "a1", status: "ready", manifest: {}, filename: "x.zip", content_type: "application/zip", size_bytes: 1, checksum: null, download_url: null, error_message: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z" }] as never,
    }),
  );
  assert.equal(stage.complete, true);
  assert.equal(stage.currentIndex, -1);
  assert.equal(statusOf(stage, "export"), "done");
});

test("deriveCreationStage: composition derived from version lists when assetTree absent", () => {
  const stage = deriveCreationStage(
    buildInput({
      latestIntake: intake(),
      versions: [songSpec({ status: "approved" })],
      lyricsVersions: [{ id: "l1", project_id: "p1", version_number: 1, lyrics: { sections: [] }, source: "manual", created_at: "2026-01-01T00:00:00Z" }] as never,
    }),
  );
  assert.equal(statusOf(stage, "composition"), "done");
});

test("deriveCreationStage: every step maps to a non-empty anchor", () => {
  const stage = deriveCreationStage(buildInput());
  for (const step of stage.steps) {
    assert.ok(step.anchor.length > 0, `step ${step.id} has empty anchor`);
  }
});

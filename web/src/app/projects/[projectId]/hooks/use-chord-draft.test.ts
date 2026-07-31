import assert from "node:assert/strict";
import test from "node:test";

import { chordDraftStorageKey } from "./use-chord-draft";
import { lyricsDraftStorageKey } from "./use-lyrics-draft";
import { structureDraftStorageKey } from "./use-structure-draft";

test("draft storage keys are scoped per source version", () => {
  assert.notEqual(chordDraftStorageKey("p1", "v1"), chordDraftStorageKey("p1", "v2"));
  assert.equal(chordDraftStorageKey("p1", "v1"), chordDraftStorageKey("p1", "v1"));
  assert.equal(chordDraftStorageKey("p1", null), chordDraftStorageKey("p1", null));
  assert.equal(chordDraftStorageKey("p1", null).endsWith(":none"), true);
});

test("lyrics and structure draft keys follow the same per-version contract", () => {
  assert.notEqual(lyricsDraftStorageKey("p1", "v1"), lyricsDraftStorageKey("p1", "v2"));
  assert.equal(lyricsDraftStorageKey("p1", "v1"), lyricsDraftStorageKey("p1", "v1"));
  assert.notEqual(structureDraftStorageKey("p1", "v1"), structureDraftStorageKey("p1", "v2"));
  assert.equal(structureDraftStorageKey("p1", "v1"), structureDraftStorageKey("p1", "v1"));
});

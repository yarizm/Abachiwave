import assert from "node:assert/strict";
import test from "node:test";

import type { LyricsVersion } from "./composition";
import {
  addLyricLine,
  analyzeLyricLine,
  applyRewriteChanges,
  createLyricsHistory,
  draftFromLyricsVersion,
  isLyricsDraft,
  lyricDiagnostics,
  lyricsDraftsEqual,
  lyricsRewriteEndpoint,
  moveLyricLine,
  parseLyricTerms,
  pushLyricsHistory,
  redoLyricsHistory,
  removeLyricLine,
  selectionResetKey,
  undoLyricsHistory,
  updateLyricLine,
} from "./lyrics-editor";

function version(): LyricsVersion {
  const line = analyzeLyricLine("We carry fire", "line-1", "A");
  return {
    id: "lyrics-1",
    project_id: "project-1",
    song_spec_id: "spec-1",
    version_number: 1,
    parent_version_id: null,
    source_revision_request_id: null,
    schema_version: 2,
    sections: [{ section_id: "verse", label: "Verse", text: line.text, lines: [line] }],
    hook_candidates: [{ id: "hook-1", text: "Carry the fire" }],
    created_at: "2026-07-14T00:00:00Z",
    updated_at: "2026-07-14T00:00:00Z",
  };
}

test("lyrics rewrite endpoint is nested below a version", () => {
  assert.equal(
    lyricsRewriteEndpoint("http://localhost:8000", "p1", "l1"),
    "http://localhost:8000/api/v1/projects/p1/lyrics/l1/rewrite",
  );
});

test("line editing keeps text synchronized and supports line ordering", () => {
  let draft = draftFromLyricsVersion(version());
  draft = updateLyricLine(draft, "verse", "line-1", { text: "We follow fire" });
  assert.equal(draft.sections[0].text, "We follow fire");
  draft = addLyricLine(draft, "verse", "line-1");
  const added = draft.sections[0].lines[1];
  assert.ok(added.line_id);
  draft = updateLyricLine(draft, "verse", added.line_id, { text: "Night opens" });
  draft = moveLyricLine(draft, "verse", added.line_id, -1);
  assert.equal(draft.sections[0].text, "Night opens\nWe follow fire");
  draft = removeLyricLine(draft, "verse", added.line_id);
  assert.equal(draft.sections[0].lines.length, 1);
});

test("history and rewrite acceptance stay local until save", () => {
  const draft = draftFromLyricsVersion(version());
  const changed = applyRewriteChanges(
    draft,
    [
      {
        section_id: "verse",
        line_id: "line-1",
        before: draft.sections[0].lines[0],
        after: analyzeLyricLine("We carry brighter fire", "line-1", "A"),
        diff: [],
      },
    ],
    new Set(["line-1"]),
  );
  let history = pushLyricsHistory(createLyricsHistory(draft), changed);
  assert.equal(history.present.sections[0].text, "We carry brighter fire");
  history = undoLyricsHistory(history);
  assert.equal(history.present.sections[0].text, "We carry fire");
  history = redoLyricsHistory(history);
  assert.equal(history.present.sections[0].text, "We carry brighter fire");
});

test("vocabulary helpers normalize terms and flag avoided expressions", () => {
  const draft = draftFromLyricsVersion(version());
  assert.deepEqual(parseLyricTerms("fire, night，fire\nroad"), ["fire", "night", "road"]);
  assert.deepEqual(lyricDiagnostics(draft.sections, ["carry"]), [
    { sectionId: "verse", lineId: "line-1", phrase: "carry" },
  ]);
});

test("local draft validation rejects corruption and equality ignores derived metrics", () => {
  const baseline = draftFromLyricsVersion(version());
  const recalculated = draftFromLyricsVersion(version());
  recalculated.sections[0].lines[0].syllable_count += 1;

  assert.equal(isLyricsDraft(baseline), true);
  assert.equal(isLyricsDraft({ sections: [{}], hookCandidates: [] }), false);
  assert.equal(lyricsDraftsEqual(baseline, recalculated), true);
});

test("selection reset key is stable across object identities of the same version", () => {
  assert.equal(selectionResetKey(null), "none");
  assert.equal(selectionResetKey({ id: "v1" }), "v1");
  assert.equal(selectionResetKey({ id: "v1" }), selectionResetKey({ id: "v1" }));
  assert.notEqual(selectionResetKey({ id: "v1" }), selectionResetKey({ id: "v2" }));
});

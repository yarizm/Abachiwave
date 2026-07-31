import assert from "node:assert/strict";
import test from "node:test";

import {
  addChordEvent,
  addChordMeasure,
  chordDisplayLabel,
  createChordHistory,
  draftFromChordVersion,
  pushChordHistory,
  redoChordHistory,
  removeChordMeasure,
  undoChordHistory,
  updateChordEvent,
} from "./chord-editor";
import type { ChordProgressionVersion } from "./composition";

const version: ChordProgressionVersion = {
  id: "chords-1",
  project_id: "project-1",
  song_spec_id: "song-spec-1",
  lyrics_version_id: null,
  version_number: 1,
  parent_version_id: null,
  schema_version: 2,
  key: "C major",
  tempo_bpm: 120,
  time_signature: "4/4",
  sections: [
    {
      section_id: "verse",
      label: "Verse",
      bars: 1,
      chords: ["Cmaj7"],
      measures: [
        {
          measure_number: 1,
          events: [
            {
              event_id: "event-1",
              measure: 1,
              beat: 1,
              duration_beats: 4,
              symbol: "Cmaj7",
              inversion: 0,
              root: "C",
              bass: "C",
              quality: "major-seventh",
              extensions: ["7"],
              pitch_classes: [0, 4, 7, 11],
              midi_notes: [48, 52, 55, 59],
              roman_numeral: "I7",
              nashville_number: "1maj7",
              borrowed: false,
            },
          ],
        },
      ],
    },
  ],
  created_at: "2026-07-14T00:00:00Z",
  updated_at: "2026-07-14T00:00:00Z",
};

test("chord draft edits clear stale theory data and keep legacy projection synchronized", () => {
  const draft = draftFromChordVersion(version);
  const edited = updateChordEvent(draft, "verse", "event-1", {
    symbol: "Dm7",
    inversion: 1,
  });
  const event = edited.sections[0].measures[0].events[0];

  assert.equal(event.symbol, "Dm7");
  assert.equal(event.inversion, 1);
  assert.equal(event.root, null);
  assert.deepEqual(event.midi_notes, []);
  assert.deepEqual(edited.sections[0].chords, ["Dm7"]);
});

test("chord history supports undo and redo", () => {
  const draft = draftFromChordVersion(version);
  const edited = updateChordEvent(draft, "verse", "event-1", { duration_beats: 2 });
  const pushed = pushChordHistory(createChordHistory(draft), edited);

  assert.equal(pushed.present.sections[0].measures[0].events[0].duration_beats, 2);
  assert.equal(undoChordHistory(pushed).present.sections[0].measures[0].events[0].duration_beats, 4);
  assert.equal(
    redoChordHistory(undoChordHistory(pushed)).present.sections[0].measures[0].events[0]
      .duration_beats,
    2,
  );
});

test("chord measures and free beat events are added without overlap", () => {
  const draft = draftFromChordVersion(version);
  const shortened = updateChordEvent(draft, "verse", "event-1", { duration_beats: 2 });
  const withEvent = addChordEvent(shortened, "verse", 1, 4);
  const events = withEvent.sections[0].measures[0].events;
  assert.equal(events.length, 2);
  assert.equal(events[1].beat, 3);
  assert.equal(events[1].duration_beats, 1);

  const withMeasure = addChordMeasure(withEvent, "verse", 4);
  assert.equal(withMeasure.sections[0].bars, 2);
  assert.equal(withMeasure.sections[0].measures[1].events[0].symbol, "N.C.");

  const removed = removeChordMeasure(withMeasure, "verse", 1);
  assert.equal(removed.sections[0].bars, 1);
  assert.equal(removed.sections[0].measures[0].measure_number, 1);
  assert.equal(removed.sections[0].measures[0].events[0].measure, 1);
});

test("chord display labels use server supplied theory notation", () => {
  const event = version.sections[0].measures[0].events[0];
  assert.equal(chordDisplayLabel(event, "symbol"), "Cmaj7");
  assert.equal(chordDisplayLabel(event, "roman"), "I7");
  assert.equal(chordDisplayLabel(event, "nashville"), "1maj7");
});

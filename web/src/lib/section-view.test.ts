import assert from "node:assert/strict";
import test from "node:test";

import { ChordMeasure, ChordSection, LyricLine, LyricSection, MidiNoteEvent } from "@/lib/composition";
import {
  assignNotesToSection,
  beatsPerMeasure,
  buildSectionView,
  noteBeatSpan,
  notePitchSpan,
} from "@/lib/section-view";

function line(id: string, text: string): LyricLine {
  return {
    line_id: id,
    text,
    rhyme_label: null,
    character_count: text.length,
    word_count: text.split(" ").length,
    syllable_count: 0,
    rhyme_key: null,
    stress_positions: [],
  };
}

function lyricSection(sectionId: string, label: string, lines: LyricLine[]): LyricSection {
  return { section_id: sectionId, label, text: lines.map((l) => l.text).join("\n"), lines };
}

function measure(number: number): ChordMeasure {
  return {
    measure_number: number,
    events: [
      {
        event_id: `event-${number}`,
        measure: number,
        beat: 1,
        duration_beats: 4,
        symbol: "E",
        inversion: null,
        root: "E",
        bass: null,
        quality: "major",
        extensions: [],
        pitch_classes: [4, 8, 11],
        midi_notes: [64, 68, 71],
        roman_numeral: "I",
        nashville_number: "1",
        borrowed: false,
      },
    ],
  };
}

function chordSection(sectionId: string, label: string, measures: ChordMeasure[]): ChordSection {
  return {
    section_id: sectionId,
    label,
    bars: measures.length,
    chords: ["E"],
    measures,
  };
}

function note(id: string, sectionId: string | null, pitch: number, start = 0): MidiNoteEvent {
  return {
    note_id: id,
    section_id: sectionId,
    pitch,
    start_beat: start,
    duration_beats: 1,
    velocity: 90,
    channel: 0,
  };
}

test("joins lyrics, chords and melody onto one row per section", () => {
  const view = buildSectionView({
    structure: [
      { section_id: "verse", label: "Verse" },
      { section_id: "chorus", label: "Chorus" },
    ],
    lyrics: [lyricSection("verse", "Verse", [line("l1", "a"), line("l2", "b")])],
    chords: [chordSection("chorus", "Chorus", [measure(1)])],
    notes: [note("n1", "verse", 60), note("n2", "chorus", 67)],
  });

  assert.deepEqual(
    view.rows.map((row) => [row.section_id, row.lyrics.length, row.measures.length, row.notes.length]),
    [
      ["verse", 2, 0, 1],
      ["chorus", 0, 1, 1],
    ],
  );
});

test("section order follows the SongSpec structure, not asset order", () => {
  const view = buildSectionView({
    structure: [
      { section_id: "intro", label: "Intro" },
      { section_id: "verse", label: "Verse" },
      { section_id: "chorus", label: "Chorus" },
    ],
    // deliberately reversed relative to the structure
    lyrics: [
      lyricSection("chorus", "Chorus", [line("l1", "a")]),
      lyricSection("intro", "Intro", [line("l2", "b")]),
    ],
    chords: [],
    notes: [],
  });

  assert.deepEqual(view.rows.map((row) => row.section_id), ["intro", "verse", "chorus"]);
});

test("reports which assets are missing for each section", () => {
  const view = buildSectionView({
    structure: [{ section_id: "verse", label: "Verse" }],
    lyrics: [lyricSection("verse", "Verse", [line("l1", "a")])],
    chords: [],
    notes: [],
  });

  assert.deepEqual(view.rows[0].gaps, { lyrics: false, chords: true, melody: true });
});

test("an empty lyric section counts as a gap", () => {
  const view = buildSectionView({
    structure: [{ section_id: "verse", label: "Verse" }],
    lyrics: [lyricSection("verse", "Verse", [])],
    chords: [chordSection("verse", "Verse", [])],
    notes: [],
  });

  assert.deepEqual(view.rows[0].gaps, { lyrics: true, chords: true, melody: true });
});

test("collects notes with no section instead of dropping or guessing them", () => {
  // This is the humming path: audio extraction parses a MIDI file, which carries
  // no song structure, so every note comes back with section_id null.
  const view = buildSectionView({
    structure: [{ section_id: "verse", label: "Verse" }],
    lyrics: [],
    chords: [],
    notes: [note("n2", null, 62, 4), note("n1", null, 60, 0), note("n3", "verse", 64)],
  });

  assert.deepEqual(view.unassignedNotes.map((n) => n.note_id), ["n1", "n2"]);
  assert.deepEqual(view.rows[0].notes.map((n) => n.note_id), ["n3"]);
});

test("notes within a section are ordered by start beat", () => {
  const view = buildSectionView({
    structure: [{ section_id: "verse", label: "Verse" }],
    lyrics: [],
    chords: [],
    notes: [note("late", "verse", 60, 8), note("early", "verse", 62, 1)],
  });

  assert.deepEqual(view.rows[0].notes.map((n) => n.note_id), ["early", "late"]);
});

test("flags section ids an asset uses that the structure does not list", () => {
  const view = buildSectionView({
    structure: [{ section_id: "verse", label: "Verse" }],
    lyrics: [lyricSection("bridge", "Bridge", [line("l1", "a")])],
    chords: [],
    notes: [note("n1", "outro", 60)],
  });

  assert.deepEqual(view.orphanSectionIds.sort(), ["bridge", "outro"]);
  assert.deepEqual(view.rows.map((row) => row.section_id), ["verse"]);
});

test("falls back to asset order when the SongSpec has no structure sections", () => {
  const view = buildSectionView({
    structure: [],
    lyrics: [lyricSection("verse", "Verse", [line("l1", "a")])],
    chords: [chordSection("chorus", "Chorus", [measure(1)])],
    notes: [],
  });

  assert.deepEqual(view.rows.map((row) => [row.section_id, row.label]), [
    ["verse", "Verse"],
    ["chorus", "Chorus"],
  ]);
});

test("assignNotesToSection returns a new list and touches only the named notes", () => {
  const notes = [note("n1", null, 60), note("n2", null, 62)];
  const assigned = assignNotesToSection(notes, ["n1"], "verse");

  assert.equal(assigned[0].section_id, "verse");
  assert.equal(assigned[1].section_id, null);
  assert.equal(notes[0].section_id, null, "input must not be mutated");
  assert.notEqual(assigned, notes);
});

test("assignNotesToSection with no ids returns the original list", () => {
  const notes = [note("n1", null, 60)];
  assert.equal(assignNotesToSection(notes, [], "verse"), notes);
});

test("noteBeatSpan covers the last note's tail, not just its onset", () => {
  assert.deepEqual(noteBeatSpan([note("n1", null, 60, 2), note("n2", null, 62, 6)]), {
    start: 2,
    end: 7,
  });
  assert.equal(noteBeatSpan([]), null);
});

test("notePitchSpan pads a narrow range so a strip never collapses", () => {
  const span = notePitchSpan([note("n1", null, 60)]);
  assert.ok(span);
  assert.equal(span.high - span.low, 12);

  const wide = notePitchSpan([note("low", null, 48), note("high", null, 84)]);
  assert.deepEqual(wide, { low: 48, high: 84 });
});

test("notePitchSpan clamps padding to the MIDI range", () => {
  const span = notePitchSpan([note("n1", null, 0)]);
  assert.ok(span);
  assert.equal(span.low, 0);
  assert.ok(span.high <= 127);
});

test("beatsPerMeasure reads the numerator and falls back to four", () => {
  assert.equal(beatsPerMeasure("4/4"), 4);
  assert.equal(beatsPerMeasure("3/4"), 3);
  assert.equal(beatsPerMeasure("6/8"), 6);
  assert.equal(beatsPerMeasure(null), 4);
  assert.equal(beatsPerMeasure(""), 4);
  assert.equal(beatsPerMeasure("nonsense"), 4);
  assert.equal(beatsPerMeasure("0/4"), 4);
});

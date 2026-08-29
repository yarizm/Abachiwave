import assert from "node:assert/strict";
import test from "node:test";

import { ChordEvent, ChordMeasure, MidiNoteEvent } from "@/lib/composition";
import { buildSectionSchedule, SectionPlaybackInput } from "@/lib/section-playback";

/**
 * ChordEvent and MidiNoteEvent both carry fields the playback math never reads
 * (roman numerals, MIDI channel, ...) alongside the handful it does. Factories
 * keep each test below focused on the fields it actually varies. `borrowed` in
 * particular is easy to drop by hand and is a typecheck failure, not a test
 * failure, so every ChordEvent comes from here rather than a literal.
 */
function chordEvent(overrides: Partial<ChordEvent> = {}): ChordEvent {
  return {
    event_id: "event-1",
    measure: 1,
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
    ...overrides,
  };
}

function chordMeasure(measureNumber: number, events: ChordEvent[]): ChordMeasure {
  return { measure_number: measureNumber, events };
}

function midiNote(overrides: Partial<MidiNoteEvent> = {}): MidiNoteEvent {
  return {
    note_id: "note-1",
    section_id: "verse",
    pitch: 64,
    start_beat: 0,
    duration_beats: 1,
    velocity: 90,
    channel: 0,
    ...overrides,
  };
}

function baseInput(overrides: Partial<SectionPlaybackInput> = {}): SectionPlaybackInput {
  return {
    measures: [],
    notes: [],
    noteStartBeat: 0,
    beatsPerMeasure: 4,
    tempoBpm: 120,
    timeSignature: "4/4",
    ...overrides,
  };
}

test("a chord on measure 2 beat 1 lands at the arithmetically correct time", () => {
  // 120bpm 4/4 is 0.5s per beat; measure 2 beat 1 is 4 beats into the section.
  const schedule = buildSectionSchedule(
    baseInput({
      measures: [chordMeasure(2, [chordEvent({ event_id: "e-2-1", measure: 2, beat: 1 })])],
    }),
  );

  assert.equal(schedule.beatSeconds, 0.5);
  assert.equal(schedule.tones.length, 1);
  assert.equal(schedule.tones[0].at, 2);
});

test("a melody note whose start_beat equals noteStartBeat lands at the top of the section", () => {
  const schedule = buildSectionSchedule(
    baseInput({
      noteStartBeat: 8,
      notes: [midiNote({ note_id: "n-1", start_beat: 8 })],
    }),
  );

  assert.equal(schedule.tones.length, 1);
  assert.equal(schedule.tones[0].at, 0);
});

test("a chord and a melody note that line up visually also line up in time", () => {
  // Regression test for the whole feature: measure 3 beat 1 is the same
  // section-local beat as noteStartBeat + 2 bars, so what the strip draws
  // stacked and what playback sounds at once must be the same beat.
  const noteStartBeat = 8;
  const schedule = buildSectionSchedule(
    baseInput({
      noteStartBeat,
      measures: [chordMeasure(3, [chordEvent({ event_id: "chord", measure: 3, beat: 1 })])],
      notes: [midiNote({ note_id: "melody", start_beat: noteStartBeat + 2 * 4 })],
    }),
  );

  const chordTone = schedule.tones.find((tone) => tone.kind === "chord");
  const melodyTone = schedule.tones.find((tone) => tone.kind === "melody");
  assert.ok(chordTone);
  assert.ok(melodyTone);
  assert.equal(chordTone.at, melodyTone.at);
});

test("totalSeconds takes the melody tail when it runs past the last bar", () => {
  const schedule = buildSectionSchedule(
    baseInput({
      measures: [chordMeasure(1, [chordEvent()])], // one bar: 4 beats
      notes: [midiNote({ start_beat: 10, duration_beats: 2 })], // tail: 12 beats
    }),
  );

  assert.equal(schedule.totalBeats, 12);
  assert.equal(schedule.totalSeconds, 6);
});

test("totalSeconds takes the chord grid when it runs past the melody", () => {
  const schedule = buildSectionSchedule(
    baseInput({
      measures: [
        chordMeasure(1, [chordEvent({ event_id: "e1", measure: 1 })]),
        chordMeasure(2, [chordEvent({ event_id: "e2", measure: 2 })]),
      ], // two bars: 8 beats
      notes: [midiNote({ start_beat: 0, duration_beats: 1 })], // tail: 1 beat
    }),
  );

  assert.equal(schedule.totalBeats, 8);
  assert.equal(schedule.totalSeconds, 4);
});

test("empty measures and empty notes yield no tones but a playable, non-zero length", () => {
  const schedule = buildSectionSchedule(baseInput());

  assert.deepEqual(schedule.tones, []);
  assert.equal(schedule.totalBeats, 4);
  assert.equal(schedule.totalSeconds, 2);
});

test("a chord event with no resolved pitches is skipped", () => {
  const schedule = buildSectionSchedule(
    baseInput({
      measures: [chordMeasure(1, [chordEvent({ midi_notes: [] })])],
    }),
  );

  assert.deepEqual(schedule.tones, []);
});

test("a 6/8 time signature changes beatSeconds relative to 4/4", () => {
  const sixEight = buildSectionSchedule(baseInput({ timeSignature: "6/8", beatsPerMeasure: 6 }));
  const fourFour = buildSectionSchedule(baseInput({ timeSignature: "4/4" }));

  assert.equal(sixEight.beatSeconds, 0.25);
  assert.equal(fourFour.beatSeconds, 0.5);
});

test("a velocity-0 melody note still produces an audible velocity", () => {
  const schedule = buildSectionSchedule(baseInput({ notes: [midiNote({ velocity: 0 })] }));

  assert.equal(schedule.tones[0].velocity, 0.15);
});

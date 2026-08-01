import assert from "node:assert/strict";
import test from "node:test";

import type { MidiNoteEvent } from "./composition";
import {
  addMidiNote,
  createMidiHistory,
  duplicateMidiNotes,
  midiDraftDuration,
  midiPitchName,
  pasteMidiNotes,
  pushMidiHistory,
  redoMidiHistory,
  removeMidiNotes,
  undoMidiHistory,
  updateMidiNotes,
} from "./midi-editor";

const note: MidiNoteEvent = {
  note_id: "note-1",
  section_id: "verse",
  pitch: 60,
  start_beat: 0,
  duration_beats: 1,
  velocity: 80,
  channel: 0,
};

test("MIDI draft supports note add, edit, delete, duplicate, and paste", () => {
  let draft = { noteEvents: [note] };
  draft = addMidiNote(draft, { ...note, note_id: "note-2", pitch: 64, start_beat: 1 });
  draft = updateMidiNotes(draft, ["note-2"], (event) => ({ ...event, pitch: 67 }));
  assert.equal(draft.noteEvents.find((event) => event.note_id === "note-2")?.pitch, 67);

  const duplicated = duplicateMidiNotes(draft, ["note-1"], 2);
  assert.equal(duplicated.draft.noteEvents.length, 3);
  assert.equal(
    duplicated.draft.noteEvents.find((event) => duplicated.createdIds.includes(event.note_id))
      ?.start_beat,
    2,
  );

  const pasted = pasteMidiNotes(draft, [note], 4);
  assert.equal(pasted.draft.noteEvents.at(-1)?.start_beat, 4);
  assert.equal(removeMidiNotes(pasted.draft, pasted.createdIds).noteEvents.length, 2);
});

test("MIDI history supports undo and redo", () => {
  const initial = { noteEvents: [note] };
  const changed = updateMidiNotes(initial, ["note-1"], (event) => ({ ...event, pitch: 72 }));
  const history = pushMidiHistory(createMidiHistory(initial), changed);
  assert.equal(undoMidiHistory(history).present.noteEvents[0].pitch, 60);
  assert.equal(redoMidiHistory(undoMidiHistory(history)).present.noteEvents[0].pitch, 72);
});

test("MIDI labels and duration are derived from note content", () => {
  assert.equal(midiPitchName(60), "C4");
  assert.equal(midiDraftDuration({ noteEvents: [{ ...note, start_beat: 10 }] }), 11);
});

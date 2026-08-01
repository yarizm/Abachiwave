import type { MidiAssetVersion, MidiNoteEvent } from "@/lib/composition";

export type MidiDraft = {
  noteEvents: MidiNoteEvent[];
};

export type MidiHistory = {
  past: MidiDraft[];
  present: MidiDraft;
  future: MidiDraft[];
};

export function draftFromMidiVersion(version: MidiAssetVersion | null): MidiDraft {
  return { noteEvents: version ? cloneNotes(version.note_events) : [] };
}

export function createMidiNoteId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `note-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function addMidiNote(
  draft: MidiDraft,
  note: Omit<MidiNoteEvent, "note_id"> & { note_id?: string },
): MidiDraft {
  return normalizeMidiDraft({
    noteEvents: [
      ...draft.noteEvents,
      {
        ...note,
        note_id: note.note_id ?? createMidiNoteId(),
      },
    ],
  });
}

export function updateMidiNotes(
  draft: MidiDraft,
  noteIds: Iterable<string>,
  update: (note: MidiNoteEvent) => MidiNoteEvent,
): MidiDraft {
  const selected = new Set(noteIds);
  return normalizeMidiDraft({
    noteEvents: draft.noteEvents.map((note) =>
      selected.has(note.note_id) ? sanitizeMidiNote(update({ ...note })) : note,
    ),
  });
}

export function removeMidiNotes(draft: MidiDraft, noteIds: Iterable<string>): MidiDraft {
  const selected = new Set(noteIds);
  return {
    noteEvents: draft.noteEvents.filter((note) => !selected.has(note.note_id)),
  };
}

export function duplicateMidiNotes(
  draft: MidiDraft,
  noteIds: Iterable<string>,
  offsetBeats = 1,
): { draft: MidiDraft; createdIds: string[] } {
  const selected = new Set(noteIds);
  const created = draft.noteEvents
    .filter((note) => selected.has(note.note_id))
    .map((note) => ({
      ...note,
      note_id: createMidiNoteId(),
      start_beat: Math.max(0, note.start_beat + offsetBeats),
    }));
  return {
    draft: normalizeMidiDraft({ noteEvents: [...draft.noteEvents, ...created] }),
    createdIds: created.map((note) => note.note_id),
  };
}

export function pasteMidiNotes(
  draft: MidiDraft,
  notes: MidiNoteEvent[],
  atBeat: number,
): { draft: MidiDraft; createdIds: string[] } {
  if (!notes.length) return { draft, createdIds: [] };
  const firstBeat = Math.min(...notes.map((note) => note.start_beat));
  const created = notes.map((note) => ({
    ...note,
    note_id: createMidiNoteId(),
    start_beat: Math.max(0, atBeat + note.start_beat - firstBeat),
  }));
  return {
    draft: normalizeMidiDraft({ noteEvents: [...draft.noteEvents, ...created] }),
    createdIds: created.map((note) => note.note_id),
  };
}

export function normalizeMidiDraft(draft: MidiDraft): MidiDraft {
  return {
    noteEvents: draft.noteEvents
      .map((note) => sanitizeMidiNote(note))
      .sort((left, right) =>
        left.start_beat - right.start_beat ||
        left.pitch - right.pitch ||
        left.note_id.localeCompare(right.note_id),
      ),
  };
}

export function createMidiHistory(draft: MidiDraft): MidiHistory {
  return { past: [], present: cloneMidiDraft(draft), future: [] };
}

export function pushMidiHistory(history: MidiHistory, draft: MidiDraft): MidiHistory {
  if (midiDraftsEqual(history.present, draft)) return history;
  return {
    past: [...history.past.slice(-49), cloneMidiDraft(history.present)],
    present: cloneMidiDraft(draft),
    future: [],
  };
}

export function undoMidiHistory(history: MidiHistory): MidiHistory {
  const previous = history.past.at(-1);
  if (!previous) return history;
  return {
    past: history.past.slice(0, -1),
    present: cloneMidiDraft(previous),
    future: [cloneMidiDraft(history.present), ...history.future],
  };
}

export function redoMidiHistory(history: MidiHistory): MidiHistory {
  const next = history.future[0];
  if (!next) return history;
  return {
    past: [...history.past, cloneMidiDraft(history.present)],
    present: cloneMidiDraft(next),
    future: history.future.slice(1),
  };
}

export function cloneMidiDraft(draft: MidiDraft): MidiDraft {
  return { noteEvents: cloneNotes(draft.noteEvents) };
}

export function midiDraftsEqual(left: MidiDraft, right: MidiDraft): boolean {
  return JSON.stringify(normalizeMidiDraft(left)) === JSON.stringify(normalizeMidiDraft(right));
}

export function isMidiDraft(value: unknown): value is MidiDraft {
  return (
    isRecord(value) &&
    Array.isArray(value.noteEvents) &&
    value.noteEvents.every(
      (note) =>
        isRecord(note) &&
        typeof note.note_id === "string" &&
        (typeof note.section_id === "string" || note.section_id === null) &&
        typeof note.pitch === "number" &&
        typeof note.start_beat === "number" &&
        typeof note.duration_beats === "number" &&
        typeof note.velocity === "number" &&
        typeof note.channel === "number",
    )
  );
}

export function midiPitchName(pitch: number): string {
  const names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  return `${names[pitch % 12]}${Math.floor(pitch / 12) - 1}`;
}

export function midiDraftDuration(draft: MidiDraft): number {
  return Math.max(
    8,
    ...draft.noteEvents.map((note) => note.start_beat + note.duration_beats),
  );
}

function sanitizeMidiNote(note: MidiNoteEvent): MidiNoteEvent {
  return {
    ...note,
    pitch: clamp(Math.round(note.pitch), 0, 127),
    start_beat: Math.max(0, roundBeat(note.start_beat)),
    duration_beats: Math.max(1 / 480, roundBeat(note.duration_beats)),
    velocity: clamp(Math.round(note.velocity), 1, 127),
    channel: clamp(Math.round(note.channel), 0, 15),
  };
}

function cloneNotes(notes: MidiNoteEvent[]): MidiNoteEvent[] {
  return notes.map((note) => ({ ...note }));
}

function roundBeat(value: number): number {
  return Math.round(value * 960) / 960;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

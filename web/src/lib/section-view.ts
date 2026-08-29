import { ChordMeasure, ChordSection, LyricLine, LyricSection, MidiNoteEvent } from "@/lib/composition";
import { StructureSection } from "@/lib/song-specs";

/**
 * Joins lyrics, chords and melody into one row per song section.
 *
 * The backend already gives every lyric section, chord section and generated note
 * a `section_id` that is stable across versions, but the workspace never used it:
 * the three editors were separate panels, each grouping by section on its own, so
 * you could not read one section's words, chords and melody together. This is the
 * join that makes that possible.
 *
 * Melody is the ragged one. `MidiNoteEvent.section_id` is nullable, and notes
 * transcribed from a humming upload have no section at all — the audio path builds
 * them from a parsed MIDI file, which has no concept of song structure. Those land
 * in `unassignedNotes` rather than being dropped or guessed at.
 */

export type SectionAssetGaps = {
  lyrics: boolean;
  chords: boolean;
  melody: boolean;
};

export type SectionRow = {
  section_id: string;
  label: string;
  lyrics: LyricLine[];
  measures: ChordMeasure[];
  notes: MidiNoteEvent[];
  /** which of the three assets have nothing for this section */
  gaps: SectionAssetGaps;
};

export type SectionView = {
  rows: SectionRow[];
  /** notes carrying no section_id, in start order — typically an extracted humming melody */
  unassignedNotes: MidiNoteEvent[];
  /** section ids an asset references that the SongSpec structure does not list */
  orphanSectionIds: string[];
};

export type SectionViewInput = {
  structure: StructureSection[];
  lyrics: LyricSection[];
  chords: ChordSection[];
  notes: MidiNoteEvent[];
};

function byStartBeat(left: MidiNoteEvent, right: MidiNoteEvent): number {
  return left.start_beat - right.start_beat || left.pitch - right.pitch;
}

/**
 * Section order comes from the SongSpec structure, which is the approved shape of
 * the song. When it is empty — a project whose SongSpec predates structure_sections,
 * or one still being drafted — fall back to the order the assets themselves imply
 * so the surface still renders something useful.
 */
function resolveOrder(input: SectionViewInput): StructureSection[] {
  if (input.structure.length > 0) {
    return input.structure;
  }
  const seen = new Map<string, string>();
  for (const section of [...input.lyrics, ...input.chords]) {
    if (!seen.has(section.section_id)) {
      seen.set(section.section_id, section.label);
    }
  }
  return [...seen].map(([section_id, label]) => ({ section_id, label }));
}

export function buildSectionView(input: SectionViewInput): SectionView {
  const lyricsBySection = new Map(input.lyrics.map((section) => [section.section_id, section]));
  const chordsBySection = new Map(input.chords.map((section) => [section.section_id, section]));

  const notesBySection = new Map<string, MidiNoteEvent[]>();
  const unassignedNotes: MidiNoteEvent[] = [];
  for (const note of input.notes) {
    if (note.section_id === null) {
      unassignedNotes.push(note);
      continue;
    }
    const bucket = notesBySection.get(note.section_id);
    if (bucket) {
      bucket.push(note);
    } else {
      notesBySection.set(note.section_id, [note]);
    }
  }

  const order = resolveOrder(input);
  const ordered = new Set(order.map((section) => section.section_id));
  const rows = order.map((section) => {
    const lyrics = lyricsBySection.get(section.section_id);
    const chords = chordsBySection.get(section.section_id);
    const notes = (notesBySection.get(section.section_id) ?? []).slice().sort(byStartBeat);
    return {
      section_id: section.section_id,
      // The structure owns the label, but a section added to an asset before the
      // SongSpec caught up still deserves a name.
      label: section.label || lyrics?.label || chords?.label || section.section_id,
      lyrics: lyrics?.lines ?? [],
      measures: chords?.measures ?? [],
      notes,
      gaps: {
        lyrics: !lyrics || lyrics.lines.length === 0,
        chords: !chords || chords.measures.length === 0,
        melody: notes.length === 0,
      },
    };
  });

  const orphanSectionIds = [
    ...new Set(
      [
        ...input.lyrics.map((section) => section.section_id),
        ...input.chords.map((section) => section.section_id),
        ...notesBySection.keys(),
      ].filter((sectionId) => !ordered.has(sectionId)),
    ),
  ];

  return { rows, unassignedNotes: unassignedNotes.slice().sort(byStartBeat), orphanSectionIds };
}

/**
 * Return a new note list with `noteIds` moved to `sectionId`.
 *
 * Assigning is a frontend operation on purpose: note_events are stored as JSON on
 * the asset row, so a saved section_id round-trips, while the .mid file in object
 * storage stays the plain exportable artifact. Extraction cannot infer the section
 * — only the person who hummed it knows which part they sang.
 */
export function assignNotesToSection(
  notes: MidiNoteEvent[],
  noteIds: ReadonlySet<string> | readonly string[],
  sectionId: string | null,
): MidiNoteEvent[] {
  const target = noteIds instanceof Set ? noteIds : new Set(noteIds);
  if (target.size === 0) {
    return notes;
  }
  return notes.map((note) =>
    target.has(note.note_id) ? { ...note, section_id: sectionId } : note,
  );
}

/**
 * Beats in one measure, read from a "4/4"-style time signature.
 *
 * The chord cells and the melody strip of a section have to agree on this or the
 * two tracks stop lining up, which is the whole point of the aligned surface.
 */
export function beatsPerMeasure(timeSignature: string | null | undefined): number {
  const beats = Number((timeSignature ?? "").split("/")[0]);
  return Number.isFinite(beats) && beats > 0 ? Math.floor(beats) : 4;
}

/** Beat span covering `notes`, or null when there are none. Used to scale a melody strip. */
export function noteBeatSpan(notes: MidiNoteEvent[]): { start: number; end: number } | null {
  if (notes.length === 0) {
    return null;
  }
  let start = Infinity;
  let end = -Infinity;
  for (const note of notes) {
    start = Math.min(start, note.start_beat);
    end = Math.max(end, note.start_beat + note.duration_beats);
  }
  return { start, end };
}

/** Pitch span covering `notes`, padded so a strip never renders a zero-height range. */
export function notePitchSpan(
  notes: MidiNoteEvent[],
  minimumSemitones = 12,
): { low: number; high: number } | null {
  if (notes.length === 0) {
    return null;
  }
  let low = Infinity;
  let high = -Infinity;
  for (const note of notes) {
    low = Math.min(low, note.pitch);
    high = Math.max(high, note.pitch);
  }
  const short = minimumSemitones - (high - low);
  if (short > 0) {
    const half = short / 2;
    low = Math.max(0, low - Math.floor(half));
    high = Math.min(127, high + Math.ceil(half));
  }
  return { low, high };
}

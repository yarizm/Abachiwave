"use client";

import { useLocale } from "@/i18n/locale-provider";
import { MidiNoteEvent } from "@/lib/composition";
import { midiPitchName } from "@/lib/midi-editor";
import { notePitchSpan } from "@/lib/section-view";

/**
 * A glanceable piano-roll strip for one song section.
 *
 * This is deliberately not the `midi-workspace` piano roll. That one is a canvas
 * editor you open to work in; this is a read-mostly thumbnail that sits in a
 * section row next to that section's lyrics and chords, so you can see the shape
 * of the melody without leaving the composition surface.
 *
 * Inline SVG rather than canvas: a dozen of these can be on screen at once, they
 * must stay crisp and re-flow with the layout, and a `viewBox` measured in beats
 * means the beat grid lines up with the chord cells above it for free — no
 * per-instance sizing code, no resize observers, no device-pixel-ratio maths.
 */

const DEFAULT_HEIGHT = 56;
/** Pad a narrow melody to an octave so a one-note section is not a hairline. */
const MINIMUM_PITCH_SEMITONES = 12;
/** Semitones the empty grid spans, so an empty strip still has a plausible height. */
const EMPTY_PITCH_SEMITONES = 12;
/** Shortest rendered note in beats: a very short note still needs a visible sliver. */
const MINIMUM_NOTE_BEATS = 0.125;
/**
 * Corner radii, in viewBox units. `preserveAspectRatio="none"` scales x (beats)
 * and y (semitones) by different factors, so a single `rx` would come out as a
 * stretched ellipse. Each axis therefore gets its own small radius in its own
 * unit, and `rx` is additionally capped at half the note so short notes do not
 * round away into lozenges.
 */
const NOTE_CORNER_BEATS = 0.2;
const NOTE_CORNER_SEMITONES = 0.25;

export type SectionMelodyStripProps = {
  notes: MidiNoteEvent[];
  /** beats in one measure, from the SongSpec time signature */
  beatsPerMeasure: number;
  /** how many measures wide the strip is, so it lines up with the chord cells */
  measureCount: number;
  /** beat offset the section starts at; notes are positioned relative to it */
  startBeat: number;
  height?: number;
  selectedNoteIds?: ReadonlySet<string>;
  onSelectNote?: (noteId: string, additive: boolean) => void;
  /** playhead position in section-local beats; null when not playing */
  playheadBeat?: number | null;
  emptyLabel: string;
};

export function SectionMelodyStrip({
  notes,
  beatsPerMeasure,
  measureCount,
  startBeat,
  height = DEFAULT_HEIGHT,
  selectedNoteIds,
  onSelectNote,
  playheadBeat,
  emptyLabel,
}: SectionMelodyStripProps) {
  const { t } = useLocale();

  // The grid range is padded; the range announced to screen readers is not, so a
  // single C4 reports "1 note, C4-C4" rather than the octave the padding invented.
  const gridSpan = notePitchSpan(notes, MINIMUM_PITCH_SEMITONES);
  const pitchRange = notePitchSpan(notes, 0);

  // A malformed time signature or an unmeasured section must not collapse the
  // viewBox to zero, which would render nothing at all.
  const barBeats = beatsPerMeasure > 0 ? beatsPerMeasure : 4;
  const bars = Math.max(1, Math.ceil(measureCount));
  const totalBeats = bars * barBeats;
  const pitchHeight = gridSpan ? gridSpan.high - gridSpan.low + 1 : EMPTY_PITCH_SEMITONES;

  const interactive = onSelectNote !== undefined;
  const label =
    pitchRange && gridSpan
      ? `${notes.length} ${t("notes")}, ${midiPitchName(pitchRange.low)}-${midiPitchName(pitchRange.high)}`
      : emptyLabel;
  // Narrowed once here so the render below can check `!== null` instead of
  // re-deriving finiteness inline; the caller still owns clamping/rounding.
  const playheadX =
    typeof playheadBeat === "number" && Number.isFinite(playheadBeat) && playheadBeat >= 0
      ? playheadBeat
      : null;

  return (
    <div className={gridSpan ? "section-melody-strip" : "section-melody-strip is-empty"}>
      <svg
        aria-label={label}
        className="section-melody-svg"
        height={height}
        preserveAspectRatio="none"
        role="img"
        viewBox={`0 0 ${totalBeats} ${pitchHeight}`}
        width="100%"
      >
        {Array.from({ length: bars - 1 }, (_, index) => {
          const x = (index + 1) * barBeats;
          return (
            <line
              className="section-melody-gridline"
              key={x}
              // The viewBox is stretched on both axes, so a plain stroke width would
              // be stretched with it. Keep gridlines a constant device width.
              vectorEffect="non-scaling-stroke"
              x1={x}
              x2={x}
              y1={0}
              y2={pitchHeight}
            />
          );
        })}
        {gridSpan
          ? notes.map((note) => {
              const width = Math.max(MINIMUM_NOTE_BEATS, note.duration_beats);
              const selected = selectedNoteIds?.has(note.note_id) ?? false;
              return (
                <rect
                  className={noteClassName(selected, interactive)}
                  height={1}
                  key={note.note_id}
                  onClick={
                    onSelectNote
                      ? (event) =>
                          onSelectNote(
                            note.note_id,
                            event.shiftKey || event.metaKey || event.ctrlKey,
                          )
                      : undefined
                  }
                  rx={Math.min(NOTE_CORNER_BEATS, width / 2)}
                  ry={NOTE_CORNER_SEMITONES}
                  width={width}
                  x={note.start_beat - startBeat}
                  // SVG y grows downward, so subtract from the top of the range to
                  // put the highest pitch at the top of the strip.
                  y={gridSpan.high - note.pitch}
                />
              );
            })
          : null}
        {playheadX !== null ? (
          <line
            className="section-melody-playhead"
            // Same reason as the gridlines above: the viewBox is stretched on
            // both axes, so this keeps the playhead a constant device width
            // instead of scaling with it.
            vectorEffect="non-scaling-stroke"
            x1={playheadX}
            x2={playheadX}
            y1={0}
            y2={pitchHeight}
          />
        ) : null}
      </svg>
      {gridSpan ? null : (
        // The svg above already carries this text as its aria-label; announcing the
        // paragraph too would read the empty state twice.
        <p aria-hidden="true" className="section-melody-empty">
          {emptyLabel}
        </p>
      )}
    </div>
  );
}

function noteClassName(selected: boolean, interactive: boolean): string {
  let className = "section-melody-note";
  if (selected) {
    className += " is-selected";
  }
  if (interactive) {
    className += " is-interactive";
  }
  return className;
}

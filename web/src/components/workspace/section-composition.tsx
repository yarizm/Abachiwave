"use client";

import { CircleStop, Gauge, Play, Redo2, RotateCcw, Save, Sparkles, Undo2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { SectionChordCell } from "@/components/workspace/section-chord-cell";
import { SectionMelodyStrip } from "@/components/workspace/section-melody-strip";
import { useChordDraft } from "@/app/projects/[projectId]/hooks/use-chord-draft";
import { useLyricsDraft } from "@/app/projects/[projectId]/hooks/use-lyrics-draft";
import { useSectionPlayback } from "@/app/projects/[projectId]/hooks/use-section-playback";
import { useLocale } from "@/i18n/locale-provider";
import {
  ChordDisplayMode,
  addChordEvent,
  addChordMeasure,
  removeChordEvent,
  removeChordMeasure,
  updateChordEvent,
} from "@/lib/chord-editor";
import {
  ChordProgressionVersion,
  ChordSection,
  HookCandidate,
  LyricSection,
  LyricsVersion,
  MidiAssetVersion,
  MidiNoteEvent,
} from "@/lib/composition";
import type { SectionPlaybackInput } from "@/lib/section-playback";
import { StructureSection } from "@/lib/song-specs";
import {
  SectionRow,
  assignNotesToSection,
  beatsPerMeasure as resolveBeatsPerMeasure,
  buildSectionView,
  noteBeatSpan,
} from "@/lib/section-view";

/**
 * The song, one row per section: its words, its chords and its melody side by side.
 *
 * Lyrics, chords and arrangement sections all carry a `section_id` that is stable
 * across versions, but the workspace never joined on it — the three editors were
 * separate panels stacked down a very long page, so the one thing writing a song
 * actually requires, reading a section's words against its chords against its
 * melody, was the one thing the UI could not do.
 *
 * Editing here is deliberately the light kind: lyric text, chord symbols and chord
 * placement, plus assigning extracted notes to a section. The heavier tools — the
 * rewrite studio, transpose, quantize, note-level piano-roll editing — stay in the
 * full editors, which this view sits alongside rather than replaces.
 */

type SectionCompositionProps = {
  activeChords: ChordProgressionVersion | null;
  activeLyrics: LyricsVersion | null;
  canGenerate: boolean;
  disabledReason?: string | null;
  isGeneratingChords: boolean;
  isGeneratingLyrics: boolean;
  isSavingChords: boolean;
  isSavingLyrics: boolean;
  isSavingMelody: boolean;
  melodyAsset: MidiAssetVersion | null;
  onChordsSave: (sections: ChordSection[]) => Promise<void>;
  onGenerateChords: () => void;
  onGenerateLyrics: () => void;
  onGenerateMidi: () => void;
  onLyricsSave: (sections: LyricSection[], hookCandidates: HookCandidate[]) => Promise<void>;
  onMelodySave: (asset: MidiAssetVersion, noteEvents: MidiNoteEvent[]) => Promise<void>;
  projectId: string;
  structure: StructureSection[];
  timeSignature: string | null;
};

export function SectionComposition({
  activeChords,
  activeLyrics,
  canGenerate,
  disabledReason,
  isGeneratingChords,
  isGeneratingLyrics,
  isSavingChords,
  isSavingLyrics,
  isSavingMelody,
  melodyAsset,
  onChordsSave,
  onGenerateChords,
  onGenerateLyrics,
  onGenerateMidi,
  onLyricsSave,
  onMelodySave,
  projectId,
  structure,
  timeSignature,
}: SectionCompositionProps) {
  const { t } = useLocale();
  const lyricsEditor = useLyricsDraft(projectId, activeLyrics);
  const chordEditor = useChordDraft(projectId, activeChords);
  const [notation, setNotation] = useState<ChordDisplayMode>("symbol");
  const [selectedNoteIds, setSelectedNoteIds] = useState<ReadonlySet<string>>(() => new Set());
  const [loop, setLoop] = useState(false);
  const [metronome, setMetronome] = useState(false);
  const playback = useSectionPlayback({
    loop,
    metronome,
    failureMessage: t("Audio could not start"),
  });

  // The melody is read from the asset rather than a draft hook: the only edit this
  // surface makes to it is section assignment, and that saves immediately.
  const notes = useMemo(() => melodyAsset?.note_events ?? [], [melodyAsset]);
  useEffect(() => {
    setSelectedNoteIds(new Set());
  }, [melodyAsset?.id]);

  const meter = timeSignature ?? activeChords?.time_signature ?? "4/4";
  const beats = resolveBeatsPerMeasure(meter);
  // The chord version owns the tempo the progression was written against; the melody
  // asset is the fallback because a hummed section can exist before any chords do.
  const tempoBpm = activeChords?.tempo_bpm ?? melodyAsset?.tempo_map[0]?.bpm ?? 120;
  const view = useMemo(
    () =>
      buildSectionView({
        structure,
        lyrics: lyricsEditor.draft.sections,
        chords: chordEditor.draft.sections,
        notes,
      }),
    [chordEditor.draft.sections, lyricsEditor.draft.sections, notes, structure],
  );

  function updateLyricLine(sectionId: string, lineId: string, text: string) {
    lyricsEditor.update({
      ...lyricsEditor.draft,
      sections: lyricsEditor.draft.sections.map((section) =>
        section.section_id === sectionId
          ? {
              ...section,
              lines: section.lines.map((line) =>
                line.line_id === lineId ? { ...line, text } : line,
              ),
            }
          : section,
      ),
    });
  }

  function toggleNote(noteId: string, additive: boolean) {
    setSelectedNoteIds((current) => {
      const next = new Set(additive ? current : []);
      if (current.has(noteId) && (additive || current.size === 1)) {
        next.delete(noteId);
      } else {
        next.add(noteId);
      }
      return next;
    });
  }

  async function assignSelectedNotes(sectionId: string) {
    if (!melodyAsset || selectedNoteIds.size === 0) {
      return;
    }
    await onMelodySave(melodyAsset, assignNotesToSection(notes, selectedNoteIds, sectionId));
    setSelectedNoteIds(new Set());
  }

  const dirty = lyricsEditor.dirty || chordEditor.dirty;
  const busy = isSavingLyrics || isSavingChords || isSavingMelody;

  return (
    <section className="panel section-composition" aria-labelledby="section-composition-title">
      <div className="section-heading">
        <div>
          <h2 id="section-composition-title">{t("Section view")}</h2>
          <p className="meta">{t("Lyrics, chords and melody for each section of the song.")}</p>
        </div>
        <div className="section-composition-tools">
          <div className="segmented-control" aria-label={t("Chord display mode")}>
            {(["symbol", "roman", "nashville"] as const).map((mode) => (
              <button
                aria-pressed={notation === mode}
                className={notation === mode ? "active" : ""}
                key={mode}
                onClick={() => setNotation(mode)}
                type="button"
              >
                {t(mode === "symbol" ? "Symbols" : mode === "roman" ? "Roman" : "Nashville")}
              </button>
            ))}
          </div>
          <button
            aria-label={t("Undo")}
            className="button secondary icon-only"
            disabled={!lyricsEditor.canUndo && !chordEditor.canUndo}
            onClick={() => {
              lyricsEditor.undo();
              chordEditor.undo();
            }}
            type="button"
          >
            <Undo2 aria-hidden="true" size={16} />
          </button>
          <button
            aria-label={t("Redo")}
            className="button secondary icon-only"
            disabled={!lyricsEditor.canRedo && !chordEditor.canRedo}
            onClick={() => {
              lyricsEditor.redo();
              chordEditor.redo();
            }}
            type="button"
          >
            <Redo2 aria-hidden="true" size={16} />
          </button>
          <label className="check-control">
            <input
              checked={metronome}
              onChange={(event) => setMetronome(event.target.checked)}
              type="checkbox"
            />
            <Gauge aria-hidden="true" size={16} />
            {t("Metronome")}
          </label>
          <label className="check-control">
            <input
              checked={loop}
              onChange={(event) => setLoop(event.target.checked)}
              type="checkbox"
            />
            <RotateCcw aria-hidden="true" size={16} />
            {t("Loop")}
          </label>
          {dirty ? <span className="badge">{t("Unsaved")}</span> : null}
        </div>
      </div>

      {playback.error ? (
        <p className="notice warning" role="status">
          {playback.error}
        </p>
      ) : null}

      {view.rows.length === 0 ? (
        <p className="empty">{disabledReason ?? t("Approve a SongSpec to lay out sections")}</p>
      ) : (
        <ol className="section-track-list">
          {view.rows.map((row) => (
            <SectionTrack
              beatsPerMeasure={beats}
              busy={busy}
              key={row.section_id}
              notation={notation}
              onChordEventAdd={(measureNumber) =>
                chordEditor.update(
                  addChordEvent(chordEditor.draft, row.section_id, measureNumber, beats),
                )
              }
              onChordEventChange={(eventId, patch) =>
                chordEditor.update(updateChordEvent(chordEditor.draft, row.section_id, eventId, patch))
              }
              onChordEventRemove={(eventId) =>
                chordEditor.update(removeChordEvent(chordEditor.draft, row.section_id, eventId))
              }
              onChordMeasureAdd={() =>
                chordEditor.update(addChordMeasure(chordEditor.draft, row.section_id, beats))
              }
              onChordMeasureRemove={(measureNumber) =>
                chordEditor.update(
                  removeChordMeasure(chordEditor.draft, row.section_id, measureNumber),
                )
              }
              onLyricChange={(lineId, text) => updateLyricLine(row.section_id, lineId, text)}
              onPlayToggle={(input) => playback.toggle(row.section_id, input)}
              playheadBeat={playback.playingSectionId === row.section_id ? playback.playheadBeat : null}
              playing={playback.playingSectionId === row.section_id}
              row={row}
              soundingChordId={
                playback.playingSectionId === row.section_id ? playback.soundingChordId : null
              }
              tempoBpm={tempoBpm}
              timeSignature={meter}
            />
          ))}
        </ol>
      )}

      {view.unassignedNotes.length > 0 && melodyAsset ? (
        <div className="section-unassigned" role="group" aria-label={t("Unassigned melody")}>
          <div className="section-heading">
            <h3>{t("Unassigned melody")}</h3>
            <span className="badge audio-status-processing">{view.unassignedNotes.length}</span>
          </div>
          <p className="meta">
            {t(
              "{count} notes carry no section. Audio extraction reads a MIDI file, which has no song structure — assign them to hear them in place.",
              { count: view.unassignedNotes.length },
            )}
          </p>
          <SectionMelodyStrip
            beatsPerMeasure={beats}
            emptyLabel={t("No melody in this section")}
            measureCount={Math.max(
              1,
              Math.ceil(
                view.unassignedNotes.reduce(
                  (widest, note) => Math.max(widest, note.start_beat + note.duration_beats),
                  0,
                ) / beats,
              ),
            )}
            notes={view.unassignedNotes}
            onSelectNote={toggleNote}
            selectedNoteIds={selectedNoteIds}
            startBeat={0}
          />
          <div className="button-row">
            {view.rows.map((row) => (
              <button
                className="button secondary compact-button"
                disabled={busy || selectedNoteIds.size === 0}
                key={row.section_id}
                onClick={() => void assignSelectedNotes(row.section_id)}
                type="button"
              >
                {t("Assign to {section}", { section: row.label })}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {view.orphanSectionIds.length > 0 ? (
        <p className="notice warning" role="status">
          {t("Sections used by an asset but missing from the SongSpec structure: {ids}", {
            ids: view.orphanSectionIds.join(", "),
          })}
        </p>
      ) : null}

      {/* Generating has to live here too. This view is where the composition route
          opens, so an empty song must be able to move forward without first knowing
          that the other view exists. */}
      <div className="button-row">
        <button
          className="button secondary"
          data-guarded={canGenerate ? undefined : ""}
          disabled={!canGenerate || busy || isGeneratingLyrics}
          onClick={onGenerateLyrics}
          title={disabledReason ?? undefined}
          type="button"
        >
          <Sparkles aria-hidden="true" size={16} />
          {t("Generate lyrics")}
        </button>
        <button
          className="button secondary"
          data-guarded={canGenerate ? undefined : ""}
          disabled={!canGenerate || busy || isGeneratingChords}
          onClick={onGenerateChords}
          title={disabledReason ?? undefined}
          type="button"
        >
          <Sparkles aria-hidden="true" size={16} />
          {t("Generate chords")}
        </button>
        <button
          className="button secondary"
          data-guarded={canGenerate ? undefined : ""}
          disabled={!canGenerate || busy}
          onClick={onGenerateMidi}
          title={disabledReason ?? undefined}
          type="button"
        >
          <Sparkles aria-hidden="true" size={16} />
          {t("Generate MIDI")}
        </button>
      </div>

      <div className="button-row">
        <button
          className="button"
          disabled={!lyricsEditor.dirty || busy}
          onClick={() =>
            void onLyricsSave(lyricsEditor.draft.sections, lyricsEditor.draft.hookCandidates)
          }
          type="button"
        >
          <Save aria-hidden="true" size={16} />
          {t("Save lyrics version")}
        </button>
        <button
          className="button"
          disabled={!chordEditor.dirty || busy}
          onClick={() => void onChordsSave(chordEditor.draft.sections)}
          type="button"
        >
          <Save aria-hidden="true" size={16} />
          {t("Save chords version")}
        </button>
      </div>
    </section>
  );
}

type SectionTrackProps = {
  beatsPerMeasure: number;
  busy: boolean;
  notation: ChordDisplayMode;
  onChordEventAdd: (measureNumber: number) => void;
  onChordEventChange: (
    eventId: string,
    patch: { symbol?: string; beat?: number; duration_beats?: number; inversion?: number | null },
  ) => void;
  onChordEventRemove: (eventId: string) => void;
  onChordMeasureAdd: () => void;
  onChordMeasureRemove: (measureNumber: number) => void;
  onLyricChange: (lineId: string, text: string) => void;
  onPlayToggle: (input: SectionPlaybackInput) => void;
  playheadBeat: number | null;
  playing: boolean;
  row: SectionRow;
  soundingChordId: string | null;
  tempoBpm: number;
  timeSignature: string;
};

function SectionTrack({
  beatsPerMeasure,
  busy,
  notation,
  onChordEventAdd,
  onChordEventChange,
  onChordEventRemove,
  onChordMeasureAdd,
  onChordMeasureRemove,
  onLyricChange,
  onPlayToggle,
  playheadBeat,
  playing,
  row,
  soundingChordId,
  tempoBpm,
  timeSignature,
}: SectionTrackProps) {
  const { t } = useLocale();
  const headingId = `section-track-${row.section_id}`;
  // One value, used for both the strip's x-origin and playback's beat origin. They
  // have to agree or the playhead drifts away from the note it is meant to be on.
  const noteStartBeat = row.notes[0]?.start_beat ?? 0;
  // The chord grid sets the strip's width whenever there are chords, because the
  // shared bar grid is the whole point of this row: widening the strip past the
  // chord track would put bar 3 of the melody under bar 4 of the chords. A melody
  // running past the last chord bar is therefore still clipped — the fix for that
  // is adding the missing measures, not silently desynchronising the two tracks.
  // With no chords at all there is no grid to hold to, so the melody sets it.
  const melodySpan = noteBeatSpan(row.notes);
  const melodyMeasures = melodySpan
    ? Math.ceil((melodySpan.end - noteStartBeat) / beatsPerMeasure)
    : 0;
  const measureCount = Math.max(1, row.measures.length || melodyMeasures);
  const canPlay = row.measures.length > 0 || row.notes.length > 0;
  const gaps = [
    row.gaps.lyrics ? t("Needs lyrics") : null,
    row.gaps.chords ? t("Needs chords") : null,
    row.gaps.melody ? t("Needs melody") : null,
  ].filter((label): label is string => label !== null);

  return (
    <li
      className={playing ? "section-track is-playing" : "section-track"}
      aria-labelledby={headingId}
    >
      <div className="section-track-head">
        <h3 id={headingId}>{row.label}</h3>
        {gaps.length > 0 ? (
          <div className="badge-row">
            {gaps.map((label) => (
              <span className="badge audio-status-processing" key={label}>
                {label}
              </span>
            ))}
          </div>
        ) : null}
        <button
          aria-label={
            playing
              ? t("Stop {section}", { section: row.label })
              : t("Audition {section}", { section: row.label })
          }
          aria-pressed={playing}
          className={
            playing
              ? "button secondary compact-button section-play is-playing"
              : "button secondary compact-button section-play"
          }
          disabled={!canPlay}
          onClick={() =>
            onPlayToggle({
              measures: row.measures,
              notes: row.notes,
              noteStartBeat,
              beatsPerMeasure,
              tempoBpm,
              timeSignature,
            })
          }
          title={canPlay ? undefined : t("Nothing to play in this section")}
          type="button"
        >
          {playing ? (
            <CircleStop aria-hidden="true" size={16} />
          ) : (
            <Play aria-hidden="true" size={16} />
          )}
          {playing ? t("Stop") : t("Audition")}
        </button>
      </div>

      <div className="section-track-body">
        <div className="section-lyrics">
          {row.lyrics.length === 0 ? (
            <p className="empty">{t("No lyrics in this section")}</p>
          ) : (
            <ol className="section-lyric-lines">
              {row.lyrics.map((line, index) => (
                <li className="section-lyric-line" key={line.line_id}>
                  <input
                    aria-label={t("{section} line {number}", {
                      section: row.label,
                      number: index + 1,
                    })}
                    className="section-lyric-text"
                    disabled={busy}
                    onChange={(event) => onLyricChange(line.line_id, event.target.value)}
                    value={line.text}
                  />
                  <span aria-hidden="true" className="section-lyric-meta">
                    {line.syllable_count}
                    {line.rhyme_key ? ` · ${line.rhyme_key}` : ""}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>

        <div className="section-timeline">
          {row.measures.length === 0 ? (
            <p className="empty">{t("No chords in this section")}</p>
          ) : (
            <div className="section-chord-track">
              {row.measures.map((measure) => (
                <SectionChordCell
                  beatsPerMeasure={beatsPerMeasure}
                  disabled={busy}
                  key={measure.measure_number}
                  measure={measure}
                  notation={notation}
                  onEventAdd={() => onChordEventAdd(measure.measure_number)}
                  onEventChange={onChordEventChange}
                  onEventRemove={onChordEventRemove}
                  onMeasureRemove={() => onChordMeasureRemove(measure.measure_number)}
                  soundingEventId={soundingChordId}
                />
              ))}
            </div>
          )}
          <SectionMelodyStrip
            beatsPerMeasure={beatsPerMeasure}
            emptyLabel={t("No melody in this section")}
            measureCount={measureCount}
            notes={row.notes}
            playheadBeat={playheadBeat}
            startBeat={noteStartBeat}
          />
          <button
            className="button secondary compact-button section-measure-add"
            disabled={busy}
            onClick={onChordMeasureAdd}
            type="button"
          >
            {t("Add measure")}
          </button>
        </div>
      </div>
    </li>
  );
}

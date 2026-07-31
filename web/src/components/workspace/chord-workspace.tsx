"use client";

import {
  CircleStop,
  FilePlus2,
  Gauge,
  ListMusic,
  Plus,
  Redo2,
  RotateCcw,
  Save,
  SlidersHorizontal,
  Trash2,
  Undo2,
  Volume2,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { useChordDraft } from "@/app/projects/[projectId]/hooks/use-chord-draft";
import { useLocale } from "@/i18n/locale-provider";
import {
  ChordDisplayMode,
  addChordEvent,
  addChordMeasure,
  chordAnalysisByEventId,
  chordDisplayLabel,
  chordDraftsEqual,
  removeChordEvent,
  removeChordMeasure,
  updateChordEvent,
} from "@/lib/chord-editor";
import type { ChordPlaybackHandle } from "@/lib/chord-playback";
import type {
  ChordPreview,
  ChordProgressionVersion,
  ChordSection,
} from "@/lib/composition";
import { validateChordSections } from "@/lib/composition";

type ChordWorkspaceProps = {
  activeChords: ChordProgressionVersion | null;
  canGenerate: boolean;
  isGenerating: boolean;
  isPreviewing: boolean;
  isSaving: boolean;
  isTransposing: boolean;
  onGenerate: () => void;
  onPreview: (sections: ChordSection[]) => Promise<ChordPreview>;
  onSave: (sections: ChordSection[]) => Promise<void>;
  onTranspose: (semitones: number, sectionIds: string[] | null) => Promise<void>;
  projectId: string;
};

const displayModes: ChordDisplayMode[] = ["symbol", "roman", "nashville"];
const transposeIntervals = [-11, -9, -7, -5, -4, -3, -2, -1, 1, 2, 3, 4, 5, 7, 9, 11];

export function ChordWorkspace({
  activeChords,
  canGenerate,
  isGenerating,
  isPreviewing,
  isSaving,
  isTransposing,
  onGenerate,
  onPreview,
  onSave,
  onTranspose,
  projectId,
}: ChordWorkspaceProps) {
  const { t, text } = useLocale();
  const editor = useChordDraft(projectId, activeChords);
  const [displayMode, setDisplayMode] = useState<ChordDisplayMode>("symbol");
  const [preview, setPreview] = useState<ChordPreview | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [transposeSemitones, setTransposeSemitones] = useState(2);
  const [transposeSectionId, setTransposeSectionId] = useState("all");
  const [metronome, setMetronome] = useState(false);
  const [loop, setLoop] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playingEventId, setPlayingEventId] = useState<string | null>(null);
  const playerRef = useRef<ChordPlaybackHandle | null>(null);

  useEffect(() => {
    setPreview(null);
    setLocalError(null);
    setTransposeSectionId("all");
    stopPlayback();
    // The active version ID is the editor baseline boundary.
  }, [activeChords?.id]);

  useEffect(
    () => () => {
      playerRef.current?.stop();
      playerRef.current = null;
    },
    [],
  );

  const beatsPerMeasure = Number(activeChords?.time_signature.split("/")[0]) || 4;
  const analysisById = useMemo(
    () => chordAnalysisByEventId(preview?.sections ?? editor.draft.sections),
    [editor.draft.sections, preview?.sections],
  );

  function updateDraft(next: typeof editor.draft) {
    editor.update(next);
    setPreview(null);
    setLocalError(null);
    stopPlayback();
  }

  function stopPlayback() {
    playerRef.current?.stop();
    playerRef.current = null;
    setIsPlaying(false);
    setPlayingEventId(null);
  }

  function validateDraft(): string | null {
    return validateChordSections(
      editor.draft.sections,
      activeChords?.time_signature ?? "4/4",
    );
  }

  async function requestPreview(): Promise<ChordPreview | null> {
    const validationError = validateDraft();
    if (validationError) {
      setLocalError(text(validationError));
      return null;
    }
    try {
      const result = await onPreview(editor.draft.sections);
      setPreview(result);
      setLocalError(null);
      return result;
    } catch {
      return null;
    }
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateDraft();
    if (validationError) {
      setLocalError(text(validationError));
      return;
    }
    setLocalError(null);
    await onSave(editor.draft.sections);
  }

  async function handlePlayback() {
    if (isPlaying) {
      stopPlayback();
      return;
    }
    const result = preview ?? (await requestPreview());
    if (!result) return;
    try {
      const { startChordPlayback } = await import("@/lib/chord-playback");
      setIsPlaying(true);
      playerRef.current = await startChordPlayback({
        sections: result.sections,
        tempoBpm: result.tempo_bpm,
        timeSignature: result.time_signature,
        loop,
        metronome,
        onEvent: setPlayingEventId,
        onEnded: () => {
          playerRef.current?.stop();
          playerRef.current = null;
          setIsPlaying(false);
        },
      });
    } catch {
      stopPlayback();
      setLocalError(t("Browser audio could not start. Check audio permissions and try again."));
    }
  }

  async function handleTranspose() {
    if (editor.dirty) {
      setLocalError(t("Save or discard the local draft before transposing."));
      return;
    }
    setLocalError(null);
    await onTranspose(
      transposeSemitones,
      transposeSectionId === "all" ? null : [transposeSectionId],
    );
  }

  function handleAddEvent(sectionId: string, measureNumber: number) {
    const next = addChordEvent(
      editor.draft,
      sectionId,
      measureNumber,
      beatsPerMeasure,
    );
    if (chordDraftsEqual(next, editor.draft)) {
      setLocalError(t("This measure has no free beat for another chord."));
      return;
    }
    updateDraft(next);
  }

  return (
    <section className="panel chord-workspace" aria-labelledby="chords-title">
      <div className="section-heading chord-heading">
        <div>
          <div className="section-heading-inline">
            <h2 id="chords-title">{t("Chord editor")}</h2>
            {activeChords ? <span className="badge">v{activeChords.version_number}</span> : null}
            {editor.dirty ? <span className="status-chip warning">{t("Unsaved")}</span> : null}
          </div>
          <p className="meta">
            {t("Place validated chords by measure and beat, then audition the progression.")}
          </p>
        </div>
        <div className="chord-heading-actions">
          <button
            className="button secondary icon-only"
            disabled={!editor.canUndo || isSaving}
            onClick={() => {
              editor.undo();
              setPreview(null);
              stopPlayback();
            }}
            title={t("Undo")}
            type="button"
          >
            <Undo2 aria-hidden="true" size={17} />
            <span className="sr-only">{t("Undo")}</span>
          </button>
          <button
            className="button secondary icon-only"
            disabled={!editor.canRedo || isSaving}
            onClick={() => {
              editor.redo();
              setPreview(null);
              stopPlayback();
            }}
            title={t("Redo")}
            type="button"
          >
            <Redo2 aria-hidden="true" size={17} />
            <span className="sr-only">{t("Redo")}</span>
          </button>
          <button
            className="button secondary"
            disabled={!canGenerate || isGenerating || isSaving}
            onClick={onGenerate}
            type="button"
          >
            <FilePlus2 aria-hidden="true" size={17} />
            {t("Generate chords")}
          </button>
        </div>
      </div>

      {editor.restored ? <p className="notice compact-notice">{t("Local draft restored")}</p> : null}

      {activeChords ? (
        <form className="chord-editor-form" onSubmit={handleSave}>
          <div className="chord-control-strip">
            <div className="chord-facts" aria-label={t("Chord project settings")}>
              <span><strong>{t("Key")}</strong>{activeChords.key}</span>
              <span><strong>{t("Tempo")}</strong>{activeChords.tempo_bpm} BPM</span>
              <span><strong>{t("Meter")}</strong>{activeChords.time_signature}</span>
            </div>
            <div className="segmented-control" aria-label={t("Chord display mode")}>
              {displayModes.map((mode) => (
                <button
                  aria-pressed={displayMode === mode}
                  className={displayMode === mode ? "active" : ""}
                  key={mode}
                  onClick={() => setDisplayMode(mode)}
                  type="button"
                >
                  {t(mode === "symbol" ? "Symbols" : mode === "roman" ? "Roman" : "Nashville")}
                </button>
              ))}
            </div>
          </div>

          <div className="chord-transport" aria-label={t("Chord audition controls")}>
            <button
              className="button secondary"
              disabled={isPreviewing || isSaving}
              onClick={requestPreview}
              type="button"
            >
              <SlidersHorizontal aria-hidden="true" size={17} />
              {preview ? t("Validated") : t("Validate")}
            </button>
            <button
              className="button"
              disabled={isPreviewing || isSaving}
              onClick={handlePlayback}
              type="button"
            >
              {isPlaying ? <CircleStop aria-hidden="true" size={17} /> : <Volume2 aria-hidden="true" size={17} />}
              {isPlaying ? t("Stop") : t("Audition")}
            </button>
            <label className="check-control">
              <input checked={metronome} onChange={(event) => setMetronome(event.target.checked)} type="checkbox" />
              <Gauge aria-hidden="true" size={16} />
              {t("Metronome")}
            </label>
            <label className="check-control">
              <input checked={loop} onChange={(event) => setLoop(event.target.checked)} type="checkbox" />
              <RotateCcw aria-hidden="true" size={16} />
              {t("Loop")}
            </label>
          </div>

          <div className="chord-sections">
            {editor.draft.sections.map((section) => (
              <section className="chord-section-editor" key={section.section_id}>
                <div className="chord-section-heading">
                  <div>
                    <h3>{text(section.label)}</h3>
                    <span className="meta">{t("{count} measures", { count: section.measures.length })}</span>
                  </div>
                  <button
                    className="button ghost compact-button"
                    disabled={section.measures.length >= 64}
                    onClick={() => updateDraft(addChordMeasure(editor.draft, section.section_id, beatsPerMeasure))}
                    type="button"
                  >
                    <Plus aria-hidden="true" size={15} />
                    {t("Add measure")}
                  </button>
                </div>
                <div className="chord-measure-scroll">
                  <div className="chord-measure-grid">
                    {section.measures.map((measure) => (
                      <div className="chord-measure" key={measure.measure_number}>
                        <div className="chord-measure-heading">
                          <span>{t("Measure {number}", { number: measure.measure_number })}</span>
                          <button
                            className="icon-button"
                            disabled={section.measures.length <= 1}
                            onClick={() => updateDraft(removeChordMeasure(editor.draft, section.section_id, measure.measure_number))}
                            title={t("Delete measure")}
                            type="button"
                          >
                            <Trash2 aria-hidden="true" size={14} />
                            <span className="sr-only">{t("Delete measure")}</span>
                          </button>
                        </div>
                        <div className="chord-event-list">
                          {measure.events.map((event) => {
                            const analysis = analysisById.get(event.event_id) ?? event;
                            return (
                              <div
                                className={`chord-event${playingEventId === event.event_id ? " playing" : ""}`}
                                key={event.event_id}
                              >
                                <div className="chord-symbol-row">
                                  <input
                                    aria-label={t("Chord symbol in measure {number}", { number: measure.measure_number })}
                                    className="chord-symbol-input"
                                    onChange={(inputEvent) => updateDraft(updateChordEvent(editor.draft, section.section_id, event.event_id, { symbol: inputEvent.target.value }))}
                                    value={event.symbol}
                                  />
                                  <button
                                    className="icon-button"
                                    disabled={measure.events.length <= 1}
                                    onClick={() => updateDraft(removeChordEvent(editor.draft, section.section_id, event.event_id))}
                                    title={t("Delete chord")}
                                    type="button"
                                  >
                                    <Trash2 aria-hidden="true" size={14} />
                                    <span className="sr-only">{t("Delete chord")}</span>
                                  </button>
                                </div>
                                <div className="chord-event-analysis">
                                  <strong>{chordDisplayLabel(analysis, displayMode)}</strong>
                                  {analysis.borrowed ? <span className="status-chip warning">{t("Borrowed")}</span> : null}
                                </div>
                                <div className="chord-event-fields">
                                  <label>
                                    <span>{t("Beat")}</span>
                                    <input
                                      max={beatsPerMeasure}
                                      min={1}
                                      onChange={(inputEvent) => updateDraft(updateChordEvent(editor.draft, section.section_id, event.event_id, { beat: Number(inputEvent.target.value) }))}
                                      step={0.5}
                                      type="number"
                                      value={event.beat}
                                    />
                                  </label>
                                  <label>
                                    <span>{t("Length")}</span>
                                    <input
                                      max={beatsPerMeasure}
                                      min={0.5}
                                      onChange={(inputEvent) => updateDraft(updateChordEvent(editor.draft, section.section_id, event.event_id, { duration_beats: Number(inputEvent.target.value) }))}
                                      step={0.5}
                                      type="number"
                                      value={event.duration_beats}
                                    />
                                  </label>
                                  <label>
                                    <span>{t("Inversion")}</span>
                                    <select
                                      onChange={(inputEvent) => updateDraft(updateChordEvent(editor.draft, section.section_id, event.event_id, { inversion: Number(inputEvent.target.value) }))}
                                      value={event.inversion ?? 0}
                                    >
                                      <option value={0}>{t("Root")}</option>
                                      <option value={1}>1</option>
                                      <option value={2}>2</option>
                                      <option value={3}>3</option>
                                    </select>
                                  </label>
                                </div>
                                <p className="chord-theory-meta">
                                  {analysis.root
                                    ? `${analysis.roman_numeral ?? "-"} · ${analysis.nashville_number ?? "-"} · ${analysis.quality ?? "-"}`
                                    : t("Validate to refresh theory labels and playback notes.")}
                                </p>
                              </div>
                            );
                          })}
                        </div>
                        <button
                          className="button ghost compact-button full-width"
                          onClick={() => handleAddEvent(section.section_id, measure.measure_number)}
                          type="button"
                        >
                          <Plus aria-hidden="true" size={14} />
                          {t("Add chord")}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </section>
            ))}
          </div>

          <div className="chord-transpose-bar">
            <div className="section-heading-inline">
              <ListMusic aria-hidden="true" size={17} />
              <strong>{t("Transpose")}</strong>
            </div>
            <label>
              <span>{t("Interval")}</span>
              <select value={transposeSemitones} onChange={(event) => setTransposeSemitones(Number(event.target.value))}>
                {transposeIntervals.map((interval) => (
                  <option key={interval} value={interval}>{interval > 0 ? `+${interval}` : interval} {t("semitones")}</option>
                ))}
              </select>
            </label>
            <label>
              <span>{t("Scope")}</span>
              <select value={transposeSectionId} onChange={(event) => setTransposeSectionId(event.target.value)}>
                <option value="all">{t("Entire song")}</option>
                {editor.draft.sections.map((section) => (
                  <option key={section.section_id} value={section.section_id}>{text(section.label)}</option>
                ))}
              </select>
            </label>
            <button className="button secondary" disabled={editor.dirty || isTransposing || isSaving} onClick={handleTranspose} type="button">
              <ListMusic aria-hidden="true" size={17} />
              {t("Create transposed version")}
            </button>
          </div>

          {localError ? <p className="error compact-error">{localError}</p> : null}

          <div className="chord-save-bar">
            <button className="button" disabled={!editor.dirty || isSaving} type="submit">
              <Save aria-hidden="true" size={17} />
              {t("Save chords version")}
            </button>
            <button
              className="button secondary"
              disabled={!editor.dirty || isSaving}
              onClick={() => {
                editor.reset();
                setPreview(null);
                stopPlayback();
              }}
              type="button"
            >
              <RotateCcw aria-hidden="true" size={17} />
              {t("Discard draft")}
            </button>
            <span className="meta">
              {editor.dirty ? t("Saving creates a new immutable version.") : t("All chord edits are saved.")}
            </span>
          </div>
        </form>
      ) : (
        <div className="empty-state compact-empty-state">
          <ListMusic aria-hidden="true" size={24} />
          <p>{t("Approve a SongSpec, then generate a chord progression.")}</p>
        </div>
      )}
    </section>
  );
}

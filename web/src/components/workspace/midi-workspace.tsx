"use client";

import {
  Clipboard,
  ClipboardPaste,
  Copy,
  Magnet,
  Music2,
  Pause,
  Play,
  Redo2,
  Repeat2,
  Save,
  Sparkles,
  Trash2,
  Undo2,
  Volume2,
} from "lucide-react";
import {
  KeyboardEvent,
  PointerEvent as ReactPointerEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { useMidiDraft } from "@/app/projects/[projectId]/hooks/use-midi-draft";
import { DownloadButton } from "@/components/workspace/download-button";
import { formatBytes } from "@/components/workspace/workspace-format";
import { useLocale } from "@/i18n/locale-provider";
import type {
  MidiAssetKind,
  MidiAssetVersion,
  MidiNoteEvent,
  MidiTransformOperation,
  MidiTransformPayload,
} from "@/lib/composition";
import { midiAssetDownloadEndpoint } from "@/lib/composition";
import {
  MidiDraft,
  addMidiNote,
  duplicateMidiNotes,
  midiDraftDuration,
  midiPitchName,
  pasteMidiNotes,
  removeMidiNotes,
  updateMidiNotes,
} from "@/lib/midi-editor";
import { normalizeApiBaseUrl } from "@/lib/projects";

const apiBaseUrl = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL);
const BEAT_WIDTH = 40;
const NOTE_HEIGHT = 14;
const GRID_BEATS = 0.25;
const TRACK_ORDER: MidiAssetKind[] = ["melody", "hook", "chord"];
const TRACK_COLORS: Record<MidiAssetKind, string> = {
  melody: "#147d92",
  hook: "#d05a37",
  chord: "#6558a6",
};

type DragState = {
  mode: "move" | "resize";
  startX: number;
  startY: number;
  baseDraft: MidiDraft;
  noteIds: string[];
};

type MidiWorkspaceProps = {
  assets: MidiAssetVersion[];
  canGenerate: boolean;
  disabledReason?: string | null;
  isSaving: boolean;
  onGenerate: () => void;
  onSave: (asset: MidiAssetVersion, noteEvents: MidiNoteEvent[]) => Promise<void>;
  onTransform: (asset: MidiAssetVersion, payload: MidiTransformPayload) => Promise<void>;
  projectId: string;
};

export function MidiWorkspace({
  assets,
  canGenerate,
  disabledReason,
  isSaving,
  onGenerate,
  onSave,
  onTransform,
  projectId,
}: MidiWorkspaceProps) {
  const { errorMessage, t, text } = useLocale();
  const [activeKind, setActiveKind] = useState<MidiAssetKind>("melody");
  const [overlay, setOverlay] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [clipboard, setClipboard] = useState<MidiNoteEvent[]>([]);
  const [previewDraft, setPreviewDraft] = useState<MidiDraft | null>(null);
  const previewRef = useRef<MidiDraft | null>(null);
  const dragRef = useRef<DragState | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [loopPlayback, setLoopPlayback] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const synthRef = useRef<import("tone").PolySynth | null>(null);
  const playbackTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const loopPlaybackRef = useRef(false);

  const latestByKind = useMemo(() => {
    const latest = new Map<MidiAssetKind, MidiAssetVersion>();
    for (const asset of assets) {
      if (!latest.has(asset.kind)) latest.set(asset.kind, asset);
    }
    return latest;
  }, [assets]);
  const activeAsset = latestByKind.get(activeKind) ?? null;
  const editor = useMidiDraft(projectId, activeAsset);
  const visibleDraft = previewDraft ?? editor.draft;
  const overlayAssets = overlay
    ? TRACK_ORDER.flatMap((kind) => {
        const asset = latestByKind.get(kind);
        return asset ? [asset] : [];
      })
    : activeAsset
      ? [activeAsset]
      : [];

  useEffect(() => {
    setSelectedIds(new Set());
    setPreviewDraft(null);
    previewRef.current = null;
    setLocalError(null);
  }, [activeAsset?.id]);

  useEffect(
    () => () => {
      if (playbackTimerRef.current) clearTimeout(playbackTimerRef.current);
      synthRef.current?.dispose();
    },
    [],
  );

  async function saveDraft() {
    if (!activeAsset || !editor.dirty || isSaving) return;
    setLocalError(null);
    try {
      await onSave(activeAsset, editor.draft.noteEvents);
      editor.clearPersisted();
    } catch (error) {
      setLocalError(errorMessage(error, "Failed to save MIDI"));
    }
  }

  async function transform(operation: MidiTransformOperation, values: Partial<MidiTransformPayload> = {}) {
    if (!activeAsset || isSaving) return;
    if (editor.dirty) {
      setLocalError(t("Save or discard the local MIDI draft before transforming."));
      return;
    }
    setLocalError(null);
    try {
      await onTransform(activeAsset, {
        midi_asset_id: activeAsset.id,
        operation,
        ...(selectedIds.size ? { note_ids: [...selectedIds] } : {}),
        ...values,
      });
    } catch (error) {
      setLocalError(errorMessage(error, "Failed to transform MIDI"));
    }
  }

  function addNote() {
    const next = addMidiNote(editor.draft, {
      section_id: null,
      pitch: 60,
      start_beat: Math.ceil(midiDraftDuration(editor.draft)),
      duration_beats: 1,
      velocity: 80,
      channel: 0,
    });
    const created = next.noteEvents.find(
      (note) => !editor.draft.noteEvents.some((current) => current.note_id === note.note_id),
    );
    editor.update(next);
    if (created) setSelectedIds(new Set([created.note_id]));
  }

  function deleteSelected() {
    if (!selectedIds.size) return;
    editor.update(removeMidiNotes(editor.draft, selectedIds));
    setSelectedIds(new Set());
  }

  function copySelected() {
    setClipboard(editor.draft.noteEvents.filter((note) => selectedIds.has(note.note_id)));
  }

  function pasteCopied() {
    const result = pasteMidiNotes(editor.draft, clipboard, midiDraftDuration(editor.draft));
    if (!result.createdIds.length) return;
    editor.update(result.draft);
    setSelectedIds(new Set(result.createdIds));
  }

  function duplicateSelected() {
    const result = duplicateMidiNotes(editor.draft, selectedIds);
    if (!result.createdIds.length) return;
    editor.update(result.draft);
    setSelectedIds(new Set(result.createdIds));
  }

  async function play() {
    if (!visibleDraft.noteEvents.length) return;
    stop();
    const [{ Midi }, Tone] = await Promise.all([import("@tonejs/midi"), import("tone")]);
    await Tone.start();
    const synth = new Tone.PolySynth(Tone.Synth).toDestination();
    synthRef.current = synth;
    const bpm = activeAsset?.tempo_map[0]?.bpm ?? 120;
    const secondsPerBeat = 60 / bpm;
    const firstBeat = Math.min(...visibleDraft.noteEvents.map((note) => note.start_beat));
    const midi = new Midi();
    midi.header.setTempo(bpm);
    const previewTrack = midi.addTrack();
    for (const note of visibleDraft.noteEvents.slice(0, 5000)) {
      previewTrack.addNote({
        duration: Math.max(0.03, note.duration_beats * secondsPerBeat),
        midi: note.pitch,
        time: (note.start_beat - firstBeat) * secondsPerBeat,
        velocity: note.velocity / 127,
      });
    }
    const now = Tone.now() + 0.08;
    for (const note of previewTrack.notes) {
      synth.triggerAttackRelease(
        Tone.Frequency(note.midi, "midi").toFrequency(),
        note.duration,
        now + note.time,
        note.velocity,
      );
    }
    const duration =
      (midiDraftDuration(visibleDraft) - firstBeat) * secondsPerBeat * 1000 + 200;
    setIsPlaying(true);
    playbackTimerRef.current = setTimeout(() => {
      if (loopPlaybackRef.current) {
        void play();
        return;
      }
      stop();
    }, Math.min(duration, 120_000));
  }

  function stop() {
    if (playbackTimerRef.current) clearTimeout(playbackTimerRef.current);
    playbackTimerRef.current = null;
    synthRef.current?.releaseAll();
    synthRef.current?.dispose();
    synthRef.current = null;
    setIsPlaying(false);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLCanvasElement>) {
    const mod = event.metaKey || event.ctrlKey;
    if (event.key === "Delete" || event.key === "Backspace") {
      event.preventDefault();
      deleteSelected();
      return;
    }
    if (mod && event.key.toLowerCase() === "c") {
      event.preventDefault();
      copySelected();
      return;
    }
    if (mod && event.key.toLowerCase() === "v") {
      event.preventDefault();
      pasteCopied();
      return;
    }
    if (!selectedIds.size || !["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
      return;
    }
    event.preventDefault();
    const beatDelta = event.key === "ArrowLeft" ? -GRID_BEATS : event.key === "ArrowRight" ? GRID_BEATS : 0;
    const pitchDelta = event.key === "ArrowDown" ? -1 : event.key === "ArrowUp" ? 1 : 0;
    editor.update(
      updateMidiNotes(editor.draft, selectedIds, (note) => ({
        ...note,
        start_beat: Math.max(0, note.start_beat + beatDelta),
        pitch: note.pitch + pitchDelta,
      })),
    );
  }

  const legacyAsset = Boolean(activeAsset && activeAsset.schema_version < 2);
  return (
    <section className="panel midi-workspace" aria-labelledby="midi-title">
      <div className="section-heading">
        <div>
          <h2 id="midi-title">MIDI</h2>
          <p className="meta">{t("Edit notes on a piano roll and save immutable MIDI versions.")}</p>
        </div>
        <span className="badge">{assets.length}</span>
      </div>

      <div className="midi-primary-actions">
        <button
          className="button secondary"
          data-guarded={!canGenerate || undefined}
          disabled={!canGenerate || isSaving}
          onClick={onGenerate}
          title={!canGenerate ? (disabledReason ?? undefined) : undefined}
          type="button"
        >
          <Music2 aria-hidden="true" size={18} />
          {t("Generate MIDI")}
        </button>
        <div className="segmented-control" aria-label={t("MIDI track")}>
          {TRACK_ORDER.map((kind) => (
            <button
              aria-pressed={activeKind === kind}
              className={activeKind === kind ? "active" : undefined}
              key={kind}
              onClick={() => setActiveKind(kind)}
              type="button"
            >
              {text(kind)}
            </button>
          ))}
        </div>
        <label className="toggle-control">
          <input checked={overlay} onChange={(event) => setOverlay(event.target.checked)} type="checkbox" />
          <span>{t("Overlay tracks")}</span>
        </label>
      </div>

      {localError ? <p className="error compact-error">{localError}</p> : null}
      {editor.restored ? <p className="notice compact-notice">{t("Local draft restored")}</p> : null}
      {legacyAsset ? (
        <p className="notice compact-notice">
          {t("This legacy MIDI has no editable note data. Regenerate it to open the piano roll.")}
        </p>
      ) : null}

      {activeAsset && !legacyAsset ? (
        <>
          <div className="midi-editor-toolbar" aria-label={t("MIDI editor tools")}>
            <button className="button secondary icon-only" disabled={!editor.canUndo} onClick={editor.undo} title={t("Undo")} type="button">
              <Undo2 aria-hidden="true" size={17} />
            </button>
            <button className="button secondary icon-only" disabled={!editor.canRedo} onClick={editor.redo} title={t("Redo")} type="button">
              <Redo2 aria-hidden="true" size={17} />
            </button>
            <button className="button secondary" onClick={addNote} type="button">
              <Music2 aria-hidden="true" size={17} />
              {t("Add note")}
            </button>
            <button className="button secondary icon-only" disabled={!selectedIds.size} onClick={copySelected} title={t("Copy")} type="button">
              <Copy aria-hidden="true" size={17} />
            </button>
            <button className="button secondary icon-only" disabled={!clipboard.length} onClick={pasteCopied} title={t("Paste")} type="button">
              <ClipboardPaste aria-hidden="true" size={17} />
            </button>
            <button className="button secondary icon-only" disabled={!selectedIds.size} onClick={duplicateSelected} title={t("Duplicate notes")} type="button">
              <Clipboard aria-hidden="true" size={17} />
            </button>
            <button className="button secondary icon-only" disabled={!selectedIds.size} onClick={deleteSelected} title={t("Delete notes")} type="button">
              <Trash2 aria-hidden="true" size={17} />
            </button>
            <span className="toolbar-spacer" />
            <label className="toggle-control">
              <input
                checked={loopPlayback}
                onChange={(event) => {
                  loopPlaybackRef.current = event.target.checked;
                  setLoopPlayback(event.target.checked);
                }}
                type="checkbox"
              />
              <Repeat2 aria-hidden="true" size={16} />
              <span>{t("Loop")}</span>
            </label>
            <button className="button secondary" onClick={isPlaying ? stop : play} type="button">
              {isPlaying ? <Pause aria-hidden="true" size={17} /> : <Play aria-hidden="true" size={17} />}
              {isPlaying ? t("Stop") : t("Audition")}
            </button>
            <button className="button" disabled={!editor.dirty || isSaving} onClick={saveDraft} type="button">
              <Save aria-hidden="true" size={17} />
              {t("Save MIDI version")}
            </button>
          </div>

          <PianoRoll
            activeKind={activeKind}
            activeNotes={visibleDraft.noteEvents}
            assets={overlayAssets}
            onCommit={(draft) => editor.update(draft)}
            onKeyDown={handleKeyDown}
            onPreview={(draft) => {
              previewRef.current = draft;
              setPreviewDraft(draft);
            }}
            onSelect={setSelectedIds}
            previewRef={previewRef}
            selectedIds={selectedIds}
            sourceDraft={editor.draft}
            dragRef={dragRef}
          />

          <div className="midi-selection-row">
            <span className="meta">
              {t("{count} notes selected", { count: selectedIds.size })} · {visibleDraft.noteEvents.length} {t("notes")}
              {editor.dirty ? ` · ${t("Unsaved")}` : ""}
            </span>
            <div className="midi-transform-actions">
              <button className="button secondary" disabled={isSaving} onClick={() => transform("quantize", { grid_beats: GRID_BEATS })} type="button">
                <Magnet aria-hidden="true" size={16} />
                {t("Quantize")}
              </button>
              <button className="button secondary" disabled={isSaving} onClick={() => transform("transpose", { semitones: -1 })} type="button">-1</button>
              <button className="button secondary" disabled={isSaving} onClick={() => transform("transpose", { semitones: 1 })} type="button">+1</button>
              <button className="button secondary" disabled={isSaving} onClick={() => transform("velocity", { velocity_delta: 8 })} type="button">
                <Volume2 aria-hidden="true" size={16} />
                {t("Velocity")}
              </button>
              <button className="button secondary" disabled={isSaving} onClick={() => transform("legato")} type="button">{t("Legato")}</button>
              <button className="button secondary" disabled={isSaving} onClick={() => transform("humanize")} type="button">
                <Sparkles aria-hidden="true" size={16} />
                {t("Humanize")}
              </button>
              <button className="button secondary" disabled={isSaving} onClick={() => transform("scale_snap")} type="button">{t("Scale snap")}</button>
            </div>
          </div>
        </>
      ) : activeAsset ? null : (
        <p className="empty">{t("Generated chord, melody, and hook MIDI files will appear here.")}</p>
      )}

      {assets.length ? (
        <div className="midi-version-list">
          <h3>{t("MIDI versions")}</h3>
          <div className="asset-list">
            {assets.map((asset) => (
              <div className="asset-row" key={asset.id}>
                <div>
                  <strong>{asset.filename}</strong>
                  <p className="meta">
                    {text(asset.kind)} v{asset.version_number} · {asset.note_events.length} {t("notes")} · {formatBytes(asset.size_bytes)}
                  </p>
                </div>
                <DownloadButton filename={asset.filename} url={midiAssetDownloadEndpoint(apiBaseUrl, projectId, asset.id)} />
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function PianoRoll({
  activeKind,
  activeNotes,
  assets,
  dragRef,
  onCommit,
  onKeyDown,
  onPreview,
  onSelect,
  previewRef,
  selectedIds,
  sourceDraft,
}: {
  activeKind: MidiAssetKind;
  activeNotes: MidiNoteEvent[];
  assets: MidiAssetVersion[];
  dragRef: React.MutableRefObject<DragState | null>;
  onCommit: (draft: MidiDraft) => void;
  onKeyDown: (event: KeyboardEvent<HTMLCanvasElement>) => void;
  onPreview: (draft: MidiDraft | null) => void;
  onSelect: (ids: Set<string>) => void;
  previewRef: React.MutableRefObject<MidiDraft | null>;
  selectedIds: Set<string>;
  sourceDraft: MidiDraft;
}) {
  const { t } = useLocale();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const allNotes = assets.flatMap((asset) => asset.note_events);
  const lowest = Math.min(48, ...(allNotes.length ? allNotes.map((note) => note.pitch - 3) : [48]));
  const highest = Math.max(72, ...(allNotes.length ? allNotes.map((note) => note.pitch + 3) : [72]));
  const minPitch = Math.max(0, lowest);
  const maxPitch = Math.min(127, Math.max(minPitch + 24, highest));
  const durationBeats = Math.min(
    256,
    Math.ceil(Math.max(midiDraftDuration({ noteEvents: activeNotes }), ...assets.map((asset) => midiDraftDuration({ noteEvents: asset.note_events })))) + 2,
  );
  const width = Math.max(720, durationBeats * BEAT_WIDTH);
  const height = (maxPitch - minPitch + 1) * NOTE_HEIGHT;

  useEffect(() => {
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    drawPianoRoll({
      context,
      width,
      height,
      minPitch,
      maxPitch,
      durationBeats,
      assets,
      activeKind,
      activeNotes,
      selectedIds,
    });
  }, [activeKind, activeNotes, assets, durationBeats, height, maxPitch, minPitch, selectedIds, width]);

  function point(event: ReactPointerEvent<HTMLCanvasElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: (event.clientX - rect.left) * (event.currentTarget.width / rect.width),
      y: (event.clientY - rect.top) * (event.currentTarget.height / rect.height),
    };
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLCanvasElement>) {
    const position = point(event);
    const hit = [...activeNotes].reverse().find((note) => noteAtPoint(note, position.x, position.y, maxPitch));
    if (!hit) {
      const startBeat = Math.max(0, Math.floor(position.x / BEAT_WIDTH / GRID_BEATS) * GRID_BEATS);
      const pitch = Math.max(minPitch, Math.min(maxPitch, maxPitch - Math.floor(position.y / NOTE_HEIGHT)));
      const next = addMidiNote(sourceDraft, {
        section_id: null,
        pitch,
        start_beat: startBeat,
        duration_beats: 1,
        velocity: 80,
        channel: 0,
      });
      const created = next.noteEvents.find(
        (note) => !sourceDraft.noteEvents.some((current) => current.note_id === note.note_id),
      );
      onCommit(next);
      if (created) onSelect(new Set([created.note_id]));
      return;
    }
    const nextSelection = event.metaKey || event.ctrlKey
      ? new Set(selectedIds)
      : new Set(selectedIds.has(hit.note_id) ? selectedIds : [hit.note_id]);
    if (event.metaKey || event.ctrlKey) {
      if (nextSelection.has(hit.note_id)) nextSelection.delete(hit.note_id);
      else nextSelection.add(hit.note_id);
    }
    if (!nextSelection.size) nextSelection.add(hit.note_id);
    onSelect(nextSelection);
    const noteRight = (hit.start_beat + hit.duration_beats) * BEAT_WIDTH;
    dragRef.current = {
      mode: Math.abs(noteRight - position.x) <= 7 ? "resize" : "move",
      startX: position.x,
      startY: position.y,
      baseDraft: sourceDraft,
      noteIds: [...nextSelection],
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLCanvasElement>) {
    const drag = dragRef.current;
    if (!drag) return;
    const position = point(event);
    const beatDelta = Math.round((position.x - drag.startX) / BEAT_WIDTH / GRID_BEATS) * GRID_BEATS;
    const pitchDelta = Math.round((drag.startY - position.y) / NOTE_HEIGHT);
    const next = updateMidiNotes(drag.baseDraft, drag.noteIds, (note) =>
      drag.mode === "resize"
        ? { ...note, duration_beats: Math.max(GRID_BEATS, note.duration_beats + beatDelta) }
        : {
            ...note,
            start_beat: Math.max(0, note.start_beat + beatDelta),
            pitch: note.pitch + pitchDelta,
          },
    );
    onPreview(next);
  }

  function handlePointerUp(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (!dragRef.current) return;
    const preview = previewRef.current;
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (preview) onCommit(preview);
    previewRef.current = null;
    onPreview(null);
  }

  return (
    <div className="piano-roll-shell">
      <div className="piano-roll-axis" aria-hidden="true">
        {Array.from({ length: maxPitch - minPitch + 1 }, (_, index) => maxPitch - index)
          .filter((pitch) => pitch % 12 === 0)
          .map((pitch) => (
            <span key={pitch} style={{ top: (maxPitch - pitch) * NOTE_HEIGHT }}>
              {midiPitchName(pitch)}
            </span>
          ))}
      </div>
      <div className="piano-roll-scroll">
        <canvas
          aria-label={t("MIDI piano roll")}
          className="piano-roll-canvas"
          height={height}
          onKeyDown={onKeyDown}
          onPointerCancel={handlePointerUp}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          ref={canvasRef}
          role="application"
          tabIndex={0}
          width={width}
        />
      </div>
    </div>
  );
}

function drawPianoRoll({
  context,
  width,
  height,
  minPitch,
  maxPitch,
  durationBeats,
  assets,
  activeKind,
  activeNotes,
  selectedIds,
}: {
  context: CanvasRenderingContext2D;
  width: number;
  height: number;
  minPitch: number;
  maxPitch: number;
  durationBeats: number;
  assets: MidiAssetVersion[];
  activeKind: MidiAssetKind;
  activeNotes: MidiNoteEvent[];
  selectedIds: Set<string>;
}) {
  const styles = getComputedStyle(context.canvas);
  const background = styles.getPropertyValue("--surface-sunken").trim() || "#f4f5f7";
  const border = styles.getPropertyValue("--border").trim() || "#d6d9de";
  const foreground = styles.getPropertyValue("--foreground").trim() || "#1f2428";
  context.clearRect(0, 0, width, height);
  context.fillStyle = background;
  context.fillRect(0, 0, width, height);
  for (let pitch = minPitch; pitch <= maxPitch; pitch += 1) {
    const y = (maxPitch - pitch) * NOTE_HEIGHT;
    if ([1, 3, 6, 8, 10].includes(pitch % 12)) {
      context.fillStyle = "rgba(20, 24, 28, 0.055)";
      context.fillRect(0, y, width, NOTE_HEIGHT);
    }
    context.strokeStyle = border;
    context.globalAlpha = pitch % 12 === 0 ? 0.72 : 0.35;
    context.beginPath();
    context.moveTo(0, y + NOTE_HEIGHT);
    context.lineTo(width, y + NOTE_HEIGHT);
    context.stroke();
  }
  for (let beat = 0; beat <= durationBeats; beat += GRID_BEATS) {
    const x = beat * BEAT_WIDTH;
    context.strokeStyle = beat % 4 === 0 ? foreground : border;
    context.globalAlpha = beat % 4 === 0 ? 0.32 : Number.isInteger(beat) ? 0.5 : 0.2;
    context.beginPath();
    context.moveTo(x, 0);
    context.lineTo(x, height);
    context.stroke();
  }
  context.globalAlpha = 1;
  for (const asset of assets) {
    if (asset.kind === activeKind) continue;
    for (const note of asset.note_events) drawNote(context, note, maxPitch, TRACK_COLORS[asset.kind], false, 0.38);
  }
  for (const note of activeNotes) {
    drawNote(context, note, maxPitch, TRACK_COLORS[activeKind], selectedIds.has(note.note_id), 0.92);
  }
}

function drawNote(
  context: CanvasRenderingContext2D,
  note: MidiNoteEvent,
  maxPitch: number,
  color: string,
  selected: boolean,
  alpha: number,
) {
  const x = note.start_beat * BEAT_WIDTH + 1;
  const y = (maxPitch - note.pitch) * NOTE_HEIGHT + 1;
  const width = Math.max(4, note.duration_beats * BEAT_WIDTH - 2);
  context.globalAlpha = alpha;
  context.fillStyle = color;
  context.fillRect(x, y, width, NOTE_HEIGHT - 2);
  if (selected) {
    context.globalAlpha = 1;
    context.strokeStyle = "#ffffff";
    context.lineWidth = 2;
    context.strokeRect(x + 1, y + 1, Math.max(1, width - 2), NOTE_HEIGHT - 4);
  }
  context.globalAlpha = 1;
  context.lineWidth = 1;
}

function noteAtPoint(note: MidiNoteEvent, x: number, y: number, maxPitch: number): boolean {
  const noteX = note.start_beat * BEAT_WIDTH;
  const noteY = (maxPitch - note.pitch) * NOTE_HEIGHT;
  return (
    x >= noteX &&
    x <= noteX + Math.max(4, note.duration_beats * BEAT_WIDTH) &&
    y >= noteY &&
    y <= noteY + NOTE_HEIGHT
  );
}

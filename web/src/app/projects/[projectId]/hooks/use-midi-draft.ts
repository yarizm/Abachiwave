"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { MidiAssetVersion } from "@/lib/composition";
import {
  MidiDraft,
  createMidiHistory,
  draftFromMidiVersion,
  isMidiDraft,
  midiDraftsEqual,
  pushMidiHistory,
  redoMidiHistory,
  undoMidiHistory,
} from "@/lib/midi-editor";

type PersistedMidiDraft = {
  schemaVersion: 1;
  sourceMidiId: string;
  draft: MidiDraft;
};

export function midiDraftStorageKey(projectId: string, sourceId: string | null): string {
  return `abachiwave:midi-draft:${projectId}:${sourceId ?? "none"}`;
}

export function useMidiDraft(projectId: string, sourceVersion: MidiAssetVersion | null) {
  const sourceId = sourceVersion?.id ?? null;
  const baselineRef = useRef({
    sourceId,
    draft: draftFromMidiVersion(sourceVersion),
  });
  if (baselineRef.current.sourceId !== sourceId) {
    baselineRef.current = { sourceId, draft: draftFromMidiVersion(sourceVersion) };
  }
  const baseline = baselineRef.current.draft;
  const storageKey = midiDraftStorageKey(projectId, sourceId);
  const [history, setHistory] = useState(() => createMidiHistory(baseline));
  const [initialized, setInitialized] = useState(false);
  const [restored, setRestored] = useState(false);

  useEffect(() => {
    let draft = baseline;
    let didRestore = false;
    if (sourceId) {
      try {
        const raw = window.localStorage.getItem(storageKey);
        const persisted: unknown = raw ? JSON.parse(raw) : null;
        if (
          isPersistedMidiDraft(persisted) &&
          persisted.sourceMidiId === sourceId &&
          isMidiDraft(persisted.draft)
        ) {
          draft = persisted.draft;
          didRestore = !midiDraftsEqual(draft, baseline);
        }
      } catch {
        window.localStorage.removeItem(storageKey);
      }
    }
    setHistory(createMidiHistory(draft));
    setRestored(didRestore);
    setInitialized(true);
  }, [baseline, sourceId, storageKey]);

  const dirty = initialized && !midiDraftsEqual(history.present, baseline);

  useEffect(() => {
    if (!initialized || !sourceId) return;
    if (!dirty) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    const persisted: PersistedMidiDraft = {
      schemaVersion: 1,
      sourceMidiId: sourceId,
      draft: history.present,
    };
    window.localStorage.setItem(storageKey, JSON.stringify(persisted));
  }, [dirty, history.present, initialized, sourceId, storageKey]);

  useEffect(() => {
    if (!dirty) return;
    const warnBeforeLeave = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnBeforeLeave);
    return () => window.removeEventListener("beforeunload", warnBeforeLeave);
  }, [dirty]);

  const update = useCallback((draft: MidiDraft) => {
    setHistory((current) => pushMidiHistory(current, draft));
    setRestored(false);
  }, []);
  const undo = useCallback(() => {
    setHistory((current) => undoMidiHistory(current));
    setRestored(false);
  }, []);
  const redo = useCallback(() => {
    setHistory((current) => redoMidiHistory(current));
    setRestored(false);
  }, []);
  const reset = useCallback(() => {
    setHistory(createMidiHistory(baseline));
    setRestored(false);
    window.localStorage.removeItem(storageKey);
  }, [baseline, storageKey]);
  const clearPersisted = useCallback(() => {
    window.localStorage.removeItem(storageKey);
  }, [storageKey]);

  return {
    draft: history.present,
    dirty,
    restored,
    canUndo: history.past.length > 0,
    canRedo: history.future.length > 0,
    update,
    undo,
    redo,
    reset,
    clearPersisted,
  };
}

function isPersistedMidiDraft(value: unknown): value is PersistedMidiDraft {
  return (
    typeof value === "object" &&
    value !== null &&
    "schemaVersion" in value &&
    value.schemaVersion === 1 &&
    "sourceMidiId" in value &&
    typeof value.sourceMidiId === "string" &&
    "draft" in value
  );
}

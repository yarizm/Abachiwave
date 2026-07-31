"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { ChordProgressionVersion } from "@/lib/composition";
import {
  ChordDraft,
  chordDraftsEqual,
  createChordHistory,
  draftFromChordVersion,
  isChordDraft,
  pushChordHistory,
  redoChordHistory,
  undoChordHistory,
} from "@/lib/chord-editor";

type PersistedChordDraft = {
  schemaVersion: 1;
  sourceChordId: string;
  draft: ChordDraft;
};

export function chordDraftStorageKey(projectId: string, sourceId: string | null): string {
  // Per-version keys keep each version's unsaved draft when the user switches
  // versions; a single project-scoped key was cleared by the clean baseline of
  // the newly selected version, destroying the previous draft.
  return `abachiwave:chord-draft:${projectId}:${sourceId ?? "none"}`;
}

export function useChordDraft(projectId: string, sourceVersion: ChordProgressionVersion | null) {
  const sourceId = sourceVersion?.id ?? null;
  const baselineRef = useRef({
    sourceId,
    draft: draftFromChordVersion(sourceVersion),
  });
  if (baselineRef.current.sourceId !== sourceId) {
    baselineRef.current = { sourceId, draft: draftFromChordVersion(sourceVersion) };
  }
  const baseline = baselineRef.current.draft;
  const storageKey = chordDraftStorageKey(projectId, sourceId);
  const [history, setHistory] = useState(() => createChordHistory(baseline));
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
          isPersistedChordDraft(persisted) &&
          persisted.sourceChordId === sourceId &&
          isChordDraft(persisted.draft)
        ) {
          draft = persisted.draft;
          didRestore = !chordDraftsEqual(draft, baseline);
        }
      } catch {
        window.localStorage.removeItem(storageKey);
      }
    }
    setHistory(createChordHistory(draft));
    setRestored(didRestore);
    setInitialized(true);
  }, [baseline, sourceId, storageKey]);

  const dirty = initialized && !chordDraftsEqual(history.present, baseline);

  useEffect(() => {
    if (!initialized || !sourceId) return;
    if (!dirty) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    const persisted: PersistedChordDraft = {
      schemaVersion: 1,
      sourceChordId: sourceId,
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

  const update = useCallback((draft: ChordDraft) => {
    setHistory((current) => pushChordHistory(current, draft));
    setRestored(false);
  }, []);

  const undo = useCallback(() => {
    setHistory((current) => undoChordHistory(current));
    setRestored(false);
  }, []);

  const redo = useCallback(() => {
    setHistory((current) => redoChordHistory(current));
    setRestored(false);
  }, []);

  const reset = useCallback(() => {
    setHistory(createChordHistory(baseline));
    setRestored(false);
    window.localStorage.removeItem(storageKey);
  }, [baseline, storageKey]);

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
  };
}

function isPersistedChordDraft(value: unknown): value is PersistedChordDraft {
  return (
    typeof value === "object" &&
    value !== null &&
    "schemaVersion" in value &&
    value.schemaVersion === 1 &&
    "sourceChordId" in value &&
    typeof value.sourceChordId === "string" &&
    "draft" in value
  );
}

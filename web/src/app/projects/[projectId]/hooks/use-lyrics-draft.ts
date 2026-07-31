"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { LyricsVersion } from "@/lib/composition";
import {
  LyricsDraft,
  createLyricsHistory,
  draftFromLyricsVersion,
  isLyricsDraft,
  lyricsDraftsEqual,
  pushLyricsHistory,
  redoLyricsHistory,
  undoLyricsHistory,
} from "@/lib/lyrics-editor";

type PersistedLyricsDraft = {
  sourceLyricsId: string;
  draft: LyricsDraft;
};

export function lyricsDraftStorageKey(projectId: string, sourceId: string | null): string {
  // Per-version keys keep each version's unsaved draft when the user switches
  // versions; a single project-scoped key was cleared by the clean baseline of
  // the newly selected version, destroying the previous draft.
  return `abachiwave:lyrics-draft:${projectId}:${sourceId ?? "none"}`;
}

export function useLyricsDraft(projectId: string, sourceVersion: LyricsVersion | null) {
  const sourceId = sourceVersion?.id ?? null;
  const baselineRef = useRef({
    sourceId,
    draft: draftFromLyricsVersion(sourceVersion),
  });
  if (baselineRef.current.sourceId !== sourceId) {
    baselineRef.current = { sourceId, draft: draftFromLyricsVersion(sourceVersion) };
  }
  const baseline = baselineRef.current.draft;
  const storageKey = lyricsDraftStorageKey(projectId, sourceId);
  const [history, setHistory] = useState(() => createLyricsHistory(baseline));
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
          isPersistedLyricsDraft(persisted) &&
          persisted.sourceLyricsId === sourceId &&
          isLyricsDraft(persisted.draft)
        ) {
          draft = persisted.draft;
          didRestore = !lyricsDraftsEqual(draft, baseline);
        }
      } catch {
        window.localStorage.removeItem(storageKey);
      }
    }
    setHistory(createLyricsHistory(draft));
    setRestored(didRestore);
    setInitialized(true);
  }, [baseline, sourceId, storageKey]);

  const dirty = initialized && !lyricsDraftsEqual(history.present, baseline);

  useEffect(() => {
    if (!initialized || !sourceId) return;
    if (!dirty) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    const persisted: PersistedLyricsDraft = { sourceLyricsId: sourceId, draft: history.present };
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

  const update = useCallback((draft: LyricsDraft) => {
    setHistory((current) => pushLyricsHistory(current, draft));
    setRestored(false);
  }, []);

  const undo = useCallback(() => {
    setHistory((current) => undoLyricsHistory(current));
    setRestored(false);
  }, []);

  const redo = useCallback(() => {
    setHistory((current) => redoLyricsHistory(current));
    setRestored(false);
  }, []);

  const reset = useCallback(() => {
    setHistory(createLyricsHistory(baseline));
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

function isPersistedLyricsDraft(value: unknown): value is PersistedLyricsDraft {
  return (
    typeof value === "object" &&
    value !== null &&
    "sourceLyricsId" in value &&
    typeof value.sourceLyricsId === "string" &&
    "draft" in value
  );
}

"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { SongSpecVersion } from "@/lib/song-specs";
import {
  StructureSectionDraft,
  createStructureHistory,
  pushStructureHistory,
  redoStructureHistory,
  structureSectionsEqual,
  undoStructureHistory,
} from "@/lib/structure";

type PersistedStructureDraft = {
  sourceSongSpecId: string;
  sections: StructureSectionDraft[];
};

export function structureDraftStorageKey(projectId: string, sourceId: string | null): string {
  // Per-version keys keep each version's unsaved draft when the user switches
  // versions; a single project-scoped key was cleared by the clean baseline of
  // the newly selected version, destroying the previous draft.
  return `abachiwave:structure-draft:${projectId}:${sourceId ?? "none"}`;
}

export function useStructureDraft(projectId: string, sourceVersion: SongSpecVersion | null) {
  const sourceId = sourceVersion?.id ?? null;
  const baseline = useMemo(
    () => sourceVersion?.song_spec.structure_sections ?? [],
    [sourceVersion],
  );
  const storageKey = structureDraftStorageKey(projectId, sourceId);
  const [history, setHistory] = useState(() => createStructureHistory([]));
  const [initialized, setInitialized] = useState(false);
  const [restored, setRestored] = useState(false);

  useEffect(() => {
    let sections: StructureSectionDraft[] = baseline.map((section) => ({ ...section }));
    let didRestore = false;
    if (sourceId) {
      try {
        const raw = window.localStorage.getItem(storageKey);
        const persisted = raw ? (JSON.parse(raw) as PersistedStructureDraft) : null;
        if (persisted?.sourceSongSpecId === sourceId && Array.isArray(persisted.sections)) {
          sections = persisted.sections;
          didRestore = !structureSectionsEqual(sections, baseline);
        }
      } catch {
        window.localStorage.removeItem(storageKey);
      }
    }
    setHistory(createStructureHistory(sections));
    setRestored(didRestore);
    setInitialized(true);
  }, [baseline, sourceId, storageKey]);

  const dirty = initialized && !structureSectionsEqual(history.present, baseline);

  useEffect(() => {
    if (!initialized || !sourceId) {
      return;
    }
    if (!dirty) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    const persisted: PersistedStructureDraft = {
      sourceSongSpecId: sourceId,
      sections: history.present,
    };
    window.localStorage.setItem(storageKey, JSON.stringify(persisted));
  }, [dirty, history.present, initialized, sourceId, storageKey]);

  useEffect(() => {
    if (!dirty) {
      return;
    }
    const warnBeforeLeave = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnBeforeLeave);
    return () => window.removeEventListener("beforeunload", warnBeforeLeave);
  }, [dirty]);

  const update = useCallback((sections: StructureSectionDraft[]) => {
    setHistory((current) => pushStructureHistory(current, sections));
    setRestored(false);
  }, []);

  const undo = useCallback(() => {
    setHistory((current) => undoStructureHistory(current));
    setRestored(false);
  }, []);

  const redo = useCallback(() => {
    setHistory((current) => redoStructureHistory(current));
    setRestored(false);
  }, []);

  const reset = useCallback(
    (sections: StructureSectionDraft[]) => {
      setHistory(createStructureHistory(sections));
      setRestored(false);
      window.localStorage.removeItem(storageKey);
    },
    [storageKey],
  );

  return {
    sections: history.present,
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

"use client";

import { useCallback, useState } from "react";

export type WorkspaceActionDomain =
  | "project"
  | "songSpec"
  | "composition"
  | "audio"
  | "delivery"
  | "demo"
  | "revision"
  | "collaboration"
  | "tasks"
  | "ai"
  | "structure"
  | "lyrics"
  | "lyricsRewrite"
  | "chords"
  | "chordsPreview"
  | "chordsTranspose"
  | "midi";

export function usePendingActions() {
  const [counts, setCounts] = useState<Partial<Record<WorkspaceActionDomain, number>>>({});

  const begin = useCallback((domain: WorkspaceActionDomain) => {
    setCounts((current) => ({ ...current, [domain]: (current[domain] ?? 0) + 1 }));
  }, []);

  const end = useCallback((domain: WorkspaceActionDomain) => {
    setCounts((current) => {
      const nextCount = Math.max(0, (current[domain] ?? 0) - 1);
      return { ...current, [domain]: nextCount };
    });
  }, []);

  const isPending = useCallback(
    (...domains: WorkspaceActionDomain[]) =>
      domains.some((domain) => (counts[domain] ?? 0) > 0),
    [counts],
  );

  return { begin, end, isPending };
}

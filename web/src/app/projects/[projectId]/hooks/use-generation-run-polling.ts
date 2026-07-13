"use client";

import { Dispatch, SetStateAction, useEffect } from "react";

import { fetchJson } from "@/lib/api-client";
import {
  GenerationRun,
  isRunActive,
  sortGenerationRuns,
  taskEndpoint,
} from "@/lib/composition";

type GenerationRunPollingOptions = {
  apiBaseUrl: string;
  runs: GenerationRun[];
  setRuns: Dispatch<SetStateAction<GenerationRun[]>>;
  onTerminal: () => Promise<void>;
  onError: (error: unknown) => void;
};

export function useGenerationRunPolling({
  apiBaseUrl,
  runs,
  setRuns,
  onTerminal,
  onError,
}: GenerationRunPollingOptions) {
  useEffect(() => {
    const activeRuns = runs.filter(isRunActive);
    if (!activeRuns.length) {
      return;
    }

    let cancelled = false;
    const timeoutId = window.setTimeout(() => {
      void Promise.all(
        activeRuns.map((run) =>
          fetchJson<GenerationRun>(taskEndpoint(apiBaseUrl, run.id), "Generation task"),
        ),
      )
        .then(async (updates) => {
          if (cancelled) {
            return;
          }
          if (updates.some((run) => !isRunActive(run))) {
            await onTerminal();
            return;
          }
          setRuns((current) => mergeGenerationRunUpdates(current, updates));
        })
        .catch((error: unknown) => {
          if (!cancelled) {
            onError(error);
          }
        });
    }, 2500);

    return () => {
      cancelled = true;
      window.clearTimeout(timeoutId);
    };
  }, [apiBaseUrl, onError, onTerminal, runs, setRuns]);
}

export function mergeGenerationRunUpdates(
  current: GenerationRun[],
  updates: GenerationRun[],
): GenerationRun[] {
  const updateMap = new Map(updates.map((run) => [run.id, run]));
  return sortGenerationRuns(current.map((run) => updateMap.get(run.id) ?? run));
}

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type {
  SectionPlaybackHandle,
  SectionPlaybackInput,
  ScheduledTone,
} from "@/lib/section-playback";

/**
 * Playback state for the section view: at most one section sounding at a time.
 *
 * One-at-a-time is the point rather than a limitation. The question this surface
 * answers is "does this section work" — its words against its chords against its
 * melody — so starting a second section stops the first instead of layering.
 *
 * Starting playback is async (Tone is loaded on demand and the AudioContext has to
 * be resumed from the click), which opens a window where the user can hit stop
 * before the engine exists. `tokenRef` closes it: every start claims a token, and a
 * handle that comes back holding a stale token is disposed instead of played.
 */

/** ~30fps. The playhead re-renders the sounding row, so this trades a little
 *  smoothness for not re-rendering a dozen chord cells sixty times a second. */
const PROGRESS_INTERVAL_MS = 33;

export type SectionPlaybackState = {
  /** section currently sounding, or null */
  playingSectionId: string | null;
  /** playhead in section-local beats, for the melody strip */
  playheadBeat: number | null;
  /** event_id of the chord sounding right now, for highlighting its cell */
  soundingChordId: string | null;
  /** note_id of the melody note sounding right now */
  soundingNoteId: string | null;
  /** true between the click and the first audible note */
  isStarting: boolean;
  error: string | null;
  toggle: (sectionId: string, input: SectionPlaybackInput) => void;
  stop: () => void;
};

export type SectionPlaybackSettings = {
  loop: boolean;
  metronome: boolean;
  /** localized fallback for a failed audio start */
  failureMessage: string;
};

export function useSectionPlayback(settings: SectionPlaybackSettings): SectionPlaybackState {
  const [playingSectionId, setPlayingSectionId] = useState<string | null>(null);
  const [playheadBeat, setPlayheadBeat] = useState<number | null>(null);
  // Chords and melody need separate slots. A section sounds far more notes than
  // chords, so one shared "what is sounding" value is overwritten by the next
  // melody note within milliseconds and the chord highlight never survives long
  // enough to be seen.
  const [soundingChordId, setSoundingChordId] = useState<string | null>(null);
  const [soundingNoteId, setSoundingNoteId] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRef = useRef<SectionPlaybackHandle | null>(null);
  const tokenRef = useRef(0);
  const lastProgressRef = useRef(0);

  // Settings are read inside the async start, which closes over the values from
  // the render that began it; a ref keeps a mid-playback toggle from being stale.
  const settingsRef = useRef(settings);
  settingsRef.current = settings;

  const stop = useCallback(() => {
    tokenRef.current += 1;
    handleRef.current?.stop();
    handleRef.current = null;
    setPlayingSectionId(null);
    setPlayheadBeat(null);
    setSoundingChordId(null);
    setSoundingNoteId(null);
    setIsStarting(false);
  }, []);

  useEffect(() => stop, [stop]);

  const toggle = useCallback(
    (sectionId: string, input: SectionPlaybackInput) => {
      if (playingSectionId === sectionId) {
        stop();
        return;
      }
      stop();
      const token = tokenRef.current;
      setError(null);
      setIsStarting(true);
      setPlayingSectionId(sectionId);

      void (async () => {
        try {
          const { startSectionPlayback } = await import("@/lib/section-playback");
          const handle = await startSectionPlayback({
            ...input,
            loop: settingsRef.current.loop,
            metronome: settingsRef.current.metronome,
            onSound: (tone: ScheduledTone | null) => {
              if (tokenRef.current !== token) return;
              if (tone === null) {
                setSoundingChordId(null);
                setSoundingNoteId(null);
              } else if (tone.kind === "chord") {
                setSoundingChordId(tone.sourceId);
              } else {
                setSoundingNoteId(tone.sourceId);
              }
            },
            onProgress: (beat: number) => {
              if (tokenRef.current !== token) return;
              const now = Date.now();
              if (now - lastProgressRef.current < PROGRESS_INTERVAL_MS) return;
              lastProgressRef.current = now;
              setPlayheadBeat(beat);
            },
            onEnded: () => {
              if (tokenRef.current !== token) return;
              stop();
            },
          });
          // Stopped while Tone was loading: the handle exists but nobody wants it.
          if (tokenRef.current !== token) {
            handle.stop();
            return;
          }
          handleRef.current = handle;
          setIsStarting(false);
        } catch {
          // The cause is almost always an AudioContext the browser refused to
          // resume, which says nothing a user can act on beyond "it did not start".
          if (tokenRef.current !== token) return;
          setError(settingsRef.current.failureMessage);
          setPlayingSectionId(null);
          setIsStarting(false);
        }
      })();
    },
    [playingSectionId, stop],
  );

  return {
    playingSectionId,
    playheadBeat,
    soundingChordId,
    soundingNoteId,
    isStarting,
    error,
    toggle,
    stop,
  };
}

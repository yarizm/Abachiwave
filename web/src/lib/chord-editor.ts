import type {
  ChordEvent,
  ChordProgressionVersion,
  ChordSection,
} from "@/lib/composition";

export type ChordDraft = {
  sections: ChordSection[];
};

export type ChordHistory = {
  past: ChordDraft[];
  present: ChordDraft;
  future: ChordDraft[];
};

export type ChordDisplayMode = "symbol" | "roman" | "nashville";

export function draftFromChordVersion(version: ChordProgressionVersion | null): ChordDraft {
  return version ? cloneChordDraft({ sections: version.sections }) : { sections: [] };
}

export function createChordEventId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `chord-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function updateChordEvent(
  draft: ChordDraft,
  sectionId: string,
  eventId: string,
  patch: Partial<Pick<ChordEvent, "symbol" | "beat" | "duration_beats" | "inversion">>,
): ChordDraft {
  return updateSection(draft, sectionId, (section) => ({
    ...section,
    measures: section.measures.map((measure) => ({
      ...measure,
      events: measure.events.map((event) => {
        if (event.event_id !== eventId) return event;
        const changedTheoryInput = patch.symbol !== undefined || patch.inversion !== undefined;
        return {
          ...event,
          ...patch,
          ...(changedTheoryInput ? emptyChordAnalysis : {}),
        };
      }),
    })),
  }));
}

export function addChordEvent(
  draft: ChordDraft,
  sectionId: string,
  measureNumber: number,
  beatsPerMeasure: number,
): ChordDraft {
  return updateSection(draft, sectionId, (section) => ({
    ...section,
    measures: section.measures.map((measure) => {
      if (measure.measure_number !== measureNumber) return measure;
      const sorted = [...measure.events].sort((left, right) => left.beat - right.beat);
      let freeOffset = 0;
      for (const event of sorted) {
        const startOffset = event.beat - 1;
        if (startOffset - freeOffset >= 1) break;
        freeOffset = Math.max(freeOffset, startOffset + event.duration_beats);
      }
      if (beatsPerMeasure - freeOffset < 1) return measure;
      return {
        ...measure,
        events: [
          ...measure.events,
          {
            event_id: createChordEventId(),
            measure: measure.measure_number,
            beat: freeOffset + 1,
            duration_beats: 1,
            symbol: "N.C.",
            inversion: 0,
            ...emptyChordAnalysis,
            roman_numeral: "N.C.",
            nashville_number: "N.C.",
          },
        ].sort((left, right) => left.beat - right.beat),
      };
    }),
  }));
}

export function removeChordEvent(
  draft: ChordDraft,
  sectionId: string,
  eventId: string,
): ChordDraft {
  return updateSection(draft, sectionId, (section) => ({
    ...section,
    measures: section.measures.map((measure) =>
      measure.events.length <= 1
        ? measure
        : {
            ...measure,
            events: measure.events.filter((event) => event.event_id !== eventId),
          },
    ),
  }));
}

export function addChordMeasure(
  draft: ChordDraft,
  sectionId: string,
  beatsPerMeasure: number,
): ChordDraft {
  return updateSection(draft, sectionId, (section) => {
    if (section.measures.length >= 64) return section;
    const measureNumber = section.measures.length + 1;
    return {
      ...section,
      measures: [
        ...section.measures,
        {
          measure_number: measureNumber,
          events: [
            {
              event_id: createChordEventId(),
              measure: measureNumber,
              beat: 1,
              duration_beats: beatsPerMeasure,
              symbol: "N.C.",
              inversion: 0,
              ...emptyChordAnalysis,
              roman_numeral: "N.C.",
              nashville_number: "N.C.",
            },
          ],
        },
      ],
    };
  });
}

export function removeChordMeasure(
  draft: ChordDraft,
  sectionId: string,
  measureNumber: number,
): ChordDraft {
  return updateSection(draft, sectionId, (section) => {
    if (section.measures.length <= 1) return section;
    const measures = section.measures
      .filter((measure) => measure.measure_number !== measureNumber)
      .map((measure, index) => ({
        ...measure,
        measure_number: index + 1,
        events: measure.events.map((event) => ({ ...event, measure: index + 1 })),
      }));
    return { ...section, measures };
  });
}

export function chordAnalysisByEventId(sections: ChordSection[]): Map<string, ChordEvent> {
  return new Map(
    sections.flatMap((section) =>
      section.measures.flatMap((measure) =>
        measure.events.map((event) => [event.event_id, event] as const),
      ),
    ),
  );
}

export function chordDisplayLabel(event: ChordEvent, mode: ChordDisplayMode): string {
  if (mode === "roman") return event.roman_numeral ?? event.symbol;
  if (mode === "nashville") return event.nashville_number ?? event.symbol;
  return event.symbol;
}

export function createChordHistory(draft: ChordDraft): ChordHistory {
  return { past: [], present: cloneChordDraft(draft), future: [] };
}

export function pushChordHistory(history: ChordHistory, draft: ChordDraft): ChordHistory {
  if (chordDraftsEqual(history.present, draft)) return history;
  return {
    past: [...history.past.slice(-49), cloneChordDraft(history.present)],
    present: cloneChordDraft(draft),
    future: [],
  };
}

export function undoChordHistory(history: ChordHistory): ChordHistory {
  const previous = history.past.at(-1);
  if (!previous) return history;
  return {
    past: history.past.slice(0, -1),
    present: cloneChordDraft(previous),
    future: [cloneChordDraft(history.present), ...history.future],
  };
}

export function redoChordHistory(history: ChordHistory): ChordHistory {
  const next = history.future[0];
  if (!next) return history;
  return {
    past: [...history.past, cloneChordDraft(history.present)],
    present: cloneChordDraft(next),
    future: history.future.slice(1),
  };
}

export function chordDraftsEqual(left: ChordDraft, right: ChordDraft): boolean {
  return JSON.stringify(editableChordDraft(left)) === JSON.stringify(editableChordDraft(right));
}

export function cloneChordDraft(draft: ChordDraft): ChordDraft {
  return {
    sections: draft.sections.map((section) => ({
      ...section,
      chords: [...section.chords],
      measures: section.measures.map((measure) => ({
        ...measure,
        events: measure.events.map((event) => ({
          ...event,
          extensions: [...event.extensions],
          pitch_classes: [...event.pitch_classes],
          midi_notes: [...event.midi_notes],
        })),
      })),
    })),
  };
}

export function isChordDraft(value: unknown): value is ChordDraft {
  if (!isRecord(value) || !Array.isArray(value.sections)) return false;
  return value.sections.every(
    (section) =>
      isRecord(section) &&
      typeof section.section_id === "string" &&
      typeof section.label === "string" &&
      typeof section.bars === "number" &&
      Array.isArray(section.chords) &&
      Array.isArray(section.measures) &&
      section.measures.every(
        (measure) =>
          isRecord(measure) &&
          typeof measure.measure_number === "number" &&
          Array.isArray(measure.events) &&
          measure.events.every(
            (event) =>
              isRecord(event) &&
              typeof event.event_id === "string" &&
              typeof event.measure === "number" &&
              typeof event.beat === "number" &&
              typeof event.duration_beats === "number" &&
              typeof event.symbol === "string",
          ),
      ),
  );
}

function updateSection(
  draft: ChordDraft,
  sectionId: string,
  update: (section: ChordSection) => ChordSection,
): ChordDraft {
  return {
    sections: draft.sections.map((section) =>
      section.section_id === sectionId ? synchronizeSection(update(section)) : section,
    ),
  };
}

function synchronizeSection(section: ChordSection): ChordSection {
  return {
    ...section,
    bars: section.measures.length,
    chords: section.measures.flatMap((measure) =>
      measure.events.map((event) => event.symbol.trim()),
    ),
  };
}

function editableChordDraft(draft: ChordDraft) {
  return draft.sections.map((section) => ({
    section_id: section.section_id,
    label: section.label,
    measures: section.measures.map((measure) => ({
      measure_number: measure.measure_number,
      events: measure.events.map((event) => ({
        event_id: event.event_id,
        measure: event.measure,
        beat: event.beat,
        duration_beats: event.duration_beats,
        symbol: event.symbol,
        inversion: event.inversion,
      })),
    })),
  }));
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

const emptyChordAnalysis = {
  root: null,
  bass: null,
  quality: null,
  extensions: [] as string[],
  pitch_classes: [] as number[],
  midi_notes: [] as number[],
  roman_numeral: null,
  nashville_number: null,
  borrowed: false,
};

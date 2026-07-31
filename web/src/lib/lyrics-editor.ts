import type {
  HookCandidate,
  LyricLine,
  LyricSection,
  LyricsVersion,
} from "@/lib/composition";
import { lyricsVersionEndpoint } from "@/lib/composition";

export type LyricsRewriteScope = "line" | "section" | "all";
export type LyricsRewriteAction =
  | "rewrite"
  | "expand"
  | "compress"
  | "change_rhyme"
  | "adjust_tone";

export type LyricsRewritePayload = {
  scope: LyricsRewriteScope;
  action: LyricsRewriteAction;
  section_id?: string;
  line_id?: string;
  instruction?: string;
  tone?: string;
  rhyme_ending?: string;
  rhyme_label?: string;
  banned_phrases?: string[];
  preferred_terms?: string[];
  sections?: LyricSection[];
};

export type LyricDiffSegment = {
  kind: "equal" | "delete" | "insert";
  text: string;
};

export type LyricRewriteChange = {
  section_id: string;
  line_id: string;
  before: LyricLine;
  after: LyricLine;
  diff: LyricDiffSegment[];
};

export type LyricsRewritePreview = {
  source_lyrics_id: string;
  scope: LyricsRewriteScope;
  action: LyricsRewriteAction;
  candidate_sections: LyricSection[];
  changes: LyricRewriteChange[];
  detected_banned_phrases: string[];
  warnings: string[];
};

export type LyricsDraft = {
  sections: LyricSection[];
  hookCandidates: HookCandidate[];
};

export type LyricsHistory = {
  past: LyricsDraft[];
  present: LyricsDraft;
  future: LyricsDraft[];
};

export type LyricDiagnostic = {
  sectionId: string;
  lineId: string;
  phrase: string;
};

const englishWordPattern = /[A-Za-z]+(?:'[A-Za-z]+)?/g;
const cjkPattern = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/g;
const endingPattern = /([A-Za-z]+|[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff])[^A-Za-z\u3400-\u9fff]*$/;

export function lyricsRewriteEndpoint(
  apiBaseUrl: string,
  projectId: string,
  lyricsVersionId: string,
): string {
  return `${lyricsVersionEndpoint(apiBaseUrl, projectId, lyricsVersionId)}/rewrite`;
}

export function draftFromLyricsVersion(version: LyricsVersion | null): LyricsDraft {
  return version
    ? cloneLyricsDraft({ sections: version.sections, hookCandidates: version.hook_candidates })
    : { sections: [], hookCandidates: [] };
}

export function createLyricLineId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `line-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function analyzeLyricLine(
  text: string,
  lineId = createLyricLineId(),
  rhymeLabel: string | null = null,
): LyricLine {
  const normalized = text.trim();
  const characters = Array.from(normalized).filter((character) => !/\s/u.test(character));
  const englishWords = normalized.match(englishWordPattern) ?? [];
  const cjkCharacters = normalized.match(cjkPattern) ?? [];
  const syllableCount =
    cjkCharacters.length +
    englishWords.reduce((total, word) => total + estimateEnglishSyllables(word), 0);
  const ending = normalized.match(endingPattern)?.[1]?.toLocaleLowerCase() ?? null;
  const rhymeKey = ending
    ? cjkPattern.test(ending)
      ? ending
      : ending.match(/[aeiouy][a-z]*$/)?.[0] ?? ending.slice(-3)
    : null;
  cjkPattern.lastIndex = 0;
  return {
    line_id: lineId,
    text: normalized,
    rhyme_label: rhymeLabel,
    character_count: characters.length,
    word_count: englishWords.length + cjkCharacters.length,
    syllable_count: syllableCount,
    rhyme_key: rhymeKey,
    stress_positions: Array.from(
      { length: Math.min(8, Math.ceil(syllableCount / 2)) },
      (_, index) => index * 2 + 1,
    ),
  };
}

export function updateLyricLine(
  draft: LyricsDraft,
  sectionId: string,
  lineId: string,
  patch: { text?: string; rhymeLabel?: string | null },
): LyricsDraft {
  return updateSection(draft, sectionId, (section) => ({
    ...section,
    lines: section.lines.map((line) =>
      line.line_id === lineId
        ? analyzeLyricLine(
            patch.text ?? line.text,
            line.line_id,
            patch.rhymeLabel === undefined ? line.rhyme_label : patch.rhymeLabel,
          )
        : line,
    ),
  }));
}

export function addLyricLine(
  draft: LyricsDraft,
  sectionId: string,
  afterLineId?: string,
): LyricsDraft {
  return updateSection(draft, sectionId, (section) => {
    const insertionIndex = afterLineId
      ? Math.max(0, section.lines.findIndex((line) => line.line_id === afterLineId) + 1)
      : section.lines.length;
    const lines = [...section.lines];
    lines.splice(insertionIndex, 0, analyzeLyricLine("", createLyricLineId()));
    return { ...section, lines };
  });
}

export function removeLyricLine(
  draft: LyricsDraft,
  sectionId: string,
  lineId: string,
): LyricsDraft {
  return updateSection(draft, sectionId, (section) =>
    section.lines.length <= 1
      ? section
      : { ...section, lines: section.lines.filter((line) => line.line_id !== lineId) },
  );
}

export function moveLyricLine(
  draft: LyricsDraft,
  sectionId: string,
  lineId: string,
  direction: -1 | 1,
): LyricsDraft {
  return updateSection(draft, sectionId, (section) => {
    const index = section.lines.findIndex((line) => line.line_id === lineId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= section.lines.length) {
      return section;
    }
    const lines = [...section.lines];
    [lines[index], lines[target]] = [lines[target], lines[index]];
    return { ...section, lines };
  });
}

export function updateHookCandidate(
  draft: LyricsDraft,
  hookId: string,
  text: string,
): LyricsDraft {
  return {
    ...draft,
    hookCandidates: draft.hookCandidates.map((hook) =>
      hook.id === hookId ? { ...hook, text } : hook,
    ),
  };
}

export function applyRewriteChanges(
  draft: LyricsDraft,
  changes: LyricRewriteChange[],
  acceptedLineIds: Set<string>,
): LyricsDraft {
  const replacements = new Map(
    changes
      .filter((change) => acceptedLineIds.has(change.line_id))
      .map((change) => [change.line_id, change.after]),
  );
  return {
    ...draft,
    sections: draft.sections.map((section) =>
      synchronizeSection({
        ...section,
        lines: section.lines.map((line) => replacements.get(line.line_id) ?? line),
      }),
    ),
  };
}

export function lyricDiagnostics(
  sections: LyricSection[],
  bannedPhrases: string[],
): LyricDiagnostic[] {
  const diagnostics: LyricDiagnostic[] = [];
  for (const section of sections) {
    for (const line of section.lines) {
      for (const phrase of bannedPhrases) {
        if (phrase && line.text.toLocaleLowerCase().includes(phrase.toLocaleLowerCase())) {
          diagnostics.push({ sectionId: section.section_id, lineId: line.line_id, phrase });
        }
      }
    }
  }
  return diagnostics;
}

export function parseLyricTerms(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/[,，\n]/u)
        .map((term) => term.trim())
        .filter(Boolean),
    ),
  ).slice(0, 50);
}

export function createLyricsHistory(draft: LyricsDraft): LyricsHistory {
  return { past: [], present: cloneLyricsDraft(draft), future: [] };
}

export function pushLyricsHistory(history: LyricsHistory, draft: LyricsDraft): LyricsHistory {
  if (lyricsDraftsEqual(history.present, draft)) {
    return history;
  }
  return {
    past: [...history.past.slice(-49), cloneLyricsDraft(history.present)],
    present: cloneLyricsDraft(draft),
    future: [],
  };
}

export function undoLyricsHistory(history: LyricsHistory): LyricsHistory {
  const previous = history.past.at(-1);
  if (!previous) return history;
  return {
    past: history.past.slice(0, -1),
    present: cloneLyricsDraft(previous),
    future: [cloneLyricsDraft(history.present), ...history.future],
  };
}

export function redoLyricsHistory(history: LyricsHistory): LyricsHistory {
  const next = history.future[0];
  if (!next) return history;
  return {
    past: [...history.past, cloneLyricsDraft(history.present)],
    present: cloneLyricsDraft(next),
    future: history.future.slice(1),
  };
}

export function lyricsDraftsEqual(left: LyricsDraft, right: LyricsDraft): boolean {
  return JSON.stringify(editableLyricsDraft(left)) === JSON.stringify(editableLyricsDraft(right));
}

export function isLyricsDraft(value: unknown): value is LyricsDraft {
  if (!isRecord(value) || !Array.isArray(value.sections) || !Array.isArray(value.hookCandidates)) {
    return false;
  }
  return (
    value.sections.every(
      (section) =>
        isRecord(section) &&
        typeof section.section_id === "string" &&
        typeof section.label === "string" &&
        typeof section.text === "string" &&
        Array.isArray(section.lines) &&
        section.lines.every(
          (line) =>
            isRecord(line) &&
            typeof line.line_id === "string" &&
            typeof line.text === "string" &&
            (line.rhyme_label === null || typeof line.rhyme_label === "string") &&
            typeof line.character_count === "number" &&
            typeof line.word_count === "number" &&
            typeof line.syllable_count === "number" &&
            (line.rhyme_key === null || typeof line.rhyme_key === "string") &&
            Array.isArray(line.stress_positions) &&
            line.stress_positions.every((position) => typeof position === "number"),
        ),
    ) &&
    value.hookCandidates.every(
      (hook) => isRecord(hook) && typeof hook.id === "string" && typeof hook.text === "string",
    )
  );
}

export function cloneLyricsDraft(draft: LyricsDraft): LyricsDraft {
  return {
    sections: draft.sections.map((section) => ({
      ...section,
      lines: section.lines.map((line) => ({
        ...line,
        stress_positions: [...line.stress_positions],
      })),
    })),
    hookCandidates: draft.hookCandidates.map((hook) => ({ ...hook })),
  };
}

function updateSection(
  draft: LyricsDraft,
  sectionId: string,
  update: (section: LyricSection) => LyricSection,
): LyricsDraft {
  return {
    ...draft,
    sections: draft.sections.map((section) =>
      section.section_id === sectionId ? synchronizeSection(update(section)) : section,
    ),
  };
}

function synchronizeSection(section: LyricSection): LyricSection {
  return { ...section, text: section.lines.map((line) => line.text.trim()).filter(Boolean).join("\n") };
}

function estimateEnglishSyllables(word: string): number {
  const normalized = word.toLocaleLowerCase().replaceAll(/[^a-z]/g, "");
  let groups = normalized.match(/[aeiouy]+/g)?.length ?? 0;
  if (
    normalized.endsWith("e") &&
    groups > 1 &&
    !normalized.endsWith("le") &&
    !normalized.endsWith("ye")
  ) {
    groups -= 1;
  }
  return Math.max(1, groups);
}

function editableLyricsDraft(draft: LyricsDraft) {
  return {
    sections: draft.sections.map((section) => ({
      section_id: section.section_id,
      label: section.label,
      lines: section.lines.map((line) => ({
        line_id: line.line_id,
        text: line.text,
        rhyme_label: line.rhyme_label,
      })),
    })),
    hookCandidates: draft.hookCandidates.map((hook) => ({ id: hook.id, text: hook.text })),
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/**
 * Key for the selection/preview reset effect: the version id, so refetched
 * objects with identical content (every loadWorkspace creates fresh
 * identities) do not discard the line the user is reviewing mid-rewrite.
 */
export function selectionResetKey(version: { id: string } | null): string {
  return version?.id ?? "none";
}

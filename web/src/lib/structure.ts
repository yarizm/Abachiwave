import type { StructureSection } from "@/lib/song-specs";

export type StructureSectionDraft = StructureSection & {
  source_section_id?: string | null;
};

export type StructureRename = {
  section_id: string;
  before: string;
  after: string;
};

export type StructureAssetImpact = {
  asset_type: string;
  id: string;
  version_number: number;
  action: "new_version" | "regenerate";
};

export type StructureImpact = {
  added_sections: StructureSection[];
  removed_sections: StructureSection[];
  renamed_sections: StructureRename[];
  reordered: boolean;
  affected_assets: StructureAssetImpact[];
  requires_midi_regeneration: boolean;
  requires_demo_regeneration: boolean;
  warnings: string[];
};

export type StructureCreatedVersion = {
  asset_type: "song_spec" | "lyrics" | "chords" | "arrangement";
  id: string;
  version_number: number;
  parent_version_id: string;
};

export type StructureChangeRequest = {
  source_song_spec_id: string;
  sections: StructureSectionDraft[];
  preview_id?: string;
};

export type StructureChange = {
  preview_id: string;
  status: "preview" | "applied";
  source_song_spec_id: string;
  sections: StructureSection[];
  impact: StructureImpact;
  created_versions: StructureCreatedVersion[];
  created_at: string;
  applied_at: string | null;
};

export type StructureHistory = {
  past: StructureSectionDraft[][];
  present: StructureSectionDraft[];
  future: StructureSectionDraft[][];
};

export function structureEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/structure`;
}

export function validateStructureSections(sections: StructureSectionDraft[]): string | null {
  if (sections.length === 0) {
    return "At least one song section is required.";
  }
  if (sections.some((section) => !section.label.trim())) {
    return "Section labels must not be empty.";
  }
  const ids = sections.map((section) => section.section_id);
  if (new Set(ids).size !== ids.length) {
    return "Section IDs must be unique.";
  }
  return null;
}

export function createStructureSectionId(
  existingIds: string[],
  entropy = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}`,
): string {
  const token = entropy.toLowerCase().replaceAll(/[^a-z0-9]/g, "").slice(0, 12) || "new";
  let candidate = `section-${token}`;
  let suffix = 2;
  while (existingIds.includes(candidate)) {
    candidate = `section-${token}-${suffix}`;
    suffix += 1;
  }
  return candidate;
}

export function moveStructureSection(
  sections: StructureSectionDraft[],
  index: number,
  direction: -1 | 1,
): StructureSectionDraft[] {
  const target = index + direction;
  if (index < 0 || index >= sections.length || target < 0 || target >= sections.length) {
    return sections;
  }
  const next = [...sections];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

export function duplicateStructureSection(
  sections: StructureSectionDraft[],
  index: number,
  sectionId: string,
  label: string,
): StructureSectionDraft[] {
  const source = sections[index];
  if (!source) {
    return sections;
  }
  const duplicate: StructureSectionDraft = {
    section_id: sectionId,
    label,
    source_section_id: source.source_section_id ?? source.section_id,
  };
  return [...sections.slice(0, index + 1), duplicate, ...sections.slice(index + 1)];
}

export function createStructureHistory(sections: StructureSectionDraft[]): StructureHistory {
  return { past: [], present: cloneSections(sections), future: [] };
}

export function pushStructureHistory(
  history: StructureHistory,
  sections: StructureSectionDraft[],
): StructureHistory {
  if (structureSectionsEqual(history.present, sections)) {
    return history;
  }
  return {
    past: [...history.past.slice(-49), cloneSections(history.present)],
    present: cloneSections(sections),
    future: [],
  };
}

export function undoStructureHistory(history: StructureHistory): StructureHistory {
  const previous = history.past.at(-1);
  if (!previous) {
    return history;
  }
  return {
    past: history.past.slice(0, -1),
    present: cloneSections(previous),
    future: [cloneSections(history.present), ...history.future],
  };
}

export function redoStructureHistory(history: StructureHistory): StructureHistory {
  const next = history.future[0];
  if (!next) {
    return history;
  }
  return {
    past: [...history.past, cloneSections(history.present)],
    present: cloneSections(next),
    future: history.future.slice(1),
  };
}

export function structureSectionsEqual(
  left: StructureSectionDraft[],
  right: StructureSectionDraft[],
): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function cloneSections(sections: StructureSectionDraft[]): StructureSectionDraft[] {
  return sections.map((section) => ({ ...section }));
}

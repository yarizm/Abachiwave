export type IdeaIntakeStatus = "needs_clarification" | "ready_for_generation" | "generated";
export type SongSpecStatus = "draft" | "approved" | "superseded";
export type WorkspaceState = "loading" | "empty" | "clarification" | "draft" | "approved";

export type ClarificationQuestion = {
  id: string;
  field: string;
  prompt: string;
  required: boolean;
};

export type StructureSection = {
  section_id: string;
  label: string;
};

export type IdeaIntake = {
  intake_id: string;
  idea: string;
  answers: Record<string, string>;
  status: IdeaIntakeStatus;
  questions: ClarificationQuestion[];
  generation_source: string;
  created_at: string;
  updated_at: string;
};

export type SongSpec = {
  theme: string | null;
  genre: string[] | null;
  language: string | null;
  tempo_bpm: number | null;
  key: string | null;
  time_signature: string | null;
  target_duration_seconds: number | null;
  mood_curve: Record<string, string> | null;
  song_structure: string[] | null;
  structure_sections?: StructureSection[] | null;
};

export type SongSpecVersion = {
  id: string;
  project_id: string;
  intake_id: string | null;
  version_number: number;
  status: SongSpecStatus;
  parent_version_id: string | null;
  approved_at: string | null;
  song_spec: SongSpec;
  missing_required_fields: string[];
  created_at: string;
  updated_at: string;
};

export function intakeEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/intake`;
}

export function latestIntakeEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${intakeEndpoint(apiBaseUrl, projectId)}/latest`;
}

export function songSpecGenerateEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/song-spec/generate`;
}

export function songSpecsEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/song-specs`;
}

export function songSpecVersionEndpoint(
  apiBaseUrl: string,
  projectId: string,
  songSpecId: string,
): string {
  return `${songSpecsEndpoint(apiBaseUrl, projectId)}/${songSpecId}`;
}

export function songSpecApproveEndpoint(
  apiBaseUrl: string,
  projectId: string,
  songSpecId: string,
): string {
  return `${songSpecVersionEndpoint(apiBaseUrl, projectId, songSpecId)}/approve`;
}

export function validateIdea(value: string): string | null {
  if (!value.trim()) {
    return "Song idea is required.";
  }
  if (value.trim().length > 4000) {
    return "Song idea must be 4000 characters or fewer.";
  }
  return null;
}

export function isSongSpecComplete(songSpec: SongSpec): boolean {
  return missingSongSpecFields(songSpec).length === 0;
}

export function missingSongSpecFields(songSpec: SongSpec): string[] {
  const missing: string[] = [];
  for (const key of [
    "theme",
    "genre",
    "language",
    "tempo_bpm",
    "key",
    "time_signature",
    "target_duration_seconds",
    "mood_curve",
    "song_structure",
  ] as const) {
    const value = songSpec[key];
    if (value === null || value === undefined) {
      missing.push(key);
      continue;
    }
    if (Array.isArray(value) && value.length === 0) {
      missing.push(key);
      continue;
    }
    if (typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === 0) {
      missing.push(key);
    }
  }
  return missing;
}

export function sortSongSpecVersions(versions: SongSpecVersion[]): SongSpecVersion[] {
  return [...versions].sort((left, right) => right.version_number - left.version_number);
}

export function workspaceState(input: {
  isLoading: boolean;
  latestIntake: IdeaIntake | null;
  versions: SongSpecVersion[];
}): WorkspaceState {
  if (input.isLoading) {
    return "loading";
  }
  if (input.versions.some((version) => version.status === "approved")) {
    return "approved";
  }
  if (input.versions.length > 0) {
    return "draft";
  }
  if (input.latestIntake?.status === "needs_clarification") {
    return "clarification";
  }
  return "empty";
}

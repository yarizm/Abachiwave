import type { GenerationRun } from "./composition";

export type TextWorkflow = "song_spec" | "lyrics" | "arrangement" | "revision";
export type GenerationCandidateStatus = "pending" | "selected";

export type ProviderCapability = {
  id: string;
  provider_name: string;
  display_name: string;
  capabilities: TextWorkflow[];
  model: string | null;
  default_params: Record<string, unknown>;
  enabled: boolean;
  is_default: boolean;
};

export type GenerationCandidate = {
  id: string;
  project_id: string;
  run_id: string;
  provider_profile_id: string | null;
  prompt_template_version_id: string | null;
  workflow: TextWorkflow;
  candidate_index: number;
  status: GenerationCandidateStatus;
  content: Record<string, unknown>;
  score: number | null;
  source_asset_ids: Record<string, unknown>;
  generation_params: Record<string, unknown>;
  provider_usage: Record<string, unknown>;
  selected_asset_type: string | null;
  selected_asset_id: string | null;
  selected_at: string | null;
  created_at: string;
};

export type CandidateSelection = {
  candidate: GenerationCandidate;
  asset_type: string;
  asset_id: string;
};

export type CandidateGeneratePayload = {
  workflow: TextWorkflow;
  provider_profile_id: string;
  candidate_count: number;
  intake_id?: string;
  song_spec_id?: string;
  feedback?: string;
};

export function providerCapabilitiesEndpoint(apiBaseUrl: string): string {
  return `${apiBaseUrl}/api/v1/providers/capabilities`;
}

export function candidatesEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${apiBaseUrl}/api/v1/projects/${projectId}/candidates`;
}

export function candidateGenerateEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${candidatesEndpoint(apiBaseUrl, projectId)}/generate`;
}

export function candidateSelectEndpoint(
  apiBaseUrl: string,
  projectId: string,
  candidateId: string,
): string {
  return `${candidatesEndpoint(apiBaseUrl, projectId)}/${candidateId}/select`;
}

export function sortGenerationCandidates(
  candidates: GenerationCandidate[],
): GenerationCandidate[] {
  return [...candidates].sort(
    (left, right) =>
      Date.parse(right.created_at) - Date.parse(left.created_at) ||
      left.candidate_index - right.candidate_index,
  );
}

export function defaultProvider(
  providers: ProviderCapability[],
): ProviderCapability | null {
  return providers.find((provider) => provider.is_default) ?? providers[0] ?? null;
}

export function localFallbackProvider(
  providers: ProviderCapability[],
): ProviderCapability | null {
  return providers.find((provider) => provider.provider_name === "local_deterministic") ?? null;
}

export function textGenerationRuns(runs: GenerationRun[]): GenerationRun[] {
  return runs.filter((run) => run.run_type === "text_generation");
}

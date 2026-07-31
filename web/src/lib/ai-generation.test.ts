import assert from "node:assert/strict";
import test from "node:test";

import {
  candidateGenerateEndpoint,
  candidateSelectEndpoint,
  candidatesEndpoint,
  defaultProvider,
  localFallbackProvider,
  providerCapabilitiesEndpoint,
  sortGenerationCandidates,
  type GenerationCandidate,
  type ProviderCapability,
} from "./ai-generation";

const providers: ProviderCapability[] = [
  {
    id: "local",
    provider_name: "local_deterministic",
    display_name: "Local deterministic",
    capabilities: ["song_spec", "lyrics", "arrangement", "revision"],
    model: null,
    default_params: {},
    enabled: true,
    is_default: false,
  },
  {
    id: "server",
    provider_name: "openai_compatible",
    display_name: "Server text provider",
    capabilities: ["song_spec", "lyrics"],
    model: "example",
    default_params: {},
    enabled: true,
    is_default: true,
  },
];

test("AI candidate endpoints are stable", () => {
  assert.equal(providerCapabilitiesEndpoint("http://api"), "http://api/api/v1/providers/capabilities");
  assert.equal(candidatesEndpoint("http://api", "p1"), "http://api/api/v1/projects/p1/candidates");
  assert.equal(
    candidateGenerateEndpoint("http://api", "p1"),
    "http://api/api/v1/projects/p1/candidates/generate",
  );
  assert.equal(
    candidateSelectEndpoint("http://api", "p1", "c1"),
    "http://api/api/v1/projects/p1/candidates/c1/select",
  );
});

test("provider helpers preserve explicit defaults and fallback", () => {
  assert.equal(defaultProvider(providers)?.id, "server");
  assert.equal(localFallbackProvider(providers)?.id, "local");
});

test("candidate sorting keeps newest runs first and candidate order stable", () => {
  const candidate = (id: string, createdAt: string, index: number): GenerationCandidate => ({
    id,
    project_id: "p1",
    run_id: "r1",
    provider_profile_id: "local",
    prompt_template_version_id: "prompt",
    workflow: "song_spec",
    candidate_index: index,
    status: "pending",
    content: {},
    score: 1,
    source_asset_ids: {},
    generation_params: {},
    provider_usage: {},
    selected_asset_type: null,
    selected_asset_id: null,
    selected_at: null,
    created_at: createdAt,
  });
  const sorted = sortGenerationCandidates([
    candidate("old", "2026-07-12T00:00:00Z", 1),
    candidate("new-2", "2026-07-13T00:00:00Z", 2),
    candidate("new-1", "2026-07-13T00:00:00Z", 1),
  ]);
  assert.deepEqual(sorted.map((item) => item.id), ["new-1", "new-2", "old"]);
});

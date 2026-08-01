import assert from "node:assert/strict";
import test from "node:test";

import type { GenerationCandidate, ProviderCapability } from "./ai-generation";
import { loadOptionalWorkspaceData } from "./workspace-api";

const provider = { id: "provider-1" } as ProviderCapability;
const candidate = {
  id: "candidate-1",
  created_at: "2026-01-01T00:00:00Z",
} as GenerationCandidate;

test("optional workspace data preserves providers when candidate loading fails", async () => {
  const result = await loadOptionalWorkspaceData(
    Promise.resolve([provider]),
    Promise.reject(new Error("candidate endpoint unavailable")),
  );

  assert.deepEqual(result.providerProfiles, [provider]);
  assert.deepEqual(result.candidates, []);
  assert.equal(result.optionalErrors.providers, null);
  assert.equal(result.optionalErrors.candidates, "candidate endpoint unavailable");
});

test("optional workspace data preserves candidates when provider loading fails", async () => {
  const result = await loadOptionalWorkspaceData(
    Promise.reject(new Error("provider endpoint unavailable")),
    Promise.resolve([candidate]),
  );

  assert.deepEqual(result.providerProfiles, []);
  assert.deepEqual(result.candidates, [candidate]);
  assert.equal(result.optionalErrors.providers, "provider endpoint unavailable");
  assert.equal(result.optionalErrors.candidates, null);
});

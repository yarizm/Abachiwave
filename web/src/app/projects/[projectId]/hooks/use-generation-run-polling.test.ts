import assert from "node:assert/strict";
import test from "node:test";

import { GenerationRun } from "@/lib/composition";

import { mergeGenerationRunUpdates } from "./use-generation-run-polling";

test("generation run polling merges updates without dropping history", () => {
  const older = run("older", "failed", "2026-01-01T00:00:00Z");
  const active = run("active", "queued", "2026-01-02T00:00:00Z");
  const completed = { ...active, status: "succeeded" as const };

  assert.deepEqual(mergeGenerationRunUpdates([older, active], [completed]), [completed, older]);
});

function run(
  id: string,
  status: GenerationRun["status"],
  createdAt: string,
): GenerationRun {
  return {
    id,
    project_id: "project",
    run_type: "demo_generation",
    status,
    arq_job_id: null,
    input_manifest: {},
    provider_name: "local",
    provider_version: "1",
    provider_params: {},
    error_message: null,
    retry_of_run_id: null,
    demo_id: null,
    result_midi_asset_id: null,
    started_at: null,
    completed_at: null,
    created_at: createdAt,
    updated_at: createdAt,
  };
}

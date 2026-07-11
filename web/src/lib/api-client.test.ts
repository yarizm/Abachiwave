import assert from "node:assert/strict";
import test from "node:test";

import { ApiRequestError, fetchJson } from "./api-client";

test("fetchJson returns typed JSON for successful responses", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => Response.json({ status: "ok" });
  try {
    const result = await fetchJson<{ status: string }>("http://example.test/health", "Health");
    assert.deepEqual(result, { status: "ok" });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("fetchJson exposes API detail, status, and request id", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    Response.json(
      { detail: "Dependency unavailable" },
      { status: 503, headers: { "X-Request-ID": "request-123" } },
    );
  try {
    await assert.rejects(
      fetchJson("http://example.test/health/ready", "Readiness"),
      (error: unknown) => {
        assert.ok(error instanceof ApiRequestError);
        assert.equal(error.message, "Readiness request failed with 503: Dependency unavailable");
        assert.equal(error.status, 503);
        assert.equal(error.requestId, "request-123");
        return true;
      },
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

import assert from "node:assert/strict";
import test from "node:test";

import { ApiRequestError, fetchJson, fetchNoContent } from "./api-client";

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

test("fetchNoContent accepts successful 204 responses without parsing JSON", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(null, { status: 204 });
  try {
    await fetchNoContent("http://example.test/audio-markers/marker-1", "Marker delete", {
      method: "DELETE",
    });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("fetchJson exposes API detail, status, and request id (string detail)", async () => {
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
        assert.equal(error.message, "Dependency unavailable");
        assert.equal(error.status, 503);
        assert.equal(error.requestId, "request-123");
        assert.equal(error.errorCode, null);
        assert.equal(error.hint, null);
        assert.equal(error.fields, null);
        return true;
      },
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("fetchJson extracts error_code, hint from headers and fields from 422 body", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    Response.json(
      {
        detail: "Validation failed",
        error_code: "validation_failed",
        fields: { name: "field required", limit: "Input should be <= 200" },
      },
      {
        status: 422,
        headers: {
          "X-Request-ID": "req-456",
          "X-Error-Code": "validation_failed",
          "X-Error-Hint": "check_required_fields",
        },
      },
    );
  try {
    await assert.rejects(
      fetchJson("http://example.test/projects", "Project create"),
      (error: unknown) => {
        assert.ok(error instanceof ApiRequestError);
        assert.equal(error.status, 422);
        assert.equal(error.errorCode, "validation_failed");
        assert.equal(error.hint, "check_required_fields");
        assert.deepEqual(error.fields, {
          name: "field required",
          limit: "Input should be <= 200",
        });
        return true;
      },
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("fetchJson extracts error_code from X-Error-Code header when body has string detail", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () =>
    Response.json(
      { detail: "SongSpec must be approved before composition generation" },
      {
        status: 409,
        headers: {
          "X-Request-ID": "req-789",
          "X-Error-Code": "song_spec_not_approved",
          "X-Error-Hint": "approve_song_spec",
        },
      },
    );
  try {
    await assert.rejects(
      fetchJson("http://example.test/lyrics/generate", "Lyrics generate"),
      (error: unknown) => {
        assert.ok(error instanceof ApiRequestError);
        assert.equal(error.status, 409);
        assert.equal(error.errorCode, "song_spec_not_approved");
        assert.equal(error.hint, "approve_song_spec");
        assert.equal(error.fields, null);
        assert.equal(
          error.message,
          "[song_spec_not_approved] SongSpec must be approved before composition generation",
        );
        return true;
      },
    );
  } finally {
    globalThis.fetch = originalFetch;
  }
});

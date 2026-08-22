import { randomUUID } from "node:crypto";

import { expect, test } from "@playwright/test";

const apiBaseUrl = process.env.ABACHIWAVE_API_BASE_URL ?? "http://localhost:8000";

test.describe("audio derivatives", () => {
  let projectId = "";

  test.beforeEach(async ({ request }, testInfo) => {
    const projectResponse = await request.post(apiBaseUrl + "/api/v1/projects", {
      data: {
        name: "E2E derivatives " + testInfo.project.name + " " + randomUUID(),
        description: "Playwright audio derivative coverage",
      },
    });
    expect(projectResponse.status()).toBe(201);
    projectId = (await projectResponse.json()).id as string;

    const uploadResponse = await request.post(
      apiBaseUrl + "/api/v1/projects/" + projectId + "/audio-uploads",
      {
        multipart: {
          kind: "reference",
          file: {
            name: "derivative-fixture.wav",
            mimeType: "audio/wav",
            buffer: buildWavBuffer(),
          },
        },
      },
    );
    expect(uploadResponse.status()).toBe(201);
  });

  test.afterEach(async ({ request }) => {
    if (projectId) {
      await request.patch(apiBaseUrl + "/api/v1/projects/" + projectId, {
        data: { status: "archived" },
        maxRetries: 2,
      });
    }
  });

  test("queues PCM WAV normalization from the audio upload row", async ({ page }) => {
    await page.goto("/projects/" + projectId);
    const audioPanel = page.locator("section[aria-labelledby='audio-title']");
    const audioRow = audioPanel.locator(".audio-upload-row").first();
    await expect(audioRow.getByText("derivative-fixture.wav", { exact: true })).toBeVisible();
    await expect(audioRow.getByRole("button", { name: "Create PCM WAV" })).toBeVisible();

    const responsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname.includes("/audio-uploads/") &&
        new URL(response.url()).pathname.endsWith("/derivatives"),
    );
    await audioRow.getByRole("button", { name: "Create PCM WAV" }).click();
    expect((await responsePromise).status()).toBe(202);
    await expect(audioRow.getByRole("button", { name: "Normalizing audio" })).toBeVisible();
  });
});

function buildWavBuffer(): Buffer {
  const sampleRate = 8_000;
  const sampleCount = sampleRate;
  const dataSize = sampleCount * 2;
  const buffer = Buffer.alloc(44 + dataSize);
  buffer.write("RIFF", 0, "ascii");
  buffer.writeUInt32LE(36 + dataSize, 4);
  buffer.write("WAVE", 8, "ascii");
  buffer.write("fmt ", 12, "ascii");
  buffer.writeUInt32LE(16, 16);
  buffer.writeUInt16LE(1, 20);
  buffer.writeUInt16LE(1, 22);
  buffer.writeUInt32LE(sampleRate, 24);
  buffer.writeUInt32LE(sampleRate * 2, 28);
  buffer.writeUInt16LE(2, 32);
  buffer.writeUInt16LE(16, 34);
  buffer.write("data", 36, "ascii");
  buffer.writeUInt32LE(dataSize, 40);
  for (let index = 0; index < sampleCount; index += 1) {
    const sample = Math.round(12_000 * Math.sin((2 * Math.PI * 440 * index) / sampleRate));
    buffer.writeInt16LE(sample, 44 + index * 2);
  }
  return buffer;
}

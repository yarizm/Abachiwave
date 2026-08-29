import { randomUUID } from "node:crypto";

import { expect, request as playwrightRequest, test } from "@playwright/test";

const apiBaseUrl = process.env.ABACHIWAVE_API_BASE_URL ?? "http://localhost:8000";

test.describe("MIDI piano roll", () => {
  let projectId: string;

  test.beforeEach(async () => {
    const request = await playwrightRequest.newContext();
    try {
      projectId = await createStructuredMidiProject(request);
    } finally {
      await request.dispose();
    }
  });

  test.afterEach(async ({ request }) => {
    if (!projectId) return;
    await request.patch(`${apiBaseUrl}/api/v1/projects/${projectId}`, {
      data: { status: "archived" },
      maxRetries: 2,
    });
  });

  test("renders notes and creates immutable edit and transform versions", async ({ page }) => {
    test.setTimeout(180_000);
    await page.goto(`/projects/${projectId}/composition`);
    const midiPanel = page.locator("section[aria-labelledby='midi-title']");
    const canvas = midiPanel.getByRole("application", { name: "MIDI piano roll" });
    await expect(canvas).toBeVisible();
    await expect(midiPanel.getByRole("button", { name: "melody" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    const loopPlayback = midiPanel.getByRole("checkbox", { name: "Loop" });
    await loopPlayback.check();
    await expect(loopPlayback).toBeChecked();

    const sampledColors = await canvas.evaluate((element: HTMLCanvasElement) => {
      const context = element.getContext("2d");
      if (!context) return 0;
      const colors = new Set<string>();
      for (let y = 4; y < element.height; y += 24) {
        for (let x = 4; x < Math.min(element.width, 1000); x += 32) {
          colors.add(Array.from(context.getImageData(x, y, 1, 1).data).join(","));
        }
      }
      return colors.size;
    });
    expect(sampledColors).toBeGreaterThan(2);

    await midiPanel.getByRole("button", { name: "Add note" }).click();
    const saveButton = midiPanel.getByRole("button", { name: "Save MIDI version" });
    await expect(saveButton).toBeEnabled();
    const saveResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === "PATCH" &&
        response.url().includes(`/api/v1/projects/${projectId}/midi-assets/`),
    );
    await saveButton.click();
    expect((await saveResponsePromise).status()).toBe(200);
    await expect(midiPanel.getByText("melody v2", { exact: false }).first()).toBeVisible();

    const transformResponsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        response.url().endsWith(`/api/v1/projects/${projectId}/midi/transform`),
    );
    await midiPanel.getByRole("button", { name: "Quantize" }).click();
    expect((await transformResponsePromise).status()).toBe(201);
    await expect(midiPanel.getByText("melody v3", { exact: false }).first()).toBeVisible();

    await midiPanel.getByRole("checkbox", { name: "Overlay tracks" }).check();
    await expect(midiPanel.getByRole("checkbox", { name: "Overlay tracks" })).toBeChecked();
  });
});

async function createStructuredMidiProject(
  request: Awaited<ReturnType<typeof playwrightRequest.newContext>>,
): Promise<string> {
  const projectResponse = await request.post(`${apiBaseUrl}/api/v1/projects`, {
    data: { name: `Piano Roll ${randomUUID()}`, description: "Playwright MIDI editor" },
  });
  expect(projectResponse.status()).toBe(201);
  const project = (await projectResponse.json()) as { id: string };
  const intakeResponse = await request.post(
    `${apiBaseUrl}/api/v1/projects/${project.id}/intake`,
    {
      data: {
        idea:
          "English pop song about finding confidence at sunrise. " +
          "Verse intimate and chorus uplifting. 120 BPM, C major, 4/4, 3:00, standard structure.",
      },
    },
  );
  expect(intakeResponse.status()).toBe(201);
  const intake = (await intakeResponse.json()) as { intake_id: string };
  const songSpecResponse = await request.post(
    `${apiBaseUrl}/api/v1/projects/${project.id}/song-spec/generate`,
    { data: { intake_id: intake.intake_id } },
  );
  expect(songSpecResponse.status()).toBe(200);
  const songSpec = (await songSpecResponse.json()) as { id: string };
  const approveResponse = await request.post(
    `${apiBaseUrl}/api/v1/projects/${project.id}/song-specs/${songSpec.id}/approve`,
  );
  expect(approveResponse.status()).toBe(200);
  const approved = (await approveResponse.json()) as { id: string };
  const lyricsResponse = await request.post(
    `${apiBaseUrl}/api/v1/projects/${project.id}/lyrics/generate`,
    { data: { song_spec_id: approved.id } },
  );
  expect(lyricsResponse.status()).toBe(201);
  const lyrics = (await lyricsResponse.json()) as { id: string };
  const chordsResponse = await request.post(
    `${apiBaseUrl}/api/v1/projects/${project.id}/chords/generate`,
    { data: { song_spec_id: approved.id, lyrics_version_id: lyrics.id } },
  );
  expect(chordsResponse.status()).toBe(201);
  const chords = (await chordsResponse.json()) as { id: string };
  const midiResponse = await request.post(
    `${apiBaseUrl}/api/v1/projects/${project.id}/midi/generate`,
    {
      data: {
        song_spec_id: approved.id,
        lyrics_version_id: lyrics.id,
        chord_version_id: chords.id,
      },
    },
  );
  expect(midiResponse.status()).toBe(201);
  return project.id;
}

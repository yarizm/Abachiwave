import { randomUUID } from "node:crypto";

import { expect, Page, test } from "@playwright/test";

const apiBaseUrl = process.env.ABACHIWAVE_API_BASE_URL ?? "http://localhost:8000";

type Project = {
  id: string;
  name: string;
};

type AudioUpload = {
  id: string;
  duration_seconds: number;
};

test.describe("audio markers", () => {
  let project: Project;
  let upload: AudioUpload;

  test.beforeEach(async ({ request }, testInfo) => {
    const name = "E2E audio markers " + testInfo.project.name + " " + randomUUID();
    const projectResponse = await request.post(apiBaseUrl + "/api/v1/projects", {
      data: { name, description: "Playwright audio marker coverage" },
    });
    expect(projectResponse.status()).toBe(201);
    project = (await projectResponse.json()) as Project;

    const uploadResponse = await request.post(
      apiBaseUrl + "/api/v1/projects/" + project.id + "/audio-uploads",
      {
        multipart: {
          kind: "reference",
          notes: "Audio marker fixture",
          file: {
            name: "audio-marker-fixture.wav",
            mimeType: "audio/wav",
            buffer: buildWavBuffer(),
          },
        },
      },
    );
    expect(uploadResponse.status()).toBe(201);
    upload = (await uploadResponse.json()) as AudioUpload;
    expect(upload.duration_seconds).toBeGreaterThan(0);
  });

  test.afterEach(async ({ request }) => {
    if (!project?.id) {
      return;
    }
    await request.patch(apiBaseUrl + "/api/v1/projects/" + project.id, {
      data: { status: "archived" },
      maxRetries: 2,
    });
  });

  test("selects a position from the waveform and creates a marker", async ({ page }) => {
    const audioRow = await openAudioRow(page, project);
    const markerEditor = audioRow.locator(".audio-marker-editor");
    const positionInput = markerEditor.getByLabel("Position (seconds)");

    await expect(markerEditor.getByRole("heading", { name: "Audio markers" })).toBeVisible();
    await expect(audioRow.getByLabel("Audio waveform")).toBeVisible();

    const picker = audioRow.getByRole("button", {
      name: "Choose marker position from waveform",
    });
    const pickerBox = await picker.boundingBox();
    expect(pickerBox).not.toBeNull();
    await picker.click({
      position: { x: pickerBox!.width * 0.35, y: Math.max(1, pickerBox!.height / 2) },
    });
    await expect
      .poll(async () => Number(await positionInput.inputValue()))
      .toBeGreaterThan(0.2);
    await expect
      .poll(async () => Number(await positionInput.inputValue()))
      .toBeLessThan(0.5);

    await markerEditor.getByLabel("Marker label").fill("Verse entry");
    await markerEditor.getByLabel("Section ID").fill("verse-1");
    await markerEditor.getByLabel("Marker notes").fill("First vocal entrance");

    const createResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname.endsWith("/audio-uploads/" + upload.id + "/markers"),
    );
    await markerEditor.getByRole("button", { name: "Add marker" }).click();
    expect((await createResponse).status()).toBe(201);

    const markerRow = audioRow.locator(".audio-marker-editor .revision-task-row").first();
    await expect(markerRow.getByLabel("Marker label")).toHaveValue("Verse entry");
    await expect(markerRow.getByLabel("Section ID")).toHaveValue("verse-1");
  });

  test("jumps to, edits, and deletes a marker on desktop and mobile layouts", async ({
    page,
    request,
  }) => {
    const markerResponse = await request.post(
      apiBaseUrl + "/api/v1/projects/" + project.id + "/audio-uploads/" + upload.id + "/markers",
      {
        data: {
          position_seconds: 0.25,
          label: "Verse entry",
          section_id: "verse-1",
          notes: "Seeded marker",
        },
      },
    );
    expect(markerResponse.status()).toBe(201);

    const audioRow = await openAudioRow(page, project);
    const markerButton = audioRow.getByRole("button", {
      name: /Jump to marker: Verse entry/,
    });
    await expect(markerButton).toBeVisible();
    await markerButton.click();

    await expect(audioRow.getByText("Playhead: 0.25s", { exact: true })).toBeVisible();
    const audio = audioRow.locator("audio");
    await expect
      .poll(async () => Number(await audio.evaluate((element) => (element as HTMLAudioElement).currentTime)), {
        timeout: 5_000,
      })
      .toBeGreaterThan(0.1);

    const markerRow = audioRow.locator(".audio-marker-editor .revision-task-row").first();
    await markerRow.getByLabel("Position (seconds)").fill("0.5");
    await markerRow.getByLabel("Marker label").fill("Chorus lift");
    await markerRow.getByLabel("Section ID").fill("chorus-1");

    const updateResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "PATCH" &&
        new URL(response.url()).pathname.includes("/audio-markers/"),
    );
    await markerRow.getByRole("button", { name: "Save marker" }).click();
    expect((await updateResponse).status()).toBe(200);
    await expect(markerRow.getByLabel("Marker label")).toHaveValue("Chorus lift");
    await expect(markerRow.getByLabel("Position (seconds)")).toHaveValue("0.5");

    page.once("dialog", (dialog) => void dialog.accept());
    const deleteResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "DELETE" &&
        new URL(response.url()).pathname.includes("/audio-markers/"),
    );
    await markerRow.getByRole("button", { name: "Delete marker" }).click();
    expect((await deleteResponse).status()).toBe(204);
    await expect(audioRow.locator(".audio-marker-editor .revision-task-row")).toHaveCount(0);
    await expect(
      audioRow.getByText("Add markers to identify sections and analysis ranges."),
    ).toBeVisible();
  });

  test("rejects a marker position outside the WAV duration before POST", async ({ page }) => {
    const audioRow = await openAudioRow(page, project);
    const markerEditor = audioRow.locator(".audio-marker-editor");
    await markerEditor
      .getByLabel("Position (seconds)")
      .fill(String(upload.duration_seconds + 1));
    await markerEditor.getByLabel("Marker label").fill("Invalid point");

    await markerEditor.getByRole("button", { name: "Add marker" }).click();
    await expect(
      markerEditor.getByText("Marker position must be within the audio duration."),
    ).toBeVisible();
    await expect(audioRow.locator(".audio-marker-editor .revision-task-row")).toHaveCount(0);
  });
});

async function openAudioRow(page: Page, project: Project) {
  await page.goto("/projects/" + project.id + "/audio");
  await expect(page.getByRole("heading", { name: project.name })).toBeVisible();
  const audioPanel = page.locator("section[aria-labelledby='audio-title']");
  await expect(audioPanel.getByText("audio-marker-fixture.wav", { exact: true })).toBeVisible();
  return audioPanel.locator(".audio-upload-row").first();
}

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

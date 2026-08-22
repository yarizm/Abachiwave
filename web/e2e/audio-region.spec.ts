import { randomUUID } from "node:crypto";

import { expect, Page, test } from "@playwright/test";

const apiBaseUrl = process.env.ABACHIWAVE_API_BASE_URL ?? "http://localhost:8000";

type Project = {
  id: string;
  name: string;
};

test.describe("audio analysis range", () => {
  let project: Project;
  let songSpecId = "";
  let uploadId = "";

  test.beforeEach(async ({ request }, testInfo) => {
    const projectResponse = await request.post(`${apiBaseUrl}/api/v1/projects`, {
      data: {
        name: `E2E audio region ${testInfo.project.name} ${randomUUID()}`,
        description: "Playwright audio analysis range coverage",
      },
    });
    expect(projectResponse.status()).toBe(201);
    project = (await projectResponse.json()) as Project;

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
    songSpecId = ((await approveResponse.json()) as { id: string }).id;

    const uploadResponse = await request.post(
      `${apiBaseUrl}/api/v1/projects/${project.id}/audio-uploads`,
      {
        multipart: {
          kind: "reference",
          notes: "Audio analysis range fixture",
          file: {
            name: "audio-region-fixture.wav",
            mimeType: "audio/wav",
            buffer: buildWavBuffer(),
          },
        },
      },
    );
    expect(uploadResponse.status()).toBe(201);
    uploadId = ((await uploadResponse.json()) as { id: string }).id;
  });

  test.afterEach(async ({ request }) => {
    if (!project?.id) {
      return;
    }
    await request.patch(`${apiBaseUrl}/api/v1/projects/${project.id}`, {
      data: { status: "archived" },
      maxRetries: 2,
    });
  });

  test("selects a waveform region and sends it in the extraction manifest", async ({ page }) => {
    const audioRow = await openAudioRow(page, project);
    await audioRow.getByRole("button", { name: "Analysis range" }).click();

    const picker = audioRow.getByRole("button", {
      name: "Select analysis range from waveform",
    });
    const pickerBox = await picker.boundingBox();
    expect(pickerBox).not.toBeNull();

    await page.mouse.move(
      pickerBox!.x + pickerBox!.width * 0.2,
      pickerBox!.y + pickerBox!.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      pickerBox!.x + pickerBox!.width * 0.6,
      pickerBox!.y + pickerBox!.height / 2,
      { steps: 4 },
    );
    await page.mouse.up();

    const startInput = audioRow.getByLabel("Range start (seconds)");
    const endInput = audioRow.getByLabel("Range end (seconds)");
    await expect.poll(async () => Number(await startInput.inputValue())).toBeCloseTo(0.2, 1);
    await expect.poll(async () => Number(await endInput.inputValue())).toBeCloseTo(0.6, 1);
    await expect(audioRow.getByRole("button", { name: "Preview selected range" })).toBeEnabled();

    const extractResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname.endsWith(`/audio-uploads/${uploadId}/extract-midi`),
    );
    await audioRow.getByRole("button", { name: "Extract selected range" }).click();
    const response = await extractResponse;
    expect(response.status()).toBe(202);
    expect(response.request().postDataJSON()).toEqual({
      song_spec_id: songSpecId,
      target_kind: "melody",
      analysis_range: {
        start_seconds: Number(await startInput.inputValue()),
        end_seconds: Number(await endInput.inputValue()),
      },
    });
  });
});

async function openAudioRow(page: Page, project: Project) {
  await page.goto(`/projects/${project.id}`);
  await expect(page.getByRole("heading", { name: project.name })).toBeVisible();
  const audioPanel = page.locator("section[aria-labelledby='audio-title']");
  await expect(audioPanel.getByText("audio-region-fixture.wav", { exact: true })).toBeVisible();
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

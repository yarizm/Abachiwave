import { readFile } from "node:fs/promises";

import { expect, Locator, Page, test } from "@playwright/test";

const apiBaseUrl = process.env.ABACHIWAVE_API_BASE_URL ?? "http://localhost:8000";

type Project = {
  id: string;
  name: string;
};

test.describe("project workspace", () => {
  let project: Project;

  test.beforeEach(async ({ request }, testInfo) => {
    const name = `E2E ${testInfo.project.name} ${Date.now()}`;
    const response = await request.post(`${apiBaseUrl}/api/v1/projects`, {
      data: { name, description: "Playwright workspace baseline" },
    });
    expect(response.status()).toBe(201);
    project = (await response.json()) as Project;
  });

  test.afterEach(async ({ request }) => {
    if (!project?.id) {
      return;
    }
    await request.patch(`${apiBaseUrl}/api/v1/projects/${project.id}`, {
      data: { status: "archived" },
    });
  });

  test("finds a project and opens its empty workspace", async ({ page }) => {
    await page.goto("/projects");
    await expect(page.getByRole("heading", { name: "Projects", exact: true })).toBeVisible();

    await page.getByRole("textbox", { name: "Search projects" }).fill(project.name);
    const projectLink = page.getByRole("link", { name: new RegExp(project.name) });
    await expect(projectLink).toBeVisible();
    await projectLink.click();

    await expect(page).toHaveURL(new RegExp(`/projects/${project.id}$`));
    await expect(page.getByRole("heading", { name: project.name })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Project review" })).toBeVisible();
    await expect(page.getByText("Blocked", { exact: false }).first()).toBeVisible();
    await expect(page.getByRole("heading", { name: "Idea intake" })).toBeVisible();
    await expect(page.getByText("No SongSpec draft yet.", { exact: false })).toBeVisible();
    await expect(page.getByRole("button", { name: "Generate lyrics" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Generate WAV demo" })).toBeDisabled();
    await expect(page.getByRole("button", { name: "Export ZIP" })).toBeDisabled();
  });

  test("shows project-name validation without issuing a create", async ({ page }) => {
    await page.goto("/projects");
    await page.getByRole("textbox", { name: "Project name" }).fill("   ");
    await page.getByRole("button", { name: "Create project" }).click();

    await expect(page.getByText("Project name is required.")).toBeVisible();
  });

  test("recovers after a transient intake failure", async ({ page }) => {
    await page.goto(`/projects/${project.id}`);
    await expect(page.getByRole("heading", { name: project.name })).toBeVisible();

    let attempts = 0;
    await page.route(`**/api/v1/projects/${project.id}/intake`, async (route) => {
      if (route.request().method() === "POST" && attempts++ === 0) {
        await route.fulfill({
          contentType: "application/json",
          status: 503,
          body: JSON.stringify({ detail: "Temporary intake outage" }),
        });
        return;
      }
      await route.continue();
    });

    await page.getByRole("textbox", { name: "Song idea" }).fill(completeIdea);
    await page.getByRole("button", { name: "Save intake" }).click();
    await expect(page.getByText("Idea intake request failed with 503", { exact: false })).toBeVisible();

    await runApiAction(
      page,
      page.getByRole("button", { name: "Save intake" }),
      "POST",
      `/api/v1/projects/${project.id}/intake`,
      201,
    );
    await expect(page.getByRole("button", { name: "Generate SongSpec draft" })).toBeEnabled();
  });

  test("runs the complete deterministic MVP workflow in the browser", async ({ page, request }, testInfo) => {
    test.skip(testInfo.project.name !== "desktop-chromium", "The full generation chain runs once on desktop.");
    test.setTimeout(240_000);

    const projectName = `Browser MVP ${Date.now()}`;
    let browserProjectId: string | null = null;

    try {
      await page.goto("/projects");
      await page.getByRole("textbox", { name: "Project name" }).fill(projectName);
      await page
        .getByRole("textbox", { name: "Description" })
        .fill("Playwright deterministic end-to-end workflow");
      const createResponse = await runApiAction(
        page,
        page.getByRole("button", { name: "Create project" }),
        "POST",
        "/api/v1/projects",
        201,
      );
      browserProjectId = ((await createResponse.json()) as Project).id;

      await page.getByRole("textbox", { name: "Search projects" }).fill(projectName);
      await page.getByRole("link", { name: new RegExp(projectName) }).click();
      await expect(page).toHaveURL(new RegExp(`/projects/${browserProjectId}$`));
      await expect(page.getByRole("heading", { name: projectName })).toBeVisible();

      await page.getByRole("textbox", { name: "Song idea" }).fill(completeIdea);
      await runApiAction(
        page,
        page.getByRole("button", { name: "Save intake" }),
        "POST",
        `/api/v1/projects/${browserProjectId}/intake`,
        201,
      );
      await runApiAction(
        page,
        page.getByRole("button", { name: "Generate SongSpec draft" }),
        "POST",
        `/api/v1/projects/${browserProjectId}/song-spec/generate`,
        200,
      );
      const approveButton = page.getByRole("button", { name: "Approve", exact: true });
      await expect(approveButton).toBeEnabled();
      await runApiAction(page, approveButton, "POST", "/approve", 200);

      await runApiAction(
        page,
        page.getByRole("button", { name: "Generate lyrics" }),
        "POST",
        `/api/v1/projects/${browserProjectId}/lyrics/generate`,
        201,
      );
      await runApiAction(
        page,
        page.getByRole("button", { name: "Generate chords" }),
        "POST",
        `/api/v1/projects/${browserProjectId}/chords/generate`,
        201,
      );
      await runApiAction(
        page,
        page.getByRole("button", { name: "Generate MIDI" }),
        "POST",
        `/api/v1/projects/${browserProjectId}/midi/generate`,
        201,
      );
      await runApiAction(
        page,
        page.getByRole("button", { name: "Generate arrangement" }),
        "POST",
        `/api/v1/projects/${browserProjectId}/arrangement/generate`,
        201,
      );

      const commentPanel = page.locator("section[aria-labelledby='comments-title']");
      await commentPanel
        .getByRole("textbox", { name: "Comment" })
        .fill("Confirm the chorus lift before handoff.");
      const commentResponse = await runApiAction(
        page,
        commentPanel.getByRole("button", { name: "Add comment" }),
        "POST",
        `/api/v1/projects/${browserProjectId}/comments`,
        201,
      );
      const commentId = ((await commentResponse.json()) as { id: string }).id;
      await runApiAction(
        page,
        commentPanel.getByRole("button", { name: "Resolve" }),
        "PATCH",
        `/api/v1/projects/${browserProjectId}/comments/${commentId}`,
        200,
      );
      await expect(commentPanel.getByText("resolved", { exact: true })).toBeVisible();

      const demoPanel = page.locator("section[aria-labelledby='demo-title']");
      await runApiAction(
        page,
        demoPanel.getByRole("button", { name: "Generate WAV demo" }),
        "POST",
        `/api/v1/projects/${browserProjectId}/demo/generate`,
        202,
      );
      await expect(demoPanel.locator("audio")).toHaveCount(1, { timeout: 120_000 });
      const demoBytes = await downloadBytes(
        page,
        demoPanel.getByRole("button", { name: "Download" }).first(),
      );
      expect(demoBytes.subarray(0, 4).toString("ascii")).toBe("RIFF");
      expect(demoBytes.subarray(8, 12).toString("ascii")).toBe("WAVE");

      const revisionPanel = page.locator("section[aria-labelledby='revision-title']");
      await revisionPanel
        .getByRole("textbox", { name: "Feedback" })
        .fill("Make the chorus lyric stronger.");
      await runApiAction(
        page,
        revisionPanel.getByRole("button", { name: "Plan revision" }),
        "POST",
        `/api/v1/projects/${browserProjectId}/revisions`,
        201,
      );
      await expect(revisionPanel.getByRole("heading", { name: "Impact preview" })).toBeVisible();
      await runApiAction(
        page,
        revisionPanel.getByRole("button", { name: "Apply", exact: true }),
        "POST",
        "/apply",
        200,
      );
      const lyricsVersionTool = revisionPanel
        .locator(".version-tool-row")
        .filter({ hasText: "Lyrics" });
      await runApiAction(
        page,
        lyricsVersionTool.getByRole("button", { name: "Diff" }),
        "GET",
        "/versions/diff",
        200,
      );
      await expect(revisionPanel.getByText("Lyrics", { exact: true }).last()).toBeVisible();
      await runApiAction(
        page,
        lyricsVersionTool.getByRole("button", { name: "Restore" }),
        "POST",
        `/api/v1/projects/${browserProjectId}/versions/restore`,
        200,
      );

      const audioPanel = page.locator("section[aria-labelledby='audio-title']");
      await audioPanel.getByLabel("WAV file").setInputFiles({
        name: "browser-humming.wav",
        mimeType: "audio/wav",
        buffer: buildWavBuffer(),
      });
      await audioPanel
        .getByRole("textbox", { name: "Notes" })
        .first()
        .fill("Browser humming fixture");
      await runApiAction(
        page,
        audioPanel.getByRole("button", { name: "Upload WAV" }),
        "POST",
        `/api/v1/projects/${browserProjectId}/audio-uploads`,
        201,
      );
      await expect(audioPanel.getByText("browser-humming.wav")).toBeVisible();
      await expect(audioPanel.getByLabel("Audio waveform")).toBeVisible();
      await runApiAction(
        page,
        audioPanel.getByRole("button", { name: "Extract MIDI" }),
        "POST",
        "/extract-midi",
        202,
      );
      await expect(audioPanel.getByText("MIDI ready:", { exact: false })).toBeVisible({
        timeout: 120_000,
      });
      const midiPanel = page.locator("section[aria-labelledby='midi-title']");
      const midiBytes = await downloadBytes(
        page,
        midiPanel.getByRole("button", { name: "Download" }).first(),
      );
      expect(midiBytes.subarray(0, 4).toString("ascii")).toBe("MThd");

      const exportPanel = page.locator("section[aria-labelledby='export-title']");
      await runApiAction(
        page,
        exportPanel.getByRole("button", { name: "Export ZIP" }),
        "POST",
        `/api/v1/projects/${browserProjectId}/exports`,
        201,
      );
      const exportBytes = await downloadBytes(
        page,
        exportPanel.getByRole("button", { name: "Download" }).first(),
      );
      expect(exportBytes.subarray(0, 2).toString("ascii")).toBe("PK");

      await runApiAction(
        page,
        page.getByRole("button", { name: "Archive project" }),
        "PATCH",
        `/api/v1/projects/${browserProjectId}`,
        200,
      );
      await expect(page.getByText("archived", { exact: true }).first()).toBeVisible();
      await runApiAction(
        page,
        page.getByRole("button", { name: "Restore project" }),
        "PATCH",
        `/api/v1/projects/${browserProjectId}`,
        200,
      );
      await expect(page.getByText("active", { exact: true }).first()).toBeVisible();
    } finally {
      if (browserProjectId) {
        await request.patch(`${apiBaseUrl}/api/v1/projects/${browserProjectId}`, {
          data: { status: "archived" },
        });
      }
    }
  });
});

const completeIdea =
  "Chinese indie rock song about riding home late at night. " +
  "Verse restrained and lonely, chorus lifting and hopeful. " +
  "128 BPM, E major, 4/4, 3:30, standard structure.";

async function runApiAction(
  page: Page,
  action: Locator,
  method: string,
  pathSuffix: string,
  expectedStatus: number,
  requiredPathFragment?: string,
) {
  const responsePromise = page.waitForResponse(
    (response) => {
      const path = new URL(response.url()).pathname;
      return (
        response.request().method() === method &&
        path.endsWith(pathSuffix) &&
        (!requiredPathFragment || path.includes(requiredPathFragment))
      );
    },
    { timeout: 120_000 },
  );
  await action.click();
  const response = await responsePromise;
  expect(response.status()).toBe(expectedStatus);
  return response;
}

async function downloadBytes(page: Page, link: Locator): Promise<Buffer> {
  await expect(link).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await link.click();
  const download = await downloadPromise;
  const path = await download.path();
  expect(path).not.toBeNull();
  return readFile(path!);
}

function buildWavBuffer(): Buffer {
  const sampleRate = 8000;
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
    const sample = Math.round(12000 * Math.sin((2 * Math.PI * 440 * index) / sampleRate));
    buffer.writeInt16LE(sample, 44 + index * 2);
  }
  return buffer;
}

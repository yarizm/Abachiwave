import { randomUUID } from "node:crypto";

import { expect, Page, test } from "@playwright/test";

const apiBaseUrl = process.env.ABACHIWAVE_API_BASE_URL ?? "http://localhost:8000";

type Project = {
  id: string;
  name: string;
};

type AudioUpload = {
  id: string;
  checksum: string;
};

test.describe("reference audio analysis", () => {
  let project: Project;
  let upload: AudioUpload;
  let approvedSongSpecId = "";

  test.beforeEach(async ({ request }, testInfo) => {
    const projectResponse = await request.post(`${apiBaseUrl}/api/v1/projects`, {
      data: {
        name: `E2E reference analysis ${testInfo.project.name} ${randomUUID()}`,
        description: "Playwright reference analysis coverage",
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
            "Verse intimate and chorus uplifting. 128 BPM, E major, 4/4, 3:00, standard structure.",
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
    approvedSongSpecId = ((await approveResponse.json()) as { id: string }).id;

    const uploadResponse = await request.post(
      `${apiBaseUrl}/api/v1/projects/${project.id}/audio-uploads`,
      {
        multipart: {
          kind: "reference",
          notes: "Reference analysis fixture",
          file: {
            name: "reference-analysis-fixture.wav",
            mimeType: "audio/wav",
            buffer: buildWavBuffer(),
          },
        },
      },
    );
    expect(uploadResponse.status()).toBe(201);
    upload = (await uploadResponse.json()) as AudioUpload;
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

  test("shows a traceable candidate and queues the selected waveform range", async ({ page }) => {
    const analysisId = randomUUID();
    const applyRequests: Array<Record<string, unknown>> = [];
    const extractionRequests: Array<Record<string, unknown>> = [];
    await page.route(
      `**/api/v1/projects/${project.id}/audio-uploads/${upload.id}/analyses**`,
      async (route) => {
        if (route.request().method() !== "GET") {
          await route.continue();
          return;
        }
        await route.fulfill({
          contentType: "application/json",
          status: 200,
          body: JSON.stringify([analysisFixture(project.id, upload, analysisId)]),
        });
      },
    );
    await page.route(
      `**/api/v1/projects/${project.id}/reference-analyses/${analysisId}/apply`,
      async (route) => {
        const payload = route.request().postDataJSON() as Record<string, unknown>;
        applyRequests.push(payload);
        const applied = payload.confirm === true;
        await route.fulfill({
          contentType: "application/json",
          status: 200,
          body: JSON.stringify({
            analysis_id: analysisId,
            source_song_spec_id: approvedSongSpecId,
            selected_fields: ["tempo_bpm", "key"],
            changes: [
              {
                field: "tempo_bpm",
                current_value: 128,
                candidate_value: 120,
                confidence: 0.5,
              },
              {
                field: "key",
                current_value: "E major",
                candidate_value: "A major",
                confidence: 0.62,
              },
            ],
            affected_asset_counts: { lyrics: 0, chords: 0, midi: 0, arrangements: 0 },
            warnings: [
              "A new SongSpec draft will be created; the approved version remains current until approval.",
              "Existing lyrics, chords, MIDI, and arrangements remain linked to the source SongSpec.",
            ],
            requires_confirmation: !applied,
            applied,
            new_song_spec_id: applied ? randomUUID() : null,
            new_song_spec_version: applied ? 2 : null,
          }),
        });
      },
    );
    await page.route(
      `**/api/v1/projects/${project.id}/audio-uploads/${upload.id}/extract-midi`,
      async (route) => {
        const payload = route.request().postDataJSON() as Record<string, unknown>;
        extractionRequests.push(payload);
        const now = new Date().toISOString();
        await route.fulfill({
          contentType: "application/json",
          status: 202,
          body: JSON.stringify({
            id: randomUUID(),
            project_id: project.id,
            run_type: "audio_to_midi",
            status: "queued",
            arq_job_id: randomUUID(),
            input_manifest: {
              audio_upload_id: upload.id,
              song_spec_id: approvedSongSpecId,
              target_kind: "melody",
              reference_analysis_id: analysisId,
              analysis_range: { mode: "full", start_seconds: 0, end_seconds: 1 },
            },
            provider_name: "spotify_basic_pitch",
            provider_version: "0.4.0",
            provider_params: {},
            provider_usage: {},
            error_code: null,
            error_message: null,
            retry_of_run_id: null,
            result_midi_asset_id: null,
            demo_id: null,
            started_at: null,
            completed_at: null,
            created_at: now,
            updated_at: now,
          }),
        });
      },
    );
    const audioRow = await openAudioRow(page, project);
    const candidate = audioRow.getByRole("region", { name: "Reference analysis candidate" });
    await expect(candidate).toContainText("120.0 BPM");
    await expect(candidate).toContainText("A major");
    await expect(candidate).toContainText("local_deterministic_reference_analysis 1.0");
    await expect(candidate).toContainText(
      "This analysis is a candidate and has not changed the SongSpec or current assets.",
    );
    await expect(audioRow).toContainText("MIDI source: analysis v1");
    await audioRow.getByRole("button", { name: "Extract MIDI" }).click();
    await expect.poll(() => extractionRequests.length).toBe(1);
    expect(extractionRequests[0]).toEqual({
      song_spec_id: approvedSongSpecId,
      target_kind: "melody",
      reference_analysis_id: analysisId,
    });
    await candidate.getByRole("checkbox", { name: "Tempo" }).check();
    await candidate.getByRole("checkbox", { name: "Key / mode" }).check();
    await candidate.getByRole("button", { name: "Preview selected fields" }).click();
    await expect(candidate).toContainText("128 → 120");
    await expect(candidate).toContainText("E major → A major");
    await candidate.getByRole("button", { name: "Confirm new SongSpec draft" }).click();
    await expect(candidate).toContainText("Created SongSpec v2");
    expect(applyRequests).toEqual([
      {
        song_spec_id: approvedSongSpecId,
        fields: ["tempo_bpm", "key"],
        confirm: false,
      },
      {
        song_spec_id: approvedSongSpecId,
        fields: ["tempo_bpm", "key"],
        confirm: true,
      },
    ]);

    await audioRow.getByRole("button", { name: "Analysis range" }).click();
    const picker = audioRow.getByRole("button", {
      name: "Select analysis range from waveform",
    });
    const pickerBox = await picker.boundingBox();
    expect(pickerBox).not.toBeNull();
    await page.mouse.move(
      pickerBox!.x + pickerBox!.width * 0.25,
      pickerBox!.y + pickerBox!.height / 2,
    );
    await page.mouse.down();
    await page.mouse.move(
      pickerBox!.x + pickerBox!.width * 0.65,
      pickerBox!.y + pickerBox!.height / 2,
      { steps: 4 },
    );
    await page.mouse.up();

    const startInput = audioRow.getByLabel("Range start (seconds)");
    const endInput = audioRow.getByLabel("Range end (seconds)");
    const responsePromise = page.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname.endsWith(`/audio-uploads/${upload.id}/analyze`),
    );
    await audioRow.getByRole("button", { name: "Analyze selected range" }).click();
    const response = await responsePromise;
    expect(response.status()).toBe(202);
    expect(response.request().postDataJSON()).toEqual({
      analysis_range: {
        start_seconds: Number(await startInput.inputValue()),
        end_seconds: Number(await endInput.inputValue()),
      },
    });
  });
});

async function openAudioRow(page: Page, project: Project) {
  await page.goto(`/projects/${project.id}/audio`);
  await expect(page.getByRole("heading", { name: project.name })).toBeVisible();
  const audioPanel = page.locator("section[aria-labelledby='audio-title']");
  await expect(
    audioPanel.getByText("reference-analysis-fixture.wav", { exact: true }),
  ).toBeVisible();
  return audioPanel.locator(".audio-upload-row").first();
}

function analysisFixture(projectId: string, upload: AudioUpload, analysisId: string) {
  return {
    id: analysisId,
    project_id: projectId,
    audio_upload_id: upload.id,
    audio_derivative_id: null,
    run_id: randomUUID(),
    version_number: 1,
    source_checksum: upload.checksum,
    analysis_range: { mode: "full", start_seconds: 0, end_seconds: 1 },
    tempo_bpm: 120,
    beat_grid: [0, 0.5, 1],
    time_signature: { value: "4/4", confidence: 0.35 },
    key_candidate: { tonic: "A", mode: "major", value: "A major", confidence: 0.62 },
    pitch_range: {
      low_midi: 69,
      high_midi: 69,
      low_note: "A4",
      high_note: "A4",
      confidence: 0.72,
    },
    loudness: {
      integrated_dbfs: -9.5,
      peak_dbfs: -3.2,
      dynamic_range_db: 4.1,
      curve: [{ time_seconds: 0.5, dbfs: -9.5 }],
      confidence: 0.78,
    },
    structure_sections: [
      { label: "main", start_seconds: 0, end_seconds: 1, confidence: 0.3 },
    ],
    chord_candidates: [
      { symbol: "A", start_seconds: 0, end_seconds: 1, confidence: 0.54 },
    ],
    instrument_tags: [{ label: "lead_vocal_or_synth", confidence: 0.67 }],
    energy_curve: [
      { time_seconds: 0.25, value: 0.5 },
      { time_seconds: 0.75, value: 1 },
    ],
    production_features: [
      { label: "channel_layout", value: "mono", confidence: 1 },
    ],
    confidence: { tempo: 0.5, energy: 0.7, overall: 0.58 },
    provider_name: "local_deterministic_reference_analysis",
    provider_version: "1.0",
    provider_params: { algorithm: "pcm_energy_autocorrelation_v1" },
    created_at: "2026-08-09T00:00:00Z",
  };
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

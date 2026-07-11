"use client";

import { Archive, ArchiveRestore, Music2, Save, Upload, XCircle } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { DownloadButton } from "@/components/workspace/download-button";
import { Waveform } from "@/components/workspace/waveform";
import { formatBytes } from "@/components/workspace/workspace-format";
import {
  AudioUpload,
  AudioUploadKind,
  AudioUploadStatus,
  GenerationRun,
  audioUploadDownloadEndpoint,
  audioUploadStatusActionLabel,
  canCancelRun,
  isRunActive,
} from "@/lib/composition";
import { normalizeApiBaseUrl } from "@/lib/projects";

export type AudioUploadUpdatePayload = {
  kind?: AudioUploadKind;
  notes?: string | null;
  status?: AudioUploadStatus;
};

type AudioWorkspaceProps = {
  approvedSongSpecId: string | null;
  file: File | null;
  isSaving: boolean;
  kind: AudioUploadKind;
  notes: string;
  onCancel: (runId: string) => void;
  onExtract: (audioUploadId: string) => void;
  onFileChange: (file: File | null) => void;
  onKindChange: (kind: AudioUploadKind) => void;
  onNotesChange: (notes: string) => void;
  onUpdateUpload: (audioUploadId: string, payload: AudioUploadUpdatePayload) => void;
  onUpload: (event: FormEvent<HTMLFormElement>) => void;
  projectId: string;
  runs: GenerationRun[];
  uploads: AudioUpload[];
};

const apiBaseUrl = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL);

export function AudioWorkspace({
  approvedSongSpecId,
  file,
  isSaving,
  kind,
  notes,
  onCancel,
  onExtract,
  onFileChange,
  onKindChange,
  onNotesChange,
  onUpdateUpload,
  onUpload,
  projectId,
  runs,
  uploads,
}: AudioWorkspaceProps) {
  const activeUploadIds = useMemo(
    () =>
      new Set(
        runs
          .filter(isRunActive)
          .map((run) => manifestString(run.input_manifest, "audio_upload_id"))
          .filter((value): value is string => value !== null),
      ),
    [runs],
  );
  return (
    <section className="panel audio-panel" aria-labelledby="audio-title">
      <div className="section-heading">
        <h2 id="audio-title">Audio</h2>
        <span className="badge">{uploads.length}</span>
      </div>
      <form className="form audio-upload-form" onSubmit={onUpload}>
        <div className="form-row">
          <div className="field">
            <label htmlFor="audio-file">WAV file</label>
            <input
              accept="audio/wav,audio/x-wav,.wav"
              id="audio-file"
              onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
              type="file"
            />
          </div>
          <div className="field">
            <label htmlFor="audio-kind">Kind</label>
            <select
              id="audio-kind"
              onChange={(event) => onKindChange(event.target.value as AudioUploadKind)}
              value={kind}
            >
              <option value="humming">Humming</option>
              <option value="reference">Reference</option>
              <option value="scratch">Scratch</option>
              <option value="other">Other</option>
            </select>
          </div>
        </div>
        <div className="field">
          <label htmlFor="audio-notes">Notes</label>
          <textarea
            id="audio-notes"
            onChange={(event) => onNotesChange(event.target.value)}
            placeholder="Chorus melody sketch, reference groove, or scratch idea..."
            value={notes}
          />
        </div>
        <button className="button" disabled={isSaving || !file} type="submit">
          <Upload aria-hidden="true" size={18} />
          Upload WAV
        </button>
      </form>

      {runs.length ? (
        <div className="run-list">
          {runs.slice(0, 4).map((run) => (
            <div className="run-row" key={run.id}>
              <div>
                <strong>{run.provider_name}</strong>
                <p className="meta">
                  {run.status} - {new Date(run.created_at).toLocaleString()}
                </p>
                {run.result_midi_asset_id ? (
                  <p className="meta">MIDI ready: {run.result_midi_asset_id.slice(0, 8)}</p>
                ) : null}
                {run.error_message ? <p className="error">{run.error_message}</p> : null}
              </div>
              {canCancelRun(run) ? (
                <button
                  className="button secondary icon-button"
                  disabled={isSaving}
                  onClick={() => onCancel(run.id)}
                  type="button"
                >
                  <XCircle aria-hidden="true" size={18} />
                  Cancel
                </button>
              ) : (
                <span className="badge">{run.result_midi_asset_id ? "midi ready" : run.status}</span>
              )}
            </div>
          ))}
        </div>
      ) : null}

      {uploads.length ? (
        <div className="audio-upload-list">
          {uploads.map((upload) => (
            <AudioUploadRow
              approvedSongSpecId={approvedSongSpecId}
              isExtracting={activeUploadIds.has(upload.id)}
              isSaving={isSaving}
              key={upload.id}
              onExtract={onExtract}
              onUpdateUpload={onUpdateUpload}
              projectId={projectId}
              upload={upload}
            />
          ))}
        </div>
      ) : (
        <p className="empty">Uploaded WAV sketches and references will appear here.</p>
      )}
    </section>
  );
}

function AudioUploadRow({
  approvedSongSpecId,
  isExtracting,
  isSaving,
  onExtract,
  onUpdateUpload,
  projectId,
  upload,
}: {
  approvedSongSpecId: string | null;
  isExtracting: boolean;
  isSaving: boolean;
  onExtract: (audioUploadId: string) => void;
  onUpdateUpload: (audioUploadId: string, payload: AudioUploadUpdatePayload) => void;
  projectId: string;
  upload: AudioUpload;
}) {
  const [kindDraft, setKindDraft] = useState<AudioUploadKind>(upload.kind);
  const [notesDraft, setNotesDraft] = useState(upload.notes ?? "");
  const StatusIcon = upload.status === "archived" ? ArchiveRestore : Archive;
  const canExtract = Boolean(approvedSongSpecId) && upload.status === "available" && !isExtracting;

  useEffect(() => {
    setKindDraft(upload.kind);
    setNotesDraft(upload.notes ?? "");
  }, [upload.kind, upload.notes]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onUpdateUpload(upload.id, {
      kind: kindDraft,
      notes: notesDraft.trim() || null,
    });
  }

  function handleStatusToggle() {
    onUpdateUpload(upload.id, {
      status: upload.status === "archived" ? "available" : "archived",
    });
  }

  return (
    <div className={`audio-upload-row audio-upload-${upload.status}`}>
      <div className="audio-upload-main">
        <div className="section-heading">
          <div>
            <strong>{upload.filename}</strong>
            <p className="meta">
              {upload.duration_seconds.toFixed(2)}s - {upload.sample_rate} Hz -{" "}
              {formatBytes(upload.size_bytes)}
            </p>
          </div>
          <div className="badge-row">
            <span className="badge">{upload.kind}</span>
            <span className={`badge audio-status-${upload.status}`}>{upload.status}</span>
          </div>
        </div>
        <Waveform peaks={upload.waveform_peaks} />
        <audio
          controls
          preload="none"
          src={audioUploadDownloadEndpoint(apiBaseUrl, projectId, upload.id)}
        />
        <form className="audio-upload-editor" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor={`audio-kind-${upload.id}`}>Kind</label>
            <select
              disabled={isSaving}
              id={`audio-kind-${upload.id}`}
              onChange={(event) => setKindDraft(event.target.value as AudioUploadKind)}
              value={kindDraft}
            >
              <option value="humming">Humming</option>
              <option value="reference">Reference</option>
              <option value="scratch">Scratch</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor={`audio-notes-${upload.id}`}>Notes</label>
            <textarea
              disabled={isSaving}
              id={`audio-notes-${upload.id}`}
              maxLength={2000}
              onChange={(event) => setNotesDraft(event.target.value)}
              value={notesDraft}
            />
          </div>
          <button className="button secondary" disabled={isSaving} type="submit">
            <Save aria-hidden="true" size={18} />
            Save
          </button>
        </form>
      </div>
      <div className="audio-upload-actions">
        <DownloadButton
          filename={upload.filename}
          url={audioUploadDownloadEndpoint(apiBaseUrl, projectId, upload.id)}
        />
        <button
          className="button secondary icon-button"
          disabled={isSaving}
          onClick={handleStatusToggle}
          type="button"
        >
          <StatusIcon aria-hidden="true" size={18} />
          {audioUploadStatusActionLabel(upload.status)}
        </button>
        <button
          className="button secondary icon-button"
          disabled={!canExtract || isSaving}
          onClick={() => onExtract(upload.id)}
          type="button"
        >
          <Music2 aria-hidden="true" size={18} />
          {isExtracting ? "Extracting" : "Extract MIDI"}
        </button>
      </div>
    </div>
  );
}

function manifestString(manifest: Record<string, unknown>, key: string): string | null {
  const value = manifest[key];
  return typeof value === "string" ? value : null;
}

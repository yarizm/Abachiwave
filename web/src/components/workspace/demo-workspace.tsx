"use client";

import { Music2, RefreshCw, XCircle } from "lucide-react";

import { DownloadButton } from "@/components/workspace/download-button";
import { Waveform } from "@/components/workspace/waveform";
import { formatBytes, formatPrerequisite } from "@/components/workspace/workspace-format";
import {
  AssetTree,
  AudioDemoVersion,
  GenerationRun,
  canCancelRun,
  canRetryRun,
  demoDownloadEndpoint,
  isRunActive,
} from "@/lib/composition";
import { normalizeApiBaseUrl } from "@/lib/projects";

type DemoWorkspaceProps = {
  assetTree: AssetTree | null;
  canGenerate: boolean;
  demos: AudioDemoVersion[];
  isSaving: boolean;
  onCancel: (runId: string) => void;
  onGenerate: () => void;
  onRetry: (runId: string) => void;
  projectId: string;
  runs: GenerationRun[];
};

const apiBaseUrl = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL);

export function DemoWorkspace({
  assetTree,
  canGenerate,
  demos,
  isSaving,
  onGenerate,
  onCancel,
  onRetry,
  projectId,
  runs,
}: DemoWorkspaceProps) {
  const missing = assetTree?.missing_prerequisites ?? [];
  const activeRuns = runs.filter(isRunActive);
  return (
    <section className="panel demo-panel" aria-labelledby="demo-title">
      <div className="section-heading">
        <h2 id="demo-title">Demo</h2>
        <span className="badge">{demos.length}</span>
      </div>
      <button
        className="button secondary full-width"
        disabled={!canGenerate || isSaving}
        onClick={onGenerate}
        type="button"
      >
        <Music2 aria-hidden="true" size={18} />
        Generate WAV demo
      </button>
      {activeRuns.length ? (
        <p className="empty">Demo generation is running. Status refreshes automatically.</p>
      ) : null}
      {missing.length ? (
        <p className="empty">Missing: {missing.map(formatPrerequisite).join(", ")}</p>
      ) : null}
      {runs.length ? (
        <div className="run-list">
          {runs.slice(0, 5).map((run) => (
            <div className="run-row" key={run.id}>
              <div>
                <strong>{run.provider_name}</strong>
                <p className="meta">
                  {run.status} - {new Date(run.created_at).toLocaleString()}
                </p>
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
              ) : canRetryRun(run) ? (
                <button
                  className="button secondary icon-button"
                  disabled={isSaving}
                  onClick={() => onRetry(run.id)}
                  type="button"
                >
                  <RefreshCw aria-hidden="true" size={18} />
                  Retry
                </button>
              ) : (
                <span className="badge">{run.demo_id ? "demo ready" : run.status}</span>
              )}
            </div>
          ))}
        </div>
      ) : null}
      {demos.length >= 2 ? (
        <div className="compare-grid" aria-label="Demo comparison">
          {demos.slice(0, 2).map((demo) => (
            <div className="compare-card" key={`compare-${demo.id}`}>
              <strong>Demo v{demo.version_number}</strong>
              <p className="meta">
                {demo.duration_seconds}s - {formatBytes(demo.size_bytes)}
              </p>
              <Waveform peaks={demo.waveform_peaks} />
              <audio
                controls
                preload="none"
                src={demoDownloadEndpoint(apiBaseUrl, projectId, demo.id)}
              />
            </div>
          ))}
        </div>
      ) : null}
      {demos.length ? (
        <div className="asset-list">
          {demos.map((demo) => (
            <div className="demo-row" key={demo.id}>
              <div>
                <strong>{demo.filename}</strong>
                <p className="meta">
                  v{demo.version_number} - {demo.duration_seconds}s - {formatBytes(demo.size_bytes)}
                </p>
                <Waveform peaks={demo.waveform_peaks} />
              </div>
              <audio
                controls
                preload="none"
                src={demoDownloadEndpoint(apiBaseUrl, projectId, demo.id)}
              />
              <DownloadButton
                filename={demo.filename}
                url={demoDownloadEndpoint(apiBaseUrl, projectId, demo.id)}
              />
            </div>
          ))}
        </div>
      ) : (
        <p className="empty">Generated WAV demos will appear here for browser playback.</p>
      )}
    </section>
  );
}

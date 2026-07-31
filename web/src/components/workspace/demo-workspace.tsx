"use client";

import { Music2, RefreshCw, XCircle } from "lucide-react";

import { DownloadButton } from "@/components/workspace/download-button";
import { Waveform } from "@/components/workspace/waveform";
import { formatBytes, formatPrerequisite } from "@/components/workspace/workspace-format";
import { useLocale } from "@/i18n/locale-provider";
import {
  AssetTree,
  AudioDemoVersion,
  GenerationRun,
  canCancelRun,
  canRetryRun,
  demoDownloadEndpoint,
  isRunActive,
  isRunInProgress,
  runProgressHint,
} from "@/lib/composition";
import { normalizeApiBaseUrl } from "@/lib/projects";

type DemoWorkspaceProps = {
  assetTree: AssetTree | null;
  canGenerate: boolean;
  disabledReason?: string | null;
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
  disabledReason,
  demos,
  isSaving,
  onGenerate,
  onCancel,
  onRetry,
  projectId,
  runs,
}: DemoWorkspaceProps) {
  const { dateTime, locale, t, text } = useLocale();
  const missing = assetTree?.missing_prerequisites ?? [];
  const activeRuns = runs.filter(isRunActive);
  return (
    <section className="panel demo-panel" aria-labelledby="demo-title">
      <div className="section-heading">
        <h2 id="demo-title">{t("Demo")}</h2>
        <span className="badge">{demos.length}</span>
      </div>
      <button
        className="button secondary full-width"
        data-guarded={!canGenerate || undefined}
        disabled={!canGenerate || isSaving}
        onClick={onGenerate}
        title={!canGenerate ? (disabledReason ?? undefined) : undefined}
        type="button"
      >
        <Music2 aria-hidden="true" size={18} />
        {t("Generate WAV demo")}
      </button>
      {activeRuns.length ? (
        <p className="empty">{t("Demo generation is running. Status refreshes automatically.")}</p>
      ) : null}
      {missing.length ? (
        <p className="empty">
          {t("Missing: {items}", { items: missing.map((item) => text(formatPrerequisite(item))).join(", ") })}
        </p>
      ) : null}
      {runs.length ? (
        <div className="run-list">
          {runs.slice(0, 5).map((run) => (
            <div className="run-row" key={run.id}>
              <div>
                <strong>
                  {run.provider_name}
                  {isRunInProgress(run) ? <span className="run-pulse" aria-hidden="true" /> : null}
                </strong>
                <p className="meta">
                  {text(run.status)} - {dateTime(run.created_at)}
                </p>
                {runProgressHint(run.status) ? (
                  <p className="meta">{t(runProgressHint(run.status)!)}</p>
                ) : null}
                {run.error_message ? (
                  <p className="error">
                    {locale === "zh-CN" && text(run.error_message) === run.error_message
                      ? t("Task failed")
                      : text(run.error_message)}
                  </p>
                ) : null}
              </div>
              {canCancelRun(run) ? (
                <button
                  className="button secondary icon-button"
                  disabled={isSaving}
                  onClick={() => onCancel(run.id)}
                  type="button"
                >
                  <XCircle aria-hidden="true" size={18} />
                  {t("Cancel")}
                </button>
              ) : canRetryRun(run) ? (
                <button
                  className="button secondary icon-button"
                  disabled={isSaving}
                  onClick={() => onRetry(run.id)}
                  type="button"
                >
                  <RefreshCw aria-hidden="true" size={18} />
                  {t("Retry")}
                </button>
              ) : (
                <span className="badge">{text(run.demo_id ? "demo ready" : run.status)}</span>
              )}
            </div>
          ))}
        </div>
      ) : null}
      {demos.length >= 2 ? (
        <div className="compare-grid" aria-label={t("Demo comparison")}>
          {demos.slice(0, 2).map((demo) => (
            <div className="compare-card" key={`compare-${demo.id}`}>
              <strong>{t("Demo v{version}", { version: demo.version_number })}</strong>
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
        <p className="empty">{t("Generated WAV demos will appear here for browser playback.")}</p>
      )}
    </section>
  );
}

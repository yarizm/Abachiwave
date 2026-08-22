"use client";

import {
  Activity,
  Archive,
  ArchiveRestore,
  Crosshair,
  Music2,
  Play,
  RefreshCw,
  Save,
  Square,
  Upload,
  XCircle,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  AudioMarkerEditor,
  type AudioMarkerCreatePayload,
  type AudioMarkerUpdatePayload,
} from "@/components/workspace/audio-marker-editor";
import { DownloadButton } from "@/components/workspace/download-button";
import { Waveform } from "@/components/workspace/waveform";
import { formatBytes } from "@/components/workspace/workspace-format";
import { useLocale } from "@/i18n/locale-provider";
import {
  AudioDerivative,
  AudioMarker,
  AudioAnalysisRange,
  ReferenceAnalysis,
  ReferenceAnalysisApplyField,
  ReferenceAnalysisApplyResult,
  AudioUpload,
  AudioUploadKind,
  AudioUploadStatus,
  GenerationRun,
  audioDerivativeDownloadEndpoint,
  audioUploadDownloadEndpoint,
  canCancelRun,
  createAudioAnalysisRange,
  formatAudioPosition,
  isRunActive,
} from "@/lib/composition";
import { normalizeApiBaseUrl } from "@/lib/projects";

export type {
  AudioMarkerCreatePayload,
  AudioMarkerUpdatePayload,
} from "@/components/workspace/audio-marker-editor";

export type AudioUploadUpdatePayload = {
  kind?: AudioUploadKind;
  notes?: string | null;
  status?: AudioUploadStatus;
};

type AudioWorkspaceProps = {
  analyses: ReferenceAnalysis[];
  approvedSongSpecId: string | null;
  derivatives: AudioDerivative[];
  file: File | null;
  isSaving: boolean;
  kind: AudioUploadKind;
  markers: AudioMarker[];
  notes: string;
  onAnalyze: (audioUploadId: string, analysisRange: AudioAnalysisRange | null) => void;
  onApplyAnalysis: (
    analysisId: string,
    fields: ReferenceAnalysisApplyField[],
    confirm: boolean,
  ) => Promise<ReferenceAnalysisApplyResult>;
  onCancel: (runId: string) => void;
  onCreateDerivative: (audioUploadId: string) => void;
  onCreateMarker: (audioUploadId: string, payload: AudioMarkerCreatePayload) => Promise<void>;
  onDeleteMarker: (markerId: string) => Promise<void>;
  onExtract: (
    audioUploadId: string,
    analysisRange: AudioAnalysisRange | null,
    referenceAnalysisId: string | null,
  ) => void;
  onFileChange: (file: File | null) => void;
  onKindChange: (kind: AudioUploadKind) => void;
  onNotesChange: (notes: string) => void;
  onUpdateMarker: (
    markerId: string,
    payload: AudioMarkerUpdatePayload,
  ) => Promise<void>;
  onUpdateUpload: (audioUploadId: string, payload: AudioUploadUpdatePayload) => void;
  onUpload: (event: FormEvent<HTMLFormElement>) => void;
  projectId: string;
  runs: GenerationRun[];
  uploads: AudioUpload[];
};

const apiBaseUrl = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL);

export function AudioWorkspace({
  analyses,
  approvedSongSpecId,
  derivatives,
  file,
  isSaving,
  kind,
  markers,
  notes,
  onAnalyze,
  onApplyAnalysis,
  onCancel,
  onCreateDerivative,
  onCreateMarker,
  onDeleteMarker,
  onExtract,
  onFileChange,
  onKindChange,
  onNotesChange,
  onUpdateMarker,
  onUpdateUpload,
  onUpload,
  projectId,
  runs,
  uploads,
}: AudioWorkspaceProps) {
  const { dateTime, locale, t, text } = useLocale();
  const activeMidiUploadIds = useMemo(
    () =>
      new Set(
        runs
          .filter((run) => run.run_type === "audio_to_midi" && isRunActive(run))
          .map((run) => manifestString(run.input_manifest, "audio_upload_id"))
          .filter((value): value is string => value !== null),
      ),
    [runs],
  );
  const activeDerivativeUploadIds = useMemo(
    () =>
      new Set(
        runs
          .filter((run) => run.run_type === "audio_derivative" && isRunActive(run))
          .map((run) => manifestString(run.input_manifest, "audio_upload_id"))
          .filter((value): value is string => value !== null),
      ),
    [runs],
  );
  const activeAnalysisUploadIds = useMemo(
    () =>
      new Set(
        runs
          .filter((run) => run.run_type === "reference_analysis" && isRunActive(run))
          .map((run) => manifestString(run.input_manifest, "audio_upload_id"))
          .filter((value): value is string => value !== null),
      ),
    [runs],
  );
  return (
    <section className="panel audio-panel" aria-labelledby="audio-title">
      <div className="section-heading">
        <h2 id="audio-title">{t("Audio")}</h2>
        <span className="badge">{uploads.length}</span>
      </div>
      <form className="form audio-upload-form" onSubmit={onUpload}>
        <div className="form-row">
          <div className="field">
            <label htmlFor="audio-file">{t("Audio file")}</label>
            <input
              accept="audio/wav,audio/x-wav,audio/mpeg,audio/mp4,audio/flac,audio/ogg,.wav,.mp3,.m4a,.flac,.ogg,.oga"
              id="audio-file"
              onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
              type="file"
            />
          </div>
          <div className="field">
            <label htmlFor="audio-kind">{t("Kind")}</label>
            <select
              id="audio-kind"
              onChange={(event) => onKindChange(event.target.value as AudioUploadKind)}
              value={kind}
            >
              <option value="humming">{t("Humming")}</option>
              <option value="reference">{t("Reference")}</option>
              <option value="scratch">{t("Scratch")}</option>
              <option value="other">{t("Other")}</option>
            </select>
          </div>
        </div>
        <div className="field">
          <label htmlFor="audio-notes">{t("Notes")}</label>
          <textarea
            id="audio-notes"
            onChange={(event) => onNotesChange(event.target.value)}
            placeholder={t("Chorus melody sketch, reference groove, or scratch idea...")}
            value={notes}
          />
        </div>
        <button className="button" disabled={isSaving || !file} type="submit">
          <Upload aria-hidden="true" size={18} />
          {t("Upload audio")}
        </button>
      </form>

      {runs.length ? (
        <div className="run-list">
          {runs.slice(0, 4).map((run) => (
            <div className="run-row" key={run.id}>
              <div>
                <strong>{run.provider_name}</strong>
                <p className="meta">
                  {text(run.status)} - {dateTime(run.created_at)}
                </p>
                {run.result_midi_asset_id ? (
                  <p className="meta">
                    {t("MIDI ready: {id}", { id: run.result_midi_asset_id.slice(0, 8) })}
                  </p>
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
              ) : (
                <span className="badge">
                  {text(run.result_midi_asset_id ? "midi ready" : run.status)}
                </span>
              )}
            </div>
          ))}
        </div>
      ) : null}

      {uploads.length ? (
        <div className="audio-upload-list">
          {uploads.map((upload) => (
            <AudioUploadRow
              analyses={analyses.filter((analysis) => analysis.audio_upload_id === upload.id)}
              approvedSongSpecId={approvedSongSpecId}
              derivatives={derivatives.filter(
                (derivative) => derivative.audio_upload_id === upload.id,
              )}
              isExtracting={activeMidiUploadIds.has(upload.id)}
              isNormalizing={activeDerivativeUploadIds.has(upload.id)}
              isAnalyzing={activeAnalysisUploadIds.has(upload.id)}
              isSaving={isSaving}
              key={upload.id}
              markers={markers.filter((marker) => marker.audio_upload_id === upload.id)}
              onAnalyze={onAnalyze}
              onApplyAnalysis={onApplyAnalysis}
              onCreateDerivative={onCreateDerivative}
              onCreateMarker={(payload) => onCreateMarker(upload.id, payload)}
              onDeleteMarker={onDeleteMarker}
              onExtract={onExtract}
              onUpdateMarker={onUpdateMarker}
              onUpdateUpload={onUpdateUpload}
              projectId={projectId}
              upload={upload}
            />
          ))}
        </div>
      ) : (
        <p className="empty">{t("Uploaded audio sketches and references will appear here.")}</p>
      )}
    </section>
  );
}

function AudioUploadRow({
  analyses,
  approvedSongSpecId,
  derivatives,
  isExtracting,
  isNormalizing,
  isAnalyzing,
  isSaving,
  markers,
  onAnalyze,
  onApplyAnalysis,
  onCreateDerivative,
  onCreateMarker,
  onDeleteMarker,
  onExtract,
  onUpdateMarker,
  onUpdateUpload,
  projectId,
  upload,
}: {
  analyses: ReferenceAnalysis[];
  approvedSongSpecId: string | null;
  derivatives: AudioDerivative[];
  isExtracting: boolean;
  isNormalizing: boolean;
  isAnalyzing: boolean;
  isSaving: boolean;
  markers: AudioMarker[];
  onAnalyze: (audioUploadId: string, analysisRange: AudioAnalysisRange | null) => void;
  onApplyAnalysis: (
    analysisId: string,
    fields: ReferenceAnalysisApplyField[],
    confirm: boolean,
  ) => Promise<ReferenceAnalysisApplyResult>;
  onCreateDerivative: (audioUploadId: string) => void;
  onCreateMarker: (payload: AudioMarkerCreatePayload) => Promise<void>;
  onDeleteMarker: (markerId: string) => Promise<void>;
  onExtract: (
    audioUploadId: string,
    analysisRange: AudioAnalysisRange | null,
    referenceAnalysisId: string | null,
  ) => void;
  onUpdateMarker: (
    markerId: string,
    payload: AudioMarkerUpdatePayload,
  ) => Promise<void>;
  onUpdateUpload: (audioUploadId: string, payload: AudioUploadUpdatePayload) => void;
  projectId: string;
  upload: AudioUpload;
}) {
  const { t, text } = useLocale();
  const [kindDraft, setKindDraft] = useState<AudioUploadKind>(upload.kind);
  const [notesDraft, setNotesDraft] = useState(upload.notes ?? "");
  const [markerPositionDraft, setMarkerPositionDraft] = useState("0");
  const [playheadSeconds, setPlayheadSeconds] = useState(0);
  const [waveformMode, setWaveformMode] = useState<"marker" | "region">("marker");
  const [analysisRange, setAnalysisRange] = useState<AudioAnalysisRange | null>(null);
  const [isPreviewingRange, setIsPreviewingRange] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const derivative = derivatives[0] ?? null;
  const latestAnalysis = analyses[0] ?? null;
  const metadata =
    upload.duration_seconds !== null &&
    upload.sample_rate !== null &&
    upload.channels !== null &&
    upload.waveform_peaks !== null
      ? {
          durationSeconds: upload.duration_seconds,
          sampleRate: upload.sample_rate,
          channels: upload.channels,
          waveformPeaks: upload.waveform_peaks,
        }
      : null;
  const activeAnalysisRange =
    metadata && analysisRange && analysisRange.end_seconds <= metadata.durationSeconds + 0.001
      ? analysisRange
      : null;
  const extractionAnalysis = analyses.find((analysis) =>
    referenceAnalysisMatchesRange(analysis, activeAnalysisRange),
  );
  const audioSource = derivative
    ? audioDerivativeDownloadEndpoint(apiBaseUrl, projectId, upload.id, derivative.id)
    : upload.format === "wav"
      ? audioUploadDownloadEndpoint(apiBaseUrl, projectId, upload.id)
      : null;
  const StatusIcon = upload.status === "archived" ? ArchiveRestore : Archive;
  const canExtract =
    Boolean(approvedSongSpecId) &&
    upload.status === "available" &&
    metadata !== null &&
    !isExtracting;
  const canAnalyze =
    upload.status === "available" && metadata !== null && !isAnalyzing;
  const canToggleArchive = upload.status === "available" || upload.status === "archived";

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
    if (!canToggleArchive) {
      return;
    }
    onUpdateUpload(upload.id, {
      status: upload.status === "archived" ? "available" : "archived",
    });
  }

  function seekAudio(positionSeconds: number) {
    if (!metadata) {
      return;
    }
    setIsPreviewingRange(false);
    const nextPosition = Math.min(metadata.durationSeconds, Math.max(0, positionSeconds));
    setPlayheadSeconds(nextPosition);
    if (audioRef.current) {
      audioRef.current.currentTime = nextPosition;
    }
  }

  function handleWaveformPositionSelect(positionSeconds: number) {
    setMarkerPositionDraft(String(Number(positionSeconds.toFixed(3))));
    seekAudio(positionSeconds);
  }

  function handleMarkerSelect(marker: { position_seconds: number }) {
    seekAudio(marker.position_seconds);
  }

  function handleWaveformModeChange(mode: "marker" | "region") {
    setWaveformMode(mode);
    setIsPreviewingRange(false);
    if (mode === "region" && audioRef.current) {
      audioRef.current.pause();
    }
  }

  function handleRangeBoundaryChange(boundary: "start" | "end", value: string) {
    if (!metadata) {
      return;
    }
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      return;
    }
    const current = activeAnalysisRange ?? {
      start_seconds: 0,
      end_seconds: metadata.durationSeconds,
    };
    const startSeconds = boundary === "start" ? parsed : current.start_seconds;
    const endSeconds = boundary === "end" ? parsed : current.end_seconds;
    const next = createAudioAnalysisRange(startSeconds, endSeconds, metadata.durationSeconds);
    if (next) {
      setAnalysisRange(next);
    }
  }

  async function handleRangePreview() {
    const audio = audioRef.current;
    if (!audio || !activeAnalysisRange) {
      return;
    }
    if (isPreviewingRange) {
      audio.pause();
      setIsPreviewingRange(false);
      return;
    }
    audio.currentTime = activeAnalysisRange.start_seconds;
    setPlayheadSeconds(activeAnalysisRange.start_seconds);
    try {
      await audio.play();
      setIsPreviewingRange(true);
    } catch {
      setIsPreviewingRange(false);
    }
  }

  function handleAudioTimeUpdate(event: FormEvent<HTMLAudioElement>) {
    const audio = event.currentTarget;
    setPlayheadSeconds(audio.currentTime);
    if (
      isPreviewingRange &&
      activeAnalysisRange &&
      audio.currentTime >= activeAnalysisRange.end_seconds - 0.01
    ) {
      audio.pause();
      audio.currentTime = activeAnalysisRange.end_seconds;
      setPlayheadSeconds(activeAnalysisRange.end_seconds);
      setIsPreviewingRange(false);
    }
  }

  return (
    <div className={`audio-upload-row audio-upload-${upload.status}`}>
      <div className="audio-upload-main">
        <div className="section-heading">
          <div>
            <strong>{upload.filename}</strong>
            <p className="meta">
              {metadata
                ? `${metadata.durationSeconds.toFixed(2)}s - ${metadata.sampleRate} Hz - ${metadata.channels} ch - ${formatBytes(upload.size_bytes)}`
                : `${t("Waiting for audio normalization")} - ${formatBytes(upload.size_bytes)}`}
            </p>
          </div>
          <div className="badge-row">
            <span className="badge">{text(upload.kind)}</span>
            <span className="badge">{upload.format.toUpperCase()}</span>
            <span className={`badge audio-status-${upload.status}`}>{text(upload.status)}</span>
          </div>
        </div>
        {metadata ? (
          <div className="waveform-mode-toolbar" aria-label={t("Waveform interaction mode")}>
            <button
              aria-pressed={waveformMode === "marker"}
              className={`button secondary${waveformMode === "marker" ? " active" : ""}`}
              onClick={() => handleWaveformModeChange("marker")}
              type="button"
            >
              <Crosshair aria-hidden="true" size={16} />
              {t("Marker point")}
            </button>
            <button
              aria-pressed={waveformMode === "region"}
              className={`button secondary${waveformMode === "region" ? " active" : ""}`}
              onClick={() => handleWaveformModeChange("region")}
              type="button"
            >
              <Crosshair aria-hidden="true" size={16} />
              {t("Analysis range")}
            </button>
          </div>
        ) : null}
        {metadata ? (
          <Waveform
            analysisRange={activeAnalysisRange}
            durationSeconds={metadata.durationSeconds}
            interactionMode={waveformMode}
            markers={markers}
            onAnalysisRangeChange={setAnalysisRange}
            onMarkerSelect={handleMarkerSelect}
            onPositionSelect={handleWaveformPositionSelect}
            peaks={metadata.waveformPeaks}
            playheadSeconds={playheadSeconds}
          />
        ) : null}
        {audioSource ? (
          <audio
            controls
            onEnded={() => setIsPreviewingRange(false)}
            onPause={() => setIsPreviewingRange(false)}
            onTimeUpdate={handleAudioTimeUpdate}
            preload="none"
            ref={audioRef}
            src={audioSource}
          />
        ) : (
          <p className="meta">{t("Playback will be available after normalization.")}</p>
        )}
        {metadata && waveformMode === "region" ? (
          <div className="audio-analysis-range-editor">
            <div className="section-heading">
              <div>
                <strong>{t("Analysis range")}</strong>
                <p className="meta">
                  {activeAnalysisRange
                    ? `${formatAudioPosition(activeAnalysisRange.start_seconds)}–${formatAudioPosition(activeAnalysisRange.end_seconds)}`
                    : t("No range selected; extraction uses the full audio.")}
                </p>
              </div>
              <button
                className="button secondary"
                disabled={!activeAnalysisRange}
                onClick={() => {
                  setAnalysisRange(null);
                  setIsPreviewingRange(false);
                  audioRef.current?.pause();
                }}
                type="button"
              >
                {t("Clear range")}
              </button>
            </div>
            <div className="form-row">
              <div className="field">
                <label htmlFor={`analysis-range-start-${upload.id}`}>{t("Range start (seconds)")}</label>
                <input
                  id={`analysis-range-start-${upload.id}`}
                  max={metadata.durationSeconds}
                  min={0}
                  onChange={(event) => handleRangeBoundaryChange("start", event.target.value)}
                  step="0.1"
                  type="number"
                  value={activeAnalysisRange?.start_seconds ?? 0}
                />
              </div>
              <div className="field">
                <label htmlFor={`analysis-range-end-${upload.id}`}>{t("Range end (seconds)")}</label>
                <input
                  id={`analysis-range-end-${upload.id}`}
                  max={metadata.durationSeconds}
                  min={0.1}
                  onChange={(event) => handleRangeBoundaryChange("end", event.target.value)}
                  step="0.1"
                  type="number"
                  value={activeAnalysisRange?.end_seconds ?? metadata.durationSeconds}
                />
              </div>
            </div>
            <button
              className="button secondary icon-button"
              disabled={!activeAnalysisRange || !audioSource}
              onClick={() => void handleRangePreview()}
              type="button"
            >
              {isPreviewingRange ? (
                <Square aria-hidden="true" size={16} />
              ) : (
                <Play aria-hidden="true" size={16} />
              )}
              {isPreviewingRange ? t("Stop range preview") : t("Preview selected range")}
            </button>
          </div>
        ) : null}
        <form className="audio-upload-editor" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor={`audio-kind-${upload.id}`}>{t("Kind")}</label>
            <select
              disabled={isSaving}
              id={`audio-kind-${upload.id}`}
              onChange={(event) => setKindDraft(event.target.value as AudioUploadKind)}
              value={kindDraft}
            >
              <option value="humming">{t("Humming")}</option>
              <option value="reference">{t("Reference")}</option>
              <option value="scratch">{t("Scratch")}</option>
              <option value="other">{t("Other")}</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor={`audio-notes-${upload.id}`}>{t("Notes")}</label>
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
            {t("Save")}
          </button>
        </form>
        <div className="audio-derivative-status">
          {derivative ? (
            <p className="meta">
              {t("PCM WAV ready: {filename}", { filename: derivative.filename })}
            </p>
          ) : upload.status === "failed" ? (
            <p className="meta">{t("Audio normalization failed. Retry to continue.")}</p>
          ) : upload.status === "processing" ? (
            <p className="meta">{t("Audio normalization is queued.")}</p>
          ) : (
            <p className="meta">{t("Standard PCM WAV has not been generated yet.")}</p>
          )}
        </div>
        {latestAnalysis ? (
          <ReferenceAnalysisCard
            analysis={latestAnalysis}
            isSaving={isSaving}
            onApply={onApplyAnalysis}
            songSpecId={approvedSongSpecId}
          />
        ) : null}
        {metadata ? (
          <AudioMarkerEditor
            durationSeconds={metadata.durationSeconds}
            isSaving={isSaving}
            markers={markers}
            onCreate={onCreateMarker}
            onDelete={onDeleteMarker}
            onPositionDraftChange={setMarkerPositionDraft}
            onUpdate={onUpdateMarker}
            positionDraft={markerPositionDraft}
          />
        ) : null}
      </div>
      <div className="audio-upload-actions">
        <DownloadButton
          filename={upload.filename}
          url={audioUploadDownloadEndpoint(apiBaseUrl, projectId, upload.id)}
        />
        <button
          className="button secondary icon-button"
          disabled={!canAnalyze || isSaving}
          onClick={() => onAnalyze(upload.id, activeAnalysisRange)}
          type="button"
        >
          <Activity aria-hidden="true" size={18} />
          {isAnalyzing
            ? t("Analyzing reference")
            : activeAnalysisRange
              ? t("Analyze selected range")
              : t("Analyze reference")}
        </button>
        <button
          className="button secondary icon-button"
          disabled={
            isSaving || isNormalizing || upload.status === "processing" || derivative !== null
          }
          onClick={() => onCreateDerivative(upload.id)}
          type="button"
        >
          <RefreshCw aria-hidden="true" size={18} />
          {isNormalizing
            ? t("Normalizing audio")
            : derivative
              ? t("PCM WAV ready")
              : upload.status === "failed"
                ? t("Retry normalization")
              : t("Create PCM WAV")}
        </button>
        {canToggleArchive ? (
          <button
            className="button secondary icon-button"
            disabled={isSaving}
            onClick={handleStatusToggle}
            type="button"
          >
            <StatusIcon aria-hidden="true" size={18} />
            {upload.status === "archived" ? t("Restore") : t("Archive")}
          </button>
        ) : null}
        <button
          className="button secondary icon-button"
          disabled={!canExtract || isSaving}
          onClick={() => onExtract(upload.id, activeAnalysisRange, extractionAnalysis?.id ?? null)}
          type="button"
        >
          <Music2 aria-hidden="true" size={18} />
          {isExtracting
            ? t("Extracting")
            : activeAnalysisRange
              ? t("Extract selected range")
              : t("Extract MIDI")}
        </button>
        {extractionAnalysis ? (
          <span className="meta">
            {t("MIDI source: analysis v{version}", {
              version: extractionAnalysis.version_number,
            })}
          </span>
        ) : (
          <span className="meta">{t("MIDI extraction has no linked analysis candidate.")}</span>
        )}
      </div>
    </div>
  );
}

const REFERENCE_APPLY_FIELDS: ReferenceAnalysisApplyField[] = [
  "tempo_bpm",
  "key",
  "time_signature",
];

function referenceAnalysisMatchesRange(
  analysis: ReferenceAnalysis,
  selectedRange: AudioAnalysisRange | null,
): boolean {
  if (selectedRange === null) return analysis.analysis_range.mode === "full";
  return (
    analysis.analysis_range.mode === "selection" &&
    Math.abs(analysis.analysis_range.start_seconds - selectedRange.start_seconds) < 0.001 &&
    Math.abs(analysis.analysis_range.end_seconds - selectedRange.end_seconds) < 0.001
  );
}

function ReferenceAnalysisCard({
  analysis,
  isSaving,
  onApply,
  songSpecId,
}: {
  analysis: ReferenceAnalysis;
  isSaving: boolean;
  onApply: (
    analysisId: string,
    fields: ReferenceAnalysisApplyField[],
    confirm: boolean,
  ) => Promise<ReferenceAnalysisApplyResult>;
  songSpecId: string | null;
}) {
  const { dateTime, t } = useLocale();
  const [selectedFields, setSelectedFields] = useState<ReferenceAnalysisApplyField[]>([]);
  const [applyPreview, setApplyPreview] = useState<ReferenceAnalysisApplyResult | null>(null);
  const [isApplying, setIsApplying] = useState(false);
  const overallConfidence = analysis.confidence.overall ?? 0;

  function handleFieldToggle(field: ReferenceAnalysisApplyField) {
    setSelectedFields((current) =>
      current.includes(field)
        ? current.filter((candidate) => candidate !== field)
        : [...current, field],
    );
    setApplyPreview(null);
  }

  async function handleApplyPreview() {
    if (!songSpecId || selectedFields.length === 0) {
      return;
    }
    setIsApplying(true);
    try {
      setApplyPreview(await onApply(analysis.id, selectedFields, false));
    } catch {
      setApplyPreview(null);
    } finally {
      setIsApplying(false);
    }
  }

  async function handleApplyConfirm() {
    if (!songSpecId || selectedFields.length === 0) {
      return;
    }
    setIsApplying(true);
    try {
      setApplyPreview(await onApply(analysis.id, selectedFields, true));
    } catch {
      setApplyPreview(null);
    } finally {
      setIsApplying(false);
    }
  }

  return (
    <section className="reference-analysis-card" aria-label={t("Reference analysis candidate")}>
      <div className="section-heading">
        <div>
          <strong>
            {t("Reference analysis candidate")} v{analysis.version_number}
          </strong>
          <p className="meta">
            {analysis.provider_name} {analysis.provider_version} · {dateTime(analysis.created_at)}
          </p>
        </div>
        <div className="badge-row">
          <span className="badge">{t("Candidate only")}</span>
          <span className="badge">{formatConfidence(overallConfidence)}</span>
        </div>
      </div>
      <p className="meta">
        {t("Analyzed range")}: {formatAudioPosition(analysis.analysis_range.start_seconds)}–
        {formatAudioPosition(analysis.analysis_range.end_seconds)} · {analysis.beat_grid.length}{" "}
        {t("beats")}
      </p>
      <div className="reference-analysis-metrics">
        <AnalysisMetric
          confidence={analysis.confidence.tempo}
          label={t("Tempo")}
          value={`${analysis.tempo_bpm.toFixed(1)} BPM`}
        />
        <AnalysisMetric
          confidence={analysis.time_signature.confidence}
          label={t("Time signature")}
          value={analysis.time_signature.value}
        />
        <AnalysisMetric
          confidence={analysis.key_candidate.confidence}
          label={t("Key / mode")}
          value={analysis.key_candidate.value}
        />
        <AnalysisMetric
          confidence={analysis.pitch_range.confidence}
          label={t("Pitch range")}
          value={`${analysis.pitch_range.low_note}–${analysis.pitch_range.high_note}`}
        />
        <AnalysisMetric
          confidence={analysis.loudness.confidence}
          label={t("Integrated loudness")}
          value={`${analysis.loudness.integrated_dbfs.toFixed(1)} dBFS`}
        />
        <AnalysisMetric
          confidence={analysis.confidence.energy}
          label={t("Dynamic range")}
          value={`${analysis.loudness.dynamic_range_db.toFixed(1)} dB`}
        />
      </div>
      {analysis.energy_curve.length > 0 ? (
        <div
          aria-label={t("Energy curve")}
          className="reference-analysis-energy"
          role="img"
        >
          {analysis.energy_curve.map((point) => (
            <span
              key={point.time_seconds}
              style={{ height: `${Math.max(4, point.value * 100)}%` }}
              title={`${formatAudioPosition(point.time_seconds)} · ${Math.round(point.value * 100)}%`}
            />
          ))}
        </div>
      ) : null}
      <div className="reference-analysis-columns">
        <AnalysisCandidateList
          items={analysis.structure_sections.map(
            (section) =>
              `${section.label} ${formatAudioPosition(section.start_seconds)}–${formatAudioPosition(section.end_seconds)} (${formatConfidence(section.confidence)})`,
          )}
          label={t("Structure candidates")}
        />
        <AnalysisCandidateList
          items={analysis.chord_candidates.map(
            (chord) =>
              `${chord.symbol} ${formatAudioPosition(chord.start_seconds)}–${formatAudioPosition(chord.end_seconds)} (${formatConfidence(chord.confidence)})`,
          )}
          label={t("Chord candidates")}
        />
      </div>
      {analysis.instrument_tags.length > 0 ? (
        <div className="badge-row reference-analysis-tags">
          {analysis.instrument_tags.map((tag) => (
            <span className="badge" key={tag.label}>
              {tag.label} · {formatConfidence(tag.confidence)}
            </span>
          ))}
        </div>
      ) : null}
      <p className="meta reference-analysis-notice">
        {t("This analysis is a candidate and has not changed the SongSpec or current assets.")}
      </p>
      <div className="reference-analysis-apply">
        <div>
          <strong>{t("Apply selected fields to a new SongSpec draft")}</strong>
          <p className="meta">{t("Preview impact before creating a draft version.")}</p>
        </div>
        <div className="reference-analysis-field-list">
          {REFERENCE_APPLY_FIELDS.map((field) => (
            <label key={field}>
              <input
                checked={selectedFields.includes(field)}
                disabled={isApplying || isSaving || !songSpecId}
                onChange={() => handleFieldToggle(field)}
                type="checkbox"
              />
              {referenceApplyFieldLabel(field, t)}
            </label>
          ))}
        </div>
        <button
          className="button secondary"
          disabled={
            isApplying || isSaving || !songSpecId || selectedFields.length === 0
          }
          onClick={() => void handleApplyPreview()}
          type="button"
        >
          {isApplying ? t("Checking impact") : t("Preview selected fields")}
        </button>
        {applyPreview ? (
          <div className="reference-analysis-impact">
            <strong>{applyPreview.applied ? t("Applied") : t("Impact preview")}</strong>
            <ul className="reference-analysis-list">
              {applyPreview.changes.map((change) => (
                <li key={change.field}>
                  {referenceApplyFieldLabel(change.field, t)}: {String(change.current_value)} →{" "}
                  {String(change.candidate_value)} ({formatConfidence(change.confidence)})
                </li>
              ))}
            </ul>
            <p className="meta">
              {t("Linked assets")}: {formatAssetCounts(applyPreview.affected_asset_counts)}
            </p>
            {applyPreview.warnings.map((warning) => (
              <p className="meta" key={warning}>
                {referenceApplyWarningLabel(warning, t)}
              </p>
            ))}
            {applyPreview.requires_confirmation ? (
              <button
                className="button"
                disabled={isApplying || isSaving}
                onClick={() => void handleApplyConfirm()}
                type="button"
              >
                {t("Confirm new SongSpec draft")}
              </button>
            ) : null}
            {applyPreview.applied && applyPreview.new_song_spec_version ? (
              <p className="success">
                {t("Created SongSpec v{version}", {
                  version: applyPreview.new_song_spec_version,
                })}
              </p>
            ) : null}
          </div>
        ) : null}
        {!songSpecId ? (
          <p className="meta">{t("Approve a SongSpec before applying reference analysis.")}</p>
        ) : null}
      </div>
    </section>
  );
}

function AnalysisMetric({
  confidence,
  label,
  value,
}: {
  confidence: number | undefined;
  label: string;
  value: string;
}) {
  return (
    <div className="reference-analysis-metric">
      <span className="meta">{label}</span>
      <strong>{value}</strong>
      <span className="meta">{formatConfidence(confidence ?? 0)}</span>
    </div>
  );
}

function AnalysisCandidateList({ items, label }: { items: string[]; label: string }) {
  return (
    <div>
      <strong>{label}</strong>
      {items.length > 0 ? (
        <ul className="reference-analysis-list">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : (
        <p className="meta">—</p>
      )}
    </div>
  );
}

function formatConfidence(value: number): string {
  return `${Math.round(Math.min(1, Math.max(0, value)) * 100)}%`;
}

function referenceApplyFieldLabel(
  field: ReferenceAnalysisApplyField,
  t: ReturnType<typeof useLocale>["t"],
): string {
  if (field === "tempo_bpm") return t("Tempo");
  if (field === "key") return t("Key / mode");
  return t("Time signature");
}

function formatAssetCounts(counts: Record<string, number>): string {
  return Object.entries(counts)
    .map(([label, count]) => `${label} ${count}`)
    .join(" · ");
}

function referenceApplyWarningLabel(
  warning: string,
  t: ReturnType<typeof useLocale>["t"],
): string {
  if (
    warning ===
    "A new SongSpec draft will be created; the approved version remains current until approval."
  ) {
    return t(
      "A new SongSpec draft will be created; the approved version remains current until approval.",
    );
  }
  if (
    warning ===
    "Existing lyrics, chords, MIDI, and arrangements remain linked to the source SongSpec."
  ) {
    return t(
      "Existing lyrics, chords, MIDI, and arrangements remain linked to the source SongSpec.",
    );
  }
  return warning;
}

function manifestString(manifest: Record<string, unknown>, key: string): string | null {
  const value = manifest[key];
  return typeof value === "string" ? value : null;
}

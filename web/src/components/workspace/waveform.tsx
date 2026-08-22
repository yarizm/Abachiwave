"use client";

import { useRef, type MouseEvent, type PointerEvent } from "react";

import { useLocale } from "@/i18n/locale-provider";
import {
  createAudioAnalysisRange,
  formatAudioPosition,
  type AudioAnalysisRange,
} from "@/lib/composition";

const EMPTY_WAVEFORM_PEAKS = Array.from({ length: 80 }, () => 0);

type WaveformMarker = {
  id: string;
  label: string;
  position_seconds: number;
};

type WaveformProps = {
  analysisRange?: AudioAnalysisRange | null;
  durationSeconds?: number;
  interactionMode?: "marker" | "region";
  markers?: WaveformMarker[];
  onAnalysisRangeChange?: (range: AudioAnalysisRange) => void;
  onMarkerSelect?: (marker: WaveformMarker) => void;
  onPositionSelect?: (positionSeconds: number) => void;
  peaks: number[];
  playheadSeconds?: number;
};

export function Waveform({
  analysisRange = null,
  durationSeconds = 0,
  interactionMode = "marker",
  markers = [],
  onAnalysisRangeChange,
  onMarkerSelect,
  onPositionSelect,
  peaks,
  playheadSeconds = 0,
}: WaveformProps) {
  const { t } = useLocale();
  const dragStartSecondsRef = useRef<number | null>(null);
  const visiblePeaks = peaks.length ? peaks : EMPTY_WAVEFORM_PEAKS;
  const markerInteractive = Boolean(
    interactionMode === "marker" && onPositionSelect && durationSeconds > 0,
  );
  const regionInteractive = Boolean(
    interactionMode === "region" && onAnalysisRangeChange && durationSeconds > 0,
  );
  const interactive = markerInteractive || regionInteractive;
  const playheadPercent = positionPercent(playheadSeconds, durationSeconds);

  function handlePositionSelect(event: MouseEvent<HTMLButtonElement>) {
    if (!markerInteractive || !onPositionSelect) {
      return;
    }
    const bounds = event.currentTarget.getBoundingClientRect();
    const ratio = bounds.width > 0 ? (event.clientX - bounds.left) / bounds.width : 0;
    const position = Math.min(durationSeconds, Math.max(0, ratio * durationSeconds));
    onPositionSelect(Number(position.toFixed(3)));
  }

  function handleRegionPointerDown(event: PointerEvent<HTMLButtonElement>) {
    if (!regionInteractive || !onAnalysisRangeChange) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const startSeconds = pointerPositionSeconds(event, durationSeconds);
    dragStartSecondsRef.current = startSeconds;
    const range = createAudioAnalysisRange(startSeconds, startSeconds, durationSeconds);
    if (range) {
      onAnalysisRangeChange(range);
    }
  }

  function handleRegionPointerMove(event: PointerEvent<HTMLButtonElement>) {
    const startSeconds = dragStartSecondsRef.current;
    if (startSeconds === null || !onAnalysisRangeChange) {
      return;
    }
    const range = createAudioAnalysisRange(
      startSeconds,
      pointerPositionSeconds(event, durationSeconds),
      durationSeconds,
    );
    if (range) {
      onAnalysisRangeChange(range);
    }
  }

  function handleRegionPointerUp(event: PointerEvent<HTMLButtonElement>) {
    handleRegionPointerMove(event);
    dragStartSecondsRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function handleRegionPointerCancel(event: PointerEvent<HTMLButtonElement>) {
    dragStartSecondsRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  return (
    <div className="waveform-stack">
      <div
        className={`waveform${interactive ? " is-interactive" : ""}${regionInteractive ? " is-region-mode" : ""}`}
      >
        <div className="waveform-bars" aria-label={t("Audio waveform")} role="img">
          {visiblePeaks.map((peak, index) => (
            <span
              className="waveform-bar"
              key={`${index}-${peak}`}
              style={{ height: `${Math.max(3, Math.round(peak * 44))}px` }}
            />
          ))}
        </div>
        {interactive ? (
          <button
            aria-label={
              regionInteractive
                ? t("Select analysis range from waveform")
                : t("Choose marker position from waveform")
            }
            className="waveform-position-picker"
            onClick={handlePositionSelect}
            onPointerCancel={handleRegionPointerCancel}
            onPointerDown={handleRegionPointerDown}
            onPointerMove={handleRegionPointerMove}
            onPointerUp={handleRegionPointerUp}
            title={
              regionInteractive
                ? t("Drag across the waveform to choose an analysis range.")
                : t("Click the waveform to choose a marker position.")
            }
            type="button"
          />
        ) : null}
        {analysisRange && durationSeconds > 0 ? (
          <span
            aria-hidden="true"
            className="waveform-analysis-range"
            style={{
              left: `${positionPercent(analysisRange.start_seconds, durationSeconds)}%`,
              width: `${rangePercent(analysisRange, durationSeconds)}%`,
            }}
          />
        ) : null}
        {durationSeconds > 0 ? (
          <span
            aria-hidden="true"
            className="waveform-playhead"
            style={{ left: `${playheadPercent}%` }}
          />
        ) : null}
        {markers.length && durationSeconds > 0 ? (
          <div className="waveform-marker-layer">
            {markers.map((marker) => {
              const label = `${t("Jump to marker")}: ${marker.label} (${marker.position_seconds.toFixed(2)}s)`;
              const style = { left: `${positionPercent(marker.position_seconds, durationSeconds)}%` };
              return onMarkerSelect ? (
                <button
                  aria-label={label}
                  className="waveform-marker"
                  key={marker.id}
                  onClick={() => onMarkerSelect(marker)}
                  style={style}
                  title={label}
                  type="button"
                />
              ) : (
                <span
                  aria-label={label}
                  className="waveform-marker"
                  key={marker.id}
                  role="img"
                  style={style}
                  title={label}
                />
              );
            })}
          </div>
        ) : null}
      </div>
      {interactive ? (
        <div className="waveform-caption">
          <span>
            {regionInteractive
              ? t("Drag across the waveform to choose an analysis range.")
              : t("Click the waveform to choose a marker position.")}
          </span>
          <span>
            {analysisRange
              ? `${t("Selected range")}: ${formatAudioPosition(analysisRange.start_seconds)}–${formatAudioPosition(analysisRange.end_seconds)}`
              : `${t("Playhead")}: ${Math.min(durationSeconds, Math.max(0, playheadSeconds)).toFixed(2)}s`}
          </span>
        </div>
      ) : null}
    </div>
  );
}

function pointerPositionSeconds(
  event: PointerEvent<HTMLButtonElement>,
  durationSeconds: number,
): number {
  const bounds = event.currentTarget.getBoundingClientRect();
  const ratio = bounds.width > 0 ? (event.clientX - bounds.left) / bounds.width : 0;
  return Number(Math.min(durationSeconds, Math.max(0, ratio * durationSeconds)).toFixed(3));
}

function rangePercent(range: AudioAnalysisRange, durationSeconds: number): number {
  if (durationSeconds <= 0) {
    return 0;
  }
  return Math.min(
    100,
    Math.max(0, ((range.end_seconds - range.start_seconds) / durationSeconds) * 100),
  );
}

function positionPercent(positionSeconds: number, durationSeconds: number): number {
  if (!Number.isFinite(positionSeconds) || durationSeconds <= 0) {
    return 0;
  }
  return Math.min(100, Math.max(0, (positionSeconds / durationSeconds) * 100));
}

const EMPTY_WAVEFORM_PEAKS = Array.from({ length: 80 }, () => 0);

export function Waveform({ peaks }: { peaks: number[] }) {
  const visiblePeaks = peaks.length ? peaks : EMPTY_WAVEFORM_PEAKS;
  return (
    <div className="waveform" aria-label="Audio waveform">
      {visiblePeaks.map((peak, index) => (
        <span
          key={`${index}-${peak}`}
          style={{ height: `${Math.max(3, Math.round(peak * 44))}px` }}
        />
      ))}
    </div>
  );
}

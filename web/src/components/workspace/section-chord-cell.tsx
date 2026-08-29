"use client";

import { Plus, Trash2 } from "lucide-react";
import { KeyboardEvent, useRef, useState } from "react";

import { useLocale } from "@/i18n/locale-provider";
import { ChordDisplayMode, chordDisplayLabel } from "@/lib/chord-editor";
import type { ChordMeasure } from "@/lib/composition";

export type ChordEventPatch = {
  symbol?: string;
  beat?: number;
  duration_beats?: number;
  inversion?: number | null;
};

export type SectionChordCellProps = {
  measure: ChordMeasure;
  /** "symbol" | "roman" | "nashville" — which label the chip shows. */
  notation: ChordDisplayMode;
  beatsPerMeasure: number;
  disabled?: boolean;
  /** Events sounding right now, highlighted while the progression plays. */
  playingEventIds?: ReadonlySet<string>;
  /** event_id of the chord currently sounding, so the cell can light up */
  soundingEventId?: string | null;
  onEventChange: (eventId: string, patch: ChordEventPatch) => void;
  onEventRemove: (eventId: string) => void;
  onEventAdd: () => void;
  onMeasureRemove: () => void;
};

export function SectionChordCell({
  measure,
  notation,
  beatsPerMeasure,
  disabled = false,
  playingEventIds,
  soundingEventId,
  onEventChange,
  onEventRemove,
  onEventAdd,
  onMeasureRemove,
}: SectionChordCellProps) {
  const { t } = useLocale();
  const [expanded, setExpanded] = useState(false);
  const chipRef = useRef<HTMLButtonElement>(null);

  const events = [...measure.events].sort((left, right) => left.beat - right.beat);
  const measureLabel = t("Measure {number}", { number: measure.measure_number });
  const symbols = events.map((event) => chordDisplayLabel(event, notation));
  const chipLabel = `${measureLabel}: ${symbols.length > 0 ? symbols.join(" ") : t("None")}`;
  // A collapsed chip has to light up too, or a multi-event measure looks
  // silent whenever the sounding event isn't the one you happen to expand.
  const chipSounding = events.some((event) => event.event_id === soundingEventId);

  function collapseOnEscape(keyEvent: KeyboardEvent<HTMLDivElement>) {
    if (keyEvent.key !== "Escape") return;
    keyEvent.stopPropagation();
    setExpanded(false);
    chipRef.current?.focus();
  }

  function changeNumber(eventId: string, field: "beat" | "duration_beats", raw: string) {
    const value = Number(raw);
    if (!Number.isFinite(value)) return;
    onEventChange(eventId, field === "beat" ? { beat: value } : { duration_beats: value });
  }

  return (
    <div className="section-chord-cell" data-measure={measure.measure_number}>
      <button
        aria-expanded={expanded}
        aria-label={chipLabel}
        className={`section-chord-chip${chipSounding ? " is-sounding" : ""}`}
        onClick={() => setExpanded((value) => !value)}
        ref={chipRef}
        type="button"
      >
        {events.length > 0 ? (
          events.map((event, index) => (
            <span
              className={`section-chord-symbol${
                playingEventIds?.has(event.event_id) ? " is-playing" : ""
              }`}
              key={event.event_id}
            >
              {symbols[index]}
            </span>
          ))
        ) : (
          <span aria-hidden="true" className="section-chord-symbol section-chord-placeholder">
            ·
          </span>
        )}
      </button>

      {expanded ? (
        <div className="section-chord-editor" onKeyDown={collapseOnEscape}>
          {events.map((event) => (
            <div
              className={`section-chord-event${event.event_id === soundingEventId ? " is-sounding" : ""}`}
              data-event={event.event_id}
              key={event.event_id}
            >
              <input
                aria-label={t("Chord symbol in measure {number}", {
                  number: measure.measure_number,
                })}
                className="section-chord-input"
                disabled={disabled}
                onChange={(inputEvent) =>
                  onEventChange(event.event_id, { symbol: inputEvent.target.value })
                }
                value={event.symbol}
              />
              <label className="section-chord-field">
                <span className="section-chord-field-label">{t("Beat")}</span>
                <input
                  className="section-chord-number"
                  disabled={disabled}
                  max={beatsPerMeasure}
                  min={1}
                  onChange={(inputEvent) =>
                    changeNumber(event.event_id, "beat", inputEvent.target.value)
                  }
                  step={1}
                  type="number"
                  value={event.beat}
                />
              </label>
              <label className="section-chord-field">
                <span className="section-chord-field-label">{t("Length")}</span>
                <input
                  className="section-chord-number"
                  disabled={disabled}
                  max={beatsPerMeasure}
                  min={1}
                  onChange={(inputEvent) =>
                    changeNumber(event.event_id, "duration_beats", inputEvent.target.value)
                  }
                  step={1}
                  type="number"
                  value={event.duration_beats}
                />
              </label>
              <label className="section-chord-field">
                <span className="section-chord-field-label">{t("Inversion")}</span>
                <select
                  className="section-chord-select"
                  disabled={disabled}
                  onChange={(inputEvent) =>
                    onEventChange(event.event_id, { inversion: Number(inputEvent.target.value) })
                  }
                  value={event.inversion ?? 0}
                >
                  <option value={0}>{t("Root")}</option>
                  <option value={1}>1</option>
                  <option value={2}>2</option>
                  <option value={3}>3</option>
                </select>
              </label>
              <button
                aria-label={t("Delete chord")}
                className="section-chord-remove"
                disabled={disabled}
                onClick={() => onEventRemove(event.event_id)}
                title={t("Delete chord")}
                type="button"
              >
                <Trash2 aria-hidden="true" size={14} />
              </button>
            </div>
          ))}
          <button
            className="section-chord-add"
            disabled={disabled}
            onClick={onEventAdd}
            type="button"
          >
            <Plus aria-hidden="true" size={14} />
            {t("Add chord")}
          </button>
          <button
            className="section-chord-measure-remove"
            disabled={disabled}
            onClick={onMeasureRemove}
            type="button"
          >
            <Trash2 aria-hidden="true" size={14} />
            {t("Delete measure")}
          </button>
        </div>
      ) : null}
    </div>
  );
}

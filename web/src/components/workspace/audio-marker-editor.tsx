"use client";

import { MapPin, Plus, Save, Trash2 } from "lucide-react";
import { FormEvent, useId, useState } from "react";

import { useLocale } from "@/i18n/locale-provider";
import {
  AudioMarker,
  validateAudioMarkerLabel,
  validateAudioMarkerPosition,
} from "@/lib/composition";

export type AudioMarkerCreatePayload = {
  position_seconds: number;
  label: string;
  section_id?: string | null;
  notes?: string | null;
};

export type AudioMarkerUpdatePayload = {
  position_seconds?: number;
  label?: string;
  section_id?: string | null;
  notes?: string | null;
};

type AudioMarkerEditorProps = {
  durationSeconds: number;
  isSaving: boolean;
  markers: AudioMarker[];
  onCreate: (payload: AudioMarkerCreatePayload) => Promise<void>;
  onDelete: (markerId: string) => Promise<void>;
  onPositionDraftChange: (value: string) => void;
  onUpdate: (markerId: string, payload: AudioMarkerUpdatePayload) => Promise<void>;
  positionDraft: string;
};

export function AudioMarkerEditor({
  durationSeconds,
  isSaving,
  markers,
  onCreate,
  onDelete,
  onPositionDraftChange,
  onUpdate,
  positionDraft,
}: AudioMarkerEditorProps) {
  const { t, text } = useLocale();
  const [labelDraft, setLabelDraft] = useState("");
  const [sectionDraft, setSectionDraft] = useState("");
  const [notesDraft, setNotesDraft] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const formId = useId();

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const position = Number(positionDraft);
    const validationError =
      validateAudioMarkerLabel(labelDraft) ??
      validateAudioMarkerPosition(position, durationSeconds);
    if (validationError) {
      setFormError(text(validationError));
      return;
    }
    setFormError(null);
    try {
      await onCreate({
        position_seconds: position,
        label: labelDraft.trim(),
        section_id: sectionDraft.trim() || null,
        notes: notesDraft.trim() || null,
      });
      onPositionDraftChange("0");
      setLabelDraft("");
      setSectionDraft("");
      setNotesDraft("");
    } catch {
      // The workspace-level error surface preserves the API detail and request id.
    }
  }

  return (
    <div className="audio-marker-editor">
      <div className="section-heading">
        <h3 className="heading-with-icon">
          <MapPin aria-hidden="true" size={18} />
          {t("Audio markers")}
        </h3>
        <span className="badge">{markers.length}</span>
      </div>
      <form className="form audio-marker-form" noValidate onSubmit={handleCreate}>
        <div className="form-row">
          <div className="field">
            <label htmlFor={`${formId}-position`}>{t("Position (seconds)")}</label>
            <input
              disabled={isSaving}
              id={`${formId}-position`}
              max={durationSeconds}
              min={0}
              onChange={(event) => onPositionDraftChange(event.target.value)}
              step="0.01"
              type="number"
              value={positionDraft}
            />
          </div>
          <div className="field">
            <label htmlFor={`${formId}-label`}>{t("Marker label")}</label>
            <input
              disabled={isSaving}
              id={`${formId}-label`}
              maxLength={120}
              onChange={(event) => setLabelDraft(event.target.value)}
              placeholder={t("Verse entry, chorus lift, edit point...")}
              value={labelDraft}
            />
          </div>
          <div className="field">
            <label htmlFor={`${formId}-section`}>{t("Section ID")}</label>
            <input
              disabled={isSaving}
              id={`${formId}-section`}
              maxLength={128}
              onChange={(event) => setSectionDraft(event.target.value)}
              placeholder={t("Optional section link")}
              value={sectionDraft}
            />
          </div>
        </div>
        <div className="field">
          <label htmlFor={`${formId}-notes`}>{t("Marker notes")}</label>
          <textarea
            disabled={isSaving}
            id={`${formId}-notes`}
            maxLength={2000}
            onChange={(event) => setNotesDraft(event.target.value)}
            value={notesDraft}
          />
        </div>
        {formError ? <p className="error">{formError}</p> : null}
        <button className="button secondary icon-button" disabled={isSaving} type="submit">
          <Plus aria-hidden="true" size={18} />
          {t("Add marker")}
        </button>
      </form>

      {markers.length ? (
        <div className="revision-task-list">
          {markers.map((marker) => (
            <AudioMarkerRow
              durationSeconds={durationSeconds}
              isSaving={isSaving}
              key={`${marker.id}:${marker.updated_at}`}
              marker={marker}
              onDelete={onDelete}
              onUpdate={onUpdate}
            />
          ))}
        </div>
      ) : (
        <p className="empty">{t("Add markers to identify sections and analysis ranges.")}</p>
      )}
    </div>
  );
}

function AudioMarkerRow({
  durationSeconds,
  isSaving,
  marker,
  onDelete,
  onUpdate,
}: {
  durationSeconds: number;
  isSaving: boolean;
  marker: AudioMarker;
  onDelete: (markerId: string) => Promise<void>;
  onUpdate: (markerId: string, payload: AudioMarkerUpdatePayload) => Promise<void>;
}) {
  const { t, text } = useLocale();
  const [positionDraft, setPositionDraft] = useState(String(marker.position_seconds));
  const [labelDraft, setLabelDraft] = useState(marker.label);
  const [sectionDraft, setSectionDraft] = useState(marker.section_id ?? "");
  const [notesDraft, setNotesDraft] = useState(marker.notes ?? "");
  const [formError, setFormError] = useState<string | null>(null);
  const formId = useId();

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const position = Number(positionDraft);
    const validationError =
      validateAudioMarkerLabel(labelDraft) ??
      validateAudioMarkerPosition(position, durationSeconds);
    if (validationError) {
      setFormError(text(validationError));
      return;
    }
    setFormError(null);
    try {
      await onUpdate(marker.id, {
        position_seconds: position,
        label: labelDraft.trim(),
        section_id: sectionDraft.trim() || null,
        notes: notesDraft.trim() || null,
      });
    } catch {
      // The workspace-level error surface preserves the API detail and request id.
    }
  }

  async function handleDelete() {
    if (!window.confirm(t("Delete this marker?"))) {
      return;
    }
    try {
      await onDelete(marker.id);
    } catch {
      // The workspace-level error surface preserves the API detail and request id.
    }
  }

  return (
    <form className="form revision-task-row" noValidate onSubmit={handleSave}>
      <div className="form-row">
        <div className="field">
          <label htmlFor={`${formId}-position`}>{t("Position (seconds)")}</label>
          <input
            disabled={isSaving}
            id={`${formId}-position`}
            max={durationSeconds}
            min={0}
            onChange={(event) => setPositionDraft(event.target.value)}
            step="0.01"
            type="number"
            value={positionDraft}
          />
        </div>
        <div className="field">
          <label htmlFor={`${formId}-label`}>{t("Marker label")}</label>
          <input
            disabled={isSaving}
            id={`${formId}-label`}
            maxLength={120}
            onChange={(event) => setLabelDraft(event.target.value)}
            value={labelDraft}
          />
        </div>
        <div className="field">
          <label htmlFor={`${formId}-section`}>{t("Section ID")}</label>
          <input
            disabled={isSaving}
            id={`${formId}-section`}
            maxLength={128}
            onChange={(event) => setSectionDraft(event.target.value)}
            value={sectionDraft}
          />
        </div>
      </div>
      <div className="field">
        <label htmlFor={`${formId}-notes`}>{t("Marker notes")}</label>
        <textarea
          disabled={isSaving}
          id={`${formId}-notes`}
          maxLength={2000}
          onChange={(event) => setNotesDraft(event.target.value)}
          value={notesDraft}
        />
      </div>
      {formError ? <p className="error">{formError}</p> : null}
      <div className="button-row">
        <button className="button secondary icon-button" disabled={isSaving} type="submit">
          <Save aria-hidden="true" size={18} />
          {t("Save marker")}
        </button>
        <button
          className="button danger icon-button"
          disabled={isSaving}
          onClick={() => void handleDelete()}
          type="button"
        >
          <Trash2 aria-hidden="true" size={18} />
          {t("Delete marker")}
        </button>
      </div>
    </form>
  );
}

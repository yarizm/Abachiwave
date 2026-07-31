"use client";

import {
  Check,
  Copy,
  Eye,
  MoveDown,
  MoveUp,
  Plus,
  Redo2,
  Trash2,
  Undo2,
} from "lucide-react";
import { useState } from "react";

import { useStructureDraft } from "@/app/projects/[projectId]/hooks/use-structure-draft";
import { useLocale } from "@/i18n/locale-provider";
import type { SongSpecVersion } from "@/lib/song-specs";
import {
  StructureChange,
  StructureChangeRequest,
  createStructureSectionId,
  duplicateStructureSection,
  moveStructureSection,
  validateStructureSections,
} from "@/lib/structure";

type StructureWorkspaceProps = {
  isSaving: boolean;
  onChange: (payload: StructureChangeRequest) => Promise<StructureChange>;
  projectId: string;
  sourceVersion: SongSpecVersion | null;
};

export function StructureWorkspace({
  isSaving,
  onChange,
  projectId,
  sourceVersion,
}: StructureWorkspaceProps) {
  const { t, text } = useLocale();
  const draft = useStructureDraft(projectId, sourceVersion);
  const [preview, setPreview] = useState<StructureChange | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const updateSections = (sections: typeof draft.sections) => {
    draft.update(sections);
    setPreview(null);
    setValidationError(null);
  };

  const previewChanges = async () => {
    if (!sourceVersion) {
      return;
    }
    const error = validateStructureSections(draft.sections);
    if (error) {
      setValidationError(text(error));
      return;
    }
    try {
      const result = await onChange({
        source_song_spec_id: sourceVersion.id,
        sections: draft.sections,
      });
      setPreview(result);
    } catch {
      setPreview(null);
    }
  };

  const applyChanges = async () => {
    if (!sourceVersion || !preview) {
      return;
    }
    try {
      const result = await onChange({
        source_song_spec_id: sourceVersion.id,
        sections: draft.sections,
        preview_id: preview.preview_id,
      });
      draft.reset(result.sections);
      setPreview(null);
    } catch {
      setPreview(null);
    }
  };

  return (
    <section className="panel structure-panel" aria-labelledby="structure-title">
      <div className="section-heading structure-heading">
        <div>
          <h2 id="structure-title">{t("Song structure")}</h2>
          <p className="meta">
            {sourceVersion
              ? t("Based on approved SongSpec v{version}", {
                  version: sourceVersion.version_number,
                })
              : t("Approve a SongSpec to edit its timeline.")}
          </p>
        </div>
        <div className="structure-toolbar">
          {draft.restored ? <span className="badge">{t("Local draft restored")}</span> : null}
          <button
            aria-label={t("Undo")}
            className="button secondary icon-only"
            disabled={!draft.canUndo || isSaving}
            onClick={() => {
              draft.undo();
              setPreview(null);
            }}
            title={t("Undo")}
            type="button"
          >
            <Undo2 aria-hidden="true" size={18} />
          </button>
          <button
            aria-label={t("Redo")}
            className="button secondary icon-only"
            disabled={!draft.canRedo || isSaving}
            onClick={() => {
              draft.redo();
              setPreview(null);
            }}
            title={t("Redo")}
            type="button"
          >
            <Redo2 aria-hidden="true" size={18} />
          </button>
        </div>
      </div>

      {sourceVersion ? (
        <>
          <div className="structure-list">
            {draft.sections.map((section, index) => (
              <div className="structure-row" key={section.section_id}>
                <span className="structure-index">{index + 1}</span>
                <div className="field">
                  <label className="sr-only" htmlFor={`structure-${section.section_id}`}>
                    {t("Section {number}", { number: index + 1 })}
                  </label>
                  <input
                    id={`structure-${section.section_id}`}
                    maxLength={120}
                    onChange={(event) =>
                      updateSections(
                        draft.sections.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, label: event.target.value } : item,
                        ),
                      )
                    }
                    value={section.label}
                  />
                  <span className="meta structure-id">{section.section_id}</span>
                </div>
                <div className="structure-row-actions">
                  <StructureIconButton
                    disabled={index === 0 || isSaving}
                    label={t("Move up")}
                    onClick={() =>
                      updateSections(moveStructureSection(draft.sections, index, -1))
                    }
                  >
                    <MoveUp aria-hidden="true" size={17} />
                  </StructureIconButton>
                  <StructureIconButton
                    disabled={index === draft.sections.length - 1 || isSaving}
                    label={t("Move down")}
                    onClick={() =>
                      updateSections(moveStructureSection(draft.sections, index, 1))
                    }
                  >
                    <MoveDown aria-hidden="true" size={17} />
                  </StructureIconButton>
                  <StructureIconButton
                    disabled={isSaving}
                    label={t("Duplicate section")}
                    onClick={() => {
                      const sectionId = createStructureSectionId(
                        draft.sections.map((item) => item.section_id),
                      );
                      updateSections(
                        duplicateStructureSection(
                          draft.sections,
                          index,
                          sectionId,
                          t("{label} copy", { label: section.label }),
                        ),
                      );
                    }}
                  >
                    <Copy aria-hidden="true" size={17} />
                  </StructureIconButton>
                  <StructureIconButton
                    disabled={draft.sections.length <= 1 || isSaving}
                    label={t("Delete section")}
                    onClick={() =>
                      updateSections(draft.sections.filter((_, itemIndex) => itemIndex !== index))
                    }
                  >
                    <Trash2 aria-hidden="true" size={17} />
                  </StructureIconButton>
                </div>
              </div>
            ))}
          </div>

          <div className="structure-footer">
            <button
              className="button secondary"
              disabled={isSaving}
              onClick={() => {
                const sectionId = createStructureSectionId(
                  draft.sections.map((section) => section.section_id),
                );
                updateSections([
                  ...draft.sections,
                  { section_id: sectionId, label: t("New section") },
                ]);
              }}
              type="button"
            >
              <Plus aria-hidden="true" size={18} />
              {t("Add section")}
            </button>
            <div className="button-row">
              <button
                className="button secondary"
                disabled={!draft.dirty || isSaving}
                onClick={() => void previewChanges()}
                type="button"
              >
                <Eye aria-hidden="true" size={18} />
                {t("Preview impact")}
              </button>
              <button
                className="button"
                disabled={!preview || isSaving}
                onClick={() => void applyChanges()}
                type="button"
              >
                <Check aria-hidden="true" size={18} />
                {t("Apply and create versions")}
              </button>
            </div>
          </div>
          {validationError ? <p className="error">{validationError}</p> : null}
          {preview ? <StructureImpactPreview change={preview} /> : null}
        </>
      ) : (
        <p className="empty">{t("No approved structure is available.")}</p>
      )}
    </section>
  );
}

function StructureIconButton({
  children,
  disabled,
  label,
  onClick,
}: {
  children: React.ReactNode;
  disabled: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      aria-label={label}
      className="button secondary icon-only"
      disabled={disabled}
      onClick={onClick}
      title={label}
      type="button"
    >
      {children}
    </button>
  );
}

function StructureImpactPreview({ change }: { change: StructureChange }) {
  const { t, text } = useLocale();
  const impact = change.impact;
  return (
    <div className="structure-impact" aria-live="polite">
      <div className="section-heading">
        <div>
          <strong>{t("Change impact")}</strong>
          <p className="meta">{t("{count} assets affected", { count: impact.affected_assets.length })}</p>
        </div>
        <div className="badge-row">
          <span className="badge">{t("{count} added", { count: impact.added_sections.length })}</span>
          <span className="badge">{t("{count} removed", { count: impact.removed_sections.length })}</span>
          <span className="badge">{t("{count} renamed", { count: impact.renamed_sections.length })}</span>
          {impact.reordered ? <span className="badge">{t("Reordered")}</span> : null}
        </div>
      </div>
      <div className="structure-impact-assets">
        {impact.affected_assets.map((asset) => (
          <div className="structure-impact-row" key={`${asset.asset_type}-${asset.id}`}>
            <span>{text(asset.asset_type)}</span>
            <span className="meta">v{asset.version_number}</span>
            <span className="badge">
              {asset.action === "new_version" ? t("New version") : t("Regenerate")}
            </span>
          </div>
        ))}
      </div>
      {impact.warnings.map((warning) => (
        <p className="meta" key={warning}>{text(warning)}</p>
      ))}
    </div>
  );
}

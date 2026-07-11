"use client";

import { Download, FilePlus2, Save } from "lucide-react";
import { FormEvent } from "react";

import { DownloadButton } from "@/components/workspace/download-button";
import { formatBytes, formatPrerequisite } from "@/components/workspace/workspace-format";
import {
  ArrangementPlan,
  ArrangementPlanVersion,
  AssetReference,
  AssetTree,
  ExportBundle,
  exportDownloadEndpoint,
} from "@/lib/composition";
import { normalizeApiBaseUrl } from "@/lib/projects";

type DeliveryWorkspaceProps = {
  activeArrangement: ArrangementPlanVersion | null;
  arrangementPlan: ArrangementPlan;
  assetTree: AssetTree | null;
  canExport: boolean;
  canGenerateArrangement: boolean;
  exports: ExportBundle[];
  isSaving: boolean;
  onArrangementChange: (next: ArrangementPlan) => void;
  onArrangementSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCreateExport: () => void;
  onGenerateArrangement: () => void;
};

const apiBaseUrl = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL);

export function DeliveryWorkspace({
  activeArrangement,
  arrangementPlan,
  assetTree,
  canExport,
  canGenerateArrangement,
  exports,
  isSaving,
  onArrangementChange,
  onArrangementSubmit,
  onCreateExport,
  onGenerateArrangement,
}: DeliveryWorkspaceProps) {
  return (
    <>
      <ArrangementPanel
        activeArrangement={activeArrangement}
        canGenerate={canGenerateArrangement}
        isSaving={isSaving}
        onChange={onArrangementChange}
        onGenerate={onGenerateArrangement}
        onSubmit={onArrangementSubmit}
        plan={arrangementPlan}
      />
      <ExportPanel
        assetTree={assetTree}
        canExport={canExport}
        exports={exports}
        isSaving={isSaving}
        onCreateExport={onCreateExport}
      />
    </>
  );
}

export function emptyArrangementPlan(): ArrangementPlan {
  return {
    overview: "",
    sections: [],
    mix_notes: "",
    reference_notes: "",
  };
}

function ArrangementPanel({
  activeArrangement,
  canGenerate,
  isSaving,
  onChange,
  onGenerate,
  onSubmit,
  plan,
}: {
  activeArrangement: ArrangementPlanVersion | null;
  canGenerate: boolean;
  isSaving: boolean;
  onChange: (next: ArrangementPlan) => void;
  onGenerate: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  plan: ArrangementPlan;
}) {
  return (
    <section className="panel" aria-labelledby="arrangement-title">
      <div className="section-heading">
        <h2 id="arrangement-title">Arrangement</h2>
        {activeArrangement ? (
          <span className="badge">v{activeArrangement.version_number}</span>
        ) : null}
      </div>
      <button
        className="button secondary full-width"
        disabled={!canGenerate || isSaving}
        onClick={onGenerate}
        type="button"
      >
        <FilePlus2 aria-hidden="true" size={18} />
        Generate arrangement
      </button>
      {activeArrangement ? (
        <form className="form compact-form" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="arrangement-overview">Overview</label>
            <textarea
              id="arrangement-overview"
              onChange={(event) => onChange({ ...plan, overview: event.target.value })}
              value={plan.overview}
            />
          </div>
          {plan.sections.map((section, index) => (
            <div className="arrangement-section" key={section.section_id}>
              <div className="section-heading">
                <strong>{section.label}</strong>
                <span className="badge">{section.energy_level}/10</span>
              </div>
              <div className="form-row">
                <div className="field">
                  <label htmlFor={`arrangement-instruments-${section.section_id}`}>
                    Instruments
                  </label>
                  <input
                    id={`arrangement-instruments-${section.section_id}`}
                    onChange={(event) =>
                      onChange({
                        ...plan,
                        sections: plan.sections.map((item, sectionIndex) =>
                          sectionIndex === index
                            ? {
                                ...item,
                                instruments: splitInstrumentInput(event.target.value),
                              }
                            : item,
                        ),
                      })
                    }
                    value={section.instruments.join(", ")}
                  />
                </div>
                <div className="field narrow-field">
                  <label htmlFor={`arrangement-energy-${section.section_id}`}>Energy</label>
                  <input
                    id={`arrangement-energy-${section.section_id}`}
                    max={10}
                    min={1}
                    onChange={(event) =>
                      onChange({
                        ...plan,
                        sections: plan.sections.map((item, sectionIndex) =>
                          sectionIndex === index
                            ? { ...item, energy_level: Number(event.target.value) }
                            : item,
                        ),
                      })
                    }
                    type="number"
                    value={section.energy_level}
                  />
                </div>
              </div>
              <div className="field">
                <label htmlFor={`arrangement-notes-${section.section_id}`}>
                  Production notes
                </label>
                <textarea
                  id={`arrangement-notes-${section.section_id}`}
                  onChange={(event) =>
                    onChange({
                      ...plan,
                      sections: plan.sections.map((item, sectionIndex) =>
                        sectionIndex === index
                          ? { ...item, production_notes: event.target.value }
                          : item,
                      ),
                    })
                  }
                  value={section.production_notes}
                />
              </div>
            </div>
          ))}
          <div className="field">
            <label htmlFor="arrangement-mix-notes">Mix notes</label>
            <textarea
              id="arrangement-mix-notes"
              onChange={(event) => onChange({ ...plan, mix_notes: event.target.value })}
              value={plan.mix_notes}
            />
          </div>
          <div className="field">
            <label htmlFor="arrangement-reference-notes">Reference notes</label>
            <textarea
              id="arrangement-reference-notes"
              onChange={(event) => onChange({ ...plan, reference_notes: event.target.value })}
              value={plan.reference_notes}
            />
          </div>
          <button className="button" disabled={isSaving} type="submit">
            <Save aria-hidden="true" size={18} />
            Save arrangement version
          </button>
        </form>
      ) : (
        <p className="empty">
          Complete SongSpec, lyrics, chords, and MIDI before generating an arrangement.
        </p>
      )}
    </section>
  );
}

function ExportPanel({
  assetTree,
  canExport,
  exports,
  isSaving,
  onCreateExport,
}: {
  assetTree: AssetTree | null;
  canExport: boolean;
  exports: ExportBundle[];
  isSaving: boolean;
  onCreateExport: () => void;
}) {
  const missing = assetTree?.missing_prerequisites ?? [];
  return (
    <section className="panel" aria-labelledby="export-title">
      <div className="section-heading">
        <h2 id="export-title">Export</h2>
        <span className="badge">{exports.length}</span>
      </div>
      <button
        className="button secondary full-width"
        disabled={!canExport || isSaving}
        onClick={onCreateExport}
        type="button"
      >
        <Download aria-hidden="true" size={18} />
        Export ZIP
      </button>
      {missing.length ? (
        <p className="empty">Missing: {missing.map(formatPrerequisite).join(", ")}</p>
      ) : null}
      {assetTree ? (
        <div className="asset-tree">
          <h3>Current assets</h3>
          <div className="current-assets">
            {[
              assetTree.current.song_spec,
              assetTree.current.lyrics,
              assetTree.current.chords,
              ...assetTree.current.midi_assets,
              assetTree.current.arrangement,
            ]
              .filter(isAssetReference)
              .map((asset) => (
                <span className="asset-pill" key={asset.id}>
                  {asset.label}
                </span>
              ))}
          </div>
          <h3>Timeline</h3>
          <div className="timeline-list">
            {assetTree.timeline.slice(0, 8).map((asset) => (
              <div className="timeline-row" key={`${asset.asset_type}-${asset.id}`}>
                <span>{asset.label}</span>
                <span className="meta">{new Date(asset.created_at).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      {exports.length ? (
        <div className="asset-list">
          {exports.map((bundle) => (
            <div className="asset-row" key={bundle.id}>
              <div>
                <strong>{bundle.filename ?? `Export ${bundle.id.slice(0, 8)}`}</strong>
                <p className="meta">
                  {bundle.status} - {bundle.size_bytes ? formatBytes(bundle.size_bytes) : "no file"}
                </p>
              </div>
              {bundle.download_url ? (
                <DownloadButton
                  filename={bundle.filename ?? "abachiwave-export.zip"}
                  url={exportDownloadEndpoint(apiBaseUrl, bundle.download_url)}
                />
              ) : (
                <span className="meta">{bundle.error_message ?? "Not downloadable"}</span>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="empty">Ready export bundles will appear here.</p>
      )}
    </section>
  );
}

function splitInstrumentInput(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function isAssetReference(asset: AssetReference | null): asset is AssetReference {
  return asset !== null;
}

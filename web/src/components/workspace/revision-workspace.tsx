"use client";

import { Check, GitCompare, Music2, RotateCcw, XCircle } from "lucide-react";
import { FormEvent } from "react";

import {
  ArrangementPlanVersion,
  AudioDemoVersion,
  LyricsVersion,
  MidiAssetVersion,
  RestoreAssetType,
  RevisionRequest,
  VersionAssetType,
  VersionDiff,
  canApplyRevision,
} from "@/lib/composition";

type RevisionWorkspaceProps = {
  arrangements: ArrangementPlanVersion[];
  demos: AudioDemoVersion[];
  feedback: string;
  isSaving: boolean;
  lyrics: LyricsVersion[];
  melodyAssets: MidiAssetVersion[];
  onApply: (revisionId: string, regenerateDemo: boolean) => void;
  onCompare: (assetType: VersionAssetType, leftId: string, rightId: string) => void;
  onFeedbackChange: (value: string) => void;
  onPlan: (event: FormEvent<HTMLFormElement>) => void;
  onReject: (revisionId: string) => void;
  onRestore: (assetType: RestoreAssetType, versionId: string) => void;
  revisions: RevisionRequest[];
  versionDiff: VersionDiff | null;
};

export function RevisionWorkspace({
  arrangements,
  demos,
  feedback,
  isSaving,
  lyrics,
  melodyAssets,
  onApply,
  onCompare,
  onFeedbackChange,
  onPlan,
  onReject,
  onRestore,
  revisions,
  versionDiff,
}: RevisionWorkspaceProps) {
  const latestPlanned = revisions.find((revision) => revision.status === "planned") ?? null;
  const canApplyLatest = latestPlanned ? canApplyRevision(latestPlanned) : false;
  return (
    <section className="panel revision-panel" aria-labelledby="revision-title">
      <div className="section-heading">
        <h2 id="revision-title">Revisions</h2>
        <span className="badge">{revisions.length}</span>
      </div>
      <form className="form" onSubmit={onPlan}>
        <div className="field">
          <label htmlFor="revision-feedback">Feedback</label>
          <textarea
            id="revision-feedback"
            onChange={(event) => onFeedbackChange(event.target.value)}
            placeholder="Make the chorus lyric stronger, lift the chorus melody, or make the bridge more sparse..."
            value={feedback}
          />
        </div>
        <button className="button" disabled={isSaving} type="submit">
          <GitCompare aria-hidden="true" size={18} />
          Plan revision
        </button>
      </form>

      {latestPlanned ? (
        <div className="revision-block">
          <div className="section-heading">
            <h3>Impact preview</h3>
            <span className="badge">{latestPlanned.status}</span>
          </div>
          <div className="revision-task-list">
            {latestPlanned.tasks.map((task) => (
              <div className="revision-task-row" key={task.id}>
                <div>
                  <strong>{formatRevisionTarget(task.target)}</strong>
                  <p className="meta">{task.summary}</p>
                  <p className="meta">
                    {task.target_section_id ?? "all sections"} -{" "}
                    {task.requires_demo_regeneration ? "demo recommended" : "demo optional"}
                  </p>
                </div>
                <span className="badge">{task.supported ? "supported" : "unsupported"}</span>
              </div>
            ))}
          </div>
          <div className="button-row">
            <button
              className="button"
              disabled={!canApplyLatest || isSaving}
              onClick={() => onApply(latestPlanned.id, false)}
              type="button"
            >
              <Check aria-hidden="true" size={18} />
              Apply
            </button>
            <button
              className="button secondary"
              disabled={!canApplyLatest || isSaving}
              onClick={() => onApply(latestPlanned.id, true)}
              type="button"
            >
              <Music2 aria-hidden="true" size={18} />
              Apply + demo
            </button>
            <button
              className="button secondary"
              disabled={isSaving}
              onClick={() => onReject(latestPlanned.id)}
              type="button"
            >
              <XCircle aria-hidden="true" size={18} />
              Reject
            </button>
          </div>
        </div>
      ) : (
        <p className="empty">Planned revisions will show their affected assets before changes are applied.</p>
      )}

      <div className="revision-block">
        <h3>Version tools</h3>
        <div className="version-tool-grid">
          <VersionToolRow
            canRestore
            disabled={lyrics.length < 2 || isSaving}
            label="Lyrics"
            onCompare={() => onCompare("lyrics", lyrics[1].id, lyrics[0].id)}
            onRestore={() => onRestore("lyrics", lyrics[1].id)}
            subtitle={versionPairLabel(lyrics[1]?.version_number, lyrics[0]?.version_number)}
          />
          <VersionToolRow
            canRestore
            disabled={melodyAssets.length < 2 || isSaving}
            label="Melody MIDI"
            onCompare={() => onCompare("midi_melody", melodyAssets[1].id, melodyAssets[0].id)}
            onRestore={() => onRestore("midi_melody", melodyAssets[1].id)}
            subtitle={versionPairLabel(
              melodyAssets[1]?.version_number,
              melodyAssets[0]?.version_number,
            )}
          />
          <VersionToolRow
            canRestore
            disabled={arrangements.length < 2 || isSaving}
            label="Arrangement"
            onCompare={() => onCompare("arrangement", arrangements[1].id, arrangements[0].id)}
            onRestore={() => onRestore("arrangement", arrangements[1].id)}
            subtitle={versionPairLabel(
              arrangements[1]?.version_number,
              arrangements[0]?.version_number,
            )}
          />
          <VersionToolRow
            disabled={demos.length < 2 || isSaving}
            label="Demo"
            onCompare={() => onCompare("demo", demos[1].id, demos[0].id)}
            subtitle={versionPairLabel(demos[1]?.version_number, demos[0]?.version_number)}
          />
        </div>
        {versionDiff ? (
          <div className="diff-list">
            <div>
              <strong>{formatVersionAssetType(versionDiff.asset_type)}</strong>
              <p className="meta">{versionDiff.summary}</p>
            </div>
            {versionDiff.changes.length ? (
              versionDiff.changes.map((change) => (
                <div className="diff-row" key={`${change.field}-${change.label}`}>
                  <strong>{change.label}</strong>
                  <p className="meta">{change.summary}</p>
                  <p>
                    <span className="meta">Before:</span> {change.left ?? "empty"}
                  </p>
                  <p>
                    <span className="meta">After:</span> {change.right ?? "empty"}
                  </p>
                </div>
              ))
            ) : (
              <p className="empty">No field-level changes detected.</p>
            )}
          </div>
        ) : null}
      </div>

      <div className="revision-block">
        <h3>Revision history</h3>
        {revisions.length ? (
          <div className="revision-task-list">
            {revisions.slice(0, 8).map((revision) => (
              <div className="revision-task-row" key={revision.id}>
                <div>
                  <strong>{revision.feedback}</strong>
                  <p className="meta">
                    {revision.status} - {new Date(revision.created_at).toLocaleString()}
                  </p>
                  {revision.created_versions.length ? (
                    <p className="meta">
                      Created:{" "}
                      {revision.created_versions
                        .map(
                          (version) =>
                            `${formatRevisionTarget(version.asset_type)} v${version.version_number}`,
                        )
                        .join(", ")}
                    </p>
                  ) : null}
                </div>
                <span className="badge">{revision.tasks.length} tasks</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="empty">Revision history is empty.</p>
        )}
      </div>
    </section>
  );
}

function VersionToolRow({
  canRestore = false,
  disabled,
  label,
  onCompare,
  onRestore,
  subtitle,
}: {
  canRestore?: boolean;
  disabled: boolean;
  label: string;
  onCompare: () => void;
  onRestore?: () => void;
  subtitle: string;
}) {
  return (
    <div className="version-tool-row">
      <div>
        <strong>{label}</strong>
        <p className="meta">{subtitle}</p>
      </div>
      <div className="button-row">
        <button
          className="button secondary icon-button"
          disabled={disabled}
          onClick={onCompare}
          type="button"
        >
          <GitCompare aria-hidden="true" size={18} />
          Diff
        </button>
        {canRestore ? (
          <button
            className="button secondary icon-button"
            disabled={disabled || !onRestore}
            onClick={onRestore}
            type="button"
          >
            <RotateCcw aria-hidden="true" size={18} />
            Restore
          </button>
        ) : null}
      </div>
    </div>
  );
}

function formatRevisionTarget(value: RestoreAssetType | VersionAssetType): string {
  switch (value) {
    case "lyrics":
      return "Lyrics";
    case "midi_melody":
      return "Melody MIDI";
    case "arrangement":
      return "Arrangement";
    case "demo":
      return "Demo";
  }
}

function formatVersionAssetType(value: VersionAssetType): string {
  return formatRevisionTarget(value);
}

function versionPairLabel(left?: number, right?: number): string {
  if (left === undefined || right === undefined) {
    return "Need at least two versions";
  }
  return `Compare v${left} to v${right}`;
}

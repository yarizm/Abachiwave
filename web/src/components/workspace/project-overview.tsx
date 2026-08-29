"use client";

import { Archive, ArchiveRestore, RefreshCw, Save } from "lucide-react";
import { FormEvent } from "react";

import { HandoffPanel, ReviewPanel } from "@/components/workspace/project-summary-panels";
import { useLocale } from "@/i18n/locale-provider";
import { Project } from "@/lib/projects";
import { ProjectHandoff, ProjectReview } from "@/lib/composition";

type ProjectHeaderProps = {
  error: string | null;
  errorHint: string | null;
  isLoading: boolean;
  onErrorHintAction: () => void;
  onRefresh: () => void;
  project: Project | null;
};

/**
 * Project identity and the load error, shown on every workspace route.
 *
 * This used to be the top of the single workspace page. It now lives in the
 * workspace layout, so the project you are editing stays named while you move
 * between the SongSpec, composition, arrangement and demo routes.
 */
export function ProjectHeader({
  error,
  errorHint,
  isLoading,
  onErrorHintAction,
  onRefresh,
  project,
}: ProjectHeaderProps) {
  const { t, text } = useLocale();
  return (
    <>
      <section className="workspace-header">
        <div>
          <p className="meta">{t("Project workspace")}</p>
          <div className="workspace-title-row">
            <h1>{project?.name ?? t("Loading project")}</h1>
            {project ? (
              <span className={`badge project-${project.status}`}>{text(project.status)}</span>
            ) : null}
          </div>
          {project?.description ? <p>{project.description}</p> : null}
        </div>
        <button className="button secondary" disabled={isLoading} onClick={onRefresh} type="button">
          <RefreshCw aria-hidden="true" size={18} />
          {t("Refresh")}
        </button>
      </section>

      {error ? (
        <div className="notice error" role="alert">
          <p>{error}</p>
          {errorHint ? (
            <button
              className="button secondary compact-button"
              onClick={onErrorHintAction}
              type="button"
            >
              {errorHint}
            </button>
          ) : null}
        </div>
      ) : null}
    </>
  );
}

type ProjectOverviewProps = {
  handoff: ProjectHandoff | null;
  review: ProjectReview | null;
};

/** Readiness and handoff, the content of the workspace overview route. */
export function ProjectOverview({ handoff, review }: ProjectOverviewProps) {
  return (
    <>
      <ReviewPanel review={review} />
      <HandoffPanel handoff={handoff} />
    </>
  );
}

type ProjectSettingsPanelProps = {
  description: string;
  isSaving: boolean;
  name: string;
  onDescriptionChange: (value: string) => void;
  onNameChange: (value: string) => void;
  onStatusToggle: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  project: Project | null;
};

export function ProjectSettingsPanel({
  description,
  isSaving,
  name,
  onDescriptionChange,
  onNameChange,
  onStatusToggle,
  onSubmit,
  project,
}: ProjectSettingsPanelProps) {
  const { dateTime, t, text } = useLocale();
  const StatusIcon = project?.status === "archived" ? ArchiveRestore : Archive;

  return (
    <section className="panel project-settings-panel" aria-labelledby="project-settings-title">
      <div className="section-heading">
        <h2 id="project-settings-title">{t("Project settings")}</h2>
        {project ? <span className={`badge project-${project.status}`}>{text(project.status)}</span> : null}
      </div>
      <div className="project-settings-grid">
        <form className="form" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="project-settings-name">{t("Name")}</label>
            <input
              disabled={!project || isSaving}
              id="project-settings-name"
              maxLength={120}
              onChange={(event) => onNameChange(event.target.value)}
              value={name}
            />
          </div>
          <div className="field">
            <label htmlFor="project-settings-description">{t("Description")}</label>
            <textarea
              disabled={!project || isSaving}
              id="project-settings-description"
              maxLength={1000}
              onChange={(event) => onDescriptionChange(event.target.value)}
              value={description}
            />
          </div>
          <div className="button-row">
            <button className="button" disabled={!project || isSaving} type="submit">
              <Save aria-hidden="true" size={18} />
              {t("Save details")}
            </button>
          </div>
        </form>
        <div className="status-action">
          <p className="meta">
            {t("Current status: {status}", { status: text(project?.status ?? "loading") })}
          </p>
          <p className="meta">
            {t("Updated {date}", { date: project ? dateTime(project.updated_at) : "..." })}
          </p>
          <button
            className="button secondary"
            disabled={!project || isSaving}
            onClick={onStatusToggle}
            type="button"
          >
            <StatusIcon aria-hidden="true" size={18} />
            {project
              ? project.status === "archived"
                ? t("Restore project")
                : t("Archive project")
              : t("Loading status")}
          </button>
        </div>
      </div>
    </section>
  );
}

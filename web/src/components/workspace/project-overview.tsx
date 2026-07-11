"use client";

import { Archive, ArchiveRestore, RefreshCw, Save } from "lucide-react";
import { FormEvent } from "react";

import { HandoffPanel, ReviewPanel } from "@/components/workspace/project-summary-panels";
import { Project, projectStatusActionLabel } from "@/lib/projects";
import { ProjectHandoff, ProjectReview } from "@/lib/composition";

type ProjectOverviewProps = {
  description: string;
  error: string | null;
  handoff: ProjectHandoff | null;
  isLoading: boolean;
  isSaving: boolean;
  name: string;
  onDescriptionChange: (value: string) => void;
  onNameChange: (value: string) => void;
  onRefresh: () => void;
  onStatusToggle: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  project: Project | null;
  review: ProjectReview | null;
};

export function ProjectOverview({
  description,
  error,
  handoff,
  isLoading,
  isSaving,
  name,
  onDescriptionChange,
  onNameChange,
  onRefresh,
  onStatusToggle,
  onSubmit,
  project,
  review,
}: ProjectOverviewProps) {
  return (
    <>
      <section className="workspace-header">
        <div>
          <p className="meta">Project workspace</p>
          <div className="workspace-title-row">
            <h1>{project?.name ?? "Loading project"}</h1>
            {project ? (
              <span className={`badge project-${project.status}`}>{project.status}</span>
            ) : null}
          </div>
          {project?.description ? <p>{project.description}</p> : null}
        </div>
        <button className="button secondary" disabled={isLoading} onClick={onRefresh} type="button">
          <RefreshCw aria-hidden="true" size={18} />
          Refresh
        </button>
      </section>

      {error ? <div className="notice error">{error}</div> : null}

      <ReviewPanel review={review} />
      <HandoffPanel handoff={handoff} />
      <ProjectSettingsPanel
        description={description}
        isSaving={isSaving}
        name={name}
        onDescriptionChange={onDescriptionChange}
        onNameChange={onNameChange}
        onStatusToggle={onStatusToggle}
        onSubmit={onSubmit}
        project={project}
      />
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

function ProjectSettingsPanel({
  description,
  isSaving,
  name,
  onDescriptionChange,
  onNameChange,
  onStatusToggle,
  onSubmit,
  project,
}: ProjectSettingsPanelProps) {
  const StatusIcon = project?.status === "archived" ? ArchiveRestore : Archive;

  return (
    <section className="panel project-settings-panel" aria-labelledby="project-settings-title">
      <div className="section-heading">
        <h2 id="project-settings-title">Project settings</h2>
        {project ? <span className={`badge project-${project.status}`}>{project.status}</span> : null}
      </div>
      <div className="project-settings-grid">
        <form className="form" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="project-settings-name">Name</label>
            <input
              disabled={!project || isSaving}
              id="project-settings-name"
              maxLength={120}
              onChange={(event) => onNameChange(event.target.value)}
              value={name}
            />
          </div>
          <div className="field">
            <label htmlFor="project-settings-description">Description</label>
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
              Save details
            </button>
          </div>
        </form>
        <div className="status-action">
          <p className="meta">Current status: {project?.status ?? "loading"}</p>
          <p className="meta">
            Updated {project ? new Date(project.updated_at).toLocaleString() : "..."}
          </p>
          <button
            className="button secondary"
            disabled={!project || isSaving}
            onClick={onStatusToggle}
            type="button"
          >
            <StatusIcon aria-hidden="true" size={18} />
            {project ? projectStatusActionLabel(project.status) : "Loading status"}
          </button>
        </div>
      </div>
    </section>
  );
}

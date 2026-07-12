"use client";

import { Archive, FolderOpen, ListFilter, Plus, RefreshCw, Search } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { useLocale } from "@/i18n/locale-provider";
import { fetchJson } from "@/lib/api-client";
import {
  Project,
  ProjectStatusFilter,
  filterProjects,
  normalizeApiBaseUrl,
  projectEndpoint,
  projectStatusCounts,
  validateProjectName,
} from "@/lib/projects";

const apiBaseUrl = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL);

export default function ProjectsClient() {
  const { dateTime, errorMessage, t, text } = useLocale();
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [statusFilter, setStatusFilter] = useState<ProjectStatusFilter>("active");
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const counts = useMemo(() => projectStatusCounts(projects), [projects]);
  const visibleProjects = useMemo(
    () => filterProjects(projects, statusFilter, searchQuery),
    [projects, searchQuery, statusFilter],
  );

  const loadProjects = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchJson<Project[]>(projectEndpoint(apiBaseUrl), "Project list");
      setProjects(data);
    } catch (loadError) {
      setError(errorMessage(loadError, "Failed to load projects"));
    } finally {
      setIsLoading(false);
    }
  }, [errorMessage]);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateProjectName(name);
    if (validationError) {
      setError(text(validationError));
      return;
    }

    setIsCreating(true);
    setError(null);
    try {
      await fetchJson<Project>(projectEndpoint(apiBaseUrl), "Project create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          description: description.trim() || undefined,
        }),
      });
      setName("");
      setDescription("");
      await loadProjects();
    } catch (createError) {
      setError(errorMessage(createError, "Failed to create project"));
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <div className="grid">
      <section className="panel" aria-labelledby="create-project-title">
        <h1 id="create-project-title">{t("Create project")}</h1>
        <p>{t("Start with a song title or working idea. Creative asset generation begins later.")}</p>
        <form className="form" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="project-name">{t("Project name")}</label>
            <input
              id="project-name"
              maxLength={120}
              onChange={(event) => setName(event.target.value)}
              placeholder={t("Night Ride")}
              value={name}
            />
          </div>
          <div className="field">
            <label htmlFor="project-description">{t("Description")}</label>
            <textarea
              id="project-description"
              maxLength={1000}
              onChange={(event) => setDescription(event.target.value)}
              placeholder={t("Chinese indie rock demo about riding home late at night")}
              value={description}
            />
          </div>
          {error ? <p className="error">{error}</p> : null}
          <button className="button" disabled={isCreating} type="submit">
            <Plus aria-hidden="true" size={18} />
            {isCreating ? t("Creating") : t("Create project")}
          </button>
        </form>
      </section>

      <section aria-labelledby="projects-title">
        <div className="projects-header">
          <div>
            <h1 id="projects-title">{t("Projects")}</h1>
            <p className="meta">
              {t("{active} active - {archived} archived", counts)}
            </p>
          </div>
          <button className="button secondary" disabled={isLoading} onClick={loadProjects} type="button">
            <RefreshCw aria-hidden="true" size={18} />
            {t("Refresh")}
          </button>
        </div>

        <div className="project-toolbar" aria-label={t("Project filters")}>
          <div className="project-filter-group">
            <button
              className={`filter-button ${statusFilter === "active" ? "is-selected" : ""}`}
              onClick={() => setStatusFilter("active")}
              type="button"
            >
              <FolderOpen aria-hidden="true" size={16} />
              {t("Active")}
              <span>{counts.active}</span>
            </button>
            <button
              className={`filter-button ${statusFilter === "archived" ? "is-selected" : ""}`}
              onClick={() => setStatusFilter("archived")}
              type="button"
            >
              <Archive aria-hidden="true" size={16} />
              {t("Archived")}
              <span>{counts.archived}</span>
            </button>
            <button
              className={`filter-button ${statusFilter === "all" ? "is-selected" : ""}`}
              onClick={() => setStatusFilter("all")}
              type="button"
            >
              <ListFilter aria-hidden="true" size={16} />
              {t("All")}
              <span>{counts.all}</span>
            </button>
          </div>
          <div className="search-field">
            <Search aria-hidden="true" size={17} />
            <input
              aria-label={t("Search projects")}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder={t("Search projects")}
              value={searchQuery}
            />
          </div>
        </div>

        {isLoading ? <div className="notice">{t("Loading projects...")}</div> : null}

        {!isLoading && projects.length === 0 ? (
          <div className="empty">{t("No projects yet. Create one to verify the local stack.")}</div>
        ) : null}

        {!isLoading && projects.length > 0 && visibleProjects.length === 0 ? (
          <div className="empty">{t("No projects match the current filters.")}</div>
        ) : null}

        <div className="project-list">
          {visibleProjects.map((project) => (
            <Link className="project-card" href={`/projects/${project.id}`} key={project.id}>
              <div className="project-title-row">
                <h2>{project.name}</h2>
                <span className={`badge project-${project.status}`}>{text(project.status)}</span>
              </div>
              {project.description ? <p>{project.description}</p> : <p className="meta">{t("No description")}</p>}
              <p className="meta">{t("Updated {date}", { date: dateTime(project.updated_at) })}</p>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

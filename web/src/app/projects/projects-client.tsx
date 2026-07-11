"use client";

import { Archive, FolderOpen, ListFilter, Plus, RefreshCw, Search } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

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
      const response = await fetch(projectEndpoint(apiBaseUrl));
      if (!response.ok) {
        throw new Error(`Project list request failed with ${response.status}`);
      }
      const data = (await response.json()) as Project[];
      setProjects(data);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load projects");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProjects();
  }, [loadProjects]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateProjectName(name);
    if (validationError) {
      setError(validationError);
      return;
    }

    setIsCreating(true);
    setError(null);
    try {
      const response = await fetch(projectEndpoint(apiBaseUrl), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          description: description.trim() || undefined,
        }),
      });
      if (!response.ok) {
        throw new Error(`Project create request failed with ${response.status}`);
      }
      setName("");
      setDescription("");
      await loadProjects();
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "Failed to create project");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <div className="grid">
      <section className="panel" aria-labelledby="create-project-title">
        <h1 id="create-project-title">Create project</h1>
        <p>Start with a song title or working idea. Creative asset generation begins later.</p>
        <form className="form" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="project-name">Project name</label>
            <input
              id="project-name"
              maxLength={120}
              onChange={(event) => setName(event.target.value)}
              placeholder="Night Ride"
              value={name}
            />
          </div>
          <div className="field">
            <label htmlFor="project-description">Description</label>
            <textarea
              id="project-description"
              maxLength={1000}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Chinese indie rock demo about riding home late at night"
              value={description}
            />
          </div>
          {error ? <p className="error">{error}</p> : null}
          <button className="button" disabled={isCreating} type="submit">
            <Plus aria-hidden="true" size={18} />
            {isCreating ? "Creating" : "Create project"}
          </button>
        </form>
      </section>

      <section aria-labelledby="projects-title">
        <div className="projects-header">
          <div>
            <h1 id="projects-title">Projects</h1>
            <p className="meta">
              {counts.active} active - {counts.archived} archived
            </p>
          </div>
          <button className="button secondary" disabled={isLoading} onClick={loadProjects} type="button">
            <RefreshCw aria-hidden="true" size={18} />
            Refresh
          </button>
        </div>

        <div className="project-toolbar" aria-label="Project filters">
          <div className="project-filter-group">
            <button
              className={`filter-button ${statusFilter === "active" ? "is-selected" : ""}`}
              onClick={() => setStatusFilter("active")}
              type="button"
            >
              <FolderOpen aria-hidden="true" size={16} />
              Active
              <span>{counts.active}</span>
            </button>
            <button
              className={`filter-button ${statusFilter === "archived" ? "is-selected" : ""}`}
              onClick={() => setStatusFilter("archived")}
              type="button"
            >
              <Archive aria-hidden="true" size={16} />
              Archived
              <span>{counts.archived}</span>
            </button>
            <button
              className={`filter-button ${statusFilter === "all" ? "is-selected" : ""}`}
              onClick={() => setStatusFilter("all")}
              type="button"
            >
              <ListFilter aria-hidden="true" size={16} />
              All
              <span>{counts.all}</span>
            </button>
          </div>
          <div className="search-field">
            <Search aria-hidden="true" size={17} />
            <input
              aria-label="Search projects"
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search projects"
              value={searchQuery}
            />
          </div>
        </div>

        {isLoading ? <div className="notice">Loading projects...</div> : null}

        {!isLoading && projects.length === 0 ? (
          <div className="empty">No projects yet. Create one to verify the local stack.</div>
        ) : null}

        {!isLoading && projects.length > 0 && visibleProjects.length === 0 ? (
          <div className="empty">No projects match the current filters.</div>
        ) : null}

        <div className="project-list">
          {visibleProjects.map((project) => (
            <Link className="project-card" href={`/projects/${project.id}`} key={project.id}>
              <div className="project-title-row">
                <h2>{project.name}</h2>
                <span className={`badge project-${project.status}`}>{project.status}</span>
              </div>
              {project.description ? <p>{project.description}</p> : <p className="meta">No description</p>}
              <p className="meta">Updated {new Date(project.updated_at).toLocaleString()}</p>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}

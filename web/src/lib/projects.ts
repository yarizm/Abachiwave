export type ProjectStatus = "active" | "archived";
export type ProjectStatusFilter = "all" | ProjectStatus;

export type Project = {
  id: string;
  name: string;
  description: string | null;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
};

export type ProjectStatusCounts = Record<ProjectStatusFilter, number>;

export function normalizeApiBaseUrl(input: string | undefined): string {
  const value = input?.trim() || "http://localhost:8000";
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

export function projectEndpoint(apiBaseUrl: string): string {
  return `${apiBaseUrl}/api/v1/projects`;
}

export function projectDetailEndpoint(apiBaseUrl: string, projectId: string): string {
  return `${projectEndpoint(apiBaseUrl)}/${projectId}`;
}

export function projectStatusActionLabel(status: ProjectStatus): string {
  return status === "archived" ? "Restore project" : "Archive project";
}

export function projectStatusCounts(projects: Project[]): ProjectStatusCounts {
  const counts: ProjectStatusCounts = { all: projects.length, active: 0, archived: 0 };
  for (const project of projects) {
    counts[project.status] += 1;
  }
  return counts;
}

export function sortProjectsByUpdatedAt(projects: Project[]): Project[] {
  return [...projects].sort(
    (left, right) =>
      new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime(),
  );
}

export function filterProjects(
  projects: Project[],
  statusFilter: ProjectStatusFilter,
  query: string,
): Project[] {
  const normalizedQuery = query.trim().toLowerCase();
  return sortProjectsByUpdatedAt(projects).filter((project) => {
    if (statusFilter !== "all" && project.status !== statusFilter) {
      return false;
    }
    if (!normalizedQuery) {
      return true;
    }
    return [project.name, project.description ?? "", project.status]
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery);
  });
}

export function validateProjectName(value: string): string | null {
  const normalized = value.trim();
  if (!normalized) {
    return "Project name is required.";
  }
  if (normalized.length > 120) {
    return "Project name must be 120 characters or fewer.";
  }
  return null;
}

export function validateProjectDescription(value: string): string | null {
  if (value.trim().length > 1000) {
    return "Project description must be 1000 characters or fewer.";
  }
  return null;
}

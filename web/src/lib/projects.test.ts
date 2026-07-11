import assert from "node:assert/strict";
import test from "node:test";

import {
  filterProjects,
  normalizeApiBaseUrl,
  projectDetailEndpoint,
  projectEndpoint,
  projectStatusCounts,
  projectStatusActionLabel,
  sortProjectsByUpdatedAt,
  validateProjectDescription,
  validateProjectName,
  type Project,
} from "./projects";

function project(
  id: string,
  name: string,
  status: Project["status"],
  updatedAt: string,
  description: string | null = null,
): Project {
  return {
    id,
    name,
    description,
    status,
    created_at: "2026-07-08T00:00:00Z",
    updated_at: updatedAt,
  };
}

test("normalizeApiBaseUrl trims trailing slash and defaults to local API", () => {
  assert.equal(normalizeApiBaseUrl(undefined), "http://localhost:8000");
  assert.equal(normalizeApiBaseUrl("http://localhost:8000/"), "http://localhost:8000");
});

test("projectEndpoint builds projects collection URL", () => {
  assert.equal(projectEndpoint("http://localhost:8000"), "http://localhost:8000/api/v1/projects");
  assert.equal(
    projectDetailEndpoint("http://localhost:8000", "project-1"),
    "http://localhost:8000/api/v1/projects/project-1",
  );
});

test("validateProjectName requires a non-blank name", () => {
  assert.equal(validateProjectName("  "), "Project name is required.");
  assert.equal(validateProjectName("Night Ride"), null);
});

test("validateProjectDescription enforces the API description limit", () => {
  assert.equal(validateProjectDescription("A local song idea"), null);
  assert.equal(
    validateProjectDescription("x".repeat(1001)),
    "Project description must be 1000 characters or fewer.",
  );
});

test("projectStatusActionLabel returns the next project action", () => {
  assert.equal(projectStatusActionLabel("active"), "Archive project");
  assert.equal(projectStatusActionLabel("archived"), "Restore project");
});

test("project list helpers count, sort, and filter local projects", () => {
  const projects = [
    project("p1", "Night Ride", "active", "2026-07-08T00:00:00Z", "Indie rock"),
    project("p2", "Old Demo", "archived", "2026-07-08T00:02:00Z", "Reference"),
    project("p3", "Morning Sketch", "active", "2026-07-08T00:01:00Z"),
  ];

  assert.deepEqual(projectStatusCounts(projects), { all: 3, active: 2, archived: 1 });
  assert.deepEqual(
    sortProjectsByUpdatedAt(projects).map((item) => item.id),
    ["p2", "p3", "p1"],
  );
  assert.deepEqual(
    filterProjects(projects, "active", "sketch").map((item) => item.id),
    ["p3"],
  );
  assert.deepEqual(
    filterProjects(projects, "archived", "").map((item) => item.id),
    ["p2"],
  );
});

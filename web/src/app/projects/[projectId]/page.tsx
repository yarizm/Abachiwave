"use client";

import { ProjectOverview } from "@/components/workspace/project-overview";

import { useWorkspace } from "./workspace-provider";

/**
 * Readiness and handoff. The creation chain is not repeated here — it is the
 * navigation in the workspace shell above.
 */
export default function ProjectOverviewPage() {
  const { projectHandoff, projectReview } = useWorkspace();
  return <ProjectOverview handoff={projectHandoff} review={projectReview} />;
}

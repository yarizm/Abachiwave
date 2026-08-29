"use client";

import { ReactNode } from "react";

import { ProjectHeader } from "@/components/workspace/project-overview";
import { WorkspaceNav } from "@/components/workspace/workspace-nav";

import { useWorkspace } from "./workspace-provider";

/**
 * The frame every workspace route renders inside: project identity, the load
 * error, and the creation-chain navigation. Only the panels below it change
 * when you move between routes.
 */
export function WorkspaceShell({ children }: { children: ReactNode }) {
  const {
    creationStage,
    error,
    errorHint,
    isLoading,
    loadWorkspace,
    project,
    projectId,
  } = useWorkspace();

  return (
    <div className="workspace">
      <ProjectHeader
        error={error}
        errorHint={errorHint}
        isLoading={isLoading}
        onErrorHintAction={loadWorkspace}
        onRefresh={loadWorkspace}
        project={project}
      />
      <WorkspaceNav projectId={projectId} stage={creationStage} />
      {children}
    </div>
  );
}

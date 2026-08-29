"use client";

import { ProjectSettingsPanel } from "@/components/workspace/project-overview";

import { useWorkspace } from "../workspace-provider";

export default function ProjectSettingsPage() {
  const {
    handleProjectSettingsSubmit,
    handleProjectStatusToggle,
    pendingActions,
    project,
    projectDescriptionDraft,
    projectNameDraft,
    setProjectDescriptionDraft,
    setProjectNameDraft,
  } = useWorkspace();
  return (
    <ProjectSettingsPanel
      description={projectDescriptionDraft}
      isSaving={pendingActions.isPending("project")}
      name={projectNameDraft}
      onDescriptionChange={setProjectDescriptionDraft}
      onNameChange={setProjectNameDraft}
      onStatusToggle={handleProjectStatusToggle}
      onSubmit={handleProjectSettingsSubmit}
      project={project}
    />
  );
}

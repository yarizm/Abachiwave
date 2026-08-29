"use client";

import dynamic from "next/dynamic";

import { useWorkspace } from "../workspace-provider";

const workspaceLoading = () => <div className="workspace-panel-loading" aria-hidden="true" />;
const DemoWorkspace = dynamic(
  () => import("@/components/workspace/demo-workspace").then((module) => module.DemoWorkspace),
  { loading: workspaceLoading },
);

export default function DemoPage() {
  const {
    assetTree,
    canGenerateDemoVersion,
    demoGuardReason,
    demoRuns,
    handleCancelRun,
    handleGenerateDemo,
    handleRetryRun,
    pendingActions,
    projectId,
    sortedDemos,
  } = useWorkspace();

  return (
    <DemoWorkspace
      assetTree={assetTree}
      canGenerate={canGenerateDemoVersion}
      disabledReason={demoGuardReason}
      demos={sortedDemos}
      isSaving={pendingActions.isPending("demo", "tasks")}
      onGenerate={handleGenerateDemo}
      onCancel={handleCancelRun}
      onRetry={handleRetryRun}
      projectId={projectId}
      runs={demoRuns}
    />
  );
}

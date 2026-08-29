"use client";

import { DeliveryWorkspace } from "@/components/workspace/delivery-workspace";

import { useWorkspace } from "../workspace-provider";

export default function ArrangementPage() {
  const {
    activeArrangement,
    arrangementDraft,
    arrangementGuardReason,
    assetTree,
    canExportProject,
    canGenerateArrangementPlan,
    exportGuardReason,
    handleArrangementSubmit,
    handleCreateExport,
    handleGenerateArrangement,
    pendingActions,
    setArrangementDraft,
    sortedExports,
  } = useWorkspace();

  return (
    <DeliveryWorkspace
      activeArrangement={activeArrangement}
      arrangementPlan={arrangementDraft}
      assetTree={assetTree}
      canExport={canExportProject}
      canGenerateArrangement={canGenerateArrangementPlan}
      arrangementDisabledReason={arrangementGuardReason}
      exportDisabledReason={exportGuardReason}
      exports={sortedExports}
      isSaving={pendingActions.isPending("delivery")}
      onArrangementChange={setArrangementDraft}
      onArrangementSubmit={handleArrangementSubmit}
      onCreateExport={handleCreateExport}
      onGenerateArrangement={handleGenerateArrangement}
    />
  );
}

"use client";

import dynamic from "next/dynamic";

import { StructureWorkspace } from "@/components/workspace/structure-workspace";
import {
  SongSpecVersionsPanel,
  SongSpecWorkspace,
} from "@/components/workspace/song-spec-workspace";

import { useWorkspace } from "../workspace-provider";

const workspaceLoading = () => <div className="workspace-panel-loading" aria-hidden="true" />;
const CandidateWorkspace = dynamic(
  () =>
    import("@/components/workspace/candidate-workspace").then(
      (module) => module.CandidateWorkspace,
    ),
  { loading: workspaceLoading },
);

export default function SongSpecPage() {
  const {
    activeVersion,
    aiLoadErrors,
    answers,
    approvedVersion,
    candidates,
    canGenerateArrangementPlan,
    draftForm,
    handleApprove,
    handleCancelRun,
    handleGenerateCandidates,
    handleGenerateDraft,
    handleIntakeSubmit,
    handleSelectCandidate,
    handleSongSpecSubmit,
    handleStructureChange,
    idea,
    latestIntake,
    loadWorkspace,
    pendingActions,
    projectId,
    providerProfiles,
    setAnswers,
    setDraftForm,
    setIdea,
    sortedVersions,
    state,
    textRuns,
  } = useWorkspace();

  return (
    <>
      <SongSpecWorkspace
        activeVersion={activeVersion}
        answers={answers}
        draftForm={draftForm}
        idea={idea}
        isSaving={pendingActions.isPending("songSpec")}
        latestIntake={latestIntake}
        onAnswersChange={setAnswers}
        onApprove={handleApprove}
        onDraftChange={setDraftForm}
        onGenerateDraft={handleGenerateDraft}
        onIdeaChange={setIdea}
        onIntakeSubmit={handleIntakeSubmit}
        onSongSpecSubmit={handleSongSpecSubmit}
        state={state}
        structureLocked={Boolean(approvedVersion)}
      />

      <StructureWorkspace
        isSaving={pendingActions.isPending("structure")}
        onChange={handleStructureChange}
        projectId={projectId}
        sourceVersion={approvedVersion}
      />

      <CandidateWorkspace
        approvedSongSpecId={approvedVersion?.id ?? null}
        canGenerateArrangement={canGenerateArrangementPlan}
        candidates={candidates}
        isSaving={pendingActions.isPending("ai", "tasks")}
        latestIntakeId={latestIntake?.intake_id ?? null}
        loadErrors={aiLoadErrors}
        onCancel={handleCancelRun}
        onGenerate={handleGenerateCandidates}
        onRetry={loadWorkspace}
        onSelect={handleSelectCandidate}
        providers={providerProfiles}
        runs={textRuns}
      />

      <SongSpecVersionsPanel versions={sortedVersions} />
    </>
  );
}

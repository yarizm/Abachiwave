"use client";

import dynamic from "next/dynamic";

import { CollaborationWorkspace } from "@/components/workspace/collaboration-workspace";

import { useWorkspace } from "../workspace-provider";

const workspaceLoading = () => <div className="workspace-panel-loading" aria-hidden="true" />;
const RevisionWorkspace = dynamic(
  () =>
    import("@/components/workspace/revision-workspace").then((module) => module.RevisionWorkspace),
  { loading: workspaceLoading },
);

export default function HistoryPage() {
  const {
    commentAuthor,
    commentBody,
    commentTargets,
    commentTargetValue,
    handleApplyRevision,
    handleCompareVersions,
    handleCreateComment,
    handleCreateRevision,
    handleRejectRevision,
    handleRestoreVersion,
    handleUpdateComment,
    melodyAssets,
    pendingActions,
    revisionFeedback,
    setCommentAuthor,
    setCommentBody,
    setCommentTargetValue,
    setRevisionFeedback,
    sortedArrangements,
    sortedComments,
    sortedDemos,
    sortedLyrics,
    sortedProjectEvents,
    sortedRevisions,
    versionDiff,
  } = useWorkspace();

  return (
    <>
      <RevisionWorkspace
        arrangements={sortedArrangements}
        demos={sortedDemos}
        feedback={revisionFeedback}
        isSaving={pendingActions.isPending("revision")}
        lyrics={sortedLyrics}
        melodyAssets={melodyAssets}
        onApply={handleApplyRevision}
        onCompare={handleCompareVersions}
        onFeedbackChange={setRevisionFeedback}
        onPlan={handleCreateRevision}
        onReject={handleRejectRevision}
        onRestore={handleRestoreVersion}
        revisions={sortedRevisions}
        versionDiff={versionDiff}
      />

      <CollaborationWorkspace
        author={commentAuthor}
        body={commentBody}
        comments={sortedComments}
        events={sortedProjectEvents}
        isSaving={pendingActions.isPending("collaboration")}
        onAuthorChange={setCommentAuthor}
        onBodyChange={setCommentBody}
        onSubmit={handleCreateComment}
        onTargetChange={setCommentTargetValue}
        onUpdateStatus={handleUpdateComment}
        targetOptions={commentTargets}
        targetValue={commentTargetValue}
      />
    </>
  );
}

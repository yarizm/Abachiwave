"use client";

import dynamic from "next/dynamic";

import { useWorkspace } from "../workspace-provider";

const workspaceLoading = () => <div className="workspace-panel-loading" aria-hidden="true" />;
const AudioWorkspace = dynamic(
  () => import("@/components/workspace/audio-workspace").then((module) => module.AudioWorkspace),
  { loading: workspaceLoading },
);

export default function AudioPage() {
  const {
    approvedVersion,
    audioRuns,
    audioUploadFile,
    audioUploadKind,
    audioUploadNotes,
    handleAnalyzeReference,
    handleApplyReferenceAnalysis,
    handleAudioUploadSubmit,
    handleCancelRun,
    handleCreateAudioDerivative,
    handleCreateAudioMarker,
    handleDeleteAudioMarker,
    handleExtractAudioMidi,
    handleUpdateAudioMarker,
    handleUpdateAudioUpload,
    pendingActions,
    projectId,
    setAudioUploadFile,
    setAudioUploadKind,
    setAudioUploadNotes,
    sortedAudioDerivatives,
    sortedAudioMarkers,
    sortedAudioUploads,
    sortedReferenceAnalyses,
  } = useWorkspace();

  return (
    <AudioWorkspace
      analyses={sortedReferenceAnalyses}
      approvedSongSpecId={approvedVersion?.id ?? null}
      derivatives={sortedAudioDerivatives}
      file={audioUploadFile}
      isSaving={pendingActions.isPending("audio", "tasks")}
      kind={audioUploadKind}
      notes={audioUploadNotes}
      markers={sortedAudioMarkers}
      onAnalyze={handleAnalyzeReference}
      onApplyAnalysis={handleApplyReferenceAnalysis}
      onCancel={handleCancelRun}
      onCreateDerivative={handleCreateAudioDerivative}
      onCreateMarker={handleCreateAudioMarker}
      onDeleteMarker={handleDeleteAudioMarker}
      onExtract={handleExtractAudioMidi}
      onFileChange={setAudioUploadFile}
      onKindChange={setAudioUploadKind}
      onNotesChange={setAudioUploadNotes}
      onUpdateUpload={handleUpdateAudioUpload}
      onUpdateMarker={handleUpdateAudioMarker}
      onUpload={handleAudioUploadSubmit}
      projectId={projectId}
      runs={audioRuns}
      uploads={sortedAudioUploads}
    />
  );
}

"use client";

import dynamic from "next/dynamic";

import { useWorkspace } from "../workspace-provider";

const workspaceLoading = () => <div className="workspace-panel-loading" aria-hidden="true" />;
const CompositionWorkspace = dynamic(
  () =>
    import("@/components/workspace/composition-workspace").then(
      (module) => module.CompositionWorkspace,
    ),
  { loading: workspaceLoading },
);

export default function CompositionPage() {
  const {
    activeChords,
    activeLyrics,
    canGenerateAssets,
    compositionGuardReason,
    handleChordsPreview,
    handleChordsSave,
    handleChordsTranspose,
    handleGenerateChords,
    handleGenerateLyrics,
    handleGenerateMidi,
    handleLyricsRewrite,
    handleLyricsSave,
    handleMidiSave,
    handleMidiTransform,
    pendingActions,
    projectId,
    sortedMidiAssets,
  } = useWorkspace();

  return (
    <CompositionWorkspace
      activeChords={activeChords}
      activeLyrics={activeLyrics}
      canGenerate={canGenerateAssets}
      disabledReason={compositionGuardReason}
      isGeneratingChords={pendingActions.isPending("chords")}
      isGeneratingLyrics={pendingActions.isPending("composition")}
      isPreviewingChords={pendingActions.isPending("chordsPreview")}
      isRewritingLyrics={pendingActions.isPending("lyricsRewrite")}
      isSavingComposition={pendingActions.isPending("composition", "midi")}
      isSavingChords={pendingActions.isPending("chords")}
      isSavingLyrics={pendingActions.isPending("lyrics")}
      isTransposingChords={pendingActions.isPending("chordsTranspose")}
      midiAssets={sortedMidiAssets}
      onGenerateChords={handleGenerateChords}
      onGenerateLyrics={handleGenerateLyrics}
      onGenerateMidi={handleGenerateMidi}
      onChordsPreview={handleChordsPreview}
      onChordsSave={handleChordsSave}
      onChordsTranspose={handleChordsTranspose}
      onLyricsRewrite={handleLyricsRewrite}
      onLyricsSave={handleLyricsSave}
      onMidiSave={handleMidiSave}
      onMidiTransform={handleMidiTransform}
      projectId={projectId}
    />
  );
}

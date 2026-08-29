"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import { useLocale } from "@/i18n/locale-provider";

import { useWorkspace } from "../workspace-provider";

const workspaceLoading = () => <div className="workspace-panel-loading" aria-hidden="true" />;
const SectionComposition = dynamic(
  () =>
    import("@/components/workspace/section-composition").then(
      (module) => module.SectionComposition,
    ),
  { loading: workspaceLoading },
);
const CompositionWorkspace = dynamic(
  () =>
    import("@/components/workspace/composition-workspace").then(
      (module) => module.CompositionWorkspace,
    ),
  { loading: workspaceLoading },
);

type CompositionView = "sections" | "editors";

/**
 * Two ways to work on the same song.
 *
 * The section view reads across assets — a section's words, chords and melody in
 * one row — which is what writing actually needs and what the stacked editors made
 * impossible. The full editors keep the heavy tools: the rewrite studio, transpose,
 * quantize, note-level piano-roll editing.
 *
 * Only one is mounted at a time. Both share the same lyric and chord drafts through
 * their persisted storage keys, so an unsaved edit survives switching between them.
 */
export default function CompositionPage() {
  const { t } = useLocale();
  const [view, setView] = useState<CompositionView>("sections");
  const {
    activeChords,
    activeLyrics,
    approvedVersion,
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
    melodyAssets,
    pendingActions,
    projectId,
    sortedMidiAssets,
  } = useWorkspace();

  // Newest melody that actually has notes. An extraction that found nothing still
  // creates a version, and letting that empty version shadow a populated earlier one
  // would report "no melody" for a song that has one.
  const melodyAsset =
    melodyAssets.find((asset) => asset.note_events.length > 0) ?? melodyAssets[0] ?? null;

  return (
    <>
      <div className="composition-view-switch">
        <div className="segmented-control" aria-label={t("Composition view")}>
          {(["sections", "editors"] as const).map((option) => (
            <button
              aria-pressed={view === option}
              className={view === option ? "active" : ""}
              key={option}
              onClick={() => setView(option)}
              type="button"
            >
              {t(option === "sections" ? "Section view" : "Full editors")}
            </button>
          ))}
        </div>
      </div>

      {view === "sections" ? (
        <SectionComposition
          activeChords={activeChords}
          activeLyrics={activeLyrics}
          canGenerate={canGenerateAssets}
          disabledReason={compositionGuardReason}
          isGeneratingChords={pendingActions.isPending("chords")}
          isGeneratingLyrics={pendingActions.isPending("composition")}
          isSavingChords={pendingActions.isPending("chords")}
          isSavingLyrics={pendingActions.isPending("lyrics")}
          isSavingMelody={pendingActions.isPending("midi")}
          melodyAsset={melodyAsset}
          onChordsSave={handleChordsSave}
          onGenerateChords={handleGenerateChords}
          onGenerateLyrics={handleGenerateLyrics}
          onGenerateMidi={handleGenerateMidi}
          onLyricsSave={handleLyricsSave}
          onMelodySave={handleMidiSave}
          projectId={projectId}
          structure={approvedVersion?.song_spec.structure_sections ?? []}
          timeSignature={approvedVersion?.song_spec.time_signature ?? null}
        />
      ) : (
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
      )}
    </>
  );
}

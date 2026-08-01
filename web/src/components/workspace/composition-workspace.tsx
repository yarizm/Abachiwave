"use client";

import { ChordWorkspace } from "@/components/workspace/chord-workspace";
import { LyricsWorkspace } from "@/components/workspace/lyrics-workspace";
import { MidiWorkspace } from "@/components/workspace/midi-workspace";
import {
  ChordProgressionVersion,
  ChordPreview,
  ChordSection,
  LyricsVersion,
  MidiAssetVersion,
  MidiNoteEvent,
  MidiTransformPayload,
} from "@/lib/composition";
import type {
  LyricsRewritePayload,
  LyricsRewritePreview,
} from "@/lib/lyrics-editor";
import type { HookCandidate, LyricSection } from "@/lib/composition";

type CompositionWorkspaceProps = {
  activeChords: ChordProgressionVersion | null;
  activeLyrics: LyricsVersion | null;
  canGenerate: boolean;
  disabledReason?: string | null;
  isGeneratingChords: boolean;
  isGeneratingLyrics: boolean;
  isPreviewingChords: boolean;
  isRewritingLyrics: boolean;
  isSavingComposition: boolean;
  isSavingChords: boolean;
  isSavingLyrics: boolean;
  isTransposingChords: boolean;
  midiAssets: MidiAssetVersion[];
  onChordsPreview: (sections: ChordSection[]) => Promise<ChordPreview>;
  onChordsSave: (sections: ChordSection[]) => Promise<void>;
  onChordsTranspose: (semitones: number, sectionIds: string[] | null) => Promise<void>;
  onGenerateChords: () => void;
  onGenerateLyrics: () => void;
  onGenerateMidi: () => void;
  onLyricsRewrite: (payload: LyricsRewritePayload) => Promise<LyricsRewritePreview>;
  onLyricsSave: (sections: LyricSection[], hookCandidates: HookCandidate[]) => Promise<void>;
  onMidiSave: (asset: MidiAssetVersion, noteEvents: MidiNoteEvent[]) => Promise<void>;
  onMidiTransform: (asset: MidiAssetVersion, payload: MidiTransformPayload) => Promise<void>;
  projectId: string;
};

export function CompositionWorkspace({
  activeChords,
  activeLyrics,
  canGenerate,
  disabledReason,
  isGeneratingChords,
  isGeneratingLyrics,
  isPreviewingChords,
  isRewritingLyrics,
  isSavingComposition,
  isSavingChords,
  isSavingLyrics,
  isTransposingChords,
  midiAssets,
  onChordsPreview,
  onChordsSave,
  onChordsTranspose,
  onGenerateChords,
  onGenerateLyrics,
  onGenerateMidi,
  onLyricsRewrite,
  onLyricsSave,
  onMidiSave,
  onMidiTransform,
  projectId,
}: CompositionWorkspaceProps) {
  return (
    <>
      <LyricsWorkspace
        activeLyrics={activeLyrics}
        canGenerate={canGenerate}
        disabledReason={disabledReason}
        isGenerating={isGeneratingLyrics}
        isRewriting={isRewritingLyrics}
        isSaving={isSavingLyrics}
        onGenerate={onGenerateLyrics}
        onRewrite={onLyricsRewrite}
        onSave={onLyricsSave}
        projectId={projectId}
      />
      <ChordWorkspace
        activeChords={activeChords}
        canGenerate={canGenerate}
        disabledReason={disabledReason}
        isGenerating={isGeneratingChords}
        isPreviewing={isPreviewingChords}
        isSaving={isSavingChords}
        isTransposing={isTransposingChords}
        onGenerate={onGenerateChords}
        onPreview={onChordsPreview}
        onSave={onChordsSave}
        onTranspose={onChordsTranspose}
        projectId={projectId}
      />
      <MidiWorkspace
        assets={midiAssets}
        canGenerate={canGenerate}
        disabledReason={disabledReason}
        isSaving={isSavingComposition}
        onGenerate={onGenerateMidi}
        onSave={onMidiSave}
        onTransform={onMidiTransform}
        projectId={projectId}
      />
    </>
  );
}

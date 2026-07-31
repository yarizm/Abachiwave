"use client";

import { Music2 } from "lucide-react";

import { ChordWorkspace } from "@/components/workspace/chord-workspace";
import { DownloadButton } from "@/components/workspace/download-button";
import { LyricsWorkspace } from "@/components/workspace/lyrics-workspace";
import { formatBytes } from "@/components/workspace/workspace-format";
import { useLocale } from "@/i18n/locale-provider";
import {
  ChordProgressionVersion,
  ChordPreview,
  ChordSection,
  LyricsVersion,
  MidiAssetVersion,
  midiAssetDownloadEndpoint,
} from "@/lib/composition";
import type {
  LyricsRewritePayload,
  LyricsRewritePreview,
} from "@/lib/lyrics-editor";
import type { HookCandidate, LyricSection } from "@/lib/composition";
import { normalizeApiBaseUrl } from "@/lib/projects";

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
  projectId: string;
};

const apiBaseUrl = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL);

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
      <MidiPanel
        assets={midiAssets}
        canGenerate={canGenerate}
        disabledReason={disabledReason}
        isSaving={isSavingComposition}
        onGenerate={onGenerateMidi}
        projectId={projectId}
      />
    </>
  );
}

function MidiPanel({
  assets,
  canGenerate,
  disabledReason,
  isSaving,
  onGenerate,
  projectId,
}: {
  assets: MidiAssetVersion[];
  canGenerate: boolean;
  disabledReason?: string | null;
  isSaving: boolean;
  onGenerate: () => void;
  projectId: string;
}) {
  const { t, text } = useLocale();
  const midiDisabled = !canGenerate || isSaving;
  return (
    <section className="panel" aria-labelledby="midi-title">
      <div className="section-heading">
        <h2 id="midi-title">MIDI</h2>
        <span className="badge">{assets.length}</span>
      </div>
      <button
        className="button secondary full-width"
        data-guarded={!canGenerate || undefined}
        disabled={midiDisabled}
        onClick={onGenerate}
        title={!canGenerate ? (disabledReason ?? undefined) : undefined}
        type="button"
      >
        <Music2 aria-hidden="true" size={18} />
        {t("Generate MIDI")}
      </button>
      {assets.length ? (
        <div className="asset-list">
          {assets.map((asset) => (
            <div className="asset-row" key={asset.id}>
              <div>
                <strong>{asset.filename}</strong>
                <p className="meta">
                  {text(asset.kind)} v{asset.version_number} - {formatBytes(asset.size_bytes)}
                </p>
              </div>
              <DownloadButton
                filename={asset.filename}
                url={midiAssetDownloadEndpoint(apiBaseUrl, projectId, asset.id)}
              />
            </div>
          ))}
        </div>
      ) : (
        <p className="empty">{t("Generated chord, melody, and hook MIDI files will appear here.")}</p>
      )}
    </section>
  );
}

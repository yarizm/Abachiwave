"use client";

import { FilePlus2, Music2, Save } from "lucide-react";
import { FormEvent } from "react";

import { DownloadButton } from "@/components/workspace/download-button";
import { formatBytes } from "@/components/workspace/workspace-format";
import { useLocale } from "@/i18n/locale-provider";
import {
  ChordProgressionVersion,
  ChordSection,
  HookCandidate,
  LyricSection,
  LyricsVersion,
  MidiAssetVersion,
  midiAssetDownloadEndpoint,
} from "@/lib/composition";
import { normalizeApiBaseUrl } from "@/lib/projects";

type CompositionWorkspaceProps = {
  activeChords: ChordProgressionVersion | null;
  activeLyrics: LyricsVersion | null;
  canGenerate: boolean;
  chordDraft: ChordSection[];
  hookDraft: HookCandidate[];
  isSaving: boolean;
  lyricDraft: LyricSection[];
  midiAssets: MidiAssetVersion[];
  onChordBarsChange: (index: number, bars: number) => void;
  onChordsChange: (index: number, chords: string[]) => void;
  onChordsSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onGenerateChords: () => void;
  onGenerateLyrics: () => void;
  onGenerateMidi: () => void;
  onHookChange: (index: number, text: string) => void;
  onLyricsSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onLyricSectionChange: (index: number, text: string) => void;
  projectId: string;
};

const apiBaseUrl = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL);

export function CompositionWorkspace({
  activeChords,
  activeLyrics,
  canGenerate,
  chordDraft,
  hookDraft,
  isSaving,
  lyricDraft,
  midiAssets,
  onChordBarsChange,
  onChordsChange,
  onChordsSubmit,
  onGenerateChords,
  onGenerateLyrics,
  onGenerateMidi,
  onHookChange,
  onLyricsSubmit,
  onLyricSectionChange,
  projectId,
}: CompositionWorkspaceProps) {
  return (
    <>
      <LyricsPanel
        activeLyrics={activeLyrics}
        canGenerate={canGenerate}
        hookDraft={hookDraft}
        isSaving={isSaving}
        lyricDraft={lyricDraft}
        onGenerate={onGenerateLyrics}
        onHookChange={onHookChange}
        onSectionChange={onLyricSectionChange}
        onSubmit={onLyricsSubmit}
      />
      <ChordsPanel
        activeChords={activeChords}
        canGenerate={canGenerate}
        chordDraft={chordDraft}
        isSaving={isSaving}
        onBarsChange={onChordBarsChange}
        onChordsChange={onChordsChange}
        onGenerate={onGenerateChords}
        onSubmit={onChordsSubmit}
      />
      <MidiPanel
        assets={midiAssets}
        canGenerate={canGenerate}
        isSaving={isSaving}
        onGenerate={onGenerateMidi}
        projectId={projectId}
      />
    </>
  );
}

function LyricsPanel({
  activeLyrics,
  canGenerate,
  hookDraft,
  isSaving,
  lyricDraft,
  onGenerate,
  onHookChange,
  onSectionChange,
  onSubmit,
}: {
  activeLyrics: LyricsVersion | null;
  canGenerate: boolean;
  hookDraft: HookCandidate[];
  isSaving: boolean;
  lyricDraft: LyricSection[];
  onGenerate: () => void;
  onHookChange: (index: number, text: string) => void;
  onSectionChange: (index: number, text: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const { t, text } = useLocale();
  return (
    <section className="panel" aria-labelledby="lyrics-title">
      <div className="section-heading">
        <h2 id="lyrics-title">{t("Lyrics")}</h2>
        {activeLyrics ? <span className="badge">v{activeLyrics.version_number}</span> : null}
      </div>
      <button
        className="button secondary full-width"
        disabled={!canGenerate || isSaving}
        onClick={onGenerate}
        type="button"
      >
        <FilePlus2 aria-hidden="true" size={18} />
        {t("Generate lyrics")}
      </button>
      {activeLyrics ? (
        <form className="form compact-form" onSubmit={onSubmit}>
          {lyricDraft.map((section, index) => (
            <div className="field" key={section.section_id}>
              <label htmlFor={`lyrics-${section.section_id}`}>{text(section.label)}</label>
              <textarea
                id={`lyrics-${section.section_id}`}
                onChange={(event) => onSectionChange(index, event.target.value)}
                value={section.text}
              />
            </div>
          ))}
          {hookDraft.length ? (
            <div className="mini-list">
              <p className="meta">{t("Hook candidates")}</p>
              {hookDraft.map((hook, index) => (
                <input
                  aria-label={t("Hook candidate {number}", { number: index + 1 })}
                  key={hook.id}
                  onChange={(event) => onHookChange(index, event.target.value)}
                  value={hook.text}
                />
              ))}
            </div>
          ) : null}
          <button className="button" disabled={isSaving} type="submit">
            <Save aria-hidden="true" size={18} />
            {t("Save lyrics version")}
          </button>
        </form>
      ) : (
        <p className="empty">{t("Approve a SongSpec, then generate a lyrics draft.")}</p>
      )}
    </section>
  );
}

function ChordsPanel({
  activeChords,
  canGenerate,
  chordDraft,
  isSaving,
  onBarsChange,
  onChordsChange,
  onGenerate,
  onSubmit,
}: {
  activeChords: ChordProgressionVersion | null;
  canGenerate: boolean;
  chordDraft: ChordSection[];
  isSaving: boolean;
  onBarsChange: (index: number, bars: number) => void;
  onChordsChange: (index: number, chords: string[]) => void;
  onGenerate: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const { t, text } = useLocale();
  return (
    <section className="panel" aria-labelledby="chords-title">
      <div className="section-heading">
        <h2 id="chords-title">{t("Chords")}</h2>
        {activeChords ? <span className="badge">v{activeChords.version_number}</span> : null}
      </div>
      <button
        className="button secondary full-width"
        disabled={!canGenerate || isSaving}
        onClick={onGenerate}
        type="button"
      >
        <Music2 aria-hidden="true" size={18} />
        {t("Generate chords")}
      </button>
      {activeChords ? (
        <form className="form compact-form" onSubmit={onSubmit}>
          {chordDraft.map((section, index) => (
            <div className="chord-editor-row" key={section.section_id}>
              <div className="field">
                <label htmlFor={`chords-${section.section_id}`}>{text(section.label)}</label>
                <input
                  id={`chords-${section.section_id}`}
                  onChange={(event) => onChordsChange(index, splitChordInput(event.target.value))}
                  value={section.chords.join(", ")}
                />
              </div>
              <div className="field narrow-field">
                <label htmlFor={`bars-${section.section_id}`}>{t("Bars")}</label>
                <input
                  id={`bars-${section.section_id}`}
                  min={1}
                  onChange={(event) => onBarsChange(index, Number(event.target.value))}
                  type="number"
                  value={section.bars}
                />
              </div>
            </div>
          ))}
          <button className="button" disabled={isSaving} type="submit">
            <Save aria-hidden="true" size={18} />
            {t("Save chords version")}
          </button>
        </form>
      ) : (
        <p className="empty">{t("Approve a SongSpec, then generate a chord progression.")}</p>
      )}
    </section>
  );
}

function MidiPanel({
  assets,
  canGenerate,
  isSaving,
  onGenerate,
  projectId,
}: {
  assets: MidiAssetVersion[];
  canGenerate: boolean;
  isSaving: boolean;
  onGenerate: () => void;
  projectId: string;
}) {
  const { t, text } = useLocale();
  return (
    <section className="panel" aria-labelledby="midi-title">
      <div className="section-heading">
        <h2 id="midi-title">MIDI</h2>
        <span className="badge">{assets.length}</span>
      </div>
      <button
        className="button secondary full-width"
        disabled={!canGenerate || isSaving}
        onClick={onGenerate}
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

function splitChordInput(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

"use client";

import {
  ArrowDown,
  ArrowUp,
  Check,
  FilePlus2,
  Plus,
  Redo2,
  RotateCcw,
  Save,
  Sparkles,
  Trash2,
  Undo2,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { useLyricsDraft } from "@/app/projects/[projectId]/hooks/use-lyrics-draft";
import { useLocale } from "@/i18n/locale-provider";
import { EmptyStateAction } from "@/components/workspace/empty-state-action";
import type {
  HookCandidate,
  LyricSection,
  LyricsVersion,
} from "@/lib/composition";
import { validateLyricSections } from "@/lib/composition";
import {
  LyricsRewriteAction,
  LyricsRewritePayload,
  LyricsRewritePreview,
  LyricsRewriteScope,
  addLyricLine,
  applyRewriteChanges,
  lyricDiagnostics,
  moveLyricLine,
  parseLyricTerms,
  removeLyricLine,
  selectionResetKey,
  updateHookCandidate,
  updateLyricLine,
} from "@/lib/lyrics-editor";

type LyricsWorkspaceProps = {
  activeLyrics: LyricsVersion | null;
  canGenerate: boolean;
  disabledReason?: string | null;
  isGenerating: boolean;
  isRewriting: boolean;
  isSaving: boolean;
  onGenerate: () => void;
  onRewrite: (payload: LyricsRewritePayload) => Promise<LyricsRewritePreview>;
  onSave: (sections: LyricSection[], hookCandidates: HookCandidate[]) => Promise<void>;
  projectId: string;
};

type LyricsPreferences = {
  banned: string;
  preferred: string;
};

const rewriteActions: LyricsRewriteAction[] = [
  "rewrite",
  "expand",
  "compress",
  "change_rhyme",
  "adjust_tone",
];

export function LyricsWorkspace({
  activeLyrics,
  canGenerate,
  disabledReason,
  isGenerating,
  isRewriting,
  isSaving,
  onGenerate,
  onRewrite,
  onSave,
  projectId,
}: LyricsWorkspaceProps) {
  const { t, text } = useLocale();
  const editor = useLyricsDraft(projectId, activeLyrics);
  const [scope, setScope] = useState<LyricsRewriteScope>("line");
  const [action, setAction] = useState<LyricsRewriteAction>("rewrite");
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [selectedLineId, setSelectedLineId] = useState<string | null>(null);
  const [instruction, setInstruction] = useState("");
  const [tone, setTone] = useState("");
  const [rhymeEnding, setRhymeEnding] = useState("");
  const [rhymeLabel, setRhymeLabel] = useState("");
  const [preferences, setPreferences] = useState<LyricsPreferences>({
    banned: "",
    preferred: "",
  });
  const [preview, setPreview] = useState<LyricsRewritePreview | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const preferencesKey = `abachiwave:lyrics-preferences:${projectId}`;
  const selectionKey = selectionResetKey(activeLyrics);
  // Reset selection only when the active *version* changes; refetched objects
  // with the same version id (every loadWorkspace) must not discard the line
  // the user is reviewing mid-rewrite.
  const activeLyricsRef = useRef(activeLyrics);
  activeLyricsRef.current = activeLyrics;

  useEffect(() => {
    const firstSection = activeLyricsRef.current?.sections[0] ?? null;
    setSelectedSectionId(firstSection?.section_id ?? null);
    setSelectedLineId(firstSection?.lines[0]?.line_id ?? null);
    setPreview(null);
    setLocalError(null);
  }, [selectionKey]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(preferencesKey);
      const stored: unknown = raw ? JSON.parse(raw) : null;
      if (isLyricsPreferences(stored)) {
        setPreferences(stored);
      } else if (raw) {
        window.localStorage.removeItem(preferencesKey);
      }
    } catch {
      window.localStorage.removeItem(preferencesKey);
    }
  }, [preferencesKey]);

  const bannedPhrases = useMemo(
    () => parseLyricTerms(preferences.banned),
    [preferences.banned],
  );
  const preferredTerms = useMemo(
    () => parseLyricTerms(preferences.preferred),
    [preferences.preferred],
  );
  const diagnostics = useMemo(
    () => lyricDiagnostics(editor.draft.sections, bannedPhrases),
    [bannedPhrases, editor.draft.sections],
  );
  const selectedSection = editor.draft.sections.find(
    (section) => section.section_id === selectedSectionId,
  );
  const canRequestRewrite =
    Boolean(activeLyrics) &&
    (scope === "all" ||
      (scope === "section" && Boolean(selectedSectionId)) ||
      (scope === "line" && Boolean(selectedLineId)));

  function updatePreferences(next: LyricsPreferences) {
    setPreferences(next);
    window.localStorage.setItem(preferencesKey, JSON.stringify(next));
  }

  function selectLine(sectionId: string, lineId: string) {
    setSelectedSectionId(sectionId);
    setSelectedLineId(lineId);
    setScope("line");
    setPreview(null);
  }

  function selectSection(sectionId: string) {
    setSelectedSectionId(sectionId);
    setSelectedLineId(null);
    setScope("section");
    setPreview(null);
  }

  function deleteLine(sectionId: string, lineId: string) {
    const section = editor.draft.sections.find((item) => item.section_id === sectionId);
    if (!section || section.lines.length <= 1) return;
    const index = section.lines.findIndex((line) => line.line_id === lineId);
    const remaining = section.lines.filter((line) => line.line_id !== lineId);
    editor.update(removeLyricLine(editor.draft, sectionId, lineId));
    if (selectedLineId === lineId) {
      const nextLine = remaining[Math.min(Math.max(index, 0), remaining.length - 1)];
      setSelectedSectionId(sectionId);
      setSelectedLineId(nextLine.line_id);
      setScope("line");
    }
    setPreview(null);
  }

  async function handleSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateLyricSections(editor.draft.sections);
    if (validationError) {
      setLocalError(text(validationError));
      return;
    }
    const hooks = editor.draft.hookCandidates
      .map((hook) => ({ ...hook, text: hook.text.trim() }))
      .filter((hook) => hook.text);
    setLocalError(null);
    await onSave(editor.draft.sections, hooks);
  }

  async function handleRewrite() {
    if (!canRequestRewrite) return;
    if (action === "change_rhyme" && !rhymeEnding.trim()) {
      setLocalError(t("Enter a rhyme ending before generating a preview."));
      return;
    }
    setLocalError(null);
    try {
      const result = await onRewrite({
        scope,
        action,
        section_id: scope === "section" ? selectedSectionId ?? undefined : undefined,
        line_id: scope === "line" ? selectedLineId ?? undefined : undefined,
        instruction: instruction.trim() || undefined,
        tone: tone.trim() || undefined,
        rhyme_ending: rhymeEnding.trim() || undefined,
        rhyme_label: rhymeLabel.trim() || undefined,
        banned_phrases: bannedPhrases,
        preferred_terms: preferredTerms,
        sections: editor.draft.sections,
      });
      setPreview(result);
    } catch {
      setPreview(null);
    }
  }

  function acceptChanges(lineIds: string[]) {
    if (!preview) return;
    editor.update(applyRewriteChanges(editor.draft, preview.changes, new Set(lineIds)));
    setPreview(null);
  }

  return (
    <section className="panel lyrics-workspace" aria-labelledby="lyrics-title">
      <div className="section-heading lyrics-heading">
        <div>
          <div className="section-heading-inline">
            <h2 id="lyrics-title">{t("Lyrics editor")}</h2>
            {activeLyrics ? <span className="badge">v{activeLyrics.version_number}</span> : null}
            {editor.dirty ? <span className="status-chip warning">{t("Unsaved")}</span> : null}
          </div>
          <p className="meta">{t("Edit controlled lyric lines, rhyme marks, and rewrite candidates.")}</p>
        </div>
        <div className="lyrics-toolbar">
          <button
            className="button secondary icon-only"
            disabled={!editor.canUndo || isSaving}
            onClick={editor.undo}
            title={t("Undo")}
            type="button"
          >
            <Undo2 aria-hidden="true" size={17} />
            <span className="sr-only">{t("Undo")}</span>
          </button>
          <button
            className="button secondary icon-only"
            disabled={!editor.canRedo || isSaving}
            onClick={editor.redo}
            title={t("Redo")}
            type="button"
          >
            <Redo2 aria-hidden="true" size={17} />
            <span className="sr-only">{t("Redo")}</span>
          </button>
          <button
            className="button secondary"
            data-guarded={!canGenerate || undefined}
            disabled={!canGenerate || isGenerating || isSaving}
            onClick={onGenerate}
            title={!canGenerate ? (disabledReason ?? undefined) : undefined}
            type="button"
          >
            <FilePlus2 aria-hidden="true" size={17} />
            {t("Generate lyrics")}
          </button>
        </div>
      </div>

      {editor.restored ? <p className="notice compact-notice">{t("Local draft restored")}</p> : null}

      {activeLyrics ? (
        <form className="lyrics-editor-form" onSubmit={handleSave}>
          <div className="lyrics-sections">
            {editor.draft.sections.map((section) => (
              <section className="lyrics-section-editor" key={section.section_id}>
                <div className="lyrics-section-heading">
                  <div>
                    <h3>{text(section.label)}</h3>
                    <span className="meta">
                      {t("{count} lines", { count: section.lines.length })}
                    </span>
                  </div>
                  <button
                    className="button ghost compact-button"
                    onClick={() => selectSection(section.section_id)}
                    type="button"
                  >
                    <Sparkles aria-hidden="true" size={15} />
                    {t("Rewrite section")}
                  </button>
                </div>
                <div className="lyric-line-list">
                  {section.lines.map((line, lineIndex) => {
                    const hasDiagnostic = diagnostics.some(
                      (item) => item.lineId === line.line_id,
                    );
                    return (
                      <div
                        className={`lyric-line-row${selectedLineId === line.line_id ? " selected" : ""}${hasDiagnostic ? " has-warning" : ""}`}
                        key={line.line_id}
                      >
                        <span className="lyric-line-number">{lineIndex + 1}</span>
                        <div className="lyric-line-content">
                          <textarea
                            aria-label={t("{section} line {number}", {
                              section: text(section.label),
                              number: lineIndex + 1,
                            })}
                            onChange={(event) =>
                              editor.update(
                                updateLyricLine(
                                  editor.draft,
                                  section.section_id,
                                  line.line_id,
                                  { text: event.target.value },
                                ),
                              )
                            }
                            onFocus={() => {
                              setSelectedSectionId(section.section_id);
                              setSelectedLineId(line.line_id);
                            }}
                            rows={2}
                            value={line.text}
                          />
                          <div className="lyric-line-metrics">
                            <span>{t("{count} chars", { count: line.character_count })}</span>
                            <span>{t("{count} syllables", { count: line.syllable_count })}</span>
                            <span>{t("Rhyme: {value}", { value: line.rhyme_key ?? "-" })}</span>
                            <span>
                              {t("Stress: {value}", {
                                value: line.stress_positions.join(" · ") || "-",
                              })}
                            </span>
                          </div>
                        </div>
                        <div className="lyric-rhyme-field">
                          <label htmlFor={`rhyme-${line.line_id}`}>{t("Mark")}</label>
                          <input
                            id={`rhyme-${line.line_id}`}
                            maxLength={16}
                            onChange={(event) =>
                              editor.update(
                                updateLyricLine(
                                  editor.draft,
                                  section.section_id,
                                  line.line_id,
                                  { rhymeLabel: event.target.value || null },
                                ),
                              )
                            }
                            placeholder="A"
                            value={line.rhyme_label ?? ""}
                          />
                        </div>
                        <div className="lyric-line-actions">
                          <button
                            className="button secondary icon-only"
                            disabled={lineIndex === 0}
                            onClick={() =>
                              editor.update(
                                moveLyricLine(
                                  editor.draft,
                                  section.section_id,
                                  line.line_id,
                                  -1,
                                ),
                              )
                            }
                            title={t("Move up")}
                            type="button"
                          >
                            <ArrowUp aria-hidden="true" size={15} />
                          </button>
                          <button
                            className="button secondary icon-only"
                            disabled={lineIndex === section.lines.length - 1}
                            onClick={() =>
                              editor.update(
                                moveLyricLine(
                                  editor.draft,
                                  section.section_id,
                                  line.line_id,
                                  1,
                                ),
                              )
                            }
                            title={t("Move down")}
                            type="button"
                          >
                            <ArrowDown aria-hidden="true" size={15} />
                          </button>
                          <button
                            className="button secondary icon-only"
                            onClick={() => selectLine(section.section_id, line.line_id)}
                            title={t("Rewrite line")}
                            type="button"
                          >
                            <Sparkles aria-hidden="true" size={15} />
                          </button>
                          <button
                            className="button secondary icon-only danger-icon"
                            disabled={section.lines.length <= 1}
                            onClick={() => deleteLine(section.section_id, line.line_id)}
                            title={t("Delete line")}
                            type="button"
                          >
                            <Trash2 aria-hidden="true" size={15} />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <button
                  className="button ghost compact-button add-lyric-line"
                  onClick={() => editor.update(addLyricLine(editor.draft, section.section_id))}
                  type="button"
                >
                  <Plus aria-hidden="true" size={15} />
                  {t("Add line")}
                </button>
              </section>
            ))}
          </div>

          {editor.draft.hookCandidates.length ? (
            <div className="lyrics-hooks">
              <h3>{t("Hook candidates")}</h3>
              <div className="lyrics-hook-grid">
                {editor.draft.hookCandidates.map((hook, index) => (
                  <label key={hook.id}>
                    <span>{t("Hook candidate {number}", { number: index + 1 })}</span>
                    <textarea
                      onChange={(event) =>
                        editor.update(
                          updateHookCandidate(editor.draft, hook.id, event.target.value),
                        )
                      }
                      rows={2}
                      value={hook.text}
                    />
                  </label>
                ))}
              </div>
            </div>
          ) : null}

          <div className="lyrics-rewrite-tools">
            <div className="lyrics-rewrite-heading">
              <div>
                <h3>{t("Rewrite studio")}</h3>
                <p className="meta">
                  {scope === "line"
                    ? t("Targeting one selected line.")
                    : scope === "section"
                      ? t("Targeting {section}.", {
                          section: selectedSection ? text(selectedSection.label) : t("a section"),
                        })
                      : t("Targeting all lyric lines.")}
                </p>
              </div>
              <div className="segmented-control" aria-label={t("Rewrite scope")}>
                {(["line", "section", "all"] as LyricsRewriteScope[]).map((value) => (
                  <button
                    aria-pressed={scope === value}
                    className={scope === value ? "active" : ""}
                    disabled={
                      (value === "line" && !selectedLineId) ||
                      (value === "section" && !selectedSectionId)
                    }
                    key={value}
                    onClick={() => setScope(value)}
                    type="button"
                  >
                    {text(value === "line" ? "Line" : value === "section" ? "Section" : "All")}
                  </button>
                ))}
              </div>
            </div>
            <div className="lyrics-rewrite-grid">
              <label>
                <span>{t("Action")}</span>
                <select
                  onChange={(event) => setAction(event.target.value as LyricsRewriteAction)}
                  value={action}
                >
                  {rewriteActions.map((value) => (
                    <option key={value} value={value}>
                      {text(rewriteActionLabel(value))}
                    </option>
                  ))}
                </select>
              </label>
              <label className="lyrics-instruction-field">
                <span>{t("Direction")}</span>
                <input
                  maxLength={500}
                  onChange={(event) => setInstruction(event.target.value)}
                  placeholder={t("Use a sharper image and fewer filler words")}
                  value={instruction}
                />
              </label>
              {action === "adjust_tone" ? (
                <label>
                  <span>{t("Tone")}</span>
                  <input
                    maxLength={80}
                    onChange={(event) => setTone(event.target.value)}
                    placeholder={t("intimate, restrained")}
                    value={tone}
                  />
                </label>
              ) : null}
              {action === "change_rhyme" ? (
                <>
                  <label>
                    <span>{t("Rhyme ending")}</span>
                    <input
                      maxLength={80}
                      onChange={(event) => setRhymeEnding(event.target.value)}
                      placeholder={t("home")}
                      value={rhymeEnding}
                    />
                  </label>
                  <label>
                    <span>{t("Rhyme mark")}</span>
                    <input
                      maxLength={16}
                      onChange={(event) => setRhymeLabel(event.target.value)}
                      placeholder="A"
                      value={rhymeLabel}
                    />
                  </label>
                </>
              ) : null}
            </div>
            <div className="lyrics-vocabulary-grid">
              <label>
                <span>{t("Avoided expressions")}</span>
                <textarea
                  onChange={(event) =>
                    updatePreferences({ ...preferences, banned: event.target.value })
                  }
                  placeholder={t("Comma-separated words or phrases")}
                  rows={2}
                  value={preferences.banned}
                />
              </label>
              <label>
                <span>{t("Preferred vocabulary")}</span>
                <textarea
                  onChange={(event) =>
                    updatePreferences({ ...preferences, preferred: event.target.value })
                  }
                  placeholder={t("Words and images to favor")}
                  rows={2}
                  value={preferences.preferred}
                />
              </label>
            </div>
            {diagnostics.length ? (
              <p className="lyrics-diagnostic" role="status">
                {t("{count} avoided-expression matches in the current draft.", {
                  count: diagnostics.length,
                })}
              </p>
            ) : null}
            <button
              className="button secondary"
              disabled={!canRequestRewrite || isRewriting || isSaving}
              onClick={handleRewrite}
              type="button"
            >
              <Sparkles aria-hidden="true" size={17} />
              {isRewriting ? t("Generating preview") : t("Preview rewrite")}
            </button>
          </div>

          {preview ? (
            <div className="lyrics-rewrite-preview">
              <div className="lyrics-preview-heading">
                <div>
                  <h3>{t("Original / candidate diff")}</h3>
                  <p className="meta">
                    {t("{count} changed lines. Accept changes into the local draft before saving.", {
                      count: preview.changes.length,
                    })}
                  </p>
                </div>
                <div className="button-row">
                  {selectedSectionId && preview.scope !== "line" ? (
                    <button
                      className="button secondary"
                      disabled={
                        !preview.changes.some(
                          (change) => change.section_id === selectedSectionId,
                        )
                      }
                      onClick={() =>
                        acceptChanges(
                          preview.changes
                            .filter((change) => change.section_id === selectedSectionId)
                            .map((change) => change.line_id),
                        )
                      }
                      type="button"
                    >
                      <Check aria-hidden="true" size={17} />
                      {t("Accept section")}
                    </button>
                  ) : null}
                  <button
                    className="button"
                    disabled={!preview.changes.length}
                    onClick={() => acceptChanges(preview.changes.map((change) => change.line_id))}
                    type="button"
                  >
                    <Check aria-hidden="true" size={17} />
                    {t("Accept all")}
                  </button>
                </div>
              </div>
              {preview.warnings.map((warning) => (
                <p className="notice compact-notice" key={warning}>
                  {text(warning)}
                </p>
              ))}
              <div className="lyrics-diff-list">
                {preview.changes.map((change) => (
                  <div className="lyrics-diff-row" key={change.line_id}>
                    <div>
                      <span className="meta">{t("Original")}</span>
                      <p>{change.before.text}</p>
                    </div>
                    <div className="lyrics-inline-diff">
                      <span className="meta">{t("Candidate")}</span>
                      <p>
                        {change.diff.map((segment, index) =>
                          segment.kind === "delete" ? (
                            <del key={`${segment.kind}-${index}`}>{segment.text}</del>
                          ) : segment.kind === "insert" ? (
                            <ins key={`${segment.kind}-${index}`}>{segment.text}</ins>
                          ) : (
                            <span key={`${segment.kind}-${index}`}>{segment.text}</span>
                          ),
                        )}
                      </p>
                    </div>
                    <button
                      className="button ghost compact-button"
                      onClick={() => acceptChanges([change.line_id])}
                      type="button"
                    >
                      <Check aria-hidden="true" size={15} />
                      {t("Accept line")}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {localError ? <p className="form-error">{localError}</p> : null}
          <div className="lyrics-footer">
            <button
              className="button ghost"
              disabled={!editor.dirty || isSaving}
              onClick={() => {
                editor.reset();
                setPreview(null);
              }}
              type="button"
            >
              <RotateCcw aria-hidden="true" size={17} />
              {t("Discard draft")}
            </button>
            <button className="button" disabled={!editor.dirty || isSaving} type="submit">
              <Save aria-hidden="true" size={17} />
              {isSaving ? t("Saving") : t("Save lyrics version")}
            </button>
          </div>
        </form>
      ) : canGenerate ? (
        <EmptyStateAction
          icon={Sparkles}
          message={t("Generate a lyrics draft from your approved SongSpec.")}
        />
      ) : (
        <EmptyStateAction
          actionLabel={t("Go to SongSpec")}
          anchor="song-spec-panel"
          message={t("Generate lyrics after approving a SongSpec")}
        />
      )}
    </section>
  );
}

function rewriteActionLabel(action: LyricsRewriteAction): string {
  switch (action) {
    case "expand":
      return "Expand";
    case "compress":
      return "Compress";
    case "change_rhyme":
      return "Change rhyme";
    case "adjust_tone":
      return "Adjust tone";
    default:
      return "Rewrite";
  }
}

function isLyricsPreferences(value: unknown): value is LyricsPreferences {
  return (
    typeof value === "object" &&
    value !== null &&
    "banned" in value &&
    typeof value.banned === "string" &&
    "preferred" in value &&
    typeof value.preferred === "string"
  );
}

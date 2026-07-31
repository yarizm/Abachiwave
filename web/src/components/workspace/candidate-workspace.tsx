"use client";

import { Check, RotateCcw, Sparkles, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useLocale } from "@/i18n/locale-provider";
import {
  GenerationCandidate,
  ProviderCapability,
  TextWorkflow,
  defaultProvider,
  localFallbackProvider,
} from "@/lib/ai-generation";
import { GenerationRun, isRunActive } from "@/lib/composition";

type CandidateWorkspaceProps = {
  approvedSongSpecId: string | null;
  canGenerateArrangement: boolean;
  candidates: GenerationCandidate[];
  isSaving: boolean;
  latestIntakeId: string | null;
  onCancel: (runId: string) => void;
  onGenerate: (input: {
    workflow: TextWorkflow;
    providerProfileId: string;
    candidateCount: number;
    feedback: string;
  }) => void;
  onSelect: (candidateId: string) => void;
  providers: ProviderCapability[];
  runs: GenerationRun[];
};

const WORKFLOWS: TextWorkflow[] = ["song_spec", "lyrics", "arrangement", "revision"];

export function CandidateWorkspace({
  approvedSongSpecId,
  canGenerateArrangement,
  candidates,
  isSaving,
  latestIntakeId,
  onCancel,
  onGenerate,
  onSelect,
  providers,
  runs,
}: CandidateWorkspaceProps) {
  const { dateTime, t, text } = useLocale();
  const [workflow, setWorkflow] = useState<TextWorkflow>("song_spec");
  const [providerProfileId, setProviderProfileId] = useState("");
  const [candidateCount, setCandidateCount] = useState(2);
  const [feedback, setFeedback] = useState("");
  const fallback = useMemo(() => localFallbackProvider(providers), [providers]);
  const visibleProviders = useMemo(
    () => providers.filter((provider) => provider.capabilities.includes(workflow)),
    [providers, workflow],
  );
  const visibleCandidates = useMemo(
    () => candidates.filter((candidate) => candidate.workflow === workflow),
    [candidates, workflow],
  );
  const workflowRuns = useMemo(
    () => runs.filter((run) => run.input_manifest.workflow === workflow),
    [runs, workflow],
  );
  const activeRuns = workflowRuns.filter(isRunActive);
  const failedRun = workflowRuns.find((run) => run.status === "failed");

  useEffect(() => {
    const current = visibleProviders.find((provider) => provider.id === providerProfileId);
    if (current) {
      return;
    }
    setProviderProfileId(defaultProvider(visibleProviders)?.id ?? "");
  }, [providerProfileId, visibleProviders]);

  const missingPrerequisite =
    workflow === "song_spec"
      ? !latestIntakeId
      : workflow === "lyrics"
        ? !approvedSongSpecId
        : workflow === "arrangement"
          ? !canGenerateArrangement
          : !feedback.trim();
  const canGenerate =
    Boolean(providerProfileId) && !missingPrerequisite && !activeRuns.length && !isSaving;

  return (
    <section className="panel candidate-panel" aria-labelledby="candidate-title">
      <div className="section-heading">
        <div>
          <h2 className="heading-with-icon" id="candidate-title">
            <Sparkles aria-hidden="true" size={20} />
            {t("AI candidates")}
          </h2>
        </div>
        {activeRuns.length ? <span className="badge">{text(activeRuns[0].status)}</span> : null}
      </div>

      <div className="candidate-controls">
        <div className="field">
          <label htmlFor="candidate-workflow">{t("Workflow")}</label>
          <select
            id="candidate-workflow"
            onChange={(event) => setWorkflow(event.target.value as TextWorkflow)}
            value={workflow}
          >
            {WORKFLOWS.map((item) => (
              <option key={item} value={item}>
                {text(item)}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="candidate-provider">{t("Provider")}</label>
          <select
            id="candidate-provider"
            onChange={(event) => setProviderProfileId(event.target.value)}
            value={providerProfileId}
          >
            {visibleProviders.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.display_name}
                {provider.model ? ` - ${provider.model}` : ""}
              </option>
            ))}
          </select>
        </div>
        <div className="field narrow-field">
          <label htmlFor="candidate-count">{t("Candidates")}</label>
          <select
            id="candidate-count"
            onChange={(event) => setCandidateCount(Number(event.target.value))}
            value={candidateCount}
          >
            {[1, 2, 3].map((count) => (
              <option key={count} value={count}>
                {count}
              </option>
            ))}
          </select>
        </div>
      </div>

      {workflow === "revision" ? (
        <div className="field candidate-feedback">
          <label htmlFor="candidate-feedback">{t("Feedback")}</label>
          <textarea
            id="candidate-feedback"
            maxLength={4000}
            onChange={(event) => setFeedback(event.target.value)}
            value={feedback}
          />
        </div>
      ) : null}

      <div className="button-row">
        <button
          className="button"
          disabled={!canGenerate}
          onClick={() =>
            onGenerate({ workflow, providerProfileId, candidateCount, feedback: feedback.trim() })
          }
          type="button"
        >
          <Sparkles aria-hidden="true" size={18} />
          {t("Generate candidates")}
        </button>
        {activeRuns.map((run) => (
          <button
            className="button secondary"
            key={run.id}
            onClick={() => onCancel(run.id)}
            type="button"
          >
            <X aria-hidden="true" size={18} />
            {t("Cancel")}
          </button>
        ))}
        {failedRun && fallback && providerProfileId !== fallback.id ? (
          <button
            className="button secondary"
            disabled={isSaving}
            onClick={() =>
              onGenerate({
                workflow,
                providerProfileId: fallback.id,
                candidateCount,
                feedback: feedback.trim(),
              })
            }
            type="button"
          >
            <RotateCcw aria-hidden="true" size={18} />
            {t("Use local fallback")}
          </button>
        ) : null}
      </div>

      {failedRun ? (
        <p className="error">
          {failedRun.error_code ?? t("Task failed")}: {failedRun.error_message ?? t("Task failed")}
        </p>
      ) : null}
      {missingPrerequisite ? <p className="meta">{prerequisiteLabel(workflow, t)}</p> : null}

      {visibleCandidates.length ? (
        <div className="candidate-grid">
          {visibleCandidates.map((candidate) => (
            <article className="candidate-card" key={candidate.id}>
              <div className="section-heading">
                <div>
                  <strong>{t("Candidate {number}", { number: candidate.candidate_index })}</strong>
                  <p className="meta">
                    {candidate.score === null
                      ? dateTime(candidate.created_at)
                      : `${t("Score {score}", { score: Math.round(candidate.score * 100) })} - ${dateTime(candidate.created_at)}`}
                  </p>
                </div>
                <span className="badge">{text(candidate.status)}</span>
              </div>
              <CandidatePreview candidate={candidate} />
              <button
                className="button secondary full-width"
                disabled={candidate.status === "selected" || isSaving}
                onClick={() => onSelect(candidate.id)}
                type="button"
              >
                <Check aria-hidden="true" size={18} />
                {candidate.status === "selected" ? t("Selected") : t("Select candidate")}
              </button>
            </article>
          ))}
        </div>
      ) : (
        <p className="empty">{t("No candidates for this workflow yet.")}</p>
      )}
    </section>
  );
}

function CandidatePreview({ candidate }: { candidate: GenerationCandidate }) {
  const { t, text } = useLocale();
  const content = candidate.content;
  if (candidate.workflow === "song_spec") {
    const genre = Array.isArray(content.genre) ? content.genre.join(", ") : "-";
    return (
      <dl className="candidate-summary">
        <div><dt>{t("Theme")}</dt><dd>{String(content.theme ?? "-")}</dd></div>
        <div><dt>{t("Genre")}</dt><dd>{genre}</dd></div>
        <div><dt>{t("BPM")}</dt><dd>{String(content.tempo_bpm ?? "-")}</dd></div>
        <div><dt>{t("Key")}</dt><dd>{String(content.key ?? "-")}</dd></div>
      </dl>
    );
  }
  if (candidate.workflow === "lyrics") {
    const sections = Array.isArray(content.sections) ? content.sections : [];
    return (
      <div className="candidate-preview-list">
        {sections.map((item, index) => {
          const section = item as Record<string, unknown>;
          return (
            <div key={`${String(section.section_id)}-${index}`}>
              <strong>{String(section.label ?? text("lyrics"))}</strong>
              <p>{String(section.text ?? "")}</p>
            </div>
          );
        })}
      </div>
    );
  }
  if (candidate.workflow === "arrangement") {
    const sections = Array.isArray(content.sections) ? content.sections : [];
    return (
      <div className="candidate-preview-list">
        <p>{String(content.overview ?? "")}</p>
        <p className="meta">{t("{count} sections", { count: sections.length })}</p>
      </div>
    );
  }
  const tasks = Array.isArray(content.tasks) ? content.tasks : [];
  return (
    <div className="candidate-preview-list">
      {tasks.map((item, index) => {
        const task = item as Record<string, unknown>;
        return <p key={`${String(task.id)}-${index}`}>{String(task.summary ?? "")}</p>;
      })}
    </div>
  );
}

function prerequisiteLabel(
  workflow: TextWorkflow,
  t: ReturnType<typeof useLocale>["t"],
): string {
  if (workflow === "song_spec") return t("Save an idea intake first.");
  if (workflow === "lyrics") return t("Approve a SongSpec first.");
  if (workflow === "arrangement") return t("Complete the arrangement prerequisites first.");
  return t("Revision feedback is required.");
}

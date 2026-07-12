"use client";

import { Check, FilePlus2, Save } from "lucide-react";
import { FormEvent } from "react";

import { useLocale } from "@/i18n/locale-provider";
import { IdeaIntake, SongSpecVersion, isSongSpecComplete } from "@/lib/song-specs";

export type SongSpecDraftForm = {
  theme: string;
  genre: string;
  language: string;
  tempo_bpm: string;
  key: string;
  time_signature: string;
  target_duration_seconds: string;
  mood_curve: string;
  song_structure: string;
};

type SongSpecWorkspaceProps = {
  activeVersion: SongSpecVersion | null;
  answers: Record<string, string>;
  draftForm: SongSpecDraftForm;
  idea: string;
  isSaving: boolean;
  latestIntake: IdeaIntake | null;
  onAnswersChange: (answers: Record<string, string>) => void;
  onApprove: () => void;
  onDraftChange: (draft: SongSpecDraftForm) => void;
  onGenerateDraft: () => void;
  onIdeaChange: (idea: string) => void;
  onIntakeSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onSongSpecSubmit: (event: FormEvent<HTMLFormElement>) => void;
  state: string;
};

export function SongSpecWorkspace({
  activeVersion,
  answers,
  draftForm,
  idea,
  isSaving,
  latestIntake,
  onAnswersChange,
  onApprove,
  onDraftChange,
  onGenerateDraft,
  onIdeaChange,
  onIntakeSubmit,
  onSongSpecSubmit,
  state,
}: SongSpecWorkspaceProps) {
  const { t, text } = useLocale();
  return (
    <div className="workspace-grid">
      <section className="panel" aria-labelledby="intake-title">
        <div className="section-heading">
          <h2 id="intake-title">{t("Idea intake")}</h2>
          <span className="badge">{text(state)}</span>
        </div>
        <form className="form" onSubmit={onIntakeSubmit}>
          <div className="field">
            <label htmlFor="idea">{t("Song idea")}</label>
            <textarea
              id="idea"
              maxLength={4000}
              onChange={(event) => onIdeaChange(event.target.value)}
              placeholder={t("Chinese indie rock song about riding home late at night...")}
              value={idea}
            />
          </div>
          {latestIntake?.questions.length ? (
            <div className="question-list">
              {latestIntake.questions.map((question) => (
                <div className="field" key={question.id}>
                  <label htmlFor={question.id}>{text(question.prompt)}</label>
                  <input
                    id={question.id}
                    onChange={(event) =>
                      onAnswersChange({
                        ...answers,
                        [question.field]: event.target.value,
                      })
                    }
                    value={answers[question.field] ?? ""}
                  />
                </div>
              ))}
            </div>
          ) : null}
          <button className="button" disabled={isSaving} type="submit">
            <Save aria-hidden="true" size={18} />
            {t("Save intake")}
          </button>
        </form>
        <button
          className="button secondary full-width"
          disabled={!latestIntake || isSaving}
          onClick={onGenerateDraft}
          type="button"
        >
          <FilePlus2 aria-hidden="true" size={18} />
          {t("Generate SongSpec draft")}
        </button>
      </section>

      <section className="panel" aria-labelledby="song-spec-title">
        <div className="section-heading">
          <h2 id="song-spec-title">{t("SongSpec editor")}</h2>
          {activeVersion ? <span className="badge">v{activeVersion.version_number}</span> : null}
        </div>
        {activeVersion ? (
          <SongSpecEditor
            activeVersion={activeVersion}
            draftForm={draftForm}
            isSaving={isSaving}
            onApprove={onApprove}
            onChange={onDraftChange}
            onSubmit={onSongSpecSubmit}
          />
        ) : (
          <div className="empty">{t("No SongSpec draft yet. Save an intake, then generate a draft.")}</div>
        )}
      </section>
    </div>
  );
}

export function SongSpecVersionsPanel({ versions }: { versions: SongSpecVersion[] }) {
  const { dateTime, t, text } = useLocale();
  return (
    <section className="panel" aria-labelledby="versions-title">
      <h2 id="versions-title">{t("SongSpec versions")}</h2>
      {versions.length === 0 ? (
        <p className="empty">{t("No versions have been generated.")}</p>
      ) : (
        <div className="version-list">
          {versions.map((version) => (
            <div className="version-row" key={version.id}>
              <div>
                <strong>v{version.version_number}</strong>
                <p className="meta">
                  {text(version.status)} - {dateTime(version.created_at)}
                </p>
              </div>
              <span className="meta">
                {version.missing_required_fields.length
                  ? t("Missing {count}", { count: version.missing_required_fields.length })
                  : t("Complete")}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function SongSpecEditor({
  activeVersion,
  draftForm,
  isSaving,
  onApprove,
  onChange,
  onSubmit,
}: {
  activeVersion: SongSpecVersion;
  draftForm: SongSpecDraftForm;
  isSaving: boolean;
  onApprove: () => void;
  onChange: (next: SongSpecDraftForm) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const { t, text } = useLocale();
  const complete = isSongSpecComplete(activeVersion.song_spec);
  return (
    <form className="form" onSubmit={onSubmit}>
      <TextField id="theme" label={t("Theme")} name="theme" onChange={onChange} state={draftForm} />
      <TextField id="genre" label={t("Genre")} name="genre" onChange={onChange} state={draftForm} />
      <div className="form-row">
        <TextField id="language" label={t("Language")} name="language" onChange={onChange} state={draftForm} />
        <TextField id="tempo_bpm" label={t("BPM")} name="tempo_bpm" onChange={onChange} state={draftForm} />
      </div>
      <div className="form-row">
        <TextField id="key" label={t("Key")} name="key" onChange={onChange} state={draftForm} />
        <TextField id="time_signature" label={t("Time")} name="time_signature" onChange={onChange} state={draftForm} />
      </div>
      <TextField
        id="target_duration_seconds"
        label={t("Duration seconds")}
        name="target_duration_seconds"
        onChange={onChange}
        state={draftForm}
      />
      <TextAreaField id="mood_curve" label={t("Mood curve JSON")} name="mood_curve" onChange={onChange} state={draftForm} />
      <TextAreaField
        id="song_structure"
        label={t("Song structure, one section per line")}
        name="song_structure"
        onChange={onChange}
        state={draftForm}
      />
      {activeVersion.missing_required_fields.length ? (
        <p className="meta">
          {t("Missing: {items}", {
            items: activeVersion.missing_required_fields.map(text).join(", "),
          })}
        </p>
      ) : null}
      <div className="button-row">
        <button className="button" disabled={isSaving} type="submit">
          <Save aria-hidden="true" size={18} />
          {t("Save new version")}
        </button>
        <button
          className="button secondary"
          disabled={isSaving || !complete}
          onClick={onApprove}
          type="button"
        >
          <Check aria-hidden="true" size={18} />
          {t("Approve")}
        </button>
      </div>
    </form>
  );
}

function TextField({
  id,
  label,
  name,
  onChange,
  state,
}: {
  id: string;
  label: string;
  name: keyof SongSpecDraftForm;
  onChange: (next: SongSpecDraftForm) => void;
  state: SongSpecDraftForm;
}) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        onChange={(event) => onChange({ ...state, [name]: event.target.value })}
        value={state[name]}
      />
    </div>
  );
}

function TextAreaField({
  id,
  label,
  name,
  onChange,
  state,
}: {
  id: string;
  label: string;
  name: keyof SongSpecDraftForm;
  onChange: (next: SongSpecDraftForm) => void;
  state: SongSpecDraftForm;
}) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <textarea
        id={id}
        onChange={(event) => onChange({ ...state, [name]: event.target.value })}
        value={state[name]}
      />
    </div>
  );
}

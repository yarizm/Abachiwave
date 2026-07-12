import { ClipboardList, Gauge, History } from "lucide-react";

import { useLocale } from "@/i18n/locale-provider";
import { ProjectEvent, ProjectHandoff, ProjectReview } from "@/lib/composition";

export function ActivityPanel({ events }: { events: ProjectEvent[] }) {
  const { dateTime, t, text } = useLocale();
  return (
    <section className="panel" aria-labelledby="activity-title">
      <div className="section-heading">
        <h2 className="heading-with-icon" id="activity-title">
          <History aria-hidden="true" size={20} />
          {t("Activity")}
        </h2>
        <span className="badge">{events.length}</span>
      </div>
      {events.length ? (
        <div className="version-list">
          {events.slice(0, 24).map((event) => (
            <div className="version-row" key={event.id}>
              <div>
                <strong>{formatEventType(event.event_type, text)}</strong>
                <p className="meta">{dateTime(event.created_at)}</p>
                <p className="meta">{formatEventDetail(event, t, text)}</p>
              </div>
              <span className="badge">{text(event.event_type.split(".")[0])}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty">{t("No activity has been recorded.")}</p>
      )}
    </section>
  );
}

export function HandoffPanel({ handoff }: { handoff: ProjectHandoff | null }) {
  const { dateTime, locale, t, text } = useLocale();
  return (
    <section className="panel handoff-panel" aria-labelledby="handoff-title">
      <div className="section-heading">
        <h2 className="heading-with-icon" id="handoff-title">
          <ClipboardList aria-hidden="true" size={20} />
          {t("Handoff summary")}
        </h2>
        {handoff ? (
          <span className={`badge review-${handoff.review.status}`}>
            {handoff.review.score}/100
          </span>
        ) : null}
      </div>
      {handoff ? (
        <>
          <div className="handoff-stats">
            <div>
              <strong>{formatReviewStatus(handoff.review.status, t)}</strong>
              <p className="meta">{t("Readiness")}</p>
            </div>
            <div>
              <strong>{handoff.open_comments.length}</strong>
              <p className="meta">{t("Open comments")}</p>
            </div>
            <div>
              <strong>{handoff.missing_prerequisites.length}</strong>
              <p className="meta">{t("Missing items")}</p>
            </div>
          </div>
          {handoff.next_actions.length ? (
            <div className="mini-list">
              <p className="meta">{t("Next actions")}</p>
              {handoff.next_actions.map((action) => (
                <p className="meta" key={action}>
                  {text(action)}
                </p>
              ))}
            </div>
          ) : null}
          <textarea
            className="handoff-markdown"
            readOnly
            value={
              locale === "zh-CN"
                ? localizedHandoffMarkdown(handoff, dateTime, t, text)
                : handoff.handoff_markdown
            }
          />
        </>
      ) : (
        <p className="empty">{t("Handoff summary will appear after the workspace loads.")}</p>
      )}
    </section>
  );
}

function localizedHandoffMarkdown(
  handoff: ProjectHandoff,
  dateTime: (value: string) => string,
  t: ReturnType<typeof useLocale>["t"],
  text: (value: string) => string,
): string {
  const assetLine = (label: string, asset: { label: string; kind?: string | null } | null) =>
    `- ${label}：${asset ? text(asset.label) : text("missing")}${asset?.kind ? `（${text(asset.kind)}）` : ""}`;
  const lines = [
    `# ${handoff.project.name} ${t("Handoff summary")}`,
    "",
    `- ${t("Project status")}：${text(handoff.project.status)}`,
    `- ${t("Review")}：${formatReviewStatus(handoff.review.status, t)} (${handoff.review.score}/100)`,
    `- ${t("Generated")}：${dateTime(handoff.generated_at)}`,
    "",
    `## ${t("Current Assets")}`,
    assetLine("SongSpec", handoff.current_assets.song_spec),
    assetLine(t("Lyrics"), handoff.current_assets.lyrics),
    assetLine(t("Chords"), handoff.current_assets.chords),
    assetLine(t("Arrangement"), handoff.current_assets.arrangement),
    `- MIDI：${
      handoff.current_assets.midi_assets.length
        ? handoff.current_assets.midi_assets.map((asset) => text(asset.label)).join("、")
        : text("missing")
    }`,
    "",
    `## ${t("Missing Prerequisites")}`,
    ...(handoff.missing_prerequisites.length
      ? handoff.missing_prerequisites.map((item) => `- ${text(item.replaceAll("_", " "))}`)
      : [`- ${t("None")}`]),
    "",
    `## ${t("Next actions")}`,
    ...(handoff.next_actions.length
      ? handoff.next_actions.map((action) => `- ${text(action)}`)
      : [`- ${t("None")}`]),
    "",
    `## ${t("Open Comments")}`,
    ...(handoff.open_comments.length
      ? handoff.open_comments.map(
          (comment) => `- [${text(comment.target_type)}] ${comment.body} (${comment.author_name})`,
        )
      : [`- ${t("None")}`]),
    "",
    `## ${t("Recent Activity")}`,
    ...(handoff.recent_events.length
      ? handoff.recent_events.map(
          (event) => `- ${dateTime(event.created_at)} - ${formatEventType(event.event_type, text)}`,
        )
      : [`- ${t("None")}`]),
  ];
  return lines.join("\n");
}

export function ReviewPanel({ review }: { review: ProjectReview | null }) {
  const { dateTime, t, text } = useLocale();
  return (
    <section className="panel review-panel" aria-labelledby="review-title">
      <div className="section-heading">
        <h2 className="heading-with-icon" id="review-title">
          <Gauge aria-hidden="true" size={20} />
          {t("Project review")}
        </h2>
        {review ? <span className={`badge review-${review.status}`}>{review.score}/100</span> : null}
      </div>
      {review ? (
        <>
          <p className="meta">
            {formatReviewStatus(review.status, t)} - {dateTime(review.generated_at)}
          </p>
          <div className="review-grid">
            {review.items.map((item) => (
              <div className="review-item" key={item.id}>
                <div className="section-heading">
                  <strong>{text(item.label)}</strong>
                  <span className={`badge review-${item.status}`}>{text(item.status)}</span>
                </div>
                <p className="meta">{text(item.detail)}</p>
              </div>
            ))}
          </div>
          {review.next_actions.length ? (
            <div className="mini-list">
              <p className="meta">{t("Next actions")}</p>
              {review.next_actions.map((action) => (
                <p className="meta" key={action}>
                  {text(action)}
                </p>
              ))}
            </div>
          ) : null}
        </>
      ) : (
        <p className="empty">{t("Project review will appear after the workspace loads.")}</p>
      )}
    </section>
  );
}

function formatEventType(eventType: string, text: (value: string) => string): string {
  const translated = text(eventType);
  if (translated !== eventType) {
    return translated;
  }
  return eventType
    .split(".")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).replaceAll("_", " "))
    .join(" ");
}

function formatEventDetail(
  event: ProjectEvent,
  t: ReturnType<typeof useLocale>["t"],
  text: (value: string) => string,
): string {
  const details = [
    event.revision_request_id
      ? t("revision {id}", { id: event.revision_request_id.slice(0, 8) })
      : null,
    event.generation_run_id ? t("run {id}", { id: event.generation_run_id.slice(0, 8) }) : null,
    event.artifact_version_id
      ? t("asset {id}", { id: event.artifact_version_id.slice(0, 8) })
      : null,
  ].filter((detail): detail is string => detail !== null);
  const payloadSummary = summarizePayload(event.payload, t, text);
  if (payloadSummary) {
    details.push(payloadSummary);
  }
  return details.join(" - ") || t("No linked asset");
}

function summarizePayload(
  payload: Record<string, unknown>,
  t: ReturnType<typeof useLocale>["t"],
  text: (value: string) => string,
): string | null {
  if (typeof payload.feedback === "string") {
    return payload.feedback;
  }
  if (typeof payload.asset_type === "string") {
    return text(payload.asset_type);
  }
  if (typeof payload.filename === "string") {
    return payload.filename;
  }
  if (typeof payload.created_versions === "number") {
    return t("{count} versions", { count: payload.created_versions });
  }
  if (typeof payload.task_count === "number") {
    return t("{count} tasks", { count: payload.task_count });
  }
  return null;
}

function formatReviewStatus(
  status: ProjectReview["status"],
  t: ReturnType<typeof useLocale>["t"],
): string {
  switch (status) {
    case "ready":
      return t("Ready for handoff");
    case "needs_work":
      return t("Needs work");
    case "blocked":
      return t("Blocked");
  }
}

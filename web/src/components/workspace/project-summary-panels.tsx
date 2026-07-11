import { ClipboardList, Gauge, History } from "lucide-react";

import { ProjectEvent, ProjectHandoff, ProjectReview } from "@/lib/composition";

export function ActivityPanel({ events }: { events: ProjectEvent[] }) {
  return (
    <section className="panel" aria-labelledby="activity-title">
      <div className="section-heading">
        <h2 className="heading-with-icon" id="activity-title">
          <History aria-hidden="true" size={20} />
          Activity
        </h2>
        <span className="badge">{events.length}</span>
      </div>
      {events.length ? (
        <div className="version-list">
          {events.slice(0, 24).map((event) => (
            <div className="version-row" key={event.id}>
              <div>
                <strong>{formatEventType(event.event_type)}</strong>
                <p className="meta">{new Date(event.created_at).toLocaleString()}</p>
                <p className="meta">{formatEventDetail(event)}</p>
              </div>
              <span className="badge">{event.event_type.split(".")[0]}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty">No activity has been recorded.</p>
      )}
    </section>
  );
}

export function HandoffPanel({ handoff }: { handoff: ProjectHandoff | null }) {
  return (
    <section className="panel handoff-panel" aria-labelledby="handoff-title">
      <div className="section-heading">
        <h2 className="heading-with-icon" id="handoff-title">
          <ClipboardList aria-hidden="true" size={20} />
          Handoff summary
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
              <strong>{formatReviewStatus(handoff.review.status)}</strong>
              <p className="meta">Readiness</p>
            </div>
            <div>
              <strong>{handoff.open_comments.length}</strong>
              <p className="meta">Open comments</p>
            </div>
            <div>
              <strong>{handoff.missing_prerequisites.length}</strong>
              <p className="meta">Missing items</p>
            </div>
          </div>
          {handoff.next_actions.length ? (
            <div className="mini-list">
              <p className="meta">Next actions</p>
              {handoff.next_actions.map((action) => (
                <p className="meta" key={action}>
                  {action}
                </p>
              ))}
            </div>
          ) : null}
          <textarea className="handoff-markdown" readOnly value={handoff.handoff_markdown} />
        </>
      ) : (
        <p className="empty">Handoff summary will appear after the workspace loads.</p>
      )}
    </section>
  );
}

export function ReviewPanel({ review }: { review: ProjectReview | null }) {
  return (
    <section className="panel review-panel" aria-labelledby="review-title">
      <div className="section-heading">
        <h2 className="heading-with-icon" id="review-title">
          <Gauge aria-hidden="true" size={20} />
          Project review
        </h2>
        {review ? <span className={`badge review-${review.status}`}>{review.score}/100</span> : null}
      </div>
      {review ? (
        <>
          <p className="meta">
            {formatReviewStatus(review.status)} - {new Date(review.generated_at).toLocaleString()}
          </p>
          <div className="review-grid">
            {review.items.map((item) => (
              <div className="review-item" key={item.id}>
                <div className="section-heading">
                  <strong>{item.label}</strong>
                  <span className={`badge review-${item.status}`}>{item.status}</span>
                </div>
                <p className="meta">{item.detail}</p>
              </div>
            ))}
          </div>
          {review.next_actions.length ? (
            <div className="mini-list">
              <p className="meta">Next actions</p>
              {review.next_actions.map((action) => (
                <p className="meta" key={action}>
                  {action}
                </p>
              ))}
            </div>
          ) : null}
        </>
      ) : (
        <p className="empty">Project review will appear after the workspace loads.</p>
      )}
    </section>
  );
}

function formatEventType(eventType: string): string {
  return eventType
    .split(".")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).replaceAll("_", " "))
    .join(" ");
}

function formatEventDetail(event: ProjectEvent): string {
  const details = [
    event.revision_request_id ? `revision ${event.revision_request_id.slice(0, 8)}` : null,
    event.generation_run_id ? `run ${event.generation_run_id.slice(0, 8)}` : null,
    event.artifact_version_id ? `asset ${event.artifact_version_id.slice(0, 8)}` : null,
  ].filter((detail): detail is string => detail !== null);
  const payloadSummary = summarizePayload(event.payload);
  if (payloadSummary) {
    details.push(payloadSummary);
  }
  return details.join(" - ") || "No linked asset";
}

function summarizePayload(payload: Record<string, unknown>): string | null {
  if (typeof payload.feedback === "string") {
    return payload.feedback;
  }
  if (typeof payload.asset_type === "string") {
    return payload.asset_type;
  }
  if (typeof payload.filename === "string") {
    return payload.filename;
  }
  if (typeof payload.created_versions === "number") {
    return `${payload.created_versions} versions`;
  }
  if (typeof payload.task_count === "number") {
    return `${payload.task_count} tasks`;
  }
  return null;
}

function formatReviewStatus(status: ProjectReview["status"]): string {
  switch (status) {
    case "ready":
      return "Ready for handoff";
    case "needs_work":
      return "Needs work";
    case "blocked":
      return "Blocked";
  }
}

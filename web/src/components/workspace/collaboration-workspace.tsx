"use client";

import { Check, MessageSquare } from "lucide-react";
import { FormEvent } from "react";

import { ActivityPanel } from "@/components/workspace/project-summary-panels";
import {
  AssetReference,
  AssetTree,
  AudioDemoVersion,
  AudioUpload,
  ExportBundle,
  ProjectComment,
  ProjectCommentTargetType,
  ProjectEvent,
  RevisionRequest,
} from "@/lib/composition";

export type CommentTargetOption = {
  value: string;
  label: string;
  target_type: ProjectCommentTargetType;
  target_id: string | null;
};

type CollaborationWorkspaceProps = {
  author: string;
  body: string;
  comments: ProjectComment[];
  events: ProjectEvent[];
  isSaving: boolean;
  onAuthorChange: (value: string) => void;
  onBodyChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onTargetChange: (value: string) => void;
  onUpdateStatus: (commentId: string, status: ProjectComment["status"]) => void;
  targetOptions: CommentTargetOption[];
  targetValue: string;
};

export function CollaborationWorkspace({
  author,
  body,
  comments,
  events,
  isSaving,
  onAuthorChange,
  onBodyChange,
  onSubmit,
  onTargetChange,
  onUpdateStatus,
  targetOptions,
  targetValue,
}: CollaborationWorkspaceProps) {
  return (
    <>
      <CommentsPanel
        author={author}
        body={body}
        comments={comments}
        isSaving={isSaving}
        onAuthorChange={onAuthorChange}
        onBodyChange={onBodyChange}
        onSubmit={onSubmit}
        onTargetChange={onTargetChange}
        onUpdateStatus={onUpdateStatus}
        targetOptions={targetOptions}
        targetValue={targetValue}
      />
      <ActivityPanel events={events} />
    </>
  );
}

export function buildCommentTargets({
  assetTree,
  demos,
  exports,
  uploads,
  revisions,
}: {
  assetTree: AssetTree | null;
  demos: AudioDemoVersion[];
  exports: ExportBundle[];
  uploads: AudioUpload[];
  revisions: RevisionRequest[];
}): CommentTargetOption[] {
  const options: CommentTargetOption[] = [
    {
      value: makeCommentTargetValue("project", null),
      label: "Project",
      target_type: "project",
      target_id: null,
    },
  ];
  const current = assetTree?.current;
  if (current?.song_spec) {
    options.push(commentTargetFromAsset("song_spec", current.song_spec));
  }
  if (current?.lyrics) {
    options.push(commentTargetFromAsset("lyrics", current.lyrics));
  }
  if (current?.chords) {
    options.push(commentTargetFromAsset("chords", current.chords));
  }
  current?.midi_assets.forEach((asset) => {
    options.push(commentTargetFromAsset("midi", asset));
  });
  if (current?.arrangement) {
    options.push(commentTargetFromAsset("arrangement", current.arrangement));
  }
  if (demos[0]) {
    options.push({
      value: makeCommentTargetValue("demo", demos[0].id),
      label: `Demo v${demos[0].version_number}`,
      target_type: "demo",
      target_id: demos[0].id,
    });
  }
  if (uploads[0]) {
    options.push({
      value: makeCommentTargetValue("audio_upload", uploads[0].id),
      label: `Audio: ${uploads[0].filename}`,
      target_type: "audio_upload",
      target_id: uploads[0].id,
    });
  }
  if (exports[0]) {
    options.push({
      value: makeCommentTargetValue("export", exports[0].id),
      label: `Export: ${exports[0].status}`,
      target_type: "export",
      target_id: exports[0].id,
    });
  }
  if (revisions[0]) {
    options.push({
      value: makeCommentTargetValue("revision", revisions[0].id),
      label: `Revision: ${revisions[0].status}`,
      target_type: "revision",
      target_id: revisions[0].id,
    });
  }
  return options;
}

export function makeCommentTargetValue(
  targetType: ProjectCommentTargetType,
  targetId: string | null,
): string {
  return `${targetType}:${targetId ?? ""}`;
}

export function parseCommentTarget(
  value: string,
): Pick<CommentTargetOption, "target_type" | "target_id"> {
  const [targetType, targetId] = value.split(":");
  return {
    target_type: targetType as ProjectCommentTargetType,
    target_id: targetId || null,
  };
}

function CommentsPanel({
  author,
  body,
  comments,
  isSaving,
  onAuthorChange,
  onBodyChange,
  onSubmit,
  onTargetChange,
  onUpdateStatus,
  targetOptions,
  targetValue,
}: Omit<CollaborationWorkspaceProps, "events">) {
  const openCount = comments.filter((comment) => comment.status === "open").length;
  return (
    <section className="panel comments-panel" aria-labelledby="comments-title">
      <div className="section-heading">
        <h2 className="heading-with-icon" id="comments-title">
          <MessageSquare aria-hidden="true" size={20} />
          Comments
        </h2>
        <span className="badge">{openCount} open</span>
      </div>
      <form className="form comment-form" onSubmit={onSubmit}>
        <div className="form-row">
          <div className="field">
            <label htmlFor="comment-author">Author</label>
            <input
              id="comment-author"
              onChange={(event) => onAuthorChange(event.target.value)}
              value={author}
            />
          </div>
          <div className="field">
            <label htmlFor="comment-target">Target</label>
            <select
              id="comment-target"
              onChange={(event) => onTargetChange(event.target.value)}
              value={targetValue}
            >
              {targetOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="field">
          <label htmlFor="comment-body">Comment</label>
          <textarea
            id="comment-body"
            onChange={(event) => onBodyChange(event.target.value)}
            placeholder="Leave feedback, handoff notes, or a decision to revisit later..."
            value={body}
          />
        </div>
        <button className="button" disabled={isSaving} type="submit">
          <MessageSquare aria-hidden="true" size={18} />
          Add comment
        </button>
      </form>
      {comments.length ? (
        <div className="comment-list">
          {comments.map((comment) => (
            <div className="comment-row" key={comment.id}>
              <div>
                <div className="section-heading">
                  <strong>{comment.author_name}</strong>
                  <span className={`badge comment-${comment.status}`}>{comment.status}</span>
                </div>
                <p>{comment.body}</p>
                <p className="meta">
                  {formatCommentTarget(comment, targetOptions)} -{" "}
                  {new Date(comment.created_at).toLocaleString()}
                </p>
              </div>
              <button
                className="button secondary icon-button"
                disabled={isSaving}
                onClick={() =>
                  onUpdateStatus(comment.id, comment.status === "open" ? "resolved" : "open")
                }
                type="button"
              >
                <Check aria-hidden="true" size={18} />
                {comment.status === "open" ? "Resolve" : "Reopen"}
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty">Comments and handoff notes will appear here.</p>
      )}
    </section>
  );
}

function commentTargetFromAsset(
  targetType: ProjectCommentTargetType,
  asset: AssetReference,
): CommentTargetOption {
  return {
    value: makeCommentTargetValue(targetType, asset.id),
    label: asset.kind ? `${asset.label} (${asset.kind})` : asset.label,
    target_type: targetType,
    target_id: asset.id,
  };
}

function formatCommentTarget(
  comment: ProjectComment,
  targetOptions: CommentTargetOption[],
): string {
  const value = makeCommentTargetValue(comment.target_type, comment.target_id);
  const option = targetOptions.find((item) => item.value === value);
  return option?.label ?? formatCommentTargetType(comment.target_type);
}

function formatCommentTargetType(targetType: ProjectCommentTargetType): string {
  return targetType
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

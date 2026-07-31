"use client";

import { ArrowRight, LucideIcon } from "lucide-react";
import { ReactNode } from "react";

type EmptyStateActionProps = {
  message: ReactNode;
  /** CTA label shown on the action button. Omit to render a message-only state. */
  actionLabel?: string;
  /** Anchor id to scroll to when the CTA is clicked. */
  anchor?: string;
  /** Optional leading icon for the message. */
  icon?: LucideIcon;
};

/**
 * Actionable empty state: a "what to do next" message plus an optional primary
 * CTA that scrolls to the prerequisite panel. Replaces the passive "no data yet"
 * copy with a guided next step, keeping #2/#3/#4 wording consistent.
 */
export function EmptyStateAction({ message, actionLabel, anchor, icon: Icon }: EmptyStateActionProps) {
  function handleAction() {
    if (!anchor) return;
    const target = document.getElementById(anchor);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      (target as HTMLElement & { focus?: () => void }).focus?.();
    }
  }

  return (
    <div className="empty-state-action">
      {Icon ? <Icon aria-hidden="true" size={20} /> : null}
      <p className="empty">{message}</p>
      {actionLabel ? (
        <button className="button" onClick={handleAction} type="button">
          {actionLabel}
          <ArrowRight aria-hidden="true" size={16} />
        </button>
      ) : null}
    </div>
  );
}

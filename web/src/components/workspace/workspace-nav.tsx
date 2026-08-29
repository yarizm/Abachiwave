"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useLocale } from "@/i18n/locale-provider";
import { TranslationKey } from "@/i18n/translations";
import { CreationStage, CreationStepId, CreationStepStatus } from "@/lib/creation-stage";

/**
 * The workspace's primary navigation.
 *
 * The creation chain used to be a progress bar whose steps scrolled to anchors on
 * one very long page. Now the chain *is* the navigation: each stage is a route, and
 * the step's derived status (done / active / blocked) is what the link carries.
 *
 * Routes with no chain step — audio, history, settings — sit in a separate group,
 * because they are entered on purpose rather than reached by walking the chain.
 */

type ChainRoute = {
  /** path segment appended to the project route; empty string is the overview */
  segment: string;
  label: TranslationKey;
  /** chain steps this route is responsible for; empty means the route has no status */
  steps: CreationStepId[];
};

const CHAIN_ROUTES: ChainRoute[] = [
  { segment: "", label: "Overview", steps: [] },
  { segment: "spec", label: "SongSpec", steps: ["idea", "song_spec", "approve"] },
  { segment: "audio", label: "Audio", steps: [] },
  { segment: "composition", label: "Composition", steps: ["composition"] },
  { segment: "arrangement", label: "Arrangement", steps: ["arrangement", "export"] },
  { segment: "demo", label: "Demo", steps: ["demo"] },
];

const UTILITY_ROUTES: { segment: string; label: TranslationKey }[] = [
  { segment: "history", label: "History" },
  { segment: "settings", label: "Settings" },
];

/**
 * Collapse the statuses of the steps a route owns into one.
 *
 * `active` wins so the chain always shows exactly one "you are here", and a route
 * counts as done only when every step it owns is done.
 */
export function routeStatus(
  stage: CreationStage,
  steps: CreationStepId[],
): CreationStepStatus | null {
  if (steps.length === 0) {
    return null;
  }
  const owned = stage.steps.filter((step) => steps.includes(step.id));
  if (owned.some((step) => step.status === "active")) {
    return "active";
  }
  if (owned.length > 0 && owned.every((step) => step.status === "done")) {
    return "done";
  }
  return owned.some((step) => step.status === "todo") ? "todo" : "blocked";
}

type WorkspaceNavProps = {
  projectId: string;
  stage: CreationStage;
};

export function WorkspaceNav({ projectId, stage }: WorkspaceNavProps) {
  const { t } = useLocale();
  const pathname = usePathname();
  const base = `/projects/${projectId}`;

  function isActive(segment: string): boolean {
    const href = segment ? `${base}/${segment}` : base;
    return pathname === href;
  }

  return (
    <nav aria-label={t("Workspace sections")} className="workspace-nav">
      <ol className="workspace-nav-chain">
        {CHAIN_ROUTES.map((route) => {
          const status = routeStatus(stage, route.steps);
          const href = route.segment ? `${base}/${route.segment}` : base;
          return (
            <li className="workspace-nav-item" key={route.segment || "overview"}>
              <Link
                aria-current={isActive(route.segment) ? "page" : undefined}
                className={`workspace-nav-link${status ? ` is-${status}` : ""}`}
                href={href}
              >
                {status === "done" ? (
                  <Check aria-hidden="true" className="workspace-nav-check" size={14} />
                ) : status ? (
                  <span aria-hidden="true" className="workspace-nav-dot" />
                ) : null}
                {t(route.label)}
              </Link>
            </li>
          );
        })}
      </ol>
      <div className="workspace-nav-utility">
        {UTILITY_ROUTES.map((route) => (
          <Link
            aria-current={isActive(route.segment) ? "page" : undefined}
            className="workspace-nav-link"
            href={`${base}/${route.segment}`}
            key={route.segment}
          >
            {t(route.label)}
          </Link>
        ))}
      </div>
    </nav>
  );
}

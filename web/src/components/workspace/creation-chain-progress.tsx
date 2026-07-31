"use client";

import { Check } from "lucide-react";

import { useLocale } from "@/i18n/locale-provider";
import { CreationStage, CreationStepId } from "@/lib/creation-stage";
import { TranslationKey } from "@/i18n/translations";

const STEP_LABELS: Record<CreationStepId, TranslationKey> = {
  idea: "Chain step: idea",
  song_spec: "Chain step: song spec",
  approve: "Chain step: approve",
  composition: "Chain step: composition",
  arrangement: "Chain step: arrangement",
  demo: "Chain step: demo",
  export: "Chain step: export",
};

type CreationChainProgressProps = {
  stage: CreationStage;
};

export function CreationChainProgress({ stage }: CreationChainProgressProps) {
  const { t } = useLocale();

  function scrollToAnchor(anchor: string) {
    const target = document.getElementById(anchor);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      (target as HTMLElement & { focus?: () => void }).focus?.();
    }
  }

  return (
    <nav className="creation-chain" aria-label={t("Creation chain")}>
      <ol className="creation-chain-steps">
        {stage.steps.map((step, index) => {
          const label = t(STEP_LABELS[step.id]);
          const isClickable = step.status === "done" || step.status === "active";
          return (
            <li
              key={step.id}
              className={`creation-chain-step is-${step.status}`}
              aria-current={index === stage.currentIndex ? "step" : undefined}
            >
              <button
                className="creation-chain-marker"
                disabled={!isClickable}
                onClick={() => scrollToAnchor(step.anchor)}
                title={t("Jump to {step}", { step: label })}
                type="button"
                aria-label={t("Jump to {step}", { step: label })}
              >
                <span className="creation-chain-index">
                  {step.status === "done" ? <Check aria-hidden="true" size={14} /> : index + 1}
                </span>
                <span className="creation-chain-label">{label}</span>
              </button>
              {index < stage.steps.length - 1 ? (
                <span className="creation-chain-connector" aria-hidden="true" />
              ) : null}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

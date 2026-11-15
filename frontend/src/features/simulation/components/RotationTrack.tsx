import * as React from "react";
import { useTranslation } from "react-i18next";
import {
  ArrowLeftRight,
  ArrowRight,
  Calendar,
  Check,
  ChevronDown,
  Sprout,
} from "lucide-react";
import { cn } from "../../../lib/utils";
import type {
  RotationAlternativeCrop,
  RotationTrackStep,
} from "../types/recommendations.types";

export interface RotationTrackProps {
  steps: RotationTrackStep[];
  onSelectAlternative?: (
    stepId: string,
    alternative: RotationAlternativeCrop
  ) => void;
  className?: string;
}

interface ThumbnailBoxProps {
  name: string;
  imageUrl?: string | null;
  isRest?: boolean;
  sizeClass: string;
  iconSizeClass: string;
  interactive?: boolean;
  expanded?: boolean;
}

function ThumbnailBox({
  name,
  imageUrl,
  isRest,
  sizeClass,
  iconSizeClass,
  interactive = false,
  expanded = false,
}: ThumbnailBoxProps) {
  const [hasError, setHasError] = React.useState(false);

  React.useEffect(() => {
    setHasError(false);
  }, [imageUrl]);

  const interactiveRing = interactive
    ? expanded
      ? "ring-2 ring-[#511D4E] border-[#511D4E]"
      : "border-[#511D4E]/45 group-hover:border-[#511D4E]"
    : "";

  if (isRest) {
    return (
      <div
        aria-hidden="true"
        className={cn(
          "flex shrink-0 items-center justify-center rounded-xl border border-[#CAD17A]/50 bg-[#CAD17A]/30 text-[#511D4E]",
          sizeClass
        )}
      >
        <Calendar className={iconSizeClass} />
      </div>
    );
  }

  if (!imageUrl || hasError) {
    return (
      <div
        aria-hidden="true"
        className={cn(
          "flex shrink-0 items-center justify-center rounded-xl border border-[#91C494]/45 bg-[#91C494]/25 text-[#511D4E] transition-colors",
          sizeClass,
          interactiveRing
        )}
      >
        <Sprout className={iconSizeClass} />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "shrink-0 overflow-hidden rounded-xl border border-[#E6E4DA] bg-white transition-colors",
        sizeClass,
        interactiveRing
      )}
    >
      <img
        src={imageUrl}
        alt={name}
        onError={() => setHasError(true)}
        className="h-full w-full object-cover"
      />
    </div>
  );
}

/**
 * Renderiza dinamicamente a trilha visual de rotação (2 a 5 passos) com suporte a troca de culturas equivalentes sugeridas pela IA.
 */
export function RotationTrack({
  steps,
  onSelectAlternative,
  className,
}: RotationTrackProps) {
  const { t } = useTranslation();
  const normalizedSteps = steps.slice(0, 5);
  const isCompact = normalizedSteps.length >= 4;
  const [expandedStepId, setExpandedStepId] = React.useState<string | null>(
    null
  );

  const expandedStep = React.useMemo(
    () =>
      normalizedSteps.find(
        (step) => step.id === expandedStepId && step.alternatives?.length
      ) ?? null,
    [normalizedSteps, expandedStepId]
  );

  const sizeClass = isCompact ? "h-12 w-12" : "h-14 w-14";
  const iconSizeClass = isCompact ? "h-5 w-5" : "h-6 w-6";

  const handleToggleStep = (stepId: string) => {
    setExpandedStepId((prev) => (prev === stepId ? null : stepId));
  };

  const handleChooseAlternative = (
    stepId: string,
    alternative: RotationAlternativeCrop
  ) => {
    onSelectAlternative?.(stepId, alternative);
    setExpandedStepId(null);
  };

  return (
    <div
      aria-label={t("simulation.trackAria")}
      className={cn("rounded-2xl bg-[#F4F3EE] px-3 py-4", className)}
    >
      <ol
        className={cn(
          "flex items-start justify-center",
          isCompact ? "flex-wrap gap-x-1 gap-y-3" : "gap-1.5"
        )}
      >
        {normalizedSteps.map((step, index) => {
          const isLast = index === normalizedSteps.length - 1;
          const hasAlternatives = Boolean(
            step.alternatives && step.alternatives.length > 0
          );
          const isExpanded = expandedStepId === step.id;

          return (
            <React.Fragment key={step.id}>
              <li
                className={cn(
                  "flex flex-col items-center text-center",
                  isCompact ? "w-[74px] shrink-0" : "min-w-0 flex-1"
                )}
              >
                {hasAlternatives ? (
                  <button
                    type="button"
                    aria-expanded={isExpanded}
                    onClick={() => handleToggleStep(step.id)}
                    className={cn(
                      "group flex w-full flex-col items-center rounded-xl p-1 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E]",
                      isExpanded ? "bg-[#511D4E]/[0.07]" : "hover:bg-white/70"
                    )}
                  >
                    <ThumbnailBox
                      name={step.name}
                      imageUrl={step.imageUrl}
                      isRest={step.isRest}
                      sizeClass={sizeClass}
                      iconSizeClass={iconSizeClass}
                      interactive
                      expanded={isExpanded}
                    />

                    <p className="mt-2 line-clamp-2 text-xs font-bold leading-tight text-[#511D4E]">
                      {step.name}
                    </p>
                    <p className="mt-0.5 text-[11px] leading-tight text-[#6D6960]">
                      {step.statusLabel}
                    </p>
                    <span className="mt-1 inline-flex items-center gap-0.5 rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-[#511D4E] shadow-xs ring-1 ring-[#511D4E]/20">
                      <span>{t("simulation.swap")}</span>
                      <ChevronDown
                        className={cn(
                          "h-3 w-3 transition-transform",
                          isExpanded && "rotate-180"
                        )}
                        aria-hidden="true"
                      />
                    </span>
                  </button>
                ) : (
                  <>
                    <ThumbnailBox
                      name={step.name}
                      imageUrl={step.imageUrl}
                      isRest={step.isRest}
                      sizeClass={sizeClass}
                      iconSizeClass={iconSizeClass}
                    />

                    <p className="mt-2 line-clamp-2 text-xs font-bold leading-tight text-[#1F1C18]">
                      {step.name}
                    </p>
                    <p className="mt-0.5 text-[11px] leading-tight text-[#6D6960]">
                      {step.statusLabel}
                    </p>
                  </>
                )}
              </li>

              {!isLast && (
                <li
                  aria-hidden="true"
                  className={cn(
                    "flex shrink-0 items-center justify-center text-[#6D6960]",
                    isCompact ? "h-12 px-0.5" : "h-14 px-0.5"
                  )}
                >
                  <ArrowRight className="h-3.5 w-3.5" />
                </li>
              )}
            </React.Fragment>
          );
        })}
      </ol>

      {expandedStep?.alternatives && (
        <div
          role="region"
          aria-label={t("simulation.alternativesAria", {
            plant: expandedStep.name,
          })}
          className="mt-3.5 rounded-xl border border-[#511D4E]/25 bg-white p-3"
        >
          <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-[#511D4E]">
            <ArrowLeftRight className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>{t("simulation.equivalentCrops")}</span>
          </div>

          <ul className="mt-2 flex flex-col gap-2">
            {expandedStep.alternatives.map((alt) => {
              const localizedName = t(
                `simulation.coverAlternatives.${alt.id}.name`,
                { defaultValue: alt.name }
              );
              const localizedReason = t(
                `simulation.coverAlternatives.${alt.id}.reason`,
                { defaultValue: alt.reason }
              );
              const isCurrent =
                localizedName === expandedStep.name ||
                alt.name === expandedStep.name;

              return (
                <li key={alt.id}>
                  <button
                    type="button"
                    onClick={() =>
                      handleChooseAlternative(expandedStep.id, {
                        ...alt,
                        name: localizedName,
                        reason: localizedReason,
                      })
                    }
                    className={cn(
                      "flex w-full items-center justify-between gap-2.5 rounded-xl border px-2.5 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E]",
                      isCurrent
                        ? "border-[#511D4E] bg-[#511D4E]/[0.06]"
                        : "border-[#E6E4DA] bg-[#F7F6F0]/60 hover:border-[#511D4E]/50 hover:bg-white"
                    )}
                  >
                    <div className="flex min-w-0 items-center gap-2.5">
                      <ThumbnailBox
                        name={localizedName}
                        imageUrl={alt.imageUrl}
                        sizeClass="h-9 w-9"
                        iconSizeClass="h-4 w-4"
                      />

                      <div className="min-w-0">
                        <p
                          className={cn(
                            "truncate text-xs font-bold",
                            isCurrent ? "text-[#511D4E]" : "text-[#1F1C18]"
                          )}
                        >
                          {localizedName}
                        </p>
                        <p className="mt-0.5 text-[11px] leading-snug text-[#6D6960]">
                          {localizedReason}
                        </p>
                      </div>
                    </div>

                    {isCurrent && (
                      <Check
                        className="h-4 w-4 shrink-0 text-[#511D4E]"
                        aria-hidden="true"
                      />
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

export default RotationTrack;

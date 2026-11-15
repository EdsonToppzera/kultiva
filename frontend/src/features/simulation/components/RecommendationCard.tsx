import {
  AlertTriangle,
  ArrowRight,
  Check,
  CloudRain,
  HelpCircle,
  ShieldAlert,
} from "lucide-react";
import { Button } from "../../../components/ui/button";
import { cn } from "../../../lib/utils";
import type {
  RotationAlternativeCrop,
  RotationScenario,
} from "../types/recommendations.types";
import { RotationTrack } from "./RotationTrack";

export interface RecommendationCardProps {
  scenario: RotationScenario;
  onSelectPlan?: (scenario: RotationScenario) => void;
  onOpenDetails?: (scenario: RotationScenario) => void;
  onSwapTrackStep?: (
    scenarioId: string,
    stepId: string,
    alternative: RotationAlternativeCrop
  ) => void;
  className?: string;
}

/**
 * Cartão reutilizável de cenário de rotação (suporta variante recomendada, padrão e alerta de risco/inviabilidade).
 */
export function RecommendationCard({
  scenario,
  onSelectPlan,
  onOpenDetails,
  onSwapTrackStep,
  className,
}: RecommendationCardProps) {
  const variant = scenario.variant ?? "standard";
  const isRecommended = variant === "recommended";
  const isRisk = variant === "risk";

  return (
    <article
      className={cn(
        "flex flex-col rounded-3xl border p-4 shadow-sm transition-shadow sm:p-5",
        isRisk
          ? "border-[1.5px] border-[#C42311] bg-[#C42311]/[0.05]"
          : "border-[#E6E4DA] bg-white",
        className
      )}
    >
      {/* Top Bar */}
      <div className="flex items-center justify-between gap-2">
        <span
          className={cn(
            "inline-flex shrink-0 items-center rounded-full px-3 py-1 text-xs font-bold leading-none",
            isRecommended && "bg-[#CAD17A] text-[#2F3A1D]",
            variant === "standard" && "bg-[#EFECE3] text-[#511D4E]",
            isRisk && "bg-[#C42311] text-white"
          )}
        >
          {scenario.optionBadge}
        </span>

        <button
          type="button"
          onClick={() => onOpenDetails?.(scenario)}
          className={cn(
            "inline-flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E]",
            isRisk
              ? "bg-[#C42311]/12 text-[#C42311] hover:bg-[#C42311]/20"
              : "bg-[#CAD17A]/35 text-[#511D4E] hover:bg-[#CAD17A]/60"
          )}
        >
          <HelpCircle className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>Ver detalhes técnicos</span>
        </button>
      </div>

      {/* Tag de Foco */}
      <p
        className={cn(
          "mt-3.5 text-[11px] font-bold uppercase tracking-wider",
          isRisk ? "text-[#C42311]" : "text-[#6D6960]"
        )}
      >
        {scenario.focusTag}
      </p>

      {/* Trilha Visual Dinâmica (2 a 5 passos) */}
      <div className="mt-3">
        <RotationTrack
          steps={scenario.steps}
          onSelectAlternative={(stepId, alternative) =>
            onSwapTrackStep?.(scenario.id, stepId, alternative)
          }
          className={isRisk ? "border border-[#C42311]/20 bg-white/80" : undefined}
        />
      </div>

      {/* Resumo Numérico (Viabilidade, Produtividade GAEZ, Risco Hídrico e Fitossanidade) */}
      {(scenario.technicalDetails.viabilityScorePercent !== undefined ||
        scenario.technicalDetails.gaez?.attainableYieldKgHa != null ||
        scenario.technicalDetails.waterRiskLabel ||
        scenario.technicalDetails.agrofit) && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {scenario.technicalDetails.viabilityScorePercent !== undefined && (
            <span className="inline-flex items-center rounded-full bg-[#511D4E]/10 px-2.5 py-1 text-[11px] font-bold text-[#511D4E]">
              Viabilidade: {scenario.technicalDetails.viabilityScorePercent}%
            </span>
          )}
          {scenario.technicalDetails.gaez?.attainableYieldKgHa != null && (
            <span className="inline-flex items-center rounded-full bg-[#91C494]/25 px-2.5 py-1 text-[11px] font-bold text-[#1E3B21]">
              GAEZ: ~{Math.round(scenario.technicalDetails.gaez.attainableYieldKgHa)} kg/ha
            </span>
          )}
          {scenario.technicalDetails.waterRiskLabel && (
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-bold",
                scenario.technicalDetails.waterRiskLabel.toLowerCase() === "alto"
                  ? "bg-[#C42311]/12 text-[#8E180B]"
                  : "bg-[#EFECE3] text-[#4E4A43]"
              )}
            >
              Risco hídrico: {scenario.technicalDetails.waterRiskLabel}
            </span>
          )}
          {scenario.technicalDetails.agrofit && (
            <span
              className={cn(
                "inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-bold",
                scenario.technicalDetails.agrofit.phytosanitaryRisk === "high"
                  ? "bg-[#C42311]/12 text-[#8E180B]"
                  : scenario.technicalDetails.agrofit.phytosanitaryRisk === "medium"
                    ? "bg-[#FCF59B]/70 text-[#4A3B12]"
                    : "bg-[#91C494]/20 text-[#1E3B21]"
              )}
            >
              Fitossanidade: {scenario.technicalDetails.agrofit.phytosanitaryRiskLabel}
            </span>
          )}
        </div>
      )}

      {/* Justificação da IA (NASA/Clima) */}
      <div
        className={cn(
          "mt-4 flex items-start gap-2.5 text-sm leading-snug",
          isRisk
            ? "rounded-2xl border border-[#C42311]/30 bg-[#C42311]/10 p-3 text-[#8E180B]"
            : "text-[#3D3933]"
        )}
      >
        {isRisk ? (
          <ShieldAlert
            className="mt-0.5 h-4 w-4 shrink-0 text-[#C42311]"
            aria-hidden="true"
          />
        ) : (
          <CloudRain
            className="mt-0.5 h-4 w-4 shrink-0 text-[#511D4E]"
            aria-hidden="true"
          />
        )}
        <p className={isRisk ? "font-semibold" : undefined}>
          {scenario.aiJustification}
        </p>
      </div>

      {/* Prós e Contras */}
      <ul className="mt-3.5 flex flex-col gap-2 text-xs leading-snug text-[#4E4A43] sm:text-sm">
        {scenario.pros.map((pro) => (
          <li key={pro} className="flex items-start gap-2.5">
            <Check
              className="mt-0.5 h-4 w-4 shrink-0 text-[#2E7D32]"
              aria-hidden="true"
            />
            <span>{pro}</span>
          </li>
        ))}

        {scenario.cons.map((con) => (
          <li key={con} className="flex items-start gap-2.5">
            <AlertTriangle
              className="mt-0.5 h-4 w-4 shrink-0 text-[#D9531E]"
              aria-hidden="true"
            />
            <span>{con}</span>
          </li>
        ))}
      </ul>

      {/* Ação */}
      <div className="mt-auto pt-5">
        <Button
          type="button"
          variant={isRisk ? "destructive" : "primary"}
          size="lg"
          onClick={() => onSelectPlan?.(scenario)}
          className="w-full"
        >
          <span>{scenario.ctaLabel ?? "Escolher este plano"}</span>
          <ArrowRight className="h-5 w-5" aria-hidden="true" />
        </Button>
      </div>
    </article>
  );
}

export default RecommendationCard;

import * as React from "react";
import { useTranslation } from "react-i18next";
import {
  AlertTriangle,
  Bug,
  ChevronLeft,
  Clock,
  Droplets,
  MapPin,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { KultivaLogo } from "../../../components/KultivaLogo";
import { KultivaLoader } from "../../../components/KultivaLoader";
import { NetworkStatusBadge } from "../../../components/NetworkStatusBadge";
import { Button } from "../../../components/ui/button";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "../../../components/ui/drawer";
import { cn } from "../../../lib/utils";
import type { NetworkSyncStatus } from "../../onboarding/types/cropHistory.types";
import type {
  AreaSummaryInfo,
  RotationAlternativeCrop,
  RotationScenario,
} from "../types/recommendations.types";
export {
  COVER_CROP_ALTERNATIVES,
  buildAreaSummaryFromOnboarding,
} from "../utils/recommendationHelpers";
import { RecommendationCard } from "./RecommendationCard";

export interface RecommendationsStepProps {
  propertyLocation?: string;
  areaSummary?: AreaSummaryInfo;
  scenarios?: RotationScenario[];
  isLoading?: boolean;
  isSubmittingPlan?: boolean;
  errorMessage?: string | null;
  networkStatus?: NetworkSyncStatus;
  onSelectPlan?: (scenario: RotationScenario) => void;
  onRetry?: () => void;
  onBack?: () => void;
}

/**
 * Tela Final do Onboarding — Recomendações de Rotação.
 * Renderiza trilhas dinâmicas (2 a 5 passos), variante crítica de risco/inviabilidade e Drawer técnico.
 */
export function RecommendationsStep({
  propertyLocation = "",
  scenarios = [],
  isLoading = false,
  isSubmittingPlan = false,
  errorMessage = null,
  networkStatus,
  onSelectPlan,
  onRetry,
  onBack,
}: RecommendationsStepProps) {
  const { t } = useTranslation();
  const [localScenarios, setLocalScenarios] =
    React.useState<RotationScenario[]>(scenarios);
  const [activeScenarioId, setActiveScenarioId] = React.useState<string | null>(
    null
  );

  React.useEffect(() => {
    setLocalScenarios(scenarios);
  }, [scenarios]);

  const activeScenario = React.useMemo(
    () =>
      localScenarios.find((item) => item.id === activeScenarioId) ?? null,
    [localScenarios, activeScenarioId]
  );

  const handleSwapTrackStep = React.useCallback(
    (
      scenarioId: string,
      stepId: string,
      alternative: RotationAlternativeCrop
    ) => {
      setLocalScenarios((prev) =>
        prev.map((scenario) => {
          if (scenario.id !== scenarioId) return scenario;
          return {
            ...scenario,
            steps: scenario.steps.map((step) =>
              step.id === stepId
                ? {
                    ...step,
                    name: alternative.name,
                    imageUrl: alternative.imageUrl ?? null,
                  }
                : step
            ),
          };
        })
      );
    },
    []
  );

  return (
    <div className="min-h-dvh w-full bg-[#F7F6F0] text-[#1F1C18]">
      <div className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-between px-5 pb-10 pt-6 md:max-w-2xl lg:max-w-6xl lg:px-8 lg:py-10">
        <div>
          {/* Header */}
          <header className="flex items-center justify-between gap-4">
            <KultivaLogo />

            <div className="flex items-center gap-2">
              <NetworkStatusBadge status={networkStatus} />
            </div>
          </header>

          {/* Localização da propriedade */}
          <div className="mt-3 flex items-center gap-1.5 text-xs font-medium text-[#6D6960] sm:text-sm">
            <MapPin className="h-4 w-4 shrink-0 text-[#511D4E]" aria-hidden="true" />
            <span>{propertyLocation}</span>
          </div>

          {/* Títulos */}
          <section className="mt-4">
            <h1 className="text-[28px] font-bold leading-tight tracking-tight text-[#511D4E] sm:text-3xl">
              {t("simulation.title")}
            </h1>
            <p className="mt-1.5 text-sm text-[#6D6960] sm:text-base">
              {t("simulation.subtitle")}
            </p>
          </section>

          {/* Grid Responsivo de Cartões */}
          <main className="mt-6">
            {isLoading ? (
              <div className="flex items-center justify-center rounded-3xl border border-[#E6E4DA] bg-white px-6 py-12">
                <KultivaLoader
                  fullscreen={false}
                  label={t("simulation.calculating")}
                />
              </div>
            ) : errorMessage || localScenarios.length === 0 ? (
              <div
                role="alert"
                className="flex flex-col items-center gap-4 rounded-3xl border border-[#C42311]/30 bg-white px-6 py-10 text-center"
              >
                <AlertTriangle
                  className="h-8 w-8 text-[#C42311]"
                  aria-hidden="true"
                />
                <p className="text-sm font-medium text-[#1F1C18]">
                  {errorMessage || t("simulation.apiErrorFallback")}
                </p>
                {onRetry && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={onRetry}
                  >
                    <RefreshCw className="h-4 w-4" aria-hidden="true" />
                    <span>{t("simulation.retry")}</span>
                  </Button>
                )}
              </div>
            ) : (
              <div className="space-y-6">
                <div className="grid grid-cols-1 gap-5 lg:grid-cols-3 lg:items-start">
                  {localScenarios.map((scenario) => (
                    <RecommendationCard
                      key={scenario.id}
                      scenario={scenario}
                      onSelectPlan={isSubmittingPlan ? undefined : onSelectPlan}
                      onOpenDetails={(item) => setActiveScenarioId(item.id)}
                      onSwapTrackStep={handleSwapTrackStep}
                    />
                  ))}
                </div>
                <p className="mx-auto max-w-2xl text-center text-xs leading-relaxed text-[#6D6960]">
                  {t("simulation.decisionDisclaimer")}
                </p>
              </div>
            )}
          </main>
        </div>

        {/* Footer */}
        <footer className="mt-8 flex justify-center pt-2">
          <Button
            type="button"
            variant="ghost"
            onClick={onBack}
            className="w-full max-w-[200px] text-sm font-semibold text-[#511D4E]"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            <span>{t("common.back")}</span>
          </Button>
        </footer>
      </div>

      {/* Drawer de Detalhes Técnicos (NASA + AGROFIT + NPK) */}
      <Drawer
        open={activeScenario !== null}
        onOpenChange={(isOpen) => {
          if (!isOpen) setActiveScenarioId(null);
        }}
      >
        <DrawerContent>
          {activeScenario && (
            <>
              <DrawerHeader>
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      "inline-flex rounded-full px-2.5 py-0.5 text-xs font-bold",
                      activeScenario.variant === "risk"
                        ? "bg-[#C42311] text-white"
                        : "bg-[#CAD17A] text-[#2F3A1D]"
                    )}
                  >
                    {activeScenario.optionBadge}
                  </span>
                  <span className="text-[11px] font-bold uppercase tracking-wider text-[#6D6960]">
                    {activeScenario.focusTag}
                  </span>
                </div>

                <DrawerTitle className="mt-1">
                  {t("simulation.drawerTitle")}
                </DrawerTitle>
                <DrawerDescription>
                  {t("simulation.drawerSubtitle")}
                </DrawerDescription>
              </DrawerHeader>

              {/* Indicadores rápidos */}
              <div className="mt-4 grid grid-cols-2 gap-2.5">
                <div className="rounded-2xl border border-[#E6E4DA] bg-white p-3">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[#6D6960]">
                    <Clock className="h-3.5 w-3.5 text-[#511D4E]" aria-hidden="true" />
                    <span>{t("simulation.estimatedCycle")}</span>
                  </div>
                  <p className="mt-1 text-sm font-bold text-[#1F1C18]">
                    {activeScenario.technicalDetails.cycleDurationDays}
                  </p>
                </div>

                <div className="rounded-2xl border border-[#E6E4DA] bg-white p-3">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[#6D6960]">
                    <Droplets
                      className="h-3.5 w-3.5 text-[#511D4E]"
                      aria-hidden="true"
                    />
                    <span>{t("simulation.waterNeeded")}</span>
                  </div>
                  <p className="mt-1 text-sm font-bold text-[#1F1C18]">
                    {activeScenario.technicalDetails.waterDemandMm}
                  </p>
                </div>
              </div>

              {/* Nota climática NASA */}
              <div
                className={cn(
                  "mt-3 rounded-2xl border p-3.5 text-xs leading-relaxed sm:text-sm",
                  activeScenario.variant === "risk"
                    ? "border-[#C42311]/40 bg-[#C42311]/10 text-[#8E180B]"
                    : "border-[#91C494]/60 bg-[#91C494]/20 text-[#1E3B21]"
                )}
              >
                <div className="mb-1 flex items-center gap-1.5 font-bold">
                  {activeScenario.variant === "risk" ? (
                    <ShieldAlert className="h-4 w-4 shrink-0" aria-hidden="true" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
                  )}
                  <span>{t("simulation.nasaAnalysis")}</span>
                </div>
                <p>{activeScenario.technicalDetails.nasaClimateNote}</p>
              </div>

              {/* Tabela NPK */}
              <div className="mt-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-[#6D6960]">
                  {t("simulation.npkTitle")}
                </h3>
                <div className="mt-2 overflow-hidden rounded-2xl border border-[#E6E4DA] bg-white">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-[#E6E4DA] bg-[#F7F6F0] text-[#6D6960]">
                      <tr>
                        <th className="px-3 py-2 font-semibold">
                          {t("simulation.nutrient")}
                        </th>
                        <th className="px-3 py-2 font-semibold">
                          {t("simulation.requirement")}
                        </th>
                        <th className="px-3 py-2 font-semibold">
                          {t("simulation.effect")}
                        </th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E6E4DA]">
                      {activeScenario.technicalDetails.npkTable.map((row) => (
                        <tr key={row.nutrient}>
                          <td className="px-3 py-2 font-bold text-[#1F1C18]">
                            {row.nutrient}
                          </td>
                          <td className="px-3 py-2">
                            <span
                              className={cn(
                                "inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold",
                                (row.requirementLevel === "Alto" ||
                                  row.requirementLevel === "High") &&
                                  "bg-[#C42311]/15 text-[#8E180B]",
                                (row.requirementLevel === "Médio" ||
                                  row.requirementLevel === "Medium") &&
                                  "bg-[#FCF59B] text-[#4A3B12]",
                                (row.requirementLevel === "Baixo" ||
                                  row.requirementLevel === "Low") &&
                                  "bg-[#91C494]/25 text-[#1E3B21]"
                              )}
                            >
                              {row.requirementLevel}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-[#4E4A43]">
                            {row.impact}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Alertas de Pragas AGROFIT */}
              <div className="mt-4">
                <h3 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#6D6960]">
                  <Bug className="h-3.5 w-3.5 text-[#511D4E]" aria-hidden="true" />
                  <span>{t("simulation.pestAlerts")}</span>
                </h3>
                <ul className="mt-2 flex flex-col gap-2">
                  {activeScenario.technicalDetails.agrofitAlerts.map((alert) => (
                    <li
                      key={alert}
                      className="rounded-xl border border-[#E6E4DA] bg-white px-3 py-2.5 text-xs leading-snug text-[#3D3933]"
                    >
                      {alert}
                    </li>
                  ))}
                </ul>
              </div>

              <DrawerFooter>
                <DrawerClose asChild>
                  <Button type="button" variant="primary" className="w-full">
                    {t("simulation.closeDetails")}
                  </Button>
                </DrawerClose>
              </DrawerFooter>
            </>
          )}
        </DrawerContent>
      </Drawer>
    </div>
  );
}

export default RecommendationsStep;


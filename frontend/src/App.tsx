import * as React from "react";
import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  ChevronLeft,
  Pencil,
  RotateCcw,
  Wifi,
  WifiOff,
} from "lucide-react";
import { KultivaLogo } from "./components/KultivaLogo";
import { LanguageSelector } from "./components/LanguageSelector";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { CropHistoryStep } from "./features/onboarding/components/CropHistoryStep";
import { PrioritiesStep } from "./features/onboarding/components/PrioritiesStep";
import { SoilTypeStep } from "./features/onboarding/components/SoilTypeStep";
import { WaterDistributionStep } from "./features/onboarding/components/WaterDistributionStep";
import {
  RecommendationsStep,
  buildRecommendationsFromOnboarding,
} from "./features/simulation/components/RecommendationsStep";
import type {
  CropHistoryData,
  NetworkSyncStatus,
} from "./features/onboarding/types/cropHistory.types";
import type { PriorityData } from "./features/onboarding/types/priority.types";
import type { SoilTypeData } from "./features/onboarding/types/soilType.types";
import type { WaterDistributionData } from "./features/onboarding/types/waterDistribution.types";
import type { RotationScenario } from "./features/simulation/types/recommendations.types";
import { AreaCalendarPage } from "./pages/AreaCalendarPage";
import { AreaDashboardPage } from "./pages/AreaDashboardPage";
import { type MapCoordinate, MapTerrainPage } from "./pages/MapTerrainPage";
import {
  PlantationsPage,
  type PlantationArea,
} from "./pages/PlantationsPage";
import {
  adaptSimulacaoToScenarios,
  buildGerarCronogramaPayload,
} from "./services/adapters";
import {
  type CoordenadaApi,
  type TerrenoResponse,
  DEFAULT_USUARIO_ID,
  converterHistoricoParaLista,
  criarTerreno,
  extrairMetodoIrrigacao,
  extrairPrioridadeDoTerreno,
  extrairTipoSolo,
  formatarAreaHectares,
  gerarCronogramaDeSimulacao,
  mapearPrioridadesIrrigacao,
  restaurarHistoricoDoTerreno,
  simularRotacao,
} from "./services/api";
import { WATER_DISTRIBUTION_OPTIONS } from "./features/onboarding/components/WaterDistributionStep";
import { SOIL_TYPE_OPTIONS } from "./features/onboarding/components/SoilTypeStep";
import { PRIORITY_OPTIONS } from "./features/onboarding/components/PrioritiesStep";

type OnboardingStep =
  | "plantations"
  | "area-dashboard"
  | "area-calendar"
  | "map-terrain"
  | 1
  | 2
  | 3
  | 4
  | "summary"
  | "recommendations";

interface DraftTerrain {
  nome_propriedade: string;
  points: MapCoordinate[];
  coordenadas_poligono: CoordenadaApi[];
  area_hectares?: number;
}

function buildMergedPrioridades(
  existingPrioridades: Record<string, unknown> | null | undefined,
  cropHistory: CropHistoryData | null,
  waterDistribution: WaterDistributionData | null,
  soilType: SoilTypeData | null,
  priority: PriorityData | null
): Record<string, unknown> {
  return {
    ...(existingPrioridades ?? {}),
    ...(cropHistory
      ? {
          historico_cultivos: converterHistoricoParaLista(cropHistory),
          nao_lembra_historico: cropHistory.naoLembro,
          cultivo_em_andamento: cropHistory.cultivoEmAndamento,
          data_inicio_cultivo:
            cropHistory.cultivoEmAndamento && cropHistory.dataInicioCultivo
              ? cropHistory.dataInicioCultivo
              : null,
        }
      : {}),
    ...(waterDistribution
      ? mapearPrioridadesIrrigacao(
          waterDistribution.metodoIrrigacao.id,
          cropHistory
        )
      : {}),
    ...(soilType ? { tipo_solo: soilType.tipoSolo.id } : {}),
    ...(priority
      ? {
          prioridade: priority.prioridade.id,
          objetivo_principal: priority.prioridade.id,
          cultura_desejada: priority.culturaDesejada?.officialName ?? null,
          praga_alvo: priority.pragaAlvo?.officialName ?? null,
        }
      : {}),
  };
}

export function App() {
  const { t } = useTranslation();
  const [step, setStep] = React.useState<OnboardingStep>("plantations");
  const [currentTerreno, setCurrentTerreno] =
    React.useState<TerrenoResponse | null>(null);
  const [draftTerrain, setDraftTerrain] = React.useState<DraftTerrain | null>(
    null
  );
  const [selectedArea, setSelectedArea] =
    React.useState<PlantationArea | null>(null);
  const [cropHistory, setCropHistory] = React.useState<CropHistoryData | null>(
    null
  );
  const [waterDistribution, setWaterDistribution] =
    React.useState<WaterDistributionData | null>(null);
  const [soilType, setSoilType] = React.useState<SoilTypeData | null>(null);
  const [priority, setPriority] = React.useState<PriorityData | null>(null);
  const [selectedPlan, setSelectedPlan] =
    React.useState<RotationScenario | null>(null);
  const [remoteScenarios, setRemoteScenarios] = React.useState<
    RotationScenario[] | null
  >(null);
  const [isSimulating, setIsSimulating] = React.useState(false);
  const [isGeneratingSchedule, setIsGeneratingSchedule] = React.useState(false);
  const [isOnline, setIsOnline] = React.useState<boolean>(() =>
    typeof navigator !== "undefined" ? navigator.onLine : true
  );

  React.useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const networkStatus: NetworkSyncStatus = isOnline ? "salvo" : "offline";

  React.useEffect(() => {
    if (step !== "recommendations") return;

    let cancelled = false;
    setIsSimulating(true);
    setRemoteScenarios(null);

    const runSimulation = async () => {
      try {
        const mergedPrioridades = buildMergedPrioridades(
          currentTerreno?.prioridades,
          cropHistory,
          waterDistribution,
          soilType,
          priority
        );

        const response = await simularRotacao({
          terreno_id: currentTerreno?.id,
          nome_propriedade:
            currentTerreno?.nome_propriedade ?? draftTerrain?.nome_propriedade,
          coordenadas_poligono:
            currentTerreno?.coordenadas_poligono ??
            draftTerrain?.coordenadas_poligono,
          nome_cultura:
            priority?.culturaDesejada?.officialName ??
            cropHistory?.ultimoCultivo?.officialName,
          historico_cultivos: cropHistory
            ? (cropHistory as unknown as Record<string, unknown>)
            : undefined,
          prioridades: mergedPrioridades,
          dados_solo: soilType
            ? { tipo_solo: soilType.tipoSolo.id }
            : undefined,
        });

        if (!cancelled) {
          setRemoteScenarios(
            adaptSimulacaoToScenarios(response, {
              cropHistory,
              waterDistribution,
              soilType,
              priority,
            })
          );
        }
      } catch {
        // Fallback offline automático para buildRecommendationsFromOnboarding
      } finally {
        if (!cancelled) {
          setIsSimulating(false);
        }
      }
    };

    void runSimulation();
    return () => {
      cancelled = true;
    };
  }, [
    step,
    currentTerreno,
    draftTerrain,
    cropHistory,
    waterDistribution,
    soilType,
    priority,
  ]);

  const handleSelectPlan = async (scenario: RotationScenario) => {
    setSelectedPlan(scenario);
    let resolvedTerreno = currentTerreno;
    let terrenoId = resolvedTerreno?.id ?? selectedArea?.terrenoId;

    setIsGeneratingSchedule(true);
    try {
      if (terrenoId == null && draftTerrain != null) {
        const mergedPrioridades = buildMergedPrioridades(
          null,
          cropHistory,
          waterDistribution,
          soilType,
          priority
        );
        resolvedTerreno = await criarTerreno({
          nome_propriedade: draftTerrain.nome_propriedade,
          usuario_id: DEFAULT_USUARIO_ID,
          coordenadas_poligono: draftTerrain.coordenadas_poligono,
          area_hectares: draftTerrain.area_hectares,
          prioridades: mergedPrioridades,
        });
        setCurrentTerreno(resolvedTerreno);
        terrenoId = resolvedTerreno.id;
      }

      if (terrenoId != null) {
        await gerarCronogramaDeSimulacao(
          buildGerarCronogramaPayload(terrenoId, scenario, cropHistory)
        );
      }
    } catch {
      // Mantém navegação mesmo offline
    } finally {
      setIsGeneratingSchedule(false);
    }

    if (resolvedTerreno) {
      setSelectedArea({
        id: String(resolvedTerreno.id),
        terrenoId: resolvedTerreno.id,
        name: resolvedTerreno.nome_propriedade,
        sizeLabel: formatarAreaHectares(resolvedTerreno.area_hectares),
        areaHectares: resolvedTerreno.area_hectares ?? null,
        coordenadasPoligono: resolvedTerreno.coordenadas_poligono,
        prioridades: resolvedTerreno.prioridades ?? null,
      });
    } else if (draftTerrain) {
      setSelectedArea({
        id: "draft",
        name: draftTerrain.nome_propriedade,
        sizeLabel: formatarAreaHectares(draftTerrain.area_hectares),
        areaHectares: draftTerrain.area_hectares ?? null,
        coordenadasPoligono: draftTerrain.coordenadas_poligono,
      });
    }
    setDraftTerrain(null);
    setStep("area-dashboard");
  };

  if (step === "summary") {
    const cropHistoryLabel = cropHistory?.naoLembro
      ? t("review.dontRemember")
      : [
          cropHistory?.ultimoCultivo?.officialName,
          cropHistory?.cultivoAnterior?.officialName,
        ]
          .filter(Boolean)
          .join(" → ") || t("review.notInformed");

    const reviewItems: Array<{
      label: string;
      value: string;
      targetStep: 1 | 2 | 3 | 4;
    }> = [
      {
        label: t("review.lastCrops"),
        value: cropHistoryLabel,
        targetStep: 1,
      },
      {
        label: t("review.water"),
        value: waterDistribution?.metodoIrrigacao
          ? t(`onboarding.water.options.${waterDistribution.metodoIrrigacao.id}.title`)
          : t("review.notInformed"),
        targetStep: 2,
      },
      {
        label: t("review.soil"),
        value: soilType?.tipoSolo
          ? t(`onboarding.soil.options.${soilType.tipoSolo.id}.title`)
          : t("review.notInformed"),
        targetStep: 3,
      },
      {
        label: t("review.objective"),
        value: priority?.prioridade
          ? priority.culturaDesejada
            ? `${t(`onboarding.priorities.options.${priority.prioridade.id}.title`)} (${priority.culturaDesejada.officialName})`
            : t(`onboarding.priorities.options.${priority.prioridade.id}.title`)
          : t("review.notInformed"),
        targetStep: 4,
      },
    ];

    return (
      <div className="min-h-dvh w-full bg-[#F7F6F0] text-[#1F1C18] md:flex md:items-center md:justify-center md:bg-[#EFECE3] md:p-6">
        <div className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-between bg-[#F7F6F0] px-5 pb-8 pt-6 md:min-h-[680px] md:rounded-3xl md:border md:border-[#E6E4DA] md:px-7 md:py-8 md:shadow-sm">
          <div>
            <header className="flex items-center justify-between gap-4">
              <KultivaLogo />

              <div className="flex items-center gap-2">
                <Badge
                  variant={isOnline ? "saved" : "offline"}
                  aria-live="polite"
                >
                  {isOnline ? (
                    <Wifi className="h-3.5 w-3.5" aria-hidden="true" />
                  ) : (
                    <WifiOff className="h-3.5 w-3.5" aria-hidden="true" />
                  )}
                  <span>{isOnline ? t("network.saved") : t("network.offline")}</span>
                </Badge>
                <LanguageSelector />
              </div>
            </header>

            <main className="mt-8">
              <h1 className="text-[26px] font-bold leading-tight tracking-tight text-[#511D4E] sm:text-[28px]">
                {t("review.title")}
              </h1>
              <p className="mt-1.5 text-sm text-[#6D6960] sm:text-base">
                {t("review.subtitle")}
              </p>

              <ul className="mt-6 flex flex-col gap-3">
                {reviewItems.map((item) => (
                  <li
                    key={item.label}
                    className="flex items-center justify-between gap-3 rounded-2xl border border-[#E6E4DA] bg-white px-4 py-3.5"
                  >
                    <div className="min-w-0">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-[#6D6960]">
                        {item.label}
                      </p>
                      <p className="mt-0.5 text-base font-bold text-[#1F1C18]">
                        {item.value}
                      </p>
                    </div>

                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setStep(item.targetStep)}
                      className="shrink-0 px-2.5 text-xs font-semibold text-[#511D4E]"
                    >
                      <Pencil className="h-3.5 w-3.5" aria-hidden="true" />
                      <span>{t("common.change")}</span>
                    </Button>
                  </li>
                ))}
              </ul>
            </main>
          </div>

          <footer className="mt-8 flex flex-col items-center gap-3 pt-4">
            <Button
              type="button"
              variant="primary"
              size="lg"
              onClick={() => {
                setSelectedPlan(null);
                setStep("recommendations");
              }}
              className="w-full"
            >
              <span>{t("review.confirmAndCompare")}</span>
              <ArrowRight className="h-5 w-5" aria-hidden="true" />
            </Button>

            <div className="flex w-full items-center justify-center gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setStep(4)}
                className="text-sm font-semibold text-[#511D4E]"
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                <span>{t("common.back")}</span>
              </Button>

              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setCropHistory(null);
                  setWaterDistribution(null);
                  setSoilType(null);
                  setPriority(null);
                  setStep(1);
                }}
                className="text-sm font-semibold text-[#6D6960]"
              >
                <RotateCcw className="h-4 w-4" aria-hidden="true" />
                <span>{t("common.restart")}</span>
              </Button>
            </div>
          </footer>
        </div>
      </div>
    );
  }

  if (step === "recommendations") {
    const { areaSummary, scenarios: fallbackScenarios } =
      buildRecommendationsFromOnboarding({
        cropHistory,
        waterDistribution,
        soilType,
        priority,
      });
    const activeScenarios = remoteScenarios ?? fallbackScenarios;

    return (
      <>
        {selectedPlan && (
          <div
            role="status"
            className="fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-full border border-[#91C494] bg-[#1E3B21] px-4 py-2.5 text-xs font-semibold text-white shadow-lg"
          >
            <span>
              {t("simulation.selectedPlanToast", {
                badge: selectedPlan.optionBadge,
                steps: selectedPlan.steps.map((s) => s.name).join(" → "),
              })}
            </span>
          </div>
        )}

        <RecommendationsStep
          propertyLocation={
            currentTerreno?.nome_propriedade ??
            draftTerrain?.nome_propriedade ??
            areaSummary.areaName
          }
          areaSummary={areaSummary}
          scenarios={activeScenarios}
          isLoading={isSimulating}
          isSubmittingPlan={isGeneratingSchedule}
          networkStatus={networkStatus}
          onSelectPlan={(scenario) => void handleSelectPlan(scenario)}
          onBack={() => {
            setSelectedPlan(null);
            setStep("summary");
          }}
        />
      </>
    );
  }

  if (step === 4) {
    return (
      <PrioritiesStep
        initialValue={priority?.prioridade.id ?? null}
        initialTargetCrop={priority?.culturaDesejada ?? null}
        initialTargetPest={priority?.pragaAlvo ?? null}
        networkStatus={networkStatus}
        terrenoId={currentTerreno?.id ?? null}
        existingPrioridades={currentTerreno?.prioridades ?? null}
        onTerrenoUpdated={(updated) => setCurrentTerreno(updated)}
        onBack={() => setStep(3)}
        onContinue={(data) => {
          setPriority(data);
          setStep("summary");
        }}
      />
    );
  }

  if (step === 3) {
    return (
      <SoilTypeStep
        initialValue={soilType?.tipoSolo.id ?? null}
        networkStatus={networkStatus}
        terrenoId={currentTerreno?.id ?? null}
        existingPrioridades={currentTerreno?.prioridades ?? null}
        onTerrenoUpdated={(updated) => setCurrentTerreno(updated)}
        onBack={() => setStep(2)}
        onContinue={(data) => {
          setSoilType(data);
          setStep(4);
        }}
      />
    );
  }

  if (step === 2) {
    return (
      <WaterDistributionStep
        initialValue={waterDistribution?.metodoIrrigacao.id ?? null}
        networkStatus={networkStatus}
        terrenoId={currentTerreno?.id ?? null}
        existingPrioridades={currentTerreno?.prioridades ?? null}
        cropHistory={cropHistory}
        onTerrenoUpdated={(updated) => setCurrentTerreno(updated)}
        onBack={() => setStep(1)}
        onContinue={(data) => {
          setWaterDistribution(data);
          setStep(3);
        }}
      />
    );
  }

  if (step === "plantations") {
    return (
      <PlantationsPage
        onCreateArea={() => {
          setCurrentTerreno(null);
          setDraftTerrain(null);
          setSelectedArea(null);
          setCropHistory(null);
          setWaterDistribution(null);
          setSoilType(null);
          setPriority(null);
          setSelectedPlan(null);
          setRemoteScenarios(null);
          setStep("map-terrain");
        }}
        onSelectArea={(area) => {
          setSelectedArea(area);
          if (area.terrenoId != null) {
            setCurrentTerreno({
              id: area.terrenoId,
              nome_propriedade: area.name,
              usuario_id: DEFAULT_USUARIO_ID,
              coordenadas_poligono: area.coordenadasPoligono ?? [],
              area_hectares: area.areaHectares ?? null,
              prioridades: area.prioridades ?? null,
            });
          } else {
            setCurrentTerreno(null);
          }

          const restoredHistory = restaurarHistoricoDoTerreno(area.prioridades);
          setCropHistory(
            restoredHistory
              ? {
                  ultimoCultivo: restoredHistory.ultimoCultivo ?? null,
                  cultivoAnterior: restoredHistory.cultivoAnterior ?? null,
                  naoLembro: Boolean(restoredHistory.naoLembro),
                  cultivoEmAndamento: Boolean(
                    restoredHistory.cultivoEmAndamento
                  ),
                  dataInicioCultivo: restoredHistory.dataInicioCultivo ?? null,
                }
              : null
          );

          const metodoId = extrairMetodoIrrigacao(area.prioridades);
          const metodoOpt = metodoId
            ? WATER_DISTRIBUTION_OPTIONS.find((o) => o.id === metodoId) ?? null
            : null;
          setWaterDistribution(
            metodoOpt ? { metodoIrrigacao: metodoOpt } : null
          );

          const soloId = extrairTipoSolo(area.prioridades);
          const soloOpt = soloId
            ? SOIL_TYPE_OPTIONS.find((o) => o.id === soloId) ?? null
            : null;
          setSoilType(soloOpt ? { tipoSolo: soloOpt } : null);

          const { priorityId, targetCrop, targetPest } =
            extrairPrioridadeDoTerreno(area.prioridades);
          const prioOpt = priorityId
            ? PRIORITY_OPTIONS.find((o) => o.id === priorityId) ?? null
            : null;
          setPriority(
            prioOpt
              ? {
                  prioridade: prioOpt,
                  culturaDesejada: targetCrop,
                  pragaAlvo: targetPest,
                }
              : null
          );

          setStep("area-dashboard");
        }}
      />
    );
  }

  if (step === "area-dashboard") {
    return (
      <AreaDashboardPage
        terrenoId={selectedArea?.terrenoId ?? currentTerreno?.id ?? null}
        cropNameFallback={
          cropHistory?.ultimoCultivo?.officialName ??
          priority?.culturaDesejada?.officialName
        }
        areaLocation={selectedArea?.name ?? currentTerreno?.nome_propriedade}
        networkStatus={networkStatus}
        onOpenCalendar={() => setStep("area-calendar")}
        onBack={() => setStep("plantations")}
      />
    );
  }

  if (step === "area-calendar") {
    return (
      <AreaCalendarPage
        terrenoId={selectedArea?.terrenoId ?? currentTerreno?.id ?? null}
        areaLocation={selectedArea?.name ?? currentTerreno?.nome_propriedade}
        networkStatus={networkStatus}
        onBack={() => setStep("area-dashboard")}
      />
    );
  }

  if (step === "map-terrain") {
    return (
      <MapTerrainPage
        initialName={draftTerrain?.nome_propriedade ?? ""}
        initialPoints={draftTerrain?.points ?? []}
        onBack={() => {
          setDraftTerrain(null);
          setStep("plantations");
        }}
        onSaveArea={(points, areaHectares, nomePropriedade) => {
          setCurrentTerreno(null);
          setDraftTerrain({
            nome_propriedade: nomePropriedade,
            points,
            coordenadas_poligono: points.map((p) => ({ lat: p.lat, lng: p.lng })),
            area_hectares: areaHectares > 0 ? areaHectares : undefined,
          });
          setSelectedPlan(null);
          setRemoteScenarios(null);
          setStep(1);
        }}
      />
    );
  }

  return (
    <CropHistoryStep
      initialData={cropHistory ?? undefined}
      networkStatus={networkStatus}
      terrenoId={currentTerreno?.id ?? null}
      existingPrioridades={currentTerreno?.prioridades ?? null}
      onTerrenoUpdated={(updated) => setCurrentTerreno(updated)}
      onBack={() => setStep("map-terrain")}
      onContinue={(data) => {
        setCropHistory(data);
        setStep(2);
      }}
    />
  );
}

export default App;

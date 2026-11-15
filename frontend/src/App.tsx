import * as React from "react";
import {
  ArrowRight,
  ChevronLeft,
  Pencil,
  RotateCcw,
  Wifi,
  WifiOff,
} from "lucide-react";
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
import { AreaDashboardPage } from "./pages/AreaDashboardPage";
import { MapTerrainPage } from "./pages/MapTerrainPage";
import {
  PlantationsPage,
  type PlantationArea,
} from "./pages/PlantationsPage";

type OnboardingStep =
  | "plantations"
  | "area-dashboard"
  | "map-terrain"
  | 1
  | 2
  | 3
  | 4
  | "summary"
  | "recommendations";

export function App() {
  const [step, setStep] = React.useState<OnboardingStep>("plantations");
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

  if (step === "summary") {
    const cropHistoryLabel = cropHistory?.naoLembro
      ? "Não lembrado"
      : [
          cropHistory?.ultimoCultivo?.officialName,
          cropHistory?.cultivoAnterior?.officialName,
        ]
          .filter(Boolean)
          .join(" → ") || "Não informado";

    const reviewItems: Array<{
      label: string;
      value: string;
      targetStep: 1 | 2 | 3 | 4;
    }> = [
      {
        label: "Histórico de Cultivos",
        value: cropHistoryLabel,
        targetStep: 1,
      },
      {
        label: "Distribuição Hídrica",
        value:
          waterDistribution?.metodoIrrigacao.title ?? "Não informado",
        targetStep: 2,
      },
      {
        label: "Tipo de Solo",
        value: soilType?.tipoSolo.title ?? "Não informado",
        targetStep: 3,
      },
      {
        label: "Prioridade",
        value: priority?.culturaDesejada
          ? `${priority.prioridade.title} (${priority.culturaDesejada.officialName})`
          : (priority?.prioridade.title ?? "Não informado"),
        targetStep: 4,
      },
    ];

    return (
      <div className="min-h-dvh w-full bg-[#F7F6F0] text-[#1F1C18] md:flex md:items-center md:justify-center md:bg-[#EFECE3] md:p-6">
        <div className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-between bg-[#F7F6F0] px-5 pb-8 pt-6 md:min-h-[680px] md:rounded-3xl md:border md:border-[#E6E4DA] md:px-7 md:py-8 md:shadow-sm">
          <div>
            <header className="flex items-center justify-between gap-4">
              <span className="text-2xl font-extrabold tracking-tight text-[#511D4E]">
                Kultiva
              </span>

              <Badge
                variant={isOnline ? "saved" : "offline"}
                aria-live="polite"
              >
                {isOnline ? (
                  <Wifi className="h-3.5 w-3.5" aria-hidden="true" />
                ) : (
                  <WifiOff className="h-3.5 w-3.5" aria-hidden="true" />
                )}
                <span>{isOnline ? "Salvo" : "Sem internet"}</span>
              </Badge>
            </header>

            <main className="mt-8">
              <h1 className="text-[26px] font-bold leading-tight tracking-tight text-[#511D4E] sm:text-[28px]">
                Confirme sua área
              </h1>
              <p className="mt-1.5 text-sm text-[#6D6960] sm:text-base">
                Revise tudo o que você marcou antes de comparar os caminhos de
                plantio.
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
                      <span>Alterar</span>
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
              <span>Confirmar e comparar</span>
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
                <span>Voltar</span>
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
                <span>Reiniciar</span>
              </Button>
            </div>
          </footer>
        </div>
      </div>
    );
  }

  if (step === "recommendations") {
    const { areaSummary, scenarios } = buildRecommendationsFromOnboarding({
      cropHistory,
      waterDistribution,
      soilType,
      priority,
    });

    return (
      <>
        {selectedPlan && (
          <div
            role="status"
            className="fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-full border border-[#91C494] bg-[#1E3B21] px-4 py-2.5 text-xs font-semibold text-white shadow-lg"
          >
            <span>
              Plano selecionado: {selectedPlan.optionBadge} (
              {selectedPlan.steps.map((s) => s.name).join(" → ")})
            </span>
          </div>
        )}

        <RecommendationsStep
          areaSummary={areaSummary}
          scenarios={scenarios}
          networkStatus={networkStatus}
          onSelectPlan={(scenario) => setSelectedPlan(scenario)}
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
        networkStatus={networkStatus}
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
        onCreateArea={() => setStep("map-terrain")}
        onSelectArea={(area) => {
          setSelectedArea(area);
          setStep("area-dashboard");
        }}
      />
    );
  }

  if (step === "area-dashboard") {
    return (
      <AreaDashboardPage
        areaLocation={selectedArea?.name}
        networkStatus={networkStatus}
        onBack={() => setStep("plantations")}
      />
    );
  }

  if (step === "map-terrain") {
    return (
      <MapTerrainPage
        onBack={() => setStep("plantations")}
        onSaveArea={() => setStep(1)}
      />
    );
  }

  return (
    <CropHistoryStep
      initialData={cropHistory ?? undefined}
      networkStatus={networkStatus}
      onBack={() => setStep("plantations")}
      onContinue={(data) => {
        setCropHistory(data);
        setStep(2);
      }}
    />
  );
}

export default App;

import * as React from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { Sparkles, X } from "lucide-react";
import { Badge } from "./components/ui/badge";
import { CropHistoryStep } from "./features/onboarding/components/CropHistoryStep";
import { WaterDistributionStep } from "./features/onboarding/components/WaterDistributionStep";
import type { CropHistoryData } from "./features/onboarding/types/cropHistory.types";
import type {
  WaterDistributionData,
  WaterDistributionId,
} from "./features/onboarding/types/waterDistribution.types";
import { type MapCoordinate, MapTerrainPage } from "./pages/MapTerrainPage";
import { type PlantationArea, PlantationsPage } from "./pages/PlantationsPage";
import {
  type CoordenadaApi,
  type SimulacaoResponse,
  type TerrenoResponse,
  converterHistoricoParaLista,
  extrairMetodoIrrigacao,
  formatarAreaHectares,
  mapearPrioridadesIrrigacao,
  restaurarHistoricoDoTerreno,
  simularRotacao,
} from "./services/api";

interface OnboardingFlowState {
  selectedArea: PlantationArea | null;
  terrenoId: number | null;
  nomePropriedade: string;
  coordenadasPoligono: CoordenadaApi[];
  prioridades: Record<string, unknown> | null;
  cropHistory: CropHistoryData | null;
  waterMethod: WaterDistributionId | null;
}

const INITIAL_FLOW_STATE: OnboardingFlowState = {
  selectedArea: null,
  terrenoId: null,
  nomePropriedade: "",
  coordenadasPoligono: [],
  prioridades: null,
  cropHistory: null,
  waterMethod: null,
};

const WATER_RISK_LABELS: Record<string, string> = {
  low: "Risco hídrico baixo",
  medium: "Risco hídrico moderado",
  high: "Risco hídrico alto",
};

export function App() {
  const navigate = useNavigate();
  const [flowState, setFlowState] =
    React.useState<OnboardingFlowState>(INITIAL_FLOW_STATE);
  const [lastSimulation, setLastSimulation] =
    React.useState<SimulacaoResponse | null>(null);
  const [simulationError, setSimulationError] = React.useState<string | null>(
    null
  );
  const [isSimulating, setIsSimulating] = React.useState(false);

  const handleStartCreateArea = () => {
    setFlowState(INITIAL_FLOW_STATE);
    setSimulationError(null);
    navigate("/mapear-terreno");
  };

  const handleSelectExistingArea = (area: PlantationArea) => {
    setSimulationError(null);
    setFlowState({
      selectedArea: area,
      terrenoId: area.terrenoId ?? null,
      nomePropriedade: area.name,
      coordenadasPoligono: area.coordenadasPoligono ?? [],
      prioridades: area.prioridades ?? null,
      cropHistory: null,
      waterMethod: extrairMetodoIrrigacao(area.prioridades),
    });
    navigate("/onboarding/historico");
  };

  const handleAreaSaved = (
    points: MapCoordinate[],
    _areaHectares: number,
    createdTerreno?: TerrenoResponse
  ) => {
    const coords =
      createdTerreno?.coordenadas_poligono ??
      points.map((point) => ({ lat: point.lat, lng: point.lng }));

    setFlowState({
      selectedArea: null,
      terrenoId: createdTerreno?.id ?? null,
      nomePropriedade: createdTerreno?.nome_propriedade ?? "Novo Terreno",
      coordenadasPoligono: coords,
      prioridades: createdTerreno?.prioridades ?? null,
      cropHistory: null,
      waterMethod: null,
    });
    navigate("/onboarding/historico");
  };

  const handleTerrenoUpdated = (updated: TerrenoResponse) => {
    setFlowState((prev) => ({
      ...prev,
      terrenoId: updated.id,
      nomePropriedade: updated.nome_propriedade,
      coordenadasPoligono: updated.coordenadas_poligono,
      prioridades: updated.prioridades ?? prev.prioridades,
    }));
  };

  const handleCropHistoryContinue = (data: CropHistoryData) => {
    const historicoLista = converterHistoricoParaLista(data);
    setFlowState((prev) => ({
      ...prev,
      cropHistory: data,
      prioridades: {
        ...(prev.prioridades ?? {}),
        historico_cultivos: historicoLista,
        nao_lembra_historico: data.naoLembro,
      },
    }));
    navigate("/onboarding/agua");
  };

  const handleWaterDistributionContinue = async (
    data: WaterDistributionData
  ) => {
    const metodoId = data.metodoIrrigacao.id;
    const prioridadesAtualizadas = {
      ...(flowState.prioridades ?? {}),
      ...mapearPrioridadesIrrigacao(metodoId, flowState.cropHistory),
    };
    const historicoLista = converterHistoricoParaLista(flowState.cropHistory);

    setFlowState((prev) => ({
      ...prev,
      waterMethod: metodoId,
      prioridades: prioridadesAtualizadas,
    }));

    setIsSimulating(true);
    setSimulationError(null);
    try {
      const resultado = await simularRotacao({
        terreno_id: flowState.terrenoId ?? undefined,
        nome_propriedade: flowState.nomePropriedade || undefined,
        coordenadas_poligono:
          flowState.terrenoId === null &&
          flowState.coordenadasPoligono.length >= 3
            ? flowState.coordenadasPoligono
            : undefined,
        historico_cultivos: historicoLista,
        prioridades: prioridadesAtualizadas,
      });
      setLastSimulation(resultado);
    } catch (error) {
      setSimulationError(
        error instanceof Error
          ? error.message
          : "Dados salvos localmente, mas não foi possível executar a simulação na API."
      );
    } finally {
      setIsSimulating(false);
      navigate("/");
    }
  };

  const handleAreaDeleted = (area: PlantationArea) => {
    if (
      lastSimulation &&
      area.terrenoId !== undefined &&
      lastSimulation.terreno_id === area.terrenoId
    ) {
      setLastSimulation(null);
    }
  };

  const simulationBanner = React.useMemo(() => {
    if (simulationError) {
      return (
        <div
          role="alert"
          className="rounded-2xl border border-[#C42311]/30 bg-[#C42311]/10 px-4 py-3 text-xs text-[#C42311]"
        >
          <div className="flex items-start justify-between gap-2">
            <p className="font-medium">{simulationError}</p>
            <button
              type="button"
              onClick={() => setSimulationError(null)}
              aria-label="Fechar aviso da simulação"
              className="shrink-0 rounded-lg p-1 hover:bg-[#C42311]/10"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>
        </div>
      );
    }

    if (!lastSimulation) {
      return null;
    }

    const areaHaRaw = lastSimulation.metricas_geoespaciais?.area_hectares;
    const areaHa = typeof areaHaRaw === "number" ? areaHaRaw : null;

    return (
      <section
        aria-label="Resultado da última simulação"
        className="rounded-2xl border border-[#CAD17A] bg-white p-4 shadow-sm"
      >
        <div className="flex items-start justify-between gap-2">
          <div>
            <Badge variant="saved">
              <Sparkles className="h-3 w-3" aria-hidden="true" />
              <span>Simulação concluída</span>
            </Badge>
            <h2 className="mt-2 text-[16px] font-bold text-[#511D4E]">
              {lastSimulation.nome_propriedade}
            </h2>
            {areaHa !== null && (
              <p className="text-xs text-[#6D6960]">
                Área analisada: {formatarAreaHectares(areaHa)}
              </p>
            )}
          </div>

          <button
            type="button"
            onClick={() => setLastSimulation(null)}
            aria-label="Fechar resumo da simulação"
            className="flex h-8 w-8 items-center justify-center rounded-xl text-[#6D6960] hover:bg-[#EFECE3]"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="mt-3 space-y-2">
          {lastSimulation.rotacoes_sugeridas.slice(0, 3).map((item) => {
            const pct = Math.round(item.viability * 100);
            const riskLabel =
              WATER_RISK_LABELS[item.water_risk.toLowerCase()] ??
              `Risco: ${item.water_risk}`;

            return (
              <div
                key={item.strategy}
                className="rounded-xl border border-[#E6E4DA] bg-[#F7F6F0] px-3 py-2.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[13px] font-bold text-[#1F1C18]">
                    {item.strategy}
                  </span>
                  <span className="shrink-0 text-[12px] font-bold text-[#511D4E]">
                    {pct}% viável
                  </span>
                </div>
                <p className="mt-0.5 text-[11px] font-medium text-[#6D6960]">
                  {riskLabel}
                  {item.benefits ? ` • ${item.benefits}` : ""}
                </p>
              </div>
            );
          })}
        </div>

        <p className="mt-3 text-[12px] leading-relaxed text-[#6D6960]">
          {lastSimulation.explicacao_ia}
        </p>
      </section>
    );
  }, [lastSimulation, simulationError]);

  return (
    <Routes>
      <Route
        path="/"
        element={
          <PlantationsPage
            onCreateArea={handleStartCreateArea}
            onSelectArea={handleSelectExistingArea}
            onAreaDeleted={handleAreaDeleted}
            simulationBanner={simulationBanner}
          />
        }
      />

      <Route
        path="/mapear-terreno"
        element={
          <MapTerrainPage
            onBack={() => navigate("/")}
            onSaveArea={handleAreaSaved}
          />
        }
      />

      <Route
        path="/onboarding/historico"
        element={
          <CropHistoryStep
            key={`history-${flowState.terrenoId ?? "draft"}`}
            terrenoId={flowState.terrenoId}
            existingPrioridades={flowState.prioridades}
            initialData={
              flowState.cropHistory ??
              restaurarHistoricoDoTerreno(flowState.prioridades)
            }
            onTerrenoUpdated={handleTerrenoUpdated}
            onBack={() =>
              navigate(flowState.selectedArea ? "/" : "/mapear-terreno")
            }
            onContinue={handleCropHistoryContinue}
          />
        }
      />

      <Route
        path="/onboarding/agua"
        element={
          <WaterDistributionStep
            key={`water-${flowState.terrenoId ?? "draft"}`}
            terrenoId={flowState.terrenoId}
            existingPrioridades={flowState.prioridades}
            cropHistory={flowState.cropHistory}
            initialValue={
              flowState.waterMethod ??
              extrairMetodoIrrigacao(flowState.prioridades)
            }
            isSubmitting={isSimulating}
            onTerrenoUpdated={handleTerrenoUpdated}
            onBack={() => navigate("/onboarding/historico")}
            onContinue={handleWaterDistributionContinue}
          />
        }
      />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;

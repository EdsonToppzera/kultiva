import * as React from "react";
import {
  AlertTriangle,
  Bug,
  ChevronLeft,
  Clock,
  Droplets,
  MapPin,
  RefreshCw,
  ShieldAlert,
  Wifi,
  WifiOff,
} from "lucide-react";
import { Badge } from "../../../components/ui/badge";
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
import type {
  CropHistoryData,
  CropOption,
  NetworkSyncStatus,
} from "../../onboarding/types/cropHistory.types";
import type { PriorityData } from "../../onboarding/types/priority.types";
import type { SoilTypeData } from "../../onboarding/types/soilType.types";
import type { WaterDistributionData } from "../../onboarding/types/waterDistribution.types";
import type {
  AreaSummaryInfo,
  RotationAlternativeCrop,
  RotationScenario,
} from "../types/recommendations.types";
import { RecommendationCard } from "./RecommendationCard";

export const COVER_CROP_ALTERNATIVES: RotationAlternativeCrop[] = [
  {
    id: "crotalaria",
    name: "Crotalária",
    reason: "Fixa nitrogênio e ajuda a controlar nematoides.",
    imageUrl: null,
  },
  {
    id: "feijao-de-porco",
    name: "Feijão-de-porco",
    reason: "Cobre rápido a terra e segura a umidade na seca.",
    imageUrl: null,
  },
  {
    id: "milheto",
    name: "Milheto",
    reason: "Rústico na falta de chuva e gera muita palhada.",
    imageUrl: null,
  },
  {
    id: "guandu",
    name: "Guandu",
    reason: "Raiz profunda que descompacta o solo duro.",
    imageUrl: null,
  },
];

export const DEFAULT_AREA_SUMMARY: AreaSummaryInfo = {
  areaName: "Área 1",
  lastCropName: "Milho",
  tagsLine: "Chuva · Barro · Recuperar a terra",
};

export const DEFAULT_RECOMMENDATIONS: RotationScenario[] = [
  {
    id: "opcao-1-feijao-porco",
    optionBadge: "1ª Opção",
    focusTag: "FOCO NO SOLO",
    variant: "recommended",
    steps: [
      {
        id: "step-milho",
        name: "Milho",
        statusLabel: "Já colhido",
        imageUrl: "/images/crops/milho.jpg",
      },
      {
        id: "step-feijao-porco",
        name: "Feijão-de-porco",
        statusLabel: "A seguir",
        imageUrl: null,
        alternatives: COVER_CROP_ALTERNATIVES,
      },
      {
        id: "step-descanso",
        name: "Descanso",
        statusLabel: "Depois",
        isRest: true,
      },
    ],
    aiJustification:
      "Com menos chuva no período, cobrir a terra ajuda a guardar a umidade.",
    pros: ["Ajuda a proteger e nutrir a terra."],
    cons: ["Não gera uma colheita para venda."],
    technicalDetails: {
      cycleDurationDays: "90 a 110 dias",
      waterDemandMm: "280 mm (Baixa)",
      nasaClimateNote:
        "Dados de precipitação e umidade do solo (NASA SMAP/POWER) indicam janela mais seca nos próximos 60 dias; a palhada reduz evaporação em até 35%.",
      npkTable: [
        {
          nutrient: "Nitrogênio (N)",
          requirementLevel: "Baixo",
          impact: "Fixa até 120 kg/ha no solo",
        },
        {
          nutrient: "Fósforo (P)",
          requirementLevel: "Médio",
          impact: "Melhora enraizamento futuro",
        },
        {
          nutrient: "Potássio (K)",
          requirementLevel: "Baixo",
          impact: "Recicla nutrientes das camadas fundas",
        },
      ],
      agrofitAlerts: [
        "Quebra o ciclo da lagarta-do-cartucho após o milho.",
        "Reduz pressão de nematoides-das-galhas antes do próximo plantio.",
      ],
    },
  },
  {
    id: "opcao-2-feijao-corda",
    optionBadge: "2ª Opção",
    focusTag: "FOCO NO SOLO",
    variant: "standard",
    steps: [
      {
        id: "step-milho",
        name: "Milho",
        statusLabel: "Já colhido",
        imageUrl: "/images/crops/milho.jpg",
      },
      {
        id: "step-feijao-corda",
        name: "Feijão-de-corda",
        statusLabel: "A seguir",
        imageUrl: "/images/crops/feijao-caupi.jpg",
      },
      {
        id: "step-descanso",
        name: "Descanso",
        statusLabel: "Depois",
        isRest: true,
      },
    ],
    aiJustification:
      "O feijão-de-corda lida com períodos secos, mas precisa de água para começar.",
    pros: ["Pode trazer retorno em um ciclo curto."],
    cons: ["Precisa de chuva na época certa."],
    technicalDetails: {
      cycleDurationDays: "65 a 80 dias",
      waterDemandMm: "350 mm (Moderada)",
      nasaClimateNote:
        "A germinação e o florescimento são sensíveis a veranicos maiores que 10 dias. Acompanhe os avisos de chuva antes da semeadura.",
      npkTable: [
        {
          nutrient: "Nitrogênio (N)",
          requirementLevel: "Baixo",
          impact: "Fixação simbiótica parcial",
        },
        {
          nutrient: "Fósforo (P)",
          requirementLevel: "Médio",
          impact: "Essencial na formação de vagens",
        },
        {
          nutrient: "Potássio (K)",
          requirementLevel: "Médio",
          impact: "Aumenta tolerância ao calor",
        },
      ],
      agrofitAlerts: [
        "Monitorar pulgão-preto e vaquinha nos primeiros 25 dias (AGROFIT).",
        "Evitar plantio muito adensado em solo de barro encharcado.",
      ],
    },
  },
  {
    id: "opcao-3-mandioca",
    optionBadge: "3ª Opção",
    focusTag: "FOCO NO SOLO",
    variant: "standard",
    steps: [
      {
        id: "step-milho",
        name: "Milho",
        statusLabel: "Já colhido",
        imageUrl: "/images/crops/milho.jpg",
      },
      {
        id: "step-mandioca",
        name: "Mandioca",
        statusLabel: "A seguir",
        imageUrl: "/images/crops/mandioca.jpg",
      },
      {
        id: "step-descanso",
        name: "Descanso",
        statusLabel: "Depois",
        isRest: true,
      },
    ],
    aiJustification:
      "Depois de pegar, a mandioca tolera períodos com menos chuva.",
    pros: ["Alimento para a família e os animais."],
    cons: ["Ocupa a área por mais tempo."],
    technicalDetails: {
      cycleDurationDays: "240 a 360 dias",
      waterDemandMm: "420 mm ao longo do ciclo",
      nasaClimateNote:
        "Alta rusticidade após 60 dias do pegamento das manivas. Evite baixar drenagem em períodos de chuva intensa.",
      npkTable: [
        {
          nutrient: "Nitrogênio (N)",
          requirementLevel: "Baixo",
          impact: "Exigência baixa na fase inicial",
        },
        {
          nutrient: "Fósforo (P)",
          requirementLevel: "Baixo",
          impact: "Aproveita fósforo residual",
        },
        {
          nutrient: "Potássio (K)",
          requirementLevel: "Alto",
          impact: "Fundamental para enchimento das raízes",
        },
      ],
      agrofitAlerts: [
        "Atenção ao mandarová e ácaro-verde em períodos secos prolongados.",
        "Usar manivas sadias para evitar podridão radicular em barro úmido.",
      ],
    },
  },
];

const WATER_SENSITIVE_CROPS = new Set([
  "feijao-carioca",
  "abobora",
  "batata-doce",
  "milho",
]);

/**
 * Constrói o resumo global e os cenários de recomendação a partir das escolhas do onboarding.
 */
export function buildRecommendationsFromOnboarding({
  cropHistory,
  waterDistribution,
  soilType,
  priority,
}: {
  cropHistory: CropHistoryData | null;
  waterDistribution: WaterDistributionData | null;
  soilType: SoilTypeData | null;
  priority: PriorityData | null;
}): {
  areaSummary: AreaSummaryInfo;
  scenarios: RotationScenario[];
} {
  const lastCrop = cropHistory?.ultimoCultivo ?? null;
  const lastCropName = lastCrop?.officialName ?? "Sem histórico";
  const waterTitle = waterDistribution?.metodoIrrigacao.title ?? "Chuva";
  const soilTitle = soilType?.tipoSolo.title ?? "Barro";
  const priorityTitle = priority?.prioridade.title ?? "Recuperar a terra";

  const areaSummary: AreaSummaryInfo = {
    areaName: "Área 1",
    lastCropName,
    tagsLine: `${waterTitle} · ${soilTitle} · ${priorityTitle}`,
  };

  const firstStep = {
    id: `hist-${lastCrop?.id ?? "area"}`,
    name: lastCrop?.officialName ?? "Área atual",
    statusLabel: lastCrop ? "Já colhido" : "Situação inicial",
    imageUrl: lastCrop?.imageUrl ?? null,
  };

  const baseScenarios = DEFAULT_RECOMMENDATIONS.map((scenario) => ({
    ...scenario,
    focusTag: priorityTitle,
    steps: [firstStep, ...scenario.steps.slice(1)],
  }));

  const targetCrop: CropOption | null = priority?.culturaDesejada ?? null;
  if (
    priority?.prioridade.id === "plantar_especifico" &&
    targetCrop !== null
  ) {
    const isDryRisk =
      waterDistribution?.metodoIrrigacao.id === "chuva" &&
      (WATER_SENSITIVE_CROPS.has(targetCrop.id) ||
        soilType?.tipoSolo.id === "areia" ||
        soilType?.tipoSolo.id === "cascalho");

    if (isDryRisk) {
      const riskScenario: RotationScenario = {
        id: `risco-${targetCrop.id}`,
        optionBadge: "Risco Altíssimo",
        focusTag: "ALERTA DE INVIABILIDADE",
        variant: "risk",
        steps: [
          firstStep,
          {
            id: `target-${targetCrop.id}`,
            name: targetCrop.officialName,
            statusLabel: "Alto risco",
            imageUrl: targetCrop.imageUrl ?? null,
          },
          {
            id: "step-descanso-risco",
            name: "Descanso",
            statusLabel: "Recuperação",
            isRest: true,
          },
        ],
        aiJustification:
          "Risco altíssimo: A NASA prevê seca severa, e esta cultura exige irrigação constante.",
        pros: [`Atende ao desejo de plantar ${targetCrop.officialName}.`],
        cons: [
          `Sem irrigação (${waterTitle}) em solo de ${soilTitle.toLowerCase()}, há alto risco de perda.`,
        ],
        ctaLabel: "Escolher mesmo assim",
        technicalDetails: {
          cycleDurationDays: "80 a 120 dias",
          waterDemandMm: "480 a 600 mm (Alta)",
          nasaClimateNote:
            "As séries históricas da NASA indicam déficit hídrico crítico para cultivo em sequeiro nesta janela. Recomenda-se cobertura morta prévia ou irrigação suplementar.",
          npkTable: [
            {
              nutrient: "Nitrogênio (N)",
              requirementLevel: "Alto",
              impact: "Perda por estresse hídrico",
            },
            {
              nutrient: "Fósforo (P)",
              requirementLevel: "Médio",
              impact: "Absorção reduzida sem umidade",
            },
            {
              nutrient: "Potássio (K)",
              requirementLevel: "Alto",
              impact: "Crítico para regulação de água",
            },
          ],
          agrofitAlerts: [
            "Plantas sob estresse hídrico ficam mais vulneráveis a ácaros e mosca-branca (AGROFIT).",
            "Considere preparar o solo com adubação verde antes de arriscar o plantio principal.",
          ],
        },
      };

      return {
        areaSummary,
        scenarios: [riskScenario, baseScenarios[0], baseScenarios[1]],
      };
    }

    const preparedScenario: RotationScenario = {
      id: `plano-preparo-${targetCrop.id}`,
      optionBadge: "1ª Opção",
      focusTag: "PREPARO PARA SUA CULTURA",
      variant: "recommended",
      steps: [
        firstStep,
        {
          id: "step-crotalaria-preparo",
          name: "Crotalária",
          statusLabel: "Preparo",
          imageUrl: null,
          alternatives: COVER_CROP_ALTERNATIVES,
        },
        {
          id: `target-${targetCrop.id}`,
          name: targetCrop.officialName,
          statusLabel: "Plantio alvo",
          imageUrl: targetCrop.imageUrl ?? null,
        },
        {
          id: "step-descanso-final",
          name: "Descanso",
          statusLabel: "Depois",
          isRest: true,
        },
      ],
      aiJustification: `Preparar a terra com cobertura verde protege a umidade para receber ${targetCrop.officialName}.`,
      pros: [
        `Prepara o solo para colher ${targetCrop.officialName} com mais vigor.`,
        "Aumenta a proteção contra ervas daninhas.",
      ],
      cons: ["Adiciona um ciclo rápido de preparo antes do plantio final."],
      technicalDetails: {
        cycleDurationDays: "150 a 190 dias (ciclo completo)",
        waterDemandMm: "360 mm",
        nasaClimateNote:
          "A combinação de cobertura prévia com o manejo hídrico atual mantém a temperatura do solo mais amena no pegamento.",
        npkTable: [
          {
            nutrient: "Nitrogênio (N)",
            requirementLevel: "Médio",
            impact: "Suprido pela cobertura anterior",
          },
          {
            nutrient: "Fósforo (P)",
            requirementLevel: "Médio",
            impact: "Reforço na linha de plantio",
          },
          {
            nutrient: "Potássio (K)",
            requirementLevel: "Médio",
            impact: "Mantém qualidade da colheita",
          },
        ],
        agrofitAlerts: [
          "Crotalária auxilia no controle natural de nematoides antes da cultura alvo.",
        ],
      },
    };

    return {
      areaSummary,
      scenarios: [
        preparedScenario,
        { ...baseScenarios[0], optionBadge: "2ª Opção", variant: "standard" },
        { ...baseScenarios[1], optionBadge: "3ª Opção", variant: "standard" },
      ],
    };
  }

  return { areaSummary, scenarios: baseScenarios };
}

const NETWORK_BADGE_CONFIG: Record<
  NetworkSyncStatus,
  {
    label: string;
    variant: "saved" | "offline" | "outline";
    icon: React.ComponentType<{ className?: string }>;
  }
> = {
  salvo: { label: "Salvo", variant: "saved", icon: Wifi },
  sincronizando: { label: "Salvando", variant: "outline", icon: RefreshCw },
  offline: { label: "Sem internet", variant: "offline", icon: WifiOff },
};

export interface RecommendationsStepProps {
  propertyLocation?: string;
  areaSummary?: AreaSummaryInfo;
  scenarios?: RotationScenario[];
  isLoading?: boolean;
  isSubmittingPlan?: boolean;
  networkStatus?: NetworkSyncStatus;
  onSelectPlan?: (scenario: RotationScenario) => void;
  onBack?: () => void;
}

/**
 * Tela Final do Onboarding — Recomendações de Rotação.
 * Renderiza trilhas dinâmicas (2 a 5 passos), variante crítica de risco/inviabilidade e Drawer técnico.
 */
export function RecommendationsStep({
  propertyLocation = "Sítio Boa Esperança - Área 1",
  scenarios = DEFAULT_RECOMMENDATIONS,
  isLoading = false,
  isSubmittingPlan = false,
  networkStatus,
  onSelectPlan,
  onBack,
}: RecommendationsStepProps) {
  const [isOnline, setIsOnline] = React.useState<boolean>(() =>
    typeof navigator !== "undefined" ? navigator.onLine : true
  );
  const [localScenarios, setLocalScenarios] =
    React.useState<RotationScenario[]>(scenarios);
  const [activeScenarioId, setActiveScenarioId] = React.useState<string | null>(
    null
  );

  React.useEffect(() => {
    setLocalScenarios(scenarios);
  }, [scenarios]);

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

  const resolvedNetworkStatus: NetworkSyncStatus =
    networkStatus ?? (isOnline ? "salvo" : "offline");

  const badgeInfo = NETWORK_BADGE_CONFIG[resolvedNetworkStatus];
  const NetworkIcon = badgeInfo.icon;

  return (
    <div className="min-h-dvh w-full bg-[#F7F6F0] text-[#1F1C18]">
      <div className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-between px-5 pb-10 pt-6 md:max-w-2xl lg:max-w-6xl lg:px-8 lg:py-10">
        <div>
          {/* Header */}
          <header className="flex items-center justify-between gap-4">
            <span className="text-2xl font-extrabold tracking-tight text-[#511D4E]">
              Kultiva
            </span>

            <Badge variant={badgeInfo.variant} aria-live="polite">
              <NetworkIcon
                className={cn(
                  "h-3.5 w-3.5",
                  resolvedNetworkStatus === "sincronizando" && "animate-spin"
                )}
                aria-hidden="true"
              />
              <span>{badgeInfo.label}</span>
            </Badge>
          </header>

          {/* Localização da propriedade */}
          <div className="mt-3 flex items-center gap-1.5 text-xs font-medium text-[#6D6960] sm:text-sm">
            <MapPin className="h-4 w-4 shrink-0 text-[#511D4E]" aria-hidden="true" />
            <span>{propertyLocation}</span>
          </div>

          {/* Títulos */}
          <section className="mt-4">
            <h1 className="text-[28px] font-bold leading-tight tracking-tight text-[#511D4E] sm:text-3xl">
              Recomendações
            </h1>
            <p className="mt-1.5 text-sm text-[#6D6960] sm:text-base">
              Essas são as recomendações com base nas informações obtidas.
            </p>
          </section>

          {/* Grid Responsivo de Cartões */}
          <main className="mt-6">
            {isLoading ? (
              <div className="flex items-center justify-center gap-3 rounded-3xl border border-[#E6E4DA] bg-white px-6 py-12 text-sm font-semibold text-[#511D4E]">
                <RefreshCw className="h-5 w-5 animate-spin" aria-hidden="true" />
                <span>Calculando recomendações para a sua área...</span>
              </div>
            ) : (
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
            <span>Voltar</span>
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
                  Detalhes Técnicos da Rotação
                </DrawerTitle>
                <DrawerDescription>
                  Cruzamento de clima (NASA) e recomendações fitossanitárias
                  (AGROFIT).
                </DrawerDescription>
              </DrawerHeader>

              {/* Indicadores rápidos */}
              <div className="mt-4 grid grid-cols-2 gap-2.5">
                <div className="rounded-2xl border border-[#E6E4DA] bg-white p-3">
                  <div className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-[#6D6960]">
                    <Clock className="h-3.5 w-3.5 text-[#511D4E]" aria-hidden="true" />
                    <span>Ciclo estimado</span>
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
                    <span>Água necessária</span>
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
                  <span>Análise Climática (NASA)</span>
                </div>
                <p>{activeScenario.technicalDetails.nasaClimateNote}</p>
              </div>

              {/* Tabela NPK */}
              <div className="mt-4">
                <h3 className="text-xs font-bold uppercase tracking-wider text-[#6D6960]">
                  Necessidades e Balanço de NPK
                </h3>
                <div className="mt-2 overflow-hidden rounded-2xl border border-[#E6E4DA] bg-white">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-[#E6E4DA] bg-[#F7F6F0] text-[#6D6960]">
                      <tr>
                        <th className="px-3 py-2 font-semibold">Nutriente</th>
                        <th className="px-3 py-2 font-semibold">Exigência</th>
                        <th className="px-3 py-2 font-semibold">Efeito</th>
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
                                row.requirementLevel === "Alto" &&
                                  "bg-[#C42311]/15 text-[#8E180B]",
                                row.requirementLevel === "Médio" &&
                                  "bg-[#FCF59B] text-[#4A3B12]",
                                row.requirementLevel === "Baixo" &&
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
                  <span>Histórico e Alertas de Pragas (AGROFIT)</span>
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
                    Fechar detalhes
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


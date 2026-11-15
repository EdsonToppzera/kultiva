import * as React from "react";
import {
  ArrowLeftRight,
  Bell,
  Bug,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  CloudRain,
  FileText,
  Info,
  Leaf,
  MapPin,
  Moon,
  Pause,
  Play,
  RefreshCw,
  ShieldAlert,
  Square,
  Sun,
  Sunrise,
  Sunset,
  TrendingUp,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from "../components/ui/drawer";
import type { NetworkSyncStatus } from "../features/onboarding/types/cropHistory.types";
import { cn } from "../lib/utils";
import {
  adaptAtividadesToCropProgress,
  adaptAtividadesToDashboardItems,
  adaptRelatorioAndAlertasToWeather,
  mapFieldReportToAlertaPayload,
} from "../services/adapters";
import {
  type AlertaClimaticoResponse,
  type RelatorioAdaptacaoResponse,
  concluirAtividade,
  dispararAlertaGatilho,
  listarAlertas,
  listarAtividades,
  marcarAlertaComoLido,
  monitorarClimaSobDemanda,
  obterRelatorioTerreno,
} from "../services/api";

export type ActivityPeriodId =
  | "manha"
  | "meio-dia"
  | "tarde"
  | "noite"
  | "qualquer-momento";

export interface AreaActivityItem {
  id: string;
  backendId?: number;
  period: ActivityPeriodId;
  periodLabel?: string;
  title: string;
  description: string;
  completed?: boolean;
  paused?: boolean;
  pausedReason?: string;
}

export interface AreaWeatherSummary {
  headline: string;
  details: string;
  weatherNotice?: string;
  sourceLabel?: string;
}

export interface AreaCropProgress {
  cropName: string;
  dayLabel: string;
}

export type FieldReportOptionId =
  | "choveu_nao_previsto"
  | "nao_choveu_esperado"
  | "encontrei_praga";

export interface FieldReportOption {
  id: FieldReportOptionId;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

export interface AreaDashboardPageProps {
  terrenoId?: number | null;
  cropNameFallback?: string;
  areaLocation?: string;
  dateLabel?: string;
  weather?: AreaWeatherSummary;
  cropProgress?: AreaCropProgress;
  activities?: AreaActivityItem[];
  networkStatus?: NetworkSyncStatus;
  isSimulationMode?: boolean;
  simulatedPlanLabel?: string | null;
  simulatedRelatorio?: RelatorioAdaptacaoResponse | null;
  simulatedAlertas?: AlertaClimaticoResponse[] | null;
  onStartSimulation?: () => void;
  onFinishSimulation?: () => void;
  onOpenCalendar?: () => void;
  onSubmitReport?: (reportId: FieldReportOptionId) => void;
  onBack?: () => void;
}

const PERIOD_CONFIG: Record<
  ActivityPeriodId,
  {
    defaultLabel: string;
    icon: React.ComponentType<{ className?: string }>;
  }
> = {
  manha: { defaultLabel: "Manhã", icon: Sunrise },
  "meio-dia": { defaultLabel: "Meio-dia", icon: Sun },
  tarde: { defaultLabel: "Tarde", icon: Sunset },
  noite: { defaultLabel: "Noite", icon: Moon },
  "qualquer-momento": { defaultLabel: "Qualquer momento", icon: Clock },
};

const PERIOD_ORDER: ActivityPeriodId[] = [
  "manha",
  "meio-dia",
  "tarde",
  "noite",
  "qualquer-momento",
];

const DEFAULT_WEATHER: AreaWeatherSummary = {
  headline: "Chuva no fim da tarde",
  details: "24°–29° · Chance de chuva: 80%",
  weatherNotice: "A rega de hoje foi pausada.",
};

const DEFAULT_CROP_PROGRESS: AreaCropProgress = {
  cropName: "Feijão-de-porco",
  dayLabel: "Dia 12",
};

const DEFAULT_ACTIVITIES: AreaActivityItem[] = [
  {
    id: "act-1",
    period: "manha",
    periodLabel: "Manhã cedo",
    title: "Conferir a umidade da terra",
    description: "Veja a terra perto da raiz.",
  },
  {
    id: "act-2",
    period: "manha",
    periodLabel: "Manhã cedo",
    title: "Olhar as folhas novas",
    description: "Procure manchas ou sinais de pragas.",
  },
  {
    id: "act-3",
    period: "tarde",
    periodLabel: "Fim de tarde",
    title: "Irrigar a área",
    description: "Rega programada para o fim do dia.",
    paused: true,
    pausedReason: "Pausado: chuva prevista para hoje.",
  },
  {
    id: "act-4",
    period: "qualquer-momento",
    periodLabel: "Qualquer momento",
    title: "Conferir a cobertura do solo",
    description: "Cubra os pontos de terra exposta.",
  },
];

const REPORT_OPTIONS: FieldReportOption[] = [
  {
    id: "choveu_nao_previsto",
    label: "Choveu e não estava previsto",
    icon: CloudRain,
  },
  {
    id: "nao_choveu_esperado",
    label: "Não choveu como o esperado",
    icon: Sun,
  },
  {
    id: "encontrei_praga",
    label: "Encontrei uma praga",
    icon: Bug,
  },
];

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

export function AreaDashboardPage({
  terrenoId,
  cropNameFallback,
  areaLocation = "Sítio Boa Esperança · Área 1",
  dateLabel,
  weather = DEFAULT_WEATHER,
  cropProgress = DEFAULT_CROP_PROGRESS,
  activities = DEFAULT_ACTIVITIES,
  networkStatus,
  isSimulationMode = false,
  simulatedPlanLabel = null,
  simulatedRelatorio = null,
  simulatedAlertas = null,
  onStartSimulation,
  onFinishSimulation,
  onOpenCalendar,
  onSubmitReport,
  onBack,
}: AreaDashboardPageProps) {
  const todayIso = React.useMemo(() => new Date().toISOString().slice(0, 10), []);
  const resolvedDateLabel = React.useMemo(() => {
    if (dateLabel) return dateLabel;
    return new Date().toLocaleDateString("pt-BR", {
      weekday: "long",
      day: "numeric",
      month: "long",
    });
  }, [dateLabel]);

  const [isOnline, setIsOnline] = React.useState<boolean>(() =>
    typeof navigator !== "undefined" ? navigator.onLine : true
  );
  const [reportDrawerOpen, setReportDrawerOpen] = React.useState(false);
  const [healthDrawerOpen, setHealthDrawerOpen] = React.useState(false);
  const [selectedReport, setSelectedReport] =
    React.useState<FieldReportOptionId>("choveu_nao_previsto");
  const [reportSavedNotice, setReportSavedNotice] = React.useState(false);
  const [liveWeather, setLiveWeather] =
    React.useState<AreaWeatherSummary | null>(null);
  const [liveCropProgress, setLiveCropProgress] =
    React.useState<AreaCropProgress | null>(null);
  const [liveActivities, setLiveActivities] = React.useState<
    AreaActivityItem[] | null
  >(null);
  const [liveRelatorio, setLiveRelatorio] =
    React.useState<RelatorioAdaptacaoResponse | null>(null);
  const [liveAlertas, setLiveAlertas] = React.useState<
    AlertaClimaticoResponse[] | null
  >(null);
  const [simWeatherOverride, setSimWeatherOverride] =
    React.useState<AreaWeatherSummary | null>(null);
  const [simActivitiesOverride, setSimActivitiesOverride] = React.useState<
    AreaActivityItem[] | null
  >(null);
  const [simAlertasOverride, setSimAlertasOverride] = React.useState<
    AlertaClimaticoResponse[] | null
  >(null);
  const [isLoadingDashboard, setIsLoadingDashboard] = React.useState(false);
  const [isSubmittingReport, setIsSubmittingReport] = React.useState(false);
  const [isTriggeringClimateCheck, setIsTriggeringClimateCheck] =
    React.useState(false);
  const [climateProfileTest, setClimateProfileTest] = React.useState<
    "seca" | "chuva_extrema" | "onda_de_calor"
  >("seca");

  const loadDashboardData = React.useCallback(async () => {
    if (isSimulationMode || terrenoId == null) {
      setLiveWeather(null);
      setLiveCropProgress(null);
      setLiveActivities(null);
      setLiveRelatorio(null);
      setLiveAlertas(null);
      return;
    }
    setIsLoadingDashboard(true);
    try {
      const [atividadesRes, alertasRes, relatorioRes] = await Promise.allSettled([
        listarAtividades({ terreno_id: terrenoId }),
        listarAlertas({ terreno_id: terrenoId }),
        obterRelatorioTerreno(terrenoId),
      ]);

      const atividadesData =
        atividadesRes.status === "fulfilled" ? atividadesRes.value : [];
      const alertasData =
        alertasRes.status === "fulfilled" ? alertasRes.value : [];
      const relatorioData =
        relatorioRes.status === "fulfilled" ? relatorioRes.value : null;

      setLiveAlertas(alertasData);
      setLiveRelatorio(relatorioData);

      if (atividadesRes.status === "fulfilled") {
        setLiveActivities(
          adaptAtividadesToDashboardItems(atividadesData, todayIso)
        );
        setLiveCropProgress(
          adaptAtividadesToCropProgress(
            atividadesData,
            todayIso,
            cropNameFallback
          )
        );
      }

      if (relatorioData || alertasData.length > 0) {
        const unreadAlerts = alertasData.filter((a) => !a.lido);
        setLiveWeather(
          adaptRelatorioAndAlertasToWeather(
            relatorioData,
            unreadAlerts.length > 0 ? unreadAlerts : alertasData
          )
        );
      } else {
        setLiveWeather(null);
      }
    } finally {
      setIsLoadingDashboard(false);
    }
  }, [terrenoId, todayIso, cropNameFallback, isSimulationMode]);

  React.useEffect(() => {
    if (isSimulationMode) {
      setSimWeatherOverride(weather);
      setSimActivitiesOverride(activities);
      setSimAlertasOverride(simulatedAlertas ?? []);
    } else {
      setSimWeatherOverride(null);
      setSimActivitiesOverride(null);
      setSimAlertasOverride(null);
    }
  }, [isSimulationMode, weather, activities, simulatedAlertas]);

  React.useEffect(() => {
    void loadDashboardData();
  }, [loadDashboardData]);

  const effectiveWeather = isSimulationMode
    ? (simWeatherOverride ?? weather)
    : (liveWeather ?? weather);
  const effectiveCropProgress = isSimulationMode
    ? cropProgress
    : (liveCropProgress ?? cropProgress);
  const effectiveActivities = isSimulationMode
    ? (simActivitiesOverride ?? activities)
    : (liveActivities !== null ? liveActivities : activities);
  const effectiveRelatorio = isSimulationMode
    ? simulatedRelatorio
    : liveRelatorio;
  const effectiveAlertas = isSimulationMode
    ? (simAlertasOverride ?? simulatedAlertas ?? [])
    : (liveAlertas ?? []);
  const unreadAlertsCount = effectiveAlertas.filter((a) => !a.lido).length;

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

  const effectiveStatus: NetworkSyncStatus =
    networkStatus ?? (isOnline ? "salvo" : "offline");
  const badgeConfig = NETWORK_BADGE_CONFIG[effectiveStatus];
  const StatusIcon = badgeConfig.icon;

  const groupedActivities = React.useMemo(() => {
    return PERIOD_ORDER.map((period) => {
      const items = effectiveActivities.filter((item) => item.period === period);
      if (items.length === 0) return null;
      const periodLabel =
        items[0].periodLabel ?? PERIOD_CONFIG[period].defaultLabel;
      return {
        period,
        label: periodLabel,
        Icon: PERIOD_CONFIG[period].icon,
        items,
      };
    }).filter((group): group is NonNullable<typeof group> => group !== null);
  }, [effectiveActivities]);

  const handleToggleActivity = async (item: AreaActivityItem) => {
    const nextCompleted = !item.completed;

    if (isSimulationMode) {
      setSimActivitiesOverride((prev) =>
        (prev ?? activities).map((act) =>
          act.id === item.id ? { ...act, completed: nextCompleted } : act
        )
      );
      return;
    }

    if (item.backendId == null) return;
    setLiveActivities((prev) =>
      prev
        ? prev.map((act) =>
            act.id === item.id ? { ...act, completed: nextCompleted } : act
          )
        : prev
    );
    try {
      await concluirAtividade(item.backendId, { concluida: nextCompleted });
    } catch {
      setLiveActivities((prev) =>
        prev
          ? prev.map((act) =>
              act.id === item.id ? { ...act, completed: item.completed } : act
            )
          : prev
      );
    }
  };

  const handleSaveReport = async () => {
    if (isSubmittingReport) return;

    if (isSimulationMode) {
      const currentActs = simActivitiesOverride ?? activities;
      if (selectedReport === "choveu_nao_previsto") {
        setSimActivitiesOverride(
          currentActs.map((act) =>
            act.title.toLowerCase().includes("irrig")
              ? {
                  ...act,
                  paused: true,
                  pausedReason: "Pausado na simulação: chuva informada no campo.",
                }
              : act
          )
        );
        setSimWeatherOverride((prev) => ({
          ...(prev ?? weather),
          headline: "Chuva registrada na simulação",
          weatherNotice: "Irrigação pausada automaticamente na simulação.",
        }));
      } else if (selectedReport === "nao_choveu_esperado") {
        setSimActivitiesOverride(
          currentActs.map((act) =>
            act.title.toLowerCase().includes("irrig")
              ? {
                  ...act,
                  paused: false,
                  pausedReason: undefined,
                }
              : act
          )
        );
        setSimWeatherOverride((prev) => ({
          ...(prev ?? weather),
          headline: "Tempo seco na simulação",
          weatherNotice: "Atenção simulada: avaliar irrigação complementar.",
        }));
      } else {
        setSimWeatherOverride((prev) => ({
          ...(prev ?? weather),
          weatherNotice:
            "Atenção simulada: priorizar inspeção fitossanitária na área.",
        }));
      }

      onSubmitReport?.(selectedReport);
      setReportDrawerOpen(false);
      setReportSavedNotice(true);
      window.setTimeout(() => setReportSavedNotice(false), 3000);
      return;
    }

    if (terrenoId != null) {
      setIsSubmittingReport(true);
      try {
        await dispararAlertaGatilho(
          mapFieldReportToAlertaPayload(terrenoId, selectedReport, todayIso)
        );
        await loadDashboardData();
      } catch {
        // Mantém fallback local caso esteja offline
      } finally {
        setIsSubmittingReport(false);
      }
    }
    onSubmitReport?.(selectedReport);
    setReportDrawerOpen(false);
    setReportSavedNotice(true);
    window.setTimeout(() => setReportSavedNotice(false), 3000);
  };

  const handleMarkAlertRead = async (alertaId: number) => {
    if (isSimulationMode) {
      setSimAlertasOverride((prev) =>
        (prev ?? simulatedAlertas ?? []).map((a) =>
          a.id === alertaId ? { ...a, lido: true } : a
        )
      );
      return;
    }
    try {
      await marcarAlertaComoLido(alertaId);
      setLiveAlertas((prev) =>
        prev ? prev.map((a) => (a.id === alertaId ? { ...a, lido: true } : a)) : prev
      );
    } catch {
      // Mantém estado atual caso offline
    }
  };

  const handleRunClimateMonitor = async () => {
    if (isSimulationMode || terrenoId == null || isTriggeringClimateCheck) return;
    setIsTriggeringClimateCheck(true);
    try {
      await monitorarClimaSobDemanda({
        terreno_id: terrenoId,
        perfil_climatico: climateProfileTest,
      });
      await loadDashboardData();
    } catch {
      // Silencioso caso offline
    } finally {
      setIsTriggeringClimateCheck(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F6F0] md:bg-[#EFECE3] md:py-6">
      <div className="mx-auto flex min-h-screen max-w-md flex-col justify-between bg-[#F7F6F0] px-5 pt-7 pb-8 text-[#1F1C18] md:min-h-[820px] md:rounded-[32px] md:border md:border-[#E6E4DA] md:shadow-sm">
        <div>
          {/* Header */}
          <header className="flex items-center justify-between gap-3">
            <span className="font-['Nunito',ui-rounded,system-ui,sans-serif] text-[24px] font-black tracking-tight text-[#511D4E]">
              Kultiva
            </span>

            <div className="flex items-center gap-2">
              {isSimulationMode && (
                <Badge
                  variant="outline"
                  className="border-[#511D4E]/30 bg-[#511D4E]/10 text-[#511D4E]"
                >
                  Modo Simulação
                </Badge>
              )}

              <Badge variant={badgeConfig.variant} aria-live="polite">
                <StatusIcon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span>{badgeConfig.label}</span>
              </Badge>
            </div>
          </header>

          {isSimulationMode && (
            <div
              role="status"
              className="mt-4 rounded-2xl border border-[#511D4E]/25 bg-[#511D4E]/[0.07] px-4 py-3 text-xs text-[#511D4E]"
            >
              <p className="font-bold">
                Simulação ativa{simulatedPlanLabel ? `: ${simulatedPlanLabel}` : ""}
              </p>
              <p className="mt-0.5 text-[#4E4A43]">
                Testando em modo seguro sem alterar seu plano real. Toque em
                &ldquo;Finalizar simulação&rdquo; abaixo para voltar à sua área
                normal.
              </p>
            </div>
          )}

          {/* Localização e Data */}
          <div className="mt-4 flex items-center gap-1.5 text-xs font-medium text-[#6D6960]">
            <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>{areaLocation}</span>
          </div>

          <p className="mt-2.5 text-xs font-medium text-[#6D6960] capitalize">
            {resolvedDateLabel}
          </p>

          {/* Card Roxo de Clima */}
          <section
            aria-label="Previsão do tempo e ajustes do dia"
            className="mt-3 rounded-3xl bg-[#511D4E] p-5 text-white shadow-sm"
          >
            <div className="flex items-start gap-3.5">
              <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-white/10">
                <CloudRain
                  className="h-7 w-7 text-[#CAD17A]"
                  aria-hidden="true"
                />
              </div>

              <div className="min-w-0 flex-1">
                <h2 className="text-[17px] font-bold leading-snug text-white">
                  {effectiveWeather.headline}
                </h2>
                <p className="mt-0.5 text-xs text-white/80">
                  {effectiveWeather.details}
                </p>
              </div>
            </div>

            {effectiveWeather.weatherNotice && (
              <div className="mt-4 flex items-center gap-2.5 rounded-2xl bg-white/10 px-3.5 py-2.5 text-xs font-medium text-white/95">
                <Info
                  className="h-4 w-4 shrink-0 text-[#FCF59B]"
                  aria-hidden="true"
                />
                <span>{effectiveWeather.weatherNotice}</span>
              </div>
            )}
          </section>

          {/* Botão Verde de Calendário */}
          <button
            type="button"
            onClick={onOpenCalendar}
            className="mt-4 flex w-full items-center justify-between gap-3 rounded-2xl bg-[#CAD17A]/35 px-4 py-3.5 text-left transition-colors hover:bg-[#CAD17A]/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#511D4E]"
          >
            <div className="flex min-w-0 items-center gap-3">
              <Leaf
                className="h-5 w-5 shrink-0 text-[#511D4E]"
                aria-hidden="true"
              />
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-[#1F1C18]">
                  {effectiveCropProgress.cropName} ·{" "}
                  {effectiveCropProgress.dayLabel}
                </p>
                <p className="text-xs text-[#5A594E]">
                  Ver calendário completo
                </p>
              </div>
            </div>

            <ChevronRight
              className="h-4 w-4 shrink-0 text-[#511D4E]"
              aria-hidden="true"
            />
          </button>

          {/* Botão de Relatório de Saúde, Clima e Adaptações [M6] / Alertas [M5] */}
          <button
            type="button"
            onClick={() => setHealthDrawerOpen(true)}
            className="mt-2.5 flex w-full items-center justify-between gap-3 rounded-2xl border border-[#E6E4DA] bg-white px-4 py-3 text-left transition-colors hover:border-[#511D4E]/45 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#511D4E]"
          >
            <div className="flex min-w-0 items-center gap-3">
              <FileText
                className="h-5 w-5 shrink-0 text-[#511D4E]"
                aria-hidden="true"
              />
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-[#1F1C18]">
                  Relatório de saúde e adaptações
                </p>
                <p className="truncate text-xs text-[#6D6960]">
                  {effectiveRelatorio
                    ? `Vigor ${Math.round(effectiveRelatorio.vigor.indice * 100)}% (${effectiveRelatorio.vigor.classificacao}) · ${effectiveRelatorio.adaptacoes.total_ajustadas_por_alerta} adaptação(ões)`
                    : "Histórico de clima, vigor e alertas da área"}
                </p>
              </div>
            </div>

            <div className="flex shrink-0 items-center gap-2">
              {unreadAlertsCount > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full bg-[#C42311] px-2 py-0.5 text-[11px] font-bold text-white">
                  <Bell className="h-3 w-3" aria-hidden="true" />
                  {unreadAlertsCount}
                </span>
              )}
              <ChevronRight
                className="h-4 w-4 text-[#511D4E]"
                aria-hidden="true"
              />
            </div>
          </button>

          {/* Atividades do dia (cards informativos por período) */}
          <section className="mt-6" aria-label="Atividades recomendadas para hoje">
            <h1 className="text-[22px] font-bold tracking-tight text-[#511D4E]">
              Seu dia na área
            </h1>

            {reportSavedNotice && (
              <p
                role="status"
                className="mt-3 rounded-2xl border border-[#CAD17A] bg-[#FCF59B]/60 px-3.5 py-2.5 text-xs font-semibold text-[#1F1C18]"
              >
                Relato salvo! Vamos considerar sua observação nas próximas
                orientações.
              </p>
            )}

            <div className="mt-4 space-y-5">
              {isLoadingDashboard && groupedActivities.length === 0 && (
                <p className="rounded-2xl border border-[#E6E4DA] bg-white px-4 py-4 text-xs text-[#6D6960]">
                  Carregando atividades da área...
                </p>
              )}

              {!isLoadingDashboard && groupedActivities.length === 0 && (
                <p className="rounded-2xl border border-[#E6E4DA] bg-white px-4 py-4 text-xs text-[#6D6960]">
                  Nenhuma atividade programada para esta área ainda.
                </p>
              )}

              {groupedActivities.map((group) => {
                const PeriodIcon = group.Icon;

                return (
                  <div key={group.period}>
                    <div className="mb-2 flex items-center gap-1.5 text-xs font-bold text-[#511D4E]">
                      <PeriodIcon
                        className="h-4 w-4 shrink-0"
                        aria-hidden="true"
                      />
                      <span>{group.label}</span>
                    </div>

                    <ul className="space-y-2.5">
                      {group.items.map((item) => {
                        const isPaused = Boolean(item.paused);

                        return (
                          <li
                            key={item.id}
                            className={cn(
                              "flex items-start gap-3 rounded-2xl border px-4 py-3.5",
                              isPaused
                                ? "border-[#BDD7EE] bg-[#EAF3FB]"
                                : "border-[#E6E4DA] bg-white"
                            )}
                          >
                            {isPaused ? (
                              <span
                                className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-[#BDD7EE] bg-white text-[#2B5B84]"
                                aria-hidden="true"
                              >
                                <Pause className="h-3.5 w-3.5" />
                              </span>
                            ) : (
                              <span
                                className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[#F4F3EE] text-[#511D4E]"
                                aria-hidden="true"
                              >
                                <PeriodIcon className="h-3.5 w-3.5" />
                              </span>
                            )}

                            <div className="min-w-0 flex-1">
                              <p
                                className={cn(
                                  "text-sm font-bold leading-snug",
                                  item.completed && "line-through opacity-70",
                                  isPaused
                                    ? "text-[#2B5B84]"
                                    : "text-[#1F1C18]"
                                )}
                              >
                                {item.title}
                              </p>
                              <p
                                className={cn(
                                  "mt-0.5 text-xs leading-relaxed",
                                  isPaused
                                    ? "text-[#3D6F9B]"
                                    : "text-[#6D6960]"
                                )}
                              >
                                {isPaused && item.pausedReason
                                  ? item.pausedReason
                                  : item.description}
                              </p>
                            </div>

                            {item.backendId != null && (
                              <button
                                type="button"
                                onClick={() => void handleToggleActivity(item)}
                                aria-label={
                                  item.completed
                                    ? `Desmarcar ${item.title}`
                                    : `Concluir ${item.title}`
                                }
                                className={cn(
                                  "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border transition-colors",
                                  item.completed
                                    ? "border-[#55A630] bg-[#55A630] text-white"
                                    : "border-[#D6D3C7] bg-white text-transparent hover:border-[#511D4E]"
                                )}
                              >
                                <Check className="h-3.5 w-3.5" aria-hidden="true" />
                              </button>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                );
              })}
            </div>
          </section>
        </div>

        {/* Botões de Ação do Painel do Dia */}
        <footer className="mt-8 flex flex-col items-center gap-3 pt-2">
          <button
            type="button"
            onClick={() => setReportDrawerOpen(true)}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-[#FCF59B] px-5 py-3.5 text-sm font-bold text-[#1F1C18] shadow-xs transition-colors hover:bg-[#F5EC7D] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#511D4E]"
          >
            <ArrowLeftRight className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>Aconteceu diferente</span>
          </button>

          {!isSimulationMode && onStartSimulation && (
            <Button
              type="button"
              variant="outline"
              size="lg"
              onClick={onStartSimulation}
              className="w-full border-[#511D4E]/35 bg-white text-[#511D4E] hover:bg-[#511D4E]/[0.06]"
            >
              <Play className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>Começar simulação</span>
            </Button>
          )}

          {isSimulationMode && onFinishSimulation && (
            <Button
              type="button"
              variant="primary"
              size="lg"
              onClick={onFinishSimulation}
              className="w-full"
            >
              <Square className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>Finalizar simulação</span>
            </Button>
          )}

          {onBack && !isSimulationMode && (
            <Button
              type="button"
              variant="ghost"
              onClick={onBack}
              className="w-full max-w-[200px] text-sm font-semibold text-[#511D4E]"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              <span>Voltar</span>
            </Button>
          )}
        </footer>
      </div>

      {/* Drawer de Relato */}
      <Drawer open={reportDrawerOpen} onOpenChange={setReportDrawerOpen}>
        <DrawerContent>
          <DrawerHeader>
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] font-bold tracking-[0.08em] text-[#6D6960] uppercase">
                SUA EXPERIÊNCIA CONTA
              </span>
              <DrawerClose
                aria-label="Fechar"
                className="flex h-8 w-8 items-center justify-center rounded-full text-[#511D4E] hover:bg-[#EFECE3]"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </DrawerClose>
            </div>

            <DrawerTitle className="mt-2 text-2xl font-bold text-[#511D4E]">
              Aconteceu diferente?
            </DrawerTitle>
            <DrawerDescription className="mt-1 text-sm text-[#6D6960]">
              Conte o que mudou na sua área.
            </DrawerDescription>
          </DrawerHeader>

          <div
            role="radiogroup"
            aria-label="O que mudou na sua área"
            className="mt-4 space-y-2.5"
          >
            {REPORT_OPTIONS.map((option) => {
              const OptionIcon = option.icon;
              const isSelected = selectedReport === option.id;

              return (
                <button
                  key={option.id}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  onClick={() => setSelectedReport(option.id)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 rounded-2xl border px-4 py-3.5 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#511D4E]",
                    isSelected
                      ? "border-[#511D4E] bg-[#511D4E]/[0.05]"
                      : "border-[#E6E4DA] bg-white hover:border-[#511D4E]/40"
                  )}
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <OptionIcon
                      className="h-5 w-5 shrink-0 text-[#511D4E]"
                      aria-hidden="true"
                    />
                    <span className="text-sm font-semibold text-[#1F1C18]">
                      {option.label}
                    </span>
                  </div>

                  {isSelected ? (
                    <Check
                      className="h-4 w-4 shrink-0 text-[#511D4E]"
                      aria-hidden="true"
                    />
                  ) : (
                    <ChevronRight
                      className="h-4 w-4 shrink-0 text-[#6D6960]"
                      aria-hidden="true"
                    />
                  )}
                </button>
              );
            })}
          </div>

          <DrawerFooter className="mt-6">
            <Button
              type="button"
              variant="primary"
              size="lg"
              onClick={handleSaveReport}
              className="w-full"
            >
              Salvar relato
            </Button>
          </DrawerFooter>
        </DrawerContent>
      </Drawer>

      {/* Drawer de Relatório de Saúde e Adaptações [M6] + Alertas [M5] */}
      <Drawer open={healthDrawerOpen} onOpenChange={setHealthDrawerOpen}>
        <DrawerContent className="max-h-[88dvh] overflow-y-auto">
          <DrawerHeader>
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] font-bold tracking-[0.08em] text-[#6D6960] uppercase">
                RELATÓRIO M6 · ALERTAS M5
              </span>
              <DrawerClose
                aria-label="Fechar relatório"
                className="flex h-8 w-8 items-center justify-center rounded-full text-[#511D4E] hover:bg-[#EFECE3]"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </DrawerClose>
            </div>

            <DrawerTitle className="mt-2 text-2xl font-bold text-[#511D4E]">
              Saúde e Adaptações da Área
            </DrawerTitle>
            <DrawerDescription className="mt-1 text-sm text-[#6D6960]">
              {effectiveRelatorio
                ? `Período de ${effectiveRelatorio.periodo_inicio} a ${effectiveRelatorio.periodo_fim} · ${effectiveRelatorio.origem_dados}`
                : "Acompanhe vigor, clima, adaptações do calendário e alertas."}
            </DrawerDescription>
          </DrawerHeader>

          {effectiveRelatorio ? (
            <div className="mt-4 space-y-4">
              {/* Vigor e Vulnerabilidade */}
              <div className="grid grid-cols-2 gap-2.5">
                <div className="rounded-2xl border border-[#E6E4DA] bg-white p-3.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase text-[#511D4E]">
                    <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
                    <span>Vigor do terreno</span>
                  </div>
                  <p className="mt-1.5 text-xl font-extrabold text-[#1F1C18]">
                    {Math.round(effectiveRelatorio.vigor.indice * 100)}%
                  </p>
                  <p className="text-xs font-semibold text-[#2E7D32]">
                    {effectiveRelatorio.vigor.classificacao} ·{" "}
                    {effectiveRelatorio.vigor.tendencia}
                  </p>
                  <p className="mt-1 text-[11px] leading-snug text-[#6D6960]">
                    {effectiveRelatorio.vigor.descricao}
                  </p>
                </div>

                <div className="rounded-2xl border border-[#E6E4DA] bg-white p-3.5">
                  <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase text-[#511D4E]">
                    <ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />
                    <span>Vulnerabilidade</span>
                  </div>
                  <p className="mt-1.5 text-xl font-extrabold text-[#1F1C18]">
                    {Math.round(effectiveRelatorio.vulnerabilidade.indice * 100)}%
                  </p>
                  <p className="text-xs font-semibold text-[#8E180B]">
                    Nível {effectiveRelatorio.vulnerabilidade.nivel}
                  </p>
                  <p className="mt-1 text-[11px] text-[#6D6960]">
                    {effectiveRelatorio.vulnerabilidade.total_alertas_periodo}{" "}
                    alerta(s) no período
                  </p>
                </div>
              </div>

              {(effectiveRelatorio.vulnerabilidade.eventos_criticos.length >
                0 ||
                effectiveRelatorio.vulnerabilidade.fatores_risco.length > 0) && (
                <div className="rounded-2xl border border-[#E6E4DA] bg-white p-3.5 text-xs">
                  {effectiveRelatorio.vulnerabilidade.eventos_criticos.length >
                    0 && (
                    <p className="text-[#8E180B]">
                      <strong>Eventos críticos:</strong>{" "}
                      {effectiveRelatorio.vulnerabilidade.eventos_criticos.join(
                        ", "
                      )}
                    </p>
                  )}
                  {effectiveRelatorio.vulnerabilidade.fatores_risco.length >
                    0 && (
                    <p className="mt-1 text-[#4E4A43]">
                      <strong>Fatores de risco:</strong>{" "}
                      {effectiveRelatorio.vulnerabilidade.fatores_risco.join(
                        " · "
                      )}
                    </p>
                  )}
                </div>
              )}

              {/* Resumo Climático e Comparativo */}
              <section className="rounded-2xl border border-[#E6E4DA] bg-white p-3.5">
                <h3 className="text-xs font-bold uppercase tracking-wider text-[#511D4E]">
                  Resumo Climático e Comparativo
                </h3>
                <div className="mt-2.5 grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded-xl bg-[#F7F6F0] p-2.5">
                    <p className="text-[10px] font-semibold uppercase text-[#6D6960]">
                      Umidade do solo
                    </p>
                    <p className="mt-0.5 font-bold text-[#1F1C18]">
                      {Math.round(
                        effectiveRelatorio.resumo_climatico.umidade_media_solo *
                          100
                      )}
                      %{" "}
                      <span className="font-normal text-[#6D6960]">
                        (
                        {Math.round(
                          effectiveRelatorio.resumo_climatico
                            .umidade_min_solo * 100
                        )}
                        –
                        {Math.round(
                          effectiveRelatorio.resumo_climatico
                            .umidade_max_solo * 100
                        )}
                        %)
                      </span>
                    </p>
                  </div>

                  <div className="rounded-xl bg-[#F7F6F0] p-2.5">
                    <p className="text-[10px] font-semibold uppercase text-[#6D6960]">
                      Temperatura
                    </p>
                    <p className="mt-0.5 font-bold text-[#1F1C18]">
                      {effectiveRelatorio.resumo_climatico.temperatura_media_c.toFixed(
                        1
                      )}
                      °C{" "}
                      <span className="font-normal text-[#6D6960]">
                        (máx{" "}
                        {effectiveRelatorio.resumo_climatico.temperatura_max_c.toFixed(
                          1
                        )}
                        °C)
                      </span>
                    </p>
                  </div>

                  <div className="rounded-xl bg-[#F7F6F0] p-2.5">
                    <p className="text-[10px] font-semibold uppercase text-[#6D6960]">
                      Chuva acumulada
                    </p>
                    <p className="mt-0.5 font-bold text-[#1F1C18]">
                      {Math.round(
                        effectiveRelatorio.resumo_climatico
                          .precipitacao_total_mm
                      )}{" "}
                      mm
                    </p>
                  </div>

                  <div className="rounded-xl bg-[#F7F6F0] p-2.5">
                    <p className="text-[10px] font-semibold uppercase text-[#6D6960]">
                      Solo exposto
                    </p>
                    <p className="mt-0.5 font-bold text-[#1F1C18]">
                      {effectiveRelatorio.resumo_climatico.dias_solo_exposto}{" "}
                      dia(s)
                    </p>
                  </div>
                </div>
                <p className="mt-2.5 text-xs leading-relaxed text-[#4E4A43]">
                  {effectiveRelatorio.comparativo_periodo.resumo_comparativo}
                </p>
              </section>

              {/* Adaptações Dinâmicas */}
              <section className="rounded-2xl border border-[#E6E4DA] bg-white p-3.5">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-[#511D4E]">
                    Adaptações no Calendário
                  </h3>
                  <span className="rounded-full bg-[#CAD17A]/40 px-2.5 py-0.5 text-[11px] font-bold text-[#2F3A1D]">
                    {effectiveRelatorio.adaptacoes.total_ajustadas_por_alerta}/
                    {effectiveRelatorio.adaptacoes.total_atividades_periodo} (
                    {Math.round(effectiveRelatorio.adaptacoes.taxa_adaptacao * 100)}
                    %)
                  </span>
                </div>

                {effectiveRelatorio.adaptacoes.atividades_ajustadas.length >
                0 ? (
                  <ul className="mt-2.5 space-y-2">
                    {effectiveRelatorio.adaptacoes.atividades_ajustadas.map(
                      (item) => (
                        <li
                          key={item.atividade_id}
                          className="rounded-xl border border-[#BDD7EE] bg-[#EAF3FB] px-3 py-2 text-xs"
                        >
                          <p className="font-bold text-[#2B5B84]">
                            {item.titulo} · {item.data_programada}
                          </p>
                          {item.motivo_ajuste && (
                            <p className="mt-0.5 text-[#3D6F9B]">
                              {item.motivo_ajuste}
                            </p>
                          )}
                        </li>
                      )
                    )}
                  </ul>
                ) : (
                  <p className="mt-2 text-xs text-[#6D6960]">
                    Nenhuma atividade precisou ser adiada ou ajustada no período.
                  </p>
                )}
              </section>

              {/* Resumo Interpretativo da IA e Recomendações */}
              <section className="rounded-2xl border border-[#91C494]/60 bg-[#91C494]/20 p-3.5 text-xs leading-relaxed text-[#1E3B21]">
                <p className="font-bold">Resumo Interpretativo (IA)</p>
                <p className="mt-1">{effectiveRelatorio.resumo_ia}</p>
                {effectiveRelatorio.recomendacoes_manejo.length > 0 && (
                  <ul className="mt-2 list-disc space-y-1 pl-4">
                    {effectiveRelatorio.recomendacoes_manejo.map((rec) => (
                      <li key={rec}>{rec}</li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          ) : (
            <div className="mt-4 rounded-2xl border border-[#E6E4DA] bg-white p-4 text-xs text-[#6D6960]">
              Relatório detalhado indisponível offline ou sem medições para esta
              área ainda.
            </div>
          )}

          {/* Alertas Climáticos [M5] */}
          <section className="mt-4 rounded-2xl border border-[#E6E4DA] bg-white p-3.5">
            <div className="flex items-center justify-between gap-2">
              <h3 className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-[#511D4E]">
                <Bell className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Alertas Climáticos ({effectiveAlertas.length})</span>
              </h3>
              {unreadAlertsCount > 0 && (
                <span className="text-[11px] font-bold text-[#C42311]">
                  {unreadAlertsCount} não lido(s)
                </span>
              )}
            </div>

            {effectiveAlertas.length > 0 ? (
              <ul className="mt-2.5 space-y-2">
                {effectiveAlertas.map((alerta) => (
                  <li
                    key={alerta.id}
                    className={cn(
                      "rounded-xl border p-3 text-xs",
                      alerta.lido
                        ? "border-[#E6E4DA] bg-[#F7F6F0]/60 text-[#6D6960]"
                        : "border-[#C42311]/30 bg-[#C42311]/[0.05] text-[#1F1C18]"
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-bold">{alerta.titulo}</p>
                        <p className="mt-0.5 text-[11px] text-[#6D6960]">
                          {alerta.data_evento} · Severidade: {alerta.severidade}
                        </p>
                      </div>
                      {!alerta.lido && (
                        <button
                          type="button"
                          onClick={() => void handleMarkAlertRead(alerta.id)}
                          className="shrink-0 rounded-full border border-[#511D4E]/30 bg-white px-2.5 py-1 text-[11px] font-semibold text-[#511D4E] hover:bg-[#511D4E]/10"
                        >
                          Marcar lido
                        </button>
                      )}
                    </div>
                    <p className="mt-1.5 leading-snug">
                      {alerta.orientacao_pratica || alerta.mensagem}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-[#6D6960]">
                Nenhum alerta climático registrado para esta área.
              </p>
            )}

            {!isSimulationMode && terrenoId != null && (
              <div className="mt-3 border-t border-[#E6E4DA] pt-3">
                <p className="text-[11px] font-bold uppercase text-[#6D6960]">
                  Testar monitoramento climático (demo)
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <select
                    aria-label="Perfil climático de verificação"
                    value={climateProfileTest}
                    onChange={(e) =>
                      setClimateProfileTest(
                        e.target.value as
                          | "seca"
                          | "chuva_extrema"
                          | "onda_de_calor"
                      )
                    }
                    className="rounded-xl border border-[#D5D1C5] bg-white px-3 py-2 text-xs font-medium text-[#1F1C18]"
                  >
                    <option value="seca">Seca</option>
                    <option value="chuva_extrema">Chuva extrema</option>
                    <option value="onda_de_calor">Onda de calor</option>
                  </select>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => void handleRunClimateMonitor()}
                    disabled={isTriggeringClimateCheck}
                    className="border-[#511D4E]/35 text-xs text-[#511D4E]"
                  >
                    <RefreshCw
                      className={cn(
                        "h-3.5 w-3.5",
                        isTriggeringClimateCheck && "animate-spin"
                      )}
                      aria-hidden="true"
                    />
                    <span>
                      {isTriggeringClimateCheck
                        ? "Verificando..."
                        : "Verificar clima agora"}
                    </span>
                  </Button>
                </div>
              </div>
            )}
          </section>

          <DrawerFooter className="mt-6">
            <DrawerClose asChild>
              <Button type="button" variant="primary" size="lg" className="w-full">
                Fechar relatório
              </Button>
            </DrawerClose>
          </DrawerFooter>
        </DrawerContent>
      </Drawer>
    </div>
  );
}


import * as React from "react";
import { useTranslation } from "react-i18next";
import {
  ArrowLeftRight,
  Bug,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  CloudRain,
  Info,
  Leaf,
  MapPin,
  Moon,
  Pause,
  RefreshCw,
  Sun,
  Sunrise,
  Sunset,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import { KultivaLogo } from "../components/KultivaLogo";
import { LanguageSelector } from "../components/LanguageSelector";
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
  concluirAtividade,
  dispararAlertaGatilho,
  listarAlertas,
  listarAtividades,
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
    labelKey: string;
    variant: "saved" | "offline" | "outline";
    icon: React.ComponentType<{ className?: string }>;
  }
> = {
  salvo: { labelKey: "network.saved", variant: "saved", icon: Wifi },
  sincronizando: { labelKey: "network.saving", variant: "outline", icon: RefreshCw },
  offline: { labelKey: "network.offline", variant: "offline", icon: WifiOff },
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
  onOpenCalendar,
  onSubmitReport,
  onBack,
}: AreaDashboardPageProps) {
  const { t, i18n } = useTranslation();
  const todayIso = React.useMemo(() => new Date().toISOString().slice(0, 10), []);
  const resolvedDateLabel = React.useMemo(() => {
    if (dateLabel) return dateLabel;
    const locale = i18n.language.startsWith("en") ? "en-US" : "pt-BR";
    return new Date().toLocaleDateString(locale, {
      weekday: "long",
      day: "numeric",
      month: "long",
    });
  }, [dateLabel, i18n.language]);

  const [isOnline, setIsOnline] = React.useState<boolean>(() =>
    typeof navigator !== "undefined" ? navigator.onLine : true
  );
  const [reportDrawerOpen, setReportDrawerOpen] = React.useState(false);
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
  const [isLoadingDashboard, setIsLoadingDashboard] = React.useState(false);
  const [isSubmittingReport, setIsSubmittingReport] = React.useState(false);

  const loadDashboardData = React.useCallback(async () => {
    if (terrenoId == null) return;
    setIsLoadingDashboard(true);
    try {
      const [atividadesRes, alertasRes, relatorioRes] = await Promise.allSettled([
        listarAtividades({ terreno_id: terrenoId }),
        listarAlertas({ terreno_id: terrenoId, lido: false }),
        obterRelatorioTerreno(terrenoId),
      ]);

      const atividadesData =
        atividadesRes.status === "fulfilled" ? atividadesRes.value : [];
      const alertasData =
        alertasRes.status === "fulfilled" ? alertasRes.value : [];
      const relatorioData =
        relatorioRes.status === "fulfilled" ? relatorioRes.value : null;

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
        setLiveWeather(
          adaptRelatorioAndAlertasToWeather(relatorioData, alertasData)
        );
      }
    } finally {
      setIsLoadingDashboard(false);
    }
  }, [terrenoId, todayIso, cropNameFallback]);

  React.useEffect(() => {
    void loadDashboardData();
  }, [loadDashboardData]);

  const effectiveWeather = liveWeather ?? weather;
  const effectiveCropProgress = liveCropProgress ?? cropProgress;
  const effectiveActivities =
    liveActivities !== null ? liveActivities : activities;

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
      const periodLabel = t(`dashboard.periods.${period}`, {
        defaultValue: items[0].periodLabel ?? PERIOD_CONFIG[period].defaultLabel,
      });
      return {
        period,
        label: periodLabel,
        Icon: PERIOD_CONFIG[period].icon,
        items,
      };
    }).filter((group): group is NonNullable<typeof group> => group !== null);
  }, [effectiveActivities]);

  const handleToggleActivity = async (item: AreaActivityItem) => {
    if (item.backendId == null) return;
    const nextCompleted = !item.completed;
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

  return (
    <div className="min-h-screen bg-[#F7F6F0] md:bg-[#EFECE3] md:py-6">
      <div className="mx-auto flex min-h-screen max-w-md flex-col justify-between bg-[#F7F6F0] px-5 pt-7 pb-8 text-[#1F1C18] md:min-h-[820px] md:rounded-[32px] md:border md:border-[#E6E4DA] md:shadow-sm">
        <div>
          {/* Header */}
          <header className="flex items-center justify-between gap-3">
            <KultivaLogo />

            <div className="flex items-center gap-2">
              <Badge variant={badgeConfig.variant} aria-live="polite">
                <StatusIcon className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span>{t(badgeConfig.labelKey)}</span>
              </Badge>
              <LanguageSelector />
            </div>
          </header>

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
                  {t("dashboard.viewFullCalendar")}
                </p>
              </div>
            </div>

            <ChevronRight
              className="h-4 w-4 shrink-0 text-[#511D4E]"
              aria-hidden="true"
            />
          </button>

          {/* Atividades do dia (cards informativos por período) */}
          <section className="mt-6" aria-label={t("dashboard.yourDayTitle")}>
            <h1 className="text-[22px] font-bold tracking-tight text-[#511D4E]">
              {t("dashboard.yourDayTitle")}
            </h1>

            {reportSavedNotice && (
              <p
                role="status"
                className="mt-3 rounded-2xl border border-[#CAD17A] bg-[#FCF59B]/60 px-3.5 py-2.5 text-xs font-semibold text-[#1F1C18]"
              >
                {t("dashboard.reportSuccess")}
              </p>
            )}

            <div className="mt-4 space-y-5">
              {isLoadingDashboard && groupedActivities.length === 0 && (
                <p className="rounded-2xl border border-[#E6E4DA] bg-white px-4 py-4 text-xs text-[#6D6960]">
                  {t("dashboard.loadingActivities")}
                </p>
              )}

              {!isLoadingDashboard && groupedActivities.length === 0 && (
                <p className="rounded-2xl border border-[#E6E4DA] bg-white px-4 py-4 text-xs text-[#6D6960]">
                  {t("dashboard.noActivitiesScheduled")}
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
                                    ? t("dashboard.uncheckTask", {
                                        title: item.title,
                                      })
                                    : t("dashboard.completeTask", {
                                        title: item.title,
                                      })
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

        {/* Botão Amarelo "Aconteceu diferente" */}
        <footer className="mt-8 flex flex-col items-center gap-3 pt-2">
          <button
            type="button"
            onClick={() => setReportDrawerOpen(true)}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-[#FCF59B] px-5 py-3.5 text-sm font-bold text-[#1F1C18] shadow-xs transition-colors hover:bg-[#F5EC7D] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#511D4E]"
          >
            <ArrowLeftRight className="h-4 w-4 shrink-0" aria-hidden="true" />
            <span>{t("dashboard.happenedDifferently")}</span>
          </button>

          {onBack && (
            <Button
              type="button"
              variant="ghost"
              onClick={onBack}
              className="w-full max-w-[200px] text-sm font-semibold text-[#511D4E]"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              <span>{t("common.back")}</span>
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
                {t("dashboard.yourExperienceCounts")}
              </span>
              <DrawerClose
                aria-label={t("common.close")}
                className="flex h-8 w-8 items-center justify-center rounded-full text-[#511D4E] hover:bg-[#EFECE3]"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </DrawerClose>
            </div>

            <DrawerTitle className="mt-2 text-2xl font-bold text-[#511D4E]">
              {t("dashboard.happenedDifferentlyQuestion")}
            </DrawerTitle>
            <DrawerDescription className="mt-1 text-sm text-[#6D6960]">
              {t("dashboard.tellWhatChanged")}
            </DrawerDescription>
          </DrawerHeader>

          <div
            role="radiogroup"
            aria-label={t("dashboard.tellWhatChanged")}
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
                      {t(`dashboard.reportOptions.${option.id}`, {
                        defaultValue: option.label,
                      })}
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
              {t("dashboard.saveReport")}
            </Button>
          </DrawerFooter>
        </DrawerContent>
      </Drawer>
    </div>
  );
}


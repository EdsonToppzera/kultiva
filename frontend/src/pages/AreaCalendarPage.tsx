import * as React from "react";
import { useTranslation } from "react-i18next";
import {
  CalendarCheck,
  ChevronLeft,
  ChevronRight,
  CloudRain,
  CloudSun,
  Info,
  MapPin,
  Pause,
  RefreshCw,
  Sun,
  Wifi,
  WifiOff,
} from "lucide-react";
import { KultivaLogo } from "../components/KultivaLogo";
import { LanguageSelector } from "../components/LanguageSelector";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import type {
  AreaCalendarData,
  CalendarDayHighlight,
  CalendarMilestoneType,
  CalendarRotationPhase,
} from "../features/calendar/types/calendar.types";
import type { NetworkSyncStatus } from "../features/onboarding/types/cropHistory.types";
import { cn } from "../lib/utils";
import { adaptAtividadesToCalendarData } from "../services/adapters";
import {
  listarAlertas,
  listarAtividades,
  obterRelatorioTerreno,
} from "../services/api";

export interface AreaCalendarPageProps {
  terrenoId?: number | null;
  areaLocation?: string;
  calendarData?: AreaCalendarData;
  networkStatus?: NetworkSyncStatus;
  onBack?: () => void;
}

const WEEKDAY_INITIALS = ["D", "S", "T", "Q", "Q", "S", "S"];

const MONTH_NAMES = [
  "Janeiro",
  "Fevereiro",
  "Março",
  "Abril",
  "Maio",
  "Junho",
  "Julho",
  "Agosto",
  "Setembro",
  "Outubro",
  "Novembro",
  "Dezembro",
];

const SHORT_MONTH_NAMES = [
  "jan",
  "fev",
  "mar",
  "abr",
  "mai",
  "jun",
  "jul",
  "ago",
  "set",
  "out",
  "nov",
  "dez",
];

const WEEKDAY_NAMES_UPPER = [
  "DOMINGO",
  "SEGUNDA-FEIRA",
  "TERÇA-FEIRA",
  "QUARTA-FEIRA",
  "QUINTA-FEIRA",
  "SEXTA-FEIRA",
  "SÁBADO",
];

const MILESTONE_DOT_CLASS: Record<CalendarMilestoneType, string> = {
  plantio: "bg-[#9AA832]",
  manejo: "bg-[#511D4E]",
  colheita: "bg-[#D97706]",
};

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

function parseIsoDate(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function toIsoDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function diffDaysInclusive(startIso: string, endIso: string): number {
  const start = parseIsoDate(startIso).getTime();
  const end = parseIsoDate(endIso).getTime();
  return Math.round((end - start) / 86_400_000) + 1;
}

function formatLongDate(
  iso: string,
  months: string[],
  isEnglish: boolean
): string {
  const date = parseIsoDate(iso);
  const monthName = months[date.getMonth()] ?? MONTH_NAMES[date.getMonth()];
  return isEnglish
    ? `${monthName} ${date.getDate()}`
    : `${date.getDate()} de ${monthName.toLowerCase()}`;
}

function formatShortDate(iso: string, shortMonths: string[]): string {
  const date = parseIsoDate(iso);
  const day = String(date.getDate()).padStart(2, "0");
  const month =
    shortMonths[date.getMonth()] ?? SHORT_MONTH_NAMES[date.getMonth()];
  return `${day} ${month} ${date.getFullYear()}`;
}

function getPhaseForDate(
  dateIso: string,
  phases: CalendarRotationPhase[]
): CalendarRotationPhase | null {
  return (
    phases.find(
      (phase) => dateIso >= phase.startDate && dateIso <= phase.endDate
    ) ?? null
  );
}

function getCycleStatusKey(percent: number): string {
  if (percent <= 10) return "calendar.cycleInitial";
  if (percent >= 85) return "calendar.cycleNearHarvest";
  return "calendar.cycleInProgress";
}

export function AreaCalendarPage({
  terrenoId,
  areaLocation = "",
  calendarData: propCalendarData,
  networkStatus,
  onBack,
}: AreaCalendarPageProps) {
  const { t, i18n } = useTranslation();
  const isEnglish = i18n.language.startsWith("en");
  const weekdayInitials = t("calendar.weekdayInitials", {
    returnObjects: true,
    defaultValue: WEEKDAY_INITIALS,
  }) as string[];
  const monthNames = t("calendar.months", {
    returnObjects: true,
    defaultValue: MONTH_NAMES,
  }) as string[];
  const shortMonthNames = t("calendar.shortMonths", {
    returnObjects: true,
    defaultValue: SHORT_MONTH_NAMES,
  }) as string[];
  const weekdaysUpper = t("calendar.weekdaysUpper", {
    returnObjects: true,
    defaultValue: WEEKDAY_NAMES_UPPER,
  }) as string[];
  const [liveCalendarData, setLiveCalendarData] =
    React.useState<AreaCalendarData | null>(null);
  const [isOnline, setIsOnline] = React.useState<boolean>(() =>
    typeof navigator !== "undefined" ? navigator.onLine : true
  );

  React.useEffect(() => {
    if (terrenoId == null) {
      setLiveCalendarData(null);
      return;
    }

    let cancelled = false;
    const todayIso = new Date().toISOString().slice(0, 10);

    async function loadCalendar() {
      const [atividadesRes, alertasRes, relatorioRes] =
        await Promise.allSettled([
          listarAtividades({ terreno_id: terrenoId as number }),
          listarAlertas({ terreno_id: terrenoId as number }),
          obterRelatorioTerreno(terrenoId as number),
        ]);

      if (cancelled) return;

      if (atividadesRes.status === "fulfilled") {
        const alertas =
          alertasRes.status === "fulfilled" ? alertasRes.value : [];
        const relatorio =
          relatorioRes.status === "fulfilled" ? relatorioRes.value : null;
        const adapted = adaptAtividadesToCalendarData(
          areaLocation,
          atividadesRes.value,
          alertas,
          relatorio,
          todayIso
        );
        setLiveCalendarData(adapted);
        setSelectedDate(adapted.todayDate);
        const parsed = parseIsoDate(adapted.todayDate);
        setViewYear(parsed.getFullYear());
        setViewMonth(parsed.getMonth());
      }
    }

    void loadCalendar();
    return () => {
      cancelled = true;
    };
  }, [terrenoId, areaLocation]);

  const todayFallback = React.useMemo(
    () => new Date().toISOString().slice(0, 10),
    []
  );
  const calendarData = liveCalendarData ??
    propCalendarData ?? {
      areaName: areaLocation,
      todayDate: todayFallback,
      phases: [],
      highlights: {},
    };

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

  const [selectedDate, setSelectedDate] = React.useState<string>(
    calendarData.todayDate
  );

  const initialDate = parseIsoDate(calendarData.todayDate);
  const [viewYear, setViewYear] = React.useState<number>(
    initialDate.getFullYear()
  );
  const [viewMonth, setViewMonth] = React.useState<number>(
    initialDate.getMonth()
  );

  const effectiveStatus: NetworkSyncStatus =
    networkStatus ?? (isOnline ? "salvo" : "offline");
  const badgeConfig = NETWORK_BADGE_CONFIG[effectiveStatus];
  const StatusIcon = badgeConfig.icon;

  const selectedDateObj = parseIsoDate(selectedDate);
  const selectedWeekday = weekdaysUpper[selectedDateObj.getDay()];
  const isSelectedToday = selectedDate === calendarData.todayDate;

  const activePhase = React.useMemo(
    () => getPhaseForDate(selectedDate, calendarData.phases),
    [selectedDate, calendarData.phases]
  );

  const selectedHighlight: CalendarDayHighlight = React.useMemo(() => {
    const existing = calendarData.highlights[selectedDate];
    if (existing) return existing;

    return {
      date: selectedDate,
      weatherHeadline: t("calendar.stableWeatherHeadline"),
      weatherDetails: t("calendar.stableWeatherDetails"),
      weatherKind: "sun",
      importantNotice: activePhase
        ? t("calendar.normalFollowUp", { crop: activePhase.cropName })
        : t("calendar.noCriticalTasks"),
    };
  }, [calendarData.highlights, selectedDate, activePhase, t]);

  const calendarCells = React.useMemo(() => {
    const firstDayOfMonth = new Date(viewYear, viewMonth, 1);
    const startOffset = firstDayOfMonth.getDay();
    const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();

    const cells: Array<{ iso: string; day: number } | null> = [];
    for (let i = 0; i < startOffset; i++) {
      cells.push(null);
    }
    for (let day = 1; day <= daysInMonth; day++) {
      const iso = toIsoDate(new Date(viewYear, viewMonth, day));
      cells.push({ iso, day });
    }
    return cells;
  }, [viewYear, viewMonth]);

  const handlePrevMonth = () => {
    if (viewMonth === 0) {
      setViewMonth(11);
      setViewYear((y) => y - 1);
    } else {
      setViewMonth((m) => m - 1);
    }
  };

  const handleNextMonth = () => {
    if (viewMonth === 11) {
      setViewMonth(0);
      setViewYear((y) => y + 1);
    } else {
      setViewMonth((m) => m + 1);
    }
  };

  const WeatherIcon =
    selectedHighlight.weatherKind === "rain"
      ? CloudRain
      : selectedHighlight.weatherKind === "cloud"
        ? CloudSun
        : Sun;

  const NoticeIcon = selectedHighlight.importantNotice
    ?.toLowerCase()
    .includes("paus")
    ? Pause
    : selectedHighlight.milestoneType
      ? CalendarCheck
      : Info;

  const phaseStats = React.useMemo(() => {
    if (!activePhase) return null;
    const totalDays = Math.max(
      1,
      diffDaysInclusive(activePhase.startDate, activePhase.endDate)
    );
    const currentDay = Math.min(
      totalDays,
      Math.max(1, diffDaysInclusive(activePhase.startDate, selectedDate))
    );
    const percent = Math.round((currentDay / totalDays) * 100);
    return { totalDays, currentDay, percent };
  }, [activePhase, selectedDate]);

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

          {/* Localização */}
          <div className="mt-4 flex items-center gap-1.5 text-xs font-medium text-[#6D6960]">
            <MapPin className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>{areaLocation}</span>
          </div>

          <p className="mt-4 text-[11px] font-bold tracking-[0.08em] text-[#6D6960] uppercase">
            {t("calendar.panorama")}
          </p>

          {/* Card Roxo: Resumo do Dia Selecionado */}
          <section
            aria-label={t("calendar.selectedDay")}
            className="mt-2.5 rounded-3xl bg-[#511D4E] p-5 text-white shadow-sm"
          >
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-[10px] font-semibold tracking-[0.08em] text-white/75 uppercase">
                  {selectedWeekday} · {t("calendar.selectedDay")}
                </p>
                <h1 className="mt-1 text-[22px] font-bold leading-tight text-white">
                  {formatLongDate(selectedDate, monthNames, isEnglish)}
                </h1>
              </div>

              {isSelectedToday && (
                <span className="rounded-full bg-white/15 px-3 py-1 text-[11px] font-bold text-white">
                  {t("calendar.today")}
                </span>
              )}
            </div>

            {selectedHighlight.milestoneLabel && (
              <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-white/15 px-3 py-1 text-[11px] font-semibold text-[#FCF59B]">
                <CalendarCheck className="h-3.5 w-3.5" aria-hidden="true" />
                <span>{selectedHighlight.milestoneLabel}</span>
              </p>
            )}

            <div className="mt-4 flex items-start gap-3">
              <WeatherIcon
                className="mt-0.5 h-6 w-6 shrink-0 text-[#CAD17A]"
                aria-hidden="true"
              />
              <div className="min-w-0">
                <p className="text-sm font-bold text-white">
                  {selectedHighlight.weatherHeadline}
                </p>
                <p className="mt-0.5 text-xs text-white/80">
                  {selectedHighlight.weatherDetails}
                </p>
              </div>
            </div>

            {selectedHighlight.importantNotice && (
              <div className="mt-4 flex items-center gap-2.5 rounded-2xl bg-white/10 px-3.5 py-2.5 text-xs font-medium text-white/95">
                <NoticeIcon
                  className="h-4 w-4 shrink-0 text-white/90"
                  aria-hidden="true"
                />
                <span>{selectedHighlight.importantNotice}</span>
              </div>
            )}
          </section>

          {/* Calendário Mensal com Fases da Rotação */}
          <section
            aria-label="Calendário da rotação de culturas"
            className="mt-4 rounded-3xl border border-[#E6E4DA] bg-white p-4 shadow-sm"
          >
            {/* Navegação do Mês */}
            <div className="flex items-center justify-between">
              <button
                type="button"
                onClick={handlePrevMonth}
                aria-label={t("calendar.prevMonth")}
                className="flex h-8 w-8 items-center justify-center rounded-full text-[#511D4E] transition-colors hover:bg-[#F7F6F0]"
              >
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              </button>

              <h2 className="text-base font-bold text-[#511D4E]">
                {monthNames[viewMonth]} {viewYear}
              </h2>

              <button
                type="button"
                onClick={handleNextMonth}
                aria-label={t("calendar.nextMonth")}
                className="flex h-8 w-8 items-center justify-center rounded-full text-[#511D4E] transition-colors hover:bg-[#F7F6F0]"
              >
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>

            {/* Cabeçalho Dias da Semana */}
            <div className="mt-3 grid grid-cols-7 gap-1 text-center">
              {weekdayInitials.map((letter, idx) => (
                <span
                  key={`${letter}-${idx}`}
                  className="py-1 text-[11px] font-semibold text-[#6D6960]"
                >
                  {letter}
                </span>
              ))}
            </div>

            {/* Grade de Dias */}
            <div className="mt-1 grid grid-cols-7 gap-1">
              {calendarCells.map((cell, index) => {
                if (!cell) {
                  return <div key={`empty-${index}`} className="h-10" />;
                }

                const phase = getPhaseForDate(cell.iso, calendarData.phases);
                const highlight = calendarData.highlights[cell.iso];
                const isSelected = cell.iso === selectedDate;
                const isToday = cell.iso === calendarData.todayDate;

                return (
                  <button
                    key={cell.iso}
                    type="button"
                    onClick={() => setSelectedDate(cell.iso)}
                    aria-label={`${cell.day} ${monthNames[viewMonth]}${phase ? `, ${phase.cropName}` : ""}`}
                    aria-pressed={isSelected}
                    className={cn(
                      "relative flex h-10 flex-col items-center justify-center rounded-xl text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[#511D4E]",
                      isSelected
                        ? "bg-[#511D4E] font-bold text-white shadow-xs"
                        : phase
                          ? cn(phase.dayBgClass, "hover:brightness-95")
                          : "text-[#1F1C18] hover:bg-[#F7F6F0]",
                      !isSelected &&
                        isToday &&
                        "ring-1.5 ring-[#511D4E] font-bold"
                    )}
                  >
                    <span>{cell.day}</span>
                    {highlight?.milestoneType && (
                      <span
                        aria-hidden="true"
                        className={cn(
                          "mt-0.5 h-1.5 w-1.5 rounded-full",
                          isSelected
                            ? "bg-[#FCF59B]"
                            : MILESTONE_DOT_CLASS[highlight.milestoneType]
                        )}
                      />
                    )}
                  </button>
                );
              })}
            </div>

            {/* Legenda de Marcos e Culturas */}
            <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-[#E6E4DA] pt-3 text-[11px] text-[#6D6960]">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#9AA832]" />
                {t("calendar.planting")}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#511D4E]" />
                {t("calendar.management")}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#D97706]" />
                {t("calendar.harvest")}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-xs bg-[#511D4E]" />
                {t("calendar.selected")}
              </span>
            </div>

            {calendarData.phases.length > 1 && (
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[11px] text-[#6D6960]">
                {calendarData.phases.map((phase) => (
                  <span
                    key={phase.id}
                    className="inline-flex items-center gap-1.5"
                  >
                    <span
                      className={cn(
                        "h-2.5 w-2.5 rounded-xs",
                        phase.legendDotClass
                      )}
                    />
                    {phase.cropName}
                  </span>
                ))}
              </div>
            )}
          </section>

          {/* Card de Progresso da Cultura em Vigor */}
          {activePhase && phaseStats ? (
            <section
              aria-label="Progresso da cultura em vigor"
              className={cn(
                "mt-4 rounded-3xl border p-5 transition-colors",
                activePhase.cardBgClass
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-lg font-bold text-[#1F1C18]">
                    {activePhase.cropName}
                  </h2>
                  <p className="mt-0.5 text-xs text-[#5A594E]">
                    {calendarData.areaName} · {activePhase.objectiveLabel}
                  </p>
                </div>

                <span className="shrink-0 rounded-full bg-[#511D4E] px-3 py-1 text-xs font-bold text-white">
                  {t("calendar.dayNumber", { day: phaseStats.currentDay })}
                </span>
              </div>

              <div className="mt-4 flex items-center justify-between text-xs font-medium text-[#5A594E]">
                <span>
                  {formatShortDate(activePhase.startDate, shortMonthNames)} →{" "}
                  {formatShortDate(activePhase.endDate, shortMonthNames)}
                </span>
                <span className="font-bold text-[#511D4E]">
                  {t("calendar.approxDays", { days: phaseStats.totalDays })}
                </span>
              </div>

              <div
                role="progressbar"
                aria-label={`Progresso de ${activePhase.cropName}`}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={phaseStats.percent}
                className="mt-2 h-2 w-full overflow-hidden rounded-full bg-white/70"
              >
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    activePhase.progressFillClass
                  )}
                  style={{ width: `${phaseStats.percent}%` }}
                />
              </div>

              <p className="mt-2.5 text-xs font-semibold text-[#511D4E]">
                {t("calendar.cyclePercent", {
                  status: t(getCycleStatusKey(phaseStats.percent)),
                  percent: phaseStats.percent,
                })}
              </p>
            </section>
          ) : (
            <section className="mt-4 rounded-3xl border border-[#E6E4DA] bg-white p-5 text-center">
              <p className="text-sm font-bold text-[#1F1C18]">
                {t("calendar.noCropOnDateTitle")}
              </p>
              <p className="mt-1 text-xs text-[#6D6960]">
                {t("calendar.noCropOnDateDesc")}
              </p>
            </section>
          )}
        </div>

        {/* Footer */}
        {onBack && (
          <footer className="mt-6 flex justify-center pt-2">
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
        )}
      </div>
    </div>
  );
}


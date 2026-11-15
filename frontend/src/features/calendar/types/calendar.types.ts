export type CalendarMilestoneType = "plantio" | "manejo" | "colheita";

export interface CalendarRotationPhase {
  id: string;
  cropName: string;
  objectiveLabel: string;
  startDate: string; // YYYY-MM-DD
  endDate: string; // YYYY-MM-DD
  /** Classes Tailwind para o fundo dos dias desta cultura no calendário */
  dayBgClass: string;
  /** Classe Tailwind para o indicador de cor na legenda de culturas */
  legendDotClass: string;
  /** Classes Tailwind para o card de progresso desta cultura */
  cardBgClass: string;
  progressFillClass: string;
}

export interface CalendarDayHighlight {
  date: string; // YYYY-MM-DD
  milestoneType?: CalendarMilestoneType;
  milestoneLabel?: string;
  weatherHeadline: string;
  weatherDetails: string;
  weatherKind?: "rain" | "sun" | "cloud";
  importantNotice?: string;
}

export interface AreaCalendarData {
  areaName: string;
  todayDate: string; // YYYY-MM-DD
  phases: CalendarRotationPhase[];
  highlights: Record<string, CalendarDayHighlight>;
}


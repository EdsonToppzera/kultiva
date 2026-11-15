export interface RotationAlternativeCrop {
  id: string;
  name: string;
  reason: string;
  imageUrl?: string | null;
}

export interface RotationTrackStep {
  id: string;
  name: string;
  statusLabel: string;
  imageUrl?: string | null;
  isRest?: boolean;
  alternatives?: RotationAlternativeCrop[];
  prepReason?: string;
  equivalencesReason?: string;
}

export interface TechnicalNpkRow {
  nutrient: string;
  impact: string;
  requirementLevel: "Baixo" | "Médio" | "Alto" | "Low" | "Medium" | "High";
}

export interface TechnicalDetailsData {
  cycleDurationDays: string;
  waterDemandMm: string;
  npkTable: TechnicalNpkRow[];
  agrofitAlerts: string[];
  nasaClimateNote: string;
}

export type RecommendationCardVariant = "recommended" | "standard" | "risk";

export interface RotationScenario {
  id: string;
  optionBadge: string;
  focusTag: string;
  variant?: RecommendationCardVariant;
  steps: RotationTrackStep[];
  aiJustification: string;
  pros: string[];
  cons: string[];
  ctaLabel?: string;
  technicalDetails: TechnicalDetailsData;
}

export interface AreaSummaryInfo {
  areaName: string;
  lastCropName: string;
  tagsLine: string;
}

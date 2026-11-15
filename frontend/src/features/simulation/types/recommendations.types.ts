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
}

export interface TechnicalNpkRow {
  nutrient: string;
  impact: string;
  requirementLevel: "Baixo" | "Médio" | "Alto";
}

export interface ScoreBreakdownItem {
  waterFitPercent: number;
  heatFitPercent: number;
  soilBenefitPercent: number;
  marketFitPercent: number;
  mlModelScorePercent?: number | null;
  temporalStabilityPercent?: number | null;
  drySpellMaxDays?: number | null;
  historyAdjustment?: number | null;
}

export interface GaezTechnicalSummary {
  suitabilityPercent?: number | null;
  attainableYieldKgHa?: number | null;
  soilQualityIndexPercent?: number | null;
  cmip6DeltaPercent?: number | null;
  inputLevel?: string | null;
  slopePercent?: number | null;
  slopeRangeLabel?: string | null;
  soilGroup?: string | null;
  limitingFactor?: string | null;
}

export interface EcocropCropComfortItem {
  cropName: string;
  scientificName?: string | null;
  family?: string | null;
  tempOptimalRangeC?: string | null;
  rainOptimalRangeMm?: string | null;
  cycleRangeDays?: string | null;
  comfortScorePercent?: number | null;
  comfortStatusLabel?: string | null;
}

export interface AgrofitTechnicalSummary {
  phytosanitaryRisk: "low" | "medium" | "high" | string;
  phytosanitaryRiskLabel: string;
  phytosanitaryPenaltyPercent: number;
  pestsCount?: number | null;
  pestsSample: string[];
  botanicalFamilies: string[];
  sameFamilyAsHistory: boolean;
  climateTriggers: string[];
}

export interface ClimateMetricsTechnicalSummary {
  soilMoisturePercent?: number | null;
  surfaceTempC?: number | null;
  annualRainMm?: number | null;
  anomalyZScore?: number | null;
  dataOriginLabel?: string | null;
}

export interface TechnicalDetailsData {
  cycleDurationDays: string;
  waterDemandMm: string;
  npkTable: TechnicalNpkRow[];
  agrofitAlerts: string[];
  nasaClimateNote: string;
  viabilityScorePercent?: number;
  waterRiskLabel?: string;
  scoreBreakdown?: ScoreBreakdownItem;
  gaez?: GaezTechnicalSummary;
  ecocrop?: EcocropCropComfortItem[];
  agrofit?: AgrofitTechnicalSummary;
  climateMetrics?: ClimateMetricsTechnicalSummary;
  aiDisclaimer?: string;
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

import { CROPS_DICTIONARY } from "../data/cropsDictionary";
import type {
  AreaCalendarData,
  CalendarDayHighlight,
  CalendarMilestoneType,
  CalendarRotationPhase,
} from "../features/calendar/types/calendar.types";
import type { CropHistoryData } from "../features/onboarding/types/cropHistory.types";
import type { PriorityData } from "../features/onboarding/types/priority.types";
import type { SoilTypeData } from "../features/onboarding/types/soilType.types";
import type { WaterDistributionData } from "../features/onboarding/types/waterDistribution.types";
import { COVER_CROP_ALTERNATIVES } from "../features/simulation/components/RecommendationsStep";
import type {
  AgrofitTechnicalSummary,
  ClimateMetricsTechnicalSummary,
  EcocropCropComfortItem,
  GaezTechnicalSummary,
  RecommendationCardVariant,
  RotationScenario,
  RotationTrackStep,
  ScoreBreakdownItem,
  TechnicalNpkRow,
} from "../features/simulation/types/recommendations.types";
import type {
  ActivityPeriodId,
  AreaActivityItem,
  AreaCropProgress,
  AreaWeatherSummary,
  FieldReportOptionId,
} from "../pages/AreaDashboardPage";
import type {
  AlertaClimaticoResponse,
  AlertaGatilhoRequest,
  AtividadeCalendarioResponse,
  EstrategiaRotacaoSugerida,
  EtapaCronogramaInput,
  GerarCronogramaRequest,
  RelatorioAdaptacaoResponse,
  SimulacaoResponse,
} from "./api";

const REST_KEYWORDS = ["descanso", "pousio", "cobertura"];

const COVER_CROP_KEYWORDS = [
  "feijão-de-porco",
  "feijao-de-porco",
  "crotalária",
  "crotalaria",
  "milheto",
  "guandu",
  "mucuna",
  "braquiária",
  "braquiaria",
  "descanso",
  "pousio",
];

function findCropImage(name: string): string | null {
  const normalized = name.trim().toLowerCase();
  if (!normalized) return null;
  const match = CROPS_DICTIONARY.find(
    (crop) =>
      crop.officialName.toLowerCase() === normalized ||
      crop.id.toLowerCase() === normalized ||
      crop.popularNames.some((alias) => alias.toLowerCase() === normalized)
  );
  return match?.imageUrl ?? null;
}

function isRestStepName(name: string): boolean {
  const normalized = name.trim().toLowerCase();
  return REST_KEYWORDS.some((kw) => normalized.includes(kw));
}

function isCoverStepName(name: string): boolean {
  const normalized = name.trim().toLowerCase();
  return COVER_CROP_KEYWORDS.some((kw) => normalized.includes(kw));
}

function parseStrategySteps(strategy: string): string[] {
  return strategy
    .split(/->|→|,|\+/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function mapFocusTag(priority?: PriorityData | null, index = 0): string {
  if (priority?.prioridade.id === "retorno_rapido") return "RETORNO RÁPIDO";
  if (priority?.prioridade.id === "consumo_racao") return "ALIMENTO E RAÇÃO";
  if (priority?.prioridade.id === "gastar_minimo") return "MENOR CUSTO";
  if (priority?.prioridade.id === "limpar_terra") return "CONTROLE DE PRAGAS";
  if (priority?.prioridade.id === "plantar_especifico") return "CULTURA DESEJADA";
  return index === 0 ? "FOCO NO SOLO" : "EQUILÍBRIO DA ÁREA";
}

function resolveVariant(
  item: EstrategiaRotacaoSugerida,
  index: number
): RecommendationCardVariant {
  const riskLower = (item.water_risk || "").toLowerCase();
  if (
    item.viability < 0.48 ||
    riskLower.includes("alto") ||
    riskLower.includes("critico") ||
    riskLower.includes("crítico")
  ) {
    return "risk";
  }
  if (index === 0) return "recommended";
  return "standard";
}

function buildProsAndCons(
  item: EstrategiaRotacaoSugerida,
  response: SimulacaoResponse,
  variant: RecommendationCardVariant
): { pros: string[]; cons: string[] } {
  const pros: string[] = [];
  const cons: string[] = [];

  if (item.benefits) {
    pros.push(item.benefits);
  }
  for (const beneficio of response.beneficios_esperados.slice(0, 2)) {
    if (!pros.includes(beneficio)) {
      pros.push(beneficio);
    }
  }
  if (pros.length === 0) {
    pros.push("Ajuda a equilibrar o solo e reduzir perdas na lavoura.");
  }

  if (variant === "risk") {
    cons.push(
      `Risco hídrico ${item.water_risk.toLowerCase()} para o período previsto.`
    );
  }
  for (const risco of response.riscos_identificados.slice(0, 2)) {
    if (!cons.includes(risco)) {
      cons.push(risco);
    }
  }
  if (cons.length === 0) {
    cons.push("Requer acompanhamento periódico de umidade e pragas.");
  }

  return { pros, cons };
}

function buildNpkTable(
  steps: RotationTrackStep[],
  breakdown?: Record<string, unknown> | null
): TechnicalNpkRow[] {
  const hasLegume = steps.some((s) => {
    const n = s.name.toLowerCase();
    return (
      n.includes("feij") ||
      n.includes("crotal") ||
      n.includes("guandu") ||
      n.includes("soja") ||
      n.includes("amendoim")
    );
  });

  const soilBonus =
    typeof breakdown?.soil_health === "number" ? breakdown.soil_health : null;

  return [
    {
      nutrient: "Nitrogênio (N)",
      requirementLevel: hasLegume ? "Baixo" : "Alto",
      impact: hasLegume
        ? "Leguminosas da rotação ajudam a fixar nitrogênio no solo."
        : "Exige adubação nitrogenada de cobertura para manter vigor.",
    },
    {
      nutrient: "Fósforo (P)",
      requirementLevel: "Médio",
      impact:
        soilBonus && soilBonus > 0.7
          ? "Bom aproveitamento radicular com a rotação sugerida."
          : "Favorece o enraizamento inicial e pegamento das mudas.",
    },
    {
      nutrient: "Potássio (K)",
      requirementLevel: "Médio",
      impact: "Contribui para resistência à falta de água e qualidade da colheita.",
    },
  ];
}

const AI_DISCLAIMER_DEFAULT =
  "Lembre-se: esta ferramenta serve para apoiar a decisão e identificar possibilidades, mas não substitui a sua experiência local. A decisão final é sempre sua.";

function normalizeLookupKey(raw: string): string {
  return raw
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function toFiniteNumber(val: unknown): number | null {
  if (typeof val === "number" && Number.isFinite(val)) return val;
  if (typeof val === "string" && val.trim() !== "") {
    const parsed = Number(val);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function toPercent01(val: unknown): number | null {
  const num = toFiniteNumber(val);
  if (num === null) return null;
  if (num <= 1.2) {
    return Math.max(0, Math.min(100, Math.round(num * 100)));
  }
  return Math.max(0, Math.min(100, Math.round(num)));
}

function translateRiskLabel(risk: string): string {
  const low = (risk || "").trim().toLowerCase();
  if (low === "low" || low === "baixo") return "Baixo";
  if (low === "medium" || low === "medio" || low === "médio") return "Médio";
  if (low === "high" || low === "alto" || low === "critico" || low === "crítico") {
    return "Alto";
  }
  return risk || "Moderado";
}

function translateComfortStatus(status: unknown): {
  label: string | null;
  percent: number | null;
} {
  if (typeof status !== "string" || !status.trim()) {
    return { label: null, percent: null };
  }
  const s = status.trim().toLowerCase();
  if (s === "optimal" || s === "ideal") return { label: "Ótimo", percent: 95 };
  if (s === "acceptable" || s === "within_absolute") {
    return { label: "Adequado", percent: 80 };
  }
  if (s === "marginal" || s === "suboptimal") {
    return { label: "Moderado", percent: 65 };
  }
  if (s === "stress" || s === "outside_absolute") {
    return { label: "Estresse", percent: 35 };
  }
  return { label: status, percent: null };
}

function formatRange(
  minVal: unknown,
  maxVal: unknown,
  unit: string
): string | null {
  const minNum = toFiniteNumber(minVal);
  const maxNum = toFiniteNumber(maxVal);
  if (minNum === null && maxNum === null) return null;
  if (minNum !== null && maxNum !== null) {
    return `${Math.round(minNum)}–${Math.round(maxNum)} ${unit}`;
  }
  const single = minNum ?? maxNum;
  return single !== null ? `${Math.round(single)} ${unit}` : null;
}

function parseSlopePercent(soilObj: Record<string, unknown> | undefined): {
  slopePercent: number | null;
  slopeRangeLabel: string | null;
} {
  if (!soilObj) return { slopePercent: null, slopeRangeLabel: null };
  const direct = toFiniteNumber(soilObj.slope_med_pct);
  const rangeStr =
    typeof soilObj.slope_range_pct === "string" &&
    soilObj.slope_range_pct.trim() &&
    soilObj.slope_range_pct !== "não informado"
      ? soilObj.slope_range_pct.trim()
      : null;
  if (direct !== null) {
    return { slopePercent: Number(direct.toFixed(1)), slopeRangeLabel: rangeStr };
  }
  if (rangeStr) {
    const nums = rangeStr.match(/\d+(?:[.,]\d+)?/g);
    if (nums && nums.length >= 2) {
      const a = Number(nums[0].replace(",", "."));
      const b = Number(nums[1].replace(",", "."));
      if (Number.isFinite(a) && Number.isFinite(b)) {
        return {
          slopePercent: Number(((a + b) / 2).toFixed(1)),
          slopeRangeLabel: rangeStr,
        };
      }
    } else if (nums && nums.length === 1) {
      const a = Number(nums[0].replace(",", "."));
      if (Number.isFinite(a)) {
        return { slopePercent: Number(a.toFixed(1)), slopeRangeLabel: rangeStr };
      }
    }
  }
  return { slopePercent: null, slopeRangeLabel: rangeStr };
}

function buildScoreBreakdownSummary(
  breakdown?: Record<string, unknown> | null
): ScoreBreakdownItem | undefined {
  if (!breakdown) return undefined;
  const waterFitPercent = toPercent01(breakdown.water_fit) ?? 70;
  const heatFitPercent = toPercent01(breakdown.heat_fit) ?? 70;
  const soilBenefitPercent = toPercent01(breakdown.soil_benefit) ?? 65;
  const marketFitPercent = toPercent01(breakdown.market) ?? 65;

  return {
    waterFitPercent,
    heatFitPercent,
    soilBenefitPercent,
    marketFitPercent,
    mlModelScorePercent: toPercent01(breakdown.ml_model_score),
    temporalStabilityPercent: toPercent01(breakdown.temporal_stability),
    drySpellMaxDays: toFiniteNumber(breakdown.dry_spell_max),
    historyAdjustment: toFiniteNumber(breakdown.history_adjustment),
  };
}

function buildGaezSummary(
  breakdown: Record<string, unknown> | null | undefined,
  metricas: Record<string, unknown> | null | undefined
): GaezTechnicalSummary | undefined {
  const gaezObj =
    metricas && typeof metricas.gaez === "object" && metricas.gaez !== null
      ? (metricas.gaez as Record<string, unknown>)
      : undefined;
  const soilObj =
    gaezObj && typeof gaezObj.soil === "object" && gaezObj.soil !== null
      ? (gaezObj.soil as Record<string, unknown>)
      : undefined;

  const suitabilityPercent = toPercent01(breakdown?.gaez_suitability);
  const attainableYieldKgHa = toFiniteNumber(breakdown?.attainable_yield_kg_ha);
  const soilQualityIndexPercent =
    toPercent01(breakdown?.soil_quality_index) ??
    toPercent01(soilObj?.soil_quality_index);

  const cmip6Raw = toFiniteNumber(breakdown?.cmip6_suitability_delta);
  const cmip6DeltaPercent =
    cmip6Raw !== null ? Math.round(cmip6Raw * 1000) / 10 : null;

  const inputLevel =
    (typeof breakdown?.gaez_input_level === "string" &&
      breakdown.gaez_input_level.trim()) ||
    (typeof gaezObj?.input_level === "string" && gaezObj.input_level.trim()) ||
    null;

  const { slopePercent, slopeRangeLabel } = parseSlopePercent(soilObj);
  const soilGroup =
    typeof soilObj?.soil_group === "string" && soilObj.soil_group.trim()
      ? soilObj.soil_group.trim()
      : null;
  const limitingFactor =
    typeof soilObj?.limiting_factor === "string" &&
    soilObj.limiting_factor.trim()
      ? soilObj.limiting_factor.trim()
      : null;

  if (
    suitabilityPercent === null &&
    attainableYieldKgHa === null &&
    soilQualityIndexPercent === null &&
    cmip6DeltaPercent === null &&
    slopePercent === null &&
    !soilGroup
  ) {
    return undefined;
  }

  return {
    suitabilityPercent,
    attainableYieldKgHa,
    soilQualityIndexPercent,
    cmip6DeltaPercent,
    inputLevel,
    slopePercent,
    slopeRangeLabel,
    soilGroup,
    limitingFactor,
  };
}

function findEcocropRecord(
  cropName: string,
  ecocropCrops: Record<string, Record<string, unknown>>
): Record<string, unknown> | null {
  const norm = normalizeLookupKey(cropName);
  if (!norm) return null;
  if (ecocropCrops[norm]) return ecocropCrops[norm];

  for (const [key, rec] of Object.entries(ecocropCrops)) {
    const keyNorm = normalizeLookupKey(key);
    if (keyNorm === norm || keyNorm.includes(norm) || norm.includes(keyNorm)) {
      return rec;
    }
    const commonNames = Array.isArray(rec.common_names)
      ? rec.common_names
      : [];
    if (
      commonNames.some(
        (cn) => normalizeLookupKey(String(cn)) === norm
      )
    ) {
      return rec;
    }
  }
  return null;
}

function buildEcocropItems(
  steps: RotationTrackStep[],
  breakdown: Record<string, unknown> | null | undefined,
  metricas: Record<string, unknown> | null | undefined
): EcocropCropComfortItem[] | undefined {
  const ecoObj =
    metricas &&
    typeof metricas.ecocrop === "object" &&
    metricas.ecocrop !== null
      ? (metricas.ecocrop as Record<string, unknown>)
      : undefined;
  const rawCrops =
    ecoObj && typeof ecoObj.crops === "object" && ecoObj.crops !== null
      ? (ecoObj.crops as Record<string, Record<string, unknown>>)
      : {};

  const comfortInfo = translateComfortStatus(breakdown?.ecocrop_comfort);
  const items: EcocropCropComfortItem[] = [];
  const seen = new Set<string>();

  for (const step of steps) {
    if (step.isRest) continue;
    const norm = normalizeLookupKey(step.name);
    if (!norm || seen.has(norm)) continue;
    seen.add(norm);

    const rec = findEcocropRecord(step.name, rawCrops);
    if (!rec) continue;

    const tempRange =
      formatRange(rec.topmin, rec.topmax, "°C") ??
      formatRange(rec.tmin, rec.tmax, "°C");
    const rainRange =
      formatRange(rec.ropmin, rec.ropmax, "mm/ano") ??
      formatRange(rec.rmin, rec.rmax, "mm/ano");
    const cycleRange = formatRange(rec.gmin, rec.gmax, "dias");

    items.push({
      cropName: step.name,
      scientificName:
        typeof rec.scientific_name === "string" ? rec.scientific_name : null,
      family:
        typeof rec.family_canonical === "string"
          ? rec.family_canonical
          : typeof rec.family === "string"
            ? rec.family
            : null,
      tempOptimalRangeC: tempRange,
      rainOptimalRangeMm: rainRange,
      cycleRangeDays: cycleRange,
      comfortScorePercent: comfortInfo.percent,
      comfortStatusLabel: comfortInfo.label,
    });
  }

  return items.length > 0 ? items : undefined;
}

function buildAgrofitSummary(
  breakdown: Record<string, unknown> | null | undefined,
  metricas: Record<string, unknown> | null | undefined
): AgrofitTechnicalSummary | undefined {
  if (!breakdown) return undefined;

  const hasFields =
    breakdown.phytosanitary_risk !== undefined ||
    breakdown.agrofit_pests_count !== undefined ||
    Array.isArray(breakdown.botanical_families) ||
    Array.isArray(breakdown.phytosanitary_triggers);

  const agroObj =
    metricas &&
    typeof metricas.agrofit === "object" &&
    metricas.agrofit !== null
      ? (metricas.agrofit as Record<string, unknown>)
      : undefined;

  if (!hasFields && !agroObj) return undefined;

  const risk = String(breakdown.phytosanitary_risk ?? "low");
  const penaltyRaw = toFiniteNumber(breakdown.phytosanitary_penalty) ?? 0;
  const pestsSample = Array.isArray(breakdown.agrofit_pests_sample)
    ? breakdown.agrofit_pests_sample.map((p) => String(p))
    : [];
  const botanicalFamilies = Array.isArray(breakdown.botanical_families)
    ? breakdown.botanical_families.map((f) => String(f))
    : [];
  const climateTriggers = Array.isArray(breakdown.phytosanitary_triggers)
    ? breakdown.phytosanitary_triggers.map((t) => String(t))
    : [];

  return {
    phytosanitaryRisk: risk,
    phytosanitaryRiskLabel: translateRiskLabel(risk),
    phytosanitaryPenaltyPercent: Math.round(penaltyRaw * 100),
    pestsCount: toFiniteNumber(breakdown.agrofit_pests_count),
    pestsSample,
    botanicalFamilies,
    sameFamilyAsHistory: Boolean(breakdown.same_family_as_history),
    climateTriggers,
  };
}

function buildClimateMetricsSummary(
  metricas: Record<string, unknown> | null | undefined,
  origem: string
): ClimateMetricsTechnicalSummary | undefined {
  if (!metricas) return undefined;
  const moisture = toPercent01(
    metricas.avg_soil_moisture_smap ?? metricas.umidade_solo_estimada
  );
  const temp = toFiniteNumber(
    metricas.avg_surface_temp_ecostress ?? metricas.temperatura_media_c
  );
  const precipDia = toFiniteNumber(metricas.avg_precipitation_gpm);
  const precipAno =
    precipDia !== null
      ? Math.round(precipDia * 365)
      : toFiniteNumber(metricas.precipitacao_estimada_mm);
  const zScoresObj =
    metricas.z_scores && typeof metricas.z_scores === "object"
      ? (metricas.z_scores as Record<string, unknown>)
      : null;
  const zScore = toFiniteNumber(
    metricas.z_score ??
      metricas.anomaly_z_score ??
      metricas.precipitation_z_score ??
      metricas.moisture_z_score ??
      zScoresObj?.precipitation_mm ??
      zScoresObj?.soil_moisture ??
      zScoresObj?.surface_temp_c
  );
  const dataOriginLabel =
    typeof metricas.origem === "string" && metricas.origem.trim()
      ? metricas.origem.trim()
      : origem || null;

  return {
    soilMoisturePercent: moisture,
    surfaceTempC: temp !== null ? Number(temp.toFixed(1)) : null,
    annualRainMm: precipAno !== null ? Math.round(precipAno) : null,
    anomalyZScore: zScore !== null ? Number(zScore.toFixed(2)) : null,
    dataOriginLabel,
  };
}

export function adaptSimulacaoToScenarios(
  response: SimulacaoResponse,
  onboarding: {
    cropHistory?: CropHistoryData | null;
    waterDistribution?: WaterDistributionData | null;
    soilType?: SoilTypeData | null;
    priority?: PriorityData | null;
  }
): RotationScenario[] {
  const lastCropName = onboarding.cropHistory?.naoLembro
    ? null
    : onboarding.cropHistory?.ultimoCultivo?.officialName ?? null;

  const sugeridas =
    response.rotacoes_sugeridas.length > 0
      ? response.rotacoes_sugeridas
      : [
          {
            strategy:
              response.plano_rotacao.length > 0
                ? response.plano_rotacao.map((e) => e.cultura).join(" -> ")
                : response.cultura_principal,
            viability: response.viability_score,
            water_risk: response.water_risk,
            benefits: response.beneficios_esperados[0] ?? null,
            explicacao: response.explicacao_ia || response.explicacao_textual,
          },
        ];

  return sugeridas.slice(0, 3).map((item, idx) => {
    const rawStepNames = parseStrategySteps(item.strategy);
    const stepNames =
      lastCropName &&
      rawStepNames.length > 0 &&
      rawStepNames[0].toLowerCase() !== lastCropName.toLowerCase()
        ? [lastCropName, ...rawStepNames]
        : rawStepNames;

    const steps: RotationTrackStep[] = stepNames.map((name, stepIndex) => {
      const isFirstLastCrop =
        lastCropName !== null &&
        stepIndex === 0 &&
        name.toLowerCase() === lastCropName.toLowerCase();
      const isRest = isRestStepName(name);
      const isCover = isCoverStepName(name);

      let statusLabel = "Depois";
      if (isFirstLastCrop) {
        statusLabel = onboarding.cropHistory?.cultivoEmAndamento
          ? "Plantado agora"
          : "Já colhido";
      } else if (
        stepIndex === 0 ||
        (lastCropName !== null && stepIndex === 1)
      ) {
        statusLabel = "A seguir";
      }

      return {
        id: `sim-${idx}-step-${stepIndex}-${name.toLowerCase().replace(/\s+/g, "-")}`,
        name,
        statusLabel,
        imageUrl: isRest ? null : findCropImage(name),
        isRest,
        alternatives:
          !isFirstLastCrop && (isCover || isRest)
            ? COVER_CROP_ALTERNATIVES
            : undefined,
      };
    });

    const variant = resolveVariant(item, idx);
    const { pros, cons } = buildProsAndCons(item, response, variant);
    const cycleDays =
      idx === 0 && response.tempo_colheita_dias > 0
        ? response.tempo_colheita_dias
        : Math.max(60, steps.filter((s) => !s.isRest).length * 85);

    const waterMm =
      idx === 0 && response.consumo_agua_mm > 0
        ? Math.round(response.consumo_agua_mm)
        : Math.max(220, Math.round(response.consumo_agua_mm || 350));

    const breakdown = item.score_breakdown ?? null;
    const metricas = response.metricas_geoespaciais ?? null;
    const phytoWarnings = Array.isArray(breakdown?.phytosanitary_warnings)
      ? breakdown.phytosanitary_warnings.map((w) => String(w))
      : [];
    const mergedAgrofitAlerts = Array.from(
      new Set([
        ...phytoWarnings,
        ...(response.riscos_identificados ?? []),
      ])
    );

    const viabilityScorePercent =
      toPercent01(item.viability ?? response.viability_score) ?? 70;
    const waterRiskLabel = translateRiskLabel(item.water_risk);

    return {
      id: `sim-scenario-${idx + 1}`,
      optionBadge: `${idx + 1}ª Opção`,
      focusTag: mapFocusTag(onboarding.priority, idx),
      variant,
      steps,
      aiJustification:
        item.explicacao ||
        response.explicacao_ia ||
        response.explicacao_textual ||
        "Rotação calculada com base no histórico da área e condições climáticas.",
      pros,
      cons,
      ctaLabel:
        variant === "risk" ? "Escolher mesmo assim" : "Escolher este plano",
      technicalDetails: {
        cycleDurationDays: `${cycleDays} dias`,
        waterDemandMm: `${waterMm} mm (${waterRiskLabel})`,
        nasaClimateNote:
          response.explicacao_textual ||
          `Análise climática (${response.origem}) com risco hídrico ${waterRiskLabel.toLowerCase()}.`,
        npkTable: buildNpkTable(steps, breakdown),
        agrofitAlerts:
          mergedAgrofitAlerts.length > 0
            ? mergedAgrofitAlerts
            : [
                "Monitore pragas iniciais nas primeiras 3 semanas após o plantio.",
              ],
        viabilityScorePercent,
        waterRiskLabel,
        scoreBreakdown: buildScoreBreakdownSummary(breakdown),
        gaez: buildGaezSummary(breakdown, metricas),
        ecocrop: buildEcocropItems(steps, breakdown, metricas),
        agrofit: buildAgrofitSummary(breakdown, metricas),
        climateMetrics: buildClimateMetricsSummary(metricas, response.origem),
        aiDisclaimer: AI_DISCLAIMER_DEFAULT,
      },
    };
  });
}

export function buildGerarCronogramaPayload(
  terrenoId: number,
  scenario: RotationScenario,
  cropHistory?: CropHistoryData | null
): GerarCronogramaRequest {
  const todayIso = new Date().toISOString().slice(0, 10);
  const dataInicio =
    cropHistory?.cultivoEmAndamento && cropHistory.dataInicioCultivo
      ? cropHistory.dataInicioCultivo
      : todayIso;

  const lastCropLower = cropHistory?.ultimoCultivo?.officialName
    ?.trim()
    .toLowerCase();

  const futureSteps = scenario.steps.filter((step, idx) => {
    if (step.isRest) return false;
    if (
      idx === 0 &&
      lastCropLower &&
      step.name.trim().toLowerCase() === lastCropLower &&
      !cropHistory?.cultivoEmAndamento
    ) {
      return false;
    }
    return true;
  });

  const effectiveSteps =
    futureSteps.length > 0
      ? futureSteps
      : scenario.steps.filter((s) => !s.isRest);

  const planoRotacao: EtapaCronogramaInput[] = effectiveSteps.map(
    (step, index) => ({
      ordem: index + 1,
      cultura: step.name,
      duracao_dias: 90,
      risco_hidrico: scenario.variant === "risk" ? "alto" : "moderado",
    })
  );

  return {
    terreno_id: terrenoId,
    nome_cultura: planoRotacao[0]?.cultura ?? "Cultura Principal",
    data_inicio: dataInicio,
    tempo_colheita_dias: 90,
    estrategia_rotacao: planoRotacao.map((e) => e.cultura).join(" -> "),
    plano_rotacao: planoRotacao,
    substituir_pendentes: true,
  };
}

function inferActivityPeriod(tipoAtividade: string): {
  period: ActivityPeriodId;
  periodLabel: string;
} {
  const tipo = tipoAtividade.trim().toLowerCase();
  if (tipo === "inspecao" || tipo === "plantio" || tipo === "adubacao" || tipo === "colheita") {
    return { period: "manha", periodLabel: "Manhã cedo" };
  }
  if (tipo === "irrigacao") {
    return { period: "tarde", periodLabel: "Fim de tarde" };
  }
  return { period: "qualquer-momento", periodLabel: "Qualquer momento" };
}

export function adaptAtividadesToDashboardItems(
  atividades: AtividadeCalendarioResponse[],
  todayIso: string
): AreaActivityItem[] {
  if (atividades.length === 0) return [];

  const todays = atividades.filter((a) => a.data_programada === todayIso);
  const source =
    todays.length > 0
      ? todays
      : atividades
          .filter((a) => !a.concluida && a.data_programada >= todayIso)
          .slice(0, 6);

  const finalItems = source.length > 0 ? source : atividades.slice(0, 6);

  return finalItems.map((atividade) => {
    const { period, periodLabel } = inferActivityPeriod(
      atividade.tipo_atividade
    );
    return {
      id: String(atividade.id),
      backendId: atividade.id,
      period,
      periodLabel,
      title: atividade.titulo,
      description:
        atividade.descricao ||
        `Atividade de ${atividade.tipo_atividade} (${atividade.data_programada}).`,
      completed: atividade.concluida,
      paused: atividade.ajustada_por_alerta && !atividade.concluida,
      pausedReason: atividade.motivo_ajuste ?? undefined,
    };
  });
}

export function adaptRelatorioAndAlertasToWeather(
  relatorio: RelatorioAdaptacaoResponse | null,
  alertas: AlertaClimaticoResponse[]
): AreaWeatherSummary {
  const latestAlert = alertas[0];
  const resumo = relatorio?.resumo_climatico;

  const tempStr = resumo
    ? `${Math.round(resumo.temperatura_media_c)}°C (máx ${Math.round(resumo.temperatura_max_c)}°C)`
    : "Clima monitorado";
  const rainStr = resumo
    ? `Chuva acumulada: ${Math.round(resumo.precipitacao_total_mm)} mm`
    : "Sem chuva forte prevista";

  let headline = "Tempo estável na área";
  if (latestAlert) {
    headline = latestAlert.titulo;
  } else if (resumo && resumo.precipitacao_total_mm > 25) {
    headline = "Chuva recente registrada";
  } else if (resumo && resumo.umidade_media_solo < 0.22) {
    headline = "Solo com umidade baixa";
  }

  return {
    headline,
    details: `${tempStr} · ${rainStr}`,
    weatherNotice:
      latestAlert?.orientacao_pratica ||
      latestAlert?.resumo_adaptacao ||
      relatorio?.recomendacoes_manejo[0],
    sourceLabel: relatorio?.origem_dados
      ? `Fonte: ${relatorio.origem_dados}`
      : undefined,
  };
}

export function adaptAtividadesToCropProgress(
  atividades: AtividadeCalendarioResponse[],
  todayIso: string,
  fallbackCropName = "Cultivo em andamento"
): AreaCropProgress {
  if (atividades.length === 0) {
    return {
      cropName: fallbackCropName,
      dayLabel: "Sem cronograma",
    };
  }

  const sorted = [...atividades].sort((a, b) =>
    a.data_programada.localeCompare(b.data_programada)
  );
  const firstDate = sorted[0].data_programada;
  const startMs = new Date(`${firstDate}T12:00:00`).getTime();
  const todayMs = new Date(`${todayIso}T12:00:00`).getTime();
  const diffDays = Math.max(1, Math.round((todayMs - startMs) / 86400000) + 1);

  const stageMatch = sorted[0].titulo.match(/\[Etapa\s+\d+\s*-\s*([^\]]+)\]/i);
  const cropName = stageMatch?.[1]?.trim() || fallbackCropName;

  return {
    cropName,
    dayLabel: todayIso < firstDate ? `Inicia em ${firstDate}` : `Dia ${diffDays}`,
  };
}

const PHASE_PALETTE = [
  {
    dayBgClass: "bg-[#B8E89E]/75",
    legendDotClass: "bg-[#79C753]",
    cardBgClass: "bg-[#B8E89E]/45 border-[#91C494]",
    progressFillClass: "bg-[#55A630]",
  },
  {
    dayBgClass: "bg-[#FBE28A]/85",
    legendDotClass: "bg-[#D99B26]",
    cardBgClass: "bg-[#FCF59B]/55 border-[#D8C56E]",
    progressFillClass: "bg-[#C98A1B]",
  },
  {
    dayBgClass: "bg-[#D8D4EC]/80",
    legendDotClass: "bg-[#511D4E]",
    cardBgClass: "bg-[#ECE9F6] border-[#C9C1E0]",
    progressFillClass: "bg-[#511D4E]",
  },
];

function extractStageCrop(titulo: string): string {
  const match = titulo.match(/\[Etapa\s+\d+\s*-\s*([^\]]+)\]/i);
  if (match?.[1]) return match[1].trim();
  return "Ciclo principal";
}

function mapMilestoneType(
  tipoAtividade: string
): CalendarMilestoneType | undefined {
  const tipo = tipoAtividade.trim().toLowerCase();
  if (tipo === "plantio") return "plantio";
  if (tipo === "colheita") return "colheita";
  if (tipo === "manejo" || tipo === "adubacao" || tipo === "irrigacao") {
    return "manejo";
  }
  return undefined;
}

export function adaptAtividadesToCalendarData(
  areaName: string,
  atividades: AtividadeCalendarioResponse[],
  alertas: AlertaClimaticoResponse[],
  relatorio: RelatorioAdaptacaoResponse | null,
  todayIso: string
): AreaCalendarData {
  const grouped = new Map<string, AtividadeCalendarioResponse[]>();
  for (const item of atividades) {
    const cropName = extractStageCrop(item.titulo);
    const list = grouped.get(cropName) ?? [];
    list.push(item);
    grouped.set(cropName, list);
  }

  const phases: CalendarRotationPhase[] = Array.from(grouped.entries()).map(
    ([cropName, items], idx) => {
      const dates = items.map((i) => i.data_programada).sort();
      const palette = PHASE_PALETTE[idx % PHASE_PALETTE.length];
      return {
        id: `phase-${idx + 1}`,
        cropName,
        objectiveLabel:
          idx === 0 ? "Etapa atual do plano" : `Etapa ${idx + 1} da rotação`,
        startDate: dates[0] ?? todayIso,
        endDate: dates[dates.length - 1] ?? todayIso,
        ...palette,
      };
    }
  );

  const highlights: Record<string, CalendarDayHighlight> = {};
  const defaultTemp = relatorio
    ? `${Math.round(relatorio.resumo_climatico.temperatura_media_c)}°C`
    : "Clima monitorado";

  for (const item of atividades) {
    const existing = highlights[item.data_programada];
    const milestoneType = mapMilestoneType(item.tipo_atividade);
    highlights[item.data_programada] = {
      date: item.data_programada,
      milestoneType: existing?.milestoneType ?? milestoneType,
      milestoneLabel: existing?.milestoneLabel ?? item.titulo,
      weatherHeadline: existing?.weatherHeadline ?? "Atividade programada",
      weatherDetails:
        existing?.weatherDetails ?? `${defaultTemp} · ${item.descricao || item.titulo}`,
      weatherKind: existing?.weatherKind ?? "sun",
      importantNotice:
        existing?.importantNotice ??
        (item.ajustada_por_alerta ? item.motivo_ajuste ?? undefined : undefined),
    };
  }

  for (const alerta of alertas) {
    const existing = highlights[alerta.data_evento];
    const isRain = alerta.tipo_evento.includes("chuva");
    highlights[alerta.data_evento] = {
      date: alerta.data_evento,
      milestoneType: existing?.milestoneType,
      milestoneLabel: existing?.milestoneLabel,
      weatherHeadline: alerta.titulo,
      weatherDetails: alerta.mensagem,
      weatherKind: isRain ? "rain" : "cloud",
      importantNotice:
        alerta.orientacao_pratica ||
        alerta.resumo_adaptacao ||
        alerta.mensagem,
    };
  }

  return {
    areaName,
    todayDate: todayIso,
    phases,
    highlights,
  };
}

export function mapFieldReportToAlertaPayload(
  terrenoId: number,
  reportId: FieldReportOptionId,
  todayIso: string
): AlertaGatilhoRequest {
  if (reportId === "choveu_nao_previsto") {
    return {
      terreno_id: terrenoId,
      tipo_evento: "chuva_intensa",
      severidade: "alta",
      data_evento: todayIso,
      origem_gatilho: "manual",
      titulo: "Relato de campo: chuva não prevista",
      mensagem:
        "O produtor informou chuva não prevista na área. Ajustar atividades sensíveis.",
      dias_adiamento: 2,
    };
  }

  if (reportId === "nao_choveu_esperado") {
    return {
      terreno_id: terrenoId,
      tipo_evento: "seca",
      severidade: "alta",
      data_evento: todayIso,
      origem_gatilho: "manual",
      titulo: "Relato de campo: falta de chuva",
      mensagem:
        "O produtor informou que não choveu como esperado. Avaliar necessidade de irrigação e cobertura.",
      dias_adiamento: 1,
    };
  }

  return {
    terreno_id: terrenoId,
    tipo_evento: "praga",
    severidade: "alta",
    data_evento: todayIso,
    origem_gatilho: "manual",
    titulo: "Relato de campo: ocorrência de praga",
    mensagem:
      "O produtor identificou sinais de praga na área. Priorizar inspeção e manejo fitossanitário.",
    dias_adiamento: 1,
  };
}

export interface SimulatedDashboardBundle {
  planLabel: string;
  weather: AreaWeatherSummary;
  cropProgress: AreaCropProgress;
  activities: AreaActivityItem[];
  calendarData: AreaCalendarData;
  relatorio: RelatorioAdaptacaoResponse;
  alertas: AlertaClimaticoResponse[];
}

function addDaysToIso(baseIso: string, days: number): string {
  const [y, m, d] = baseIso.split("-").map(Number);
  const dt = new Date(y, m - 1, d + days);
  const yyyy = dt.getFullYear();
  const mm = String(dt.getMonth() + 1).padStart(2, "0");
  const dd = String(dt.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export function buildSimulatedDashboardAndCalendar(
  scenario: RotationScenario,
  simulacao: SimulacaoResponse | null,
  areaName: string,
  cropHistory?: CropHistoryData | null
): SimulatedDashboardBundle {
  const todayIso = new Date().toISOString().slice(0, 10);
  const startIso =
    cropHistory?.cultivoEmAndamento && cropHistory.dataInicioCultivo
      ? cropHistory.dataInicioCultivo
      : todayIso;

  const lastCropLower = cropHistory?.ultimoCultivo?.officialName
    ?.trim()
    .toLowerCase();

  const futureSteps = scenario.steps.filter((step, idx) => {
    if (step.isRest) return false;
    if (
      idx === 0 &&
      lastCropLower &&
      step.name.trim().toLowerCase() === lastCropLower &&
      !cropHistory?.cultivoEmAndamento
    ) {
      return false;
    }
    return true;
  });

  const activeSteps =
    futureSteps.length > 0
      ? futureSteps
      : scenario.steps.filter((s) => !s.isRest);

  const primaryCrop = activeSteps[0]?.name ?? "Cultivo simulado";
  const planLabel = `${scenario.optionBadge} · ${activeSteps
    .map((s) => s.name)
    .join(" → ")}`;

  const startMs = new Date(`${startIso}T12:00:00`).getTime();
  const todayMs = new Date(`${todayIso}T12:00:00`).getTime();
  const currentDay = Math.max(1, Math.round((todayMs - startMs) / 86400000) + 1);

  const climate = scenario.technicalDetails.climateMetrics;
  const viabilityPct = scenario.technicalDetails.viabilityScorePercent ?? 75;
  const isRisk = scenario.variant === "risk";
  const waterNotice =
    scenario.technicalDetails.agrofitAlerts[0] || scenario.aiJustification;

  const tempNum = climate?.surfaceTempC ?? 27;
  const moistureNum = climate?.soilMoisturePercent ?? 32;
  const rainAnnualNum = climate?.annualRainMm ?? 920;

  const weather: AreaWeatherSummary = {
    headline: isRisk
      ? "Atenção climática na simulação"
      : `Cenário simulado: ${scenario.technicalDetails.waterRiskLabel ?? "Moderado"} risco hídrico`,
    details: `${Math.round(tempNum)}°C · Umidade do solo ${Math.round(moistureNum)}% · Chuva est. ${Math.round(rainAnnualNum)} mm/ano`,
    weatherNotice: waterNotice,
    sourceLabel: `Simulação (${climate?.dataOriginLabel ?? simulacao?.origem ?? "sandbox"})`,
  };

  const cropProgress: AreaCropProgress = {
    cropName: primaryCrop,
    dayLabel: todayIso < startIso ? `Inicia em ${startIso}` : `Dia ${currentDay} (Simulado)`,
  };

  const activities: AreaActivityItem[] = [
    {
      id: "sim-act-1",
      backendId: -1,
      period: "manha",
      periodLabel: "Manhã cedo",
      title: `Preparo e conferência para ${primaryCrop}`,
      description: `Avaliar umidade do solo antes do manejo inicial de ${primaryCrop}.`,
      completed: false,
    },
    {
      id: "sim-act-2",
      backendId: -2,
      period: "manha",
      periodLabel: "Manhã cedo",
      title: "Inspeção preventiva de folhas e pragas",
      description:
        scenario.technicalDetails.agrofit?.pestsSample[0]
          ? `Monitorar sinais iniciais (ex.: ${scenario.technicalDetails.agrofit.pestsSample[0]}).`
          : "Verificar sinais iniciais de insetos ou manchas nas plantas.",
      completed: false,
    },
    {
      id: "sim-act-3",
      backendId: -3,
      period: "tarde",
      periodLabel: "Fim de tarde",
      title: `Irrigação complementar · ${primaryCrop}`,
      description: "Ajustar lâmina de água conforme umidade do solo observada.",
      completed: false,
      paused: isRisk && (scenario.technicalDetails.agrofit?.climateTriggers.length ?? 0) > 0,
      pausedReason: isRisk
        ? "Alerta simulado: revisar disponibilidade hídrica antes de irrigar."
        : undefined,
    },
    {
      id: "sim-act-4",
      backendId: -4,
      period: "qualquer-momento",
      periodLabel: "Qualquer momento",
      title: "Manter cobertura morta no solo",
      description: "Protege a terra contra insolação direta e preserva a umidade.",
      completed: false,
    },
  ];

  const phases: CalendarRotationPhase[] = [];
  const highlights: Record<string, CalendarDayHighlight> = {};
  let cursorOffset = 0;

  activeSteps.forEach((step, idx) => {
    const duration = 30;
    const phaseStart = addDaysToIso(startIso, cursorOffset);
    const phaseMid = addDaysToIso(startIso, cursorOffset + 12);
    const phaseEnd = addDaysToIso(startIso, cursorOffset + duration - 1);
    const palette = PHASE_PALETTE[idx % PHASE_PALETTE.length];

    phases.push({
      id: `sim-phase-${idx + 1}`,
      cropName: step.name,
      objectiveLabel:
        idx === 0 ? "Etapa simulada atual" : `Etapa ${idx + 1} (Simulada)`,
      startDate: phaseStart,
      endDate: phaseEnd,
      ...palette,
    });

    highlights[phaseStart] = {
      date: phaseStart,
      milestoneType: "plantio",
      milestoneLabel: `Plantio simulado · ${step.name}`,
      weatherHeadline: weather.headline,
      weatherDetails: weather.details,
      weatherKind: isRisk ? "sun" : "cloud",
      importantNotice: `Início simulado da etapa ${idx + 1} (${step.name}).`,
    };

    highlights[phaseMid] = {
      date: phaseMid,
      milestoneType: "manejo",
      milestoneLabel: `Manejo e inspeção · ${step.name}`,
      weatherHeadline: "Janela de manejo preventivo",
      weatherDetails: weather.details,
      weatherKind: "cloud",
      importantNotice: waterNotice,
    };

    highlights[phaseEnd] = {
      date: phaseEnd,
      milestoneType: "colheita",
      milestoneLabel: `Colheita / transição · ${step.name}`,
      weatherHeadline: "Fechamento do ciclo da etapa",
      weatherDetails: weather.details,
      weatherKind: "sun",
      importantNotice: `Preparar sucessão após ${step.name}.`,
    };

    cursorOffset += duration;
  });

  if (!highlights[todayIso]) {
    highlights[todayIso] = {
      date: todayIso,
      weatherHeadline: weather.headline,
      weatherDetails: weather.details,
      weatherKind: isRisk ? "sun" : "cloud",
      importantNotice: waterNotice,
    };
  }

  const calendarData: AreaCalendarData = {
    areaName: `${areaName} (Simulação)`,
    todayDate: todayIso,
    phases,
    highlights,
  };

  const alertas: AlertaClimaticoResponse[] =
    scenario.technicalDetails.agrofitAlerts.slice(0, 3).map((msg, idx) => ({
      id: -(idx + 1),
      terreno_id: -1,
      tipo_evento: isRisk ? "seca" : "fitossanitario",
      severidade: isRisk ? "alta" : "media",
      titulo: idx === 0 ? "Alerta simulado do cenário" : `Aviso técnico ${idx + 1}`,
      mensagem: msg,
      data_evento: todayIso,
      origem_gatilho: "simulacao_sandbox",
      processado_background: true,
      resumo_adaptacao:
        "Atividades ajustadas virtualmente no Painel do Dia simulado.",
      orientacao_pratica: msg,
      lido: false,
      criado_em: new Date().toISOString(),
    }));

  const relatorio: RelatorioAdaptacaoResponse = {
    terreno_id: -1,
    nome_propriedade: `${areaName} (Simulação)`,
    periodo_inicio: startIso,
    periodo_fim: addDaysToIso(startIso, Math.max(30, cursorOffset - 1)),
    origem_dados: climate?.dataOriginLabel ?? simulacao?.origem ?? "simulacao_sandbox",
    resumo_climatico: {
      umidade_media_solo: Number((moistureNum / 100).toFixed(2)),
      umidade_min_solo: Number((Math.max(0.08, moistureNum / 100 - 0.06)).toFixed(2)),
      umidade_max_solo: Number((Math.min(0.65, moistureNum / 100 + 0.08)).toFixed(2)),
      temperatura_media_c: Number(tempNum.toFixed(1)),
      temperatura_max_c: Number((tempNum + 3.5).toFixed(1)),
      precipitacao_total_mm: Math.round(rainAnnualNum / 4),
      precipitacao_media_mm: Number((rainAnnualNum / 365).toFixed(1)),
      dias_solo_exposto: isRisk ? 8 : 2,
      total_medicoes: 14,
    },
    vigor: {
      indice: Number((viabilityPct / 100).toFixed(2)),
      classificacao: viabilityPct >= 75 ? "Alto" : viabilityPct >= 55 ? "Moderado" : "Baixo",
      tendencia: isRisk ? "Atenção" : "Estável",
      descricao: scenario.aiJustification,
    },
    vulnerabilidade: {
      indice: Number(((100 - viabilityPct) / 100).toFixed(2)),
      nivel: isRisk ? "Alta" : viabilityPct >= 75 ? "Baixa" : "Moderada",
      total_alertas_periodo: alertas.length,
      eventos_criticos: scenario.technicalDetails.agrofit?.climateTriggers ?? [],
      fatores_risco: scenario.cons,
    },
    adaptacoes: {
      total_atividades_periodo: activities.length,
      total_ajustadas_por_alerta: activities.filter((a) => a.paused).length,
      taxa_adaptacao: Number(
        (
          activities.filter((a) => a.paused).length / Math.max(1, activities.length)
        ).toFixed(2)
      ),
      atividades_ajustadas: activities
        .filter((a) => a.paused)
        .map((a, i) => ({
          atividade_id: -(i + 1),
          titulo: a.title,
          tipo_atividade: "irrigacao",
          data_programada: todayIso,
          prioridade: "alta",
          status: "adiada",
          motivo_ajuste: a.pausedReason ?? "Ajuste simulado",
        })),
    },
    alertas_periodo: alertas.map((a) => ({
      id: a.id,
      tipo_evento: a.tipo_evento,
      severidade: a.severidade,
      titulo: a.titulo,
      data_evento: a.data_evento,
      processado_background: a.processado_background,
      resumo_adaptacao: a.resumo_adaptacao,
    })),
    serie_historica: [],
    recomendacoes_manejo: [
      ...scenario.pros,
      ...scenario.technicalDetails.agrofitAlerts.slice(0, 2),
    ],
    comparativo_periodo: {
      data_inicial: startIso,
      data_final: addDaysToIso(startIso, Math.max(30, cursorOffset - 1)),
      umidade_inicial: Number((moistureNum / 100).toFixed(2)),
      umidade_final: Number(
        (Math.min(0.6, moistureNum / 100 + (isRisk ? -0.02 : 0.04))).toFixed(2)
      ),
      variacao_umidade: isRisk ? -0.02 : 0.04,
      variacao_umidade_percentual: isRisk ? -6 : 12,
      temperatura_inicial_c: Number(tempNum.toFixed(1)),
      temperatura_final_c: Number((tempNum + (isRisk ? 1.2 : -0.5)).toFixed(1)),
      variacao_temperatura_c: isRisk ? 1.2 : -0.5,
      precipitacao_inicial_mm: Math.round(rainAnnualNum / 12),
      precipitacao_final_mm: Math.round(rainAnnualNum / 12),
      variacao_precipitacao_mm: 0,
      tendencia_geral: isRisk ? "alerta" : "melhora",
      resumo_comparativo: `Projeção simulada para ${planLabel} com viabilidade de ${viabilityPct}% e risco hídrico ${scenario.technicalDetails.waterRiskLabel ?? "moderado"}.`,
    },
    resumo_ia: scenario.aiJustification,
    explicacao_ia: `${scenario.technicalDetails.nasaClimateNote}\n\n${scenario.technicalDetails.aiDisclaimer ?? AI_DISCLAIMER_DEFAULT}`,
  };

  return {
    planLabel,
    weather,
    cropProgress,
    activities,
    calendarData,
    relatorio,
    alertas,
  };
}


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
  RecommendationCardVariant,
  RotationScenario,
  RotationTrackStep,
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
        waterDemandMm: `${waterMm} mm (${item.water_risk})`,
        nasaClimateNote:
          response.explicacao_textual ||
          `Análise climática (${response.origem}) com risco hídrico ${item.water_risk.toLowerCase()}.`,
        npkTable: buildNpkTable(steps, item.score_breakdown),
        agrofitAlerts:
          response.riscos_identificados.length > 0
            ? response.riscos_identificados
            : [
                "Monitore pragas iniciais nas primeiras 3 semanas após o plantio.",
              ],
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
  weather: AreaWeatherSummary;
  cropProgress: AreaCropProgress;
  activities: AreaActivityItem[];
  calendarData: AreaCalendarData;
}

function addIsoDays(isoDate: string, days: number): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  const date = new Date(Date.UTC(y, (m || 1) - 1, (d || 1) + days));
  return date.toISOString().slice(0, 10);
}

/**
 * Gera dados em memória para Dashboard e Calendário durante o modo simulação,
 * sem persistir terreno ou cronograma no backend.
 */
export function buildSimulatedDashboardAndCalendar(
  scenario: RotationScenario,
  simulacao: SimulacaoResponse | null,
  areaName: string,
  cropHistory?: CropHistoryData | null
): SimulatedDashboardBundle {
  const todayIso = new Date().toISOString().slice(0, 10);
  const cronograma = buildGerarCronogramaPayload(-1, scenario, cropHistory);
  const fallbackDuration = 90;
  const etapas =
    cronograma.plano_rotacao && cronograma.plano_rotacao.length > 0
      ? cronograma.plano_rotacao
      : [
          {
            ordem: 1,
            cultura:
              scenario.steps[0]?.name ??
              cronograma.nome_cultura ??
              "Cultivo",
            duracao_dias: fallbackDuration,
            risco_hidrico: scenario.variant === "risk" ? "alto" : "moderado",
          },
        ];

  const syntheticAtividades: AtividadeCalendarioResponse[] = [];
  let cursorDate = cronograma.data_inicio || todayIso;
  let seqId = -1;

  etapas.forEach((etapa, idx) => {
    const duration = Math.max(30, etapa.duracao_dias || fallbackDuration);
    const stageTag = `[Etapa ${idx + 1} - ${etapa.cultura}]`;
    const isRisky =
      etapa.risco_hidrico === "alto" || scenario.variant === "risk";

    const pushActivity = (
      offsetDays: number,
      tipo: string,
      tituloSuffix: string,
      descricao: string,
      adjusted = false,
      reason?: string
    ) => {
      syntheticAtividades.push({
        id: seqId--,
        terreno_id: null,
        titulo: `${stageTag} ${tituloSuffix}`,
        descricao,
        tipo_atividade: tipo,
        data_programada: addIsoDays(cursorDate, offsetDays),
        prioridade: isRisky ? "alta" : "media",
        status: "pendente",
        concluida: false,
        ajustada_por_alerta: adjusted,
        motivo_ajuste: reason ?? null,
      });
    };

    pushActivity(
      0,
      "plantio",
      `Plantio de ${etapa.cultura}`,
      `Preparo inicial do solo e semeadura de ${etapa.cultura}.`
    );
    pushActivity(
      7,
      "inspecao",
      `Vistoria inicial de ${etapa.cultura}`,
      "Verificar germinação, umidade perto da raiz e sinais iniciais de pragas."
    );
    pushActivity(
      21,
      "irrigacao",
      `Manejo e rega de ${etapa.cultura}`,
      `Controle hídrico (${scenario.technicalDetails.waterDemandMm}).`,
      isRisky,
      isRisky
        ? "Atenção ao risco hídrico simulado: priorize cobertura do solo."
        : undefined
    );
    pushActivity(
      duration - 1,
      "colheita",
      `Colheita de ${etapa.cultura}`,
      `Encerramento estimado do ciclo de ${etapa.cultura}.`
    );

    cursorDate = addIsoDays(cursorDate, duration);
  });

  const firstCropName = etapas[0]?.cultura ?? scenario.focusTag;
  const activities = adaptAtividadesToDashboardItems(
    syntheticAtividades,
    todayIso
  );
  const cropProgress = adaptAtividadesToCropProgress(
    syntheticAtividades,
    todayIso,
    firstCropName
  );
  const calendarData = adaptAtividadesToCalendarData(
    areaName,
    syntheticAtividades,
    [],
    null,
    todayIso
  );

  const headline =
    scenario.variant === "risk"
      ? `Atenção hídrica · ${scenario.focusTag}`
      : `${scenario.optionBadge} · ${scenario.focusTag}`;
  const detailsParts = [
    `Ciclo: ${scenario.technicalDetails.cycleDurationDays}`,
    `Água: ${scenario.technicalDetails.waterDemandMm}`,
  ];
  if (simulacao?.consumo_agua_mm) {
    detailsParts.push(`${Math.round(simulacao.consumo_agua_mm)} mm`);
  }

  const weather: AreaWeatherSummary = {
    headline,
    details: detailsParts.join(" · "),
    weatherNotice:
      simulacao?.explicacao_textual?.trim() ||
      scenario.technicalDetails.nasaClimateNote ||
      scenario.aiJustification,
  };

  return {
    weather,
    cropProgress,
    activities,
    calendarData,
  };
}


import { CROPS_DICTIONARY } from "../data/cropsDictionary";
import i18n from "../i18n";
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
import { COVER_CROP_ALTERNATIVES } from "../features/simulation/utils/recommendationHelpers";
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

const EN_CROP_NAMES_BY_KEY: Record<string, string> = {
  milho: "Corn",
  mandioca: "Cassava",
  "feijao-carioca": "Pinto bean",
  "feijao-caupi": "Cowpea",
  "feijao-de-corda": "Cowpea",
  "feijao-de-porco": "Jack bean",
  soja: "Soybean",
  sorgo: "Sorghum",
  milheto: "Pearl millet",
  crotalaria: "Sunn hemp",
  crotalária: "Sunn hemp",
  amendoim: "Peanut",
  guandu: "Pigeon pea",
  "feijao-guandu": "Pigeon pea",
  girassol: "Sunflower",
  algodao: "Cotton",
  algodão: "Cotton",
  arroz: "Rice",
  cafe: "Coffee",
  café: "Coffee",
  tomate: "Tomato",
  abobora: "Pumpkin",
  abóbora: "Pumpkin",
  "batata-doce": "Sweet potato",
  mucuna: "Velvet bean",
  braquiaria: "Brachiaria",
  braquiária: "Brachiaria",
};

function translateCropStepName(name: string, isEnglish: boolean): string {
  if (isRestStepName(name)) {
    return i18n.t("simulation.restStep");
  }
  if (!isEnglish) return name;

  const trimmed = name.trim();
  if (trimmed.includes("/")) {
    return trimmed
      .split("/")
      .map((part) => translateCropStepName(part.trim(), true))
      .join(" / ");
  }

  const hasCurrentSuffix = /\(atual\)\s*$/i.test(trimmed);
  const baseName = trimmed.replace(/\s*\(atual\)\s*$/i, "").trim();
  const normalized = baseName.toLowerCase();

  let translated = baseName;
  if (EN_CROP_NAMES_BY_KEY[normalized]) {
    translated = EN_CROP_NAMES_BY_KEY[normalized];
  } else {
    const match = CROPS_DICTIONARY.find(
      (crop) =>
        crop.officialName.toLowerCase() === normalized ||
        crop.popularNames.some((alias) => alias.toLowerCase() === normalized)
    );
    if (match && EN_CROP_NAMES_BY_KEY[match.id]) {
      translated = EN_CROP_NAMES_BY_KEY[match.id];
    }
  }

  return hasCurrentSuffix ? `${translated} (Current)` : translated;
}

function localizeCropNamesInText(text: string, isEnglish: boolean): string {
  if (!isEnglish || !text) return text;
  const entries: Array<[string, string]> = [
    ["feijão-caupi", "Cowpea"],
    ["feijao-caupi", "Cowpea"],
    ["feijão-carioca", "Pinto bean"],
    ["feijão-de-porco", "Jack bean"],
    ["feijão-guandu", "Pigeon pea"],
    ["batata-doce", "Sweet potato"],
    ["sorgo", "Sorghum"],
    ["milheto", "Pearl millet"],
    ["amendoim", "Peanut"],
    ["mandioca", "Cassava"],
    ["crotalária", "Sunn hemp"],
    ["milho", "Corn"],
    ["soja", "Soybean"],
    ["braquiária", "Brachiaria"],
    ["gergelim", "Sesame"],
    ["girassol", "Sunflower"],
    ["algodão", "Cotton"],
    ["arroz", "Rice"],
    ["mucuna", "Velvet bean"],
    ["guandu", "Pigeon pea"],
    ["(atual)", "(Current)"],
  ];
  let out = text;
  for (const [pt, en] of entries) {
    const escaped = pt.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    out = out.replace(new RegExp(escaped, "gi"), en);
  }
  return out;
}

function translateWaterRisk(risk: string, isEnglish: boolean): string {
  const lower = (risk || "").trim().toLowerCase();
  if (lower === "low" || lower === "baixo" || lower === "baixa") {
    return isEnglish ? "low" : "baixo";
  }
  if (
    lower === "medium" ||
    lower === "moderate" ||
    lower === "medio" ||
    lower === "médio" ||
    lower === "moderado"
  ) {
    return isEnglish ? "medium" : "médio";
  }
  if (
    lower === "high" ||
    lower === "alto" ||
    lower === "alta" ||
    lower === "critico" ||
    lower === "crítico"
  ) {
    return isEnglish ? "high" : "alto";
  }
  return risk;
}

function mapFocusTag(priority?: PriorityData | null, index = 0): string {
  if (priority?.prioridade.id === "retorno_rapido") {
    return i18n.t("simulation.focusTags.fastReturn");
  }
  if (priority?.prioridade.id === "consumo_racao") {
    return i18n.t("simulation.focusTags.foodFeed");
  }
  if (priority?.prioridade.id === "gastar_minimo") {
    return i18n.t("simulation.focusTags.lowestCost");
  }
  if (priority?.prioridade.id === "limpar_terra") {
    return i18n.t("simulation.focusTags.pestControl");
  }
  if (priority?.prioridade.id === "plantar_especifico") {
    return i18n.t("simulation.focusTags.targetCrop");
  }
  return index === 0
    ? i18n.t("simulation.focusTags.soilFocus")
    : i18n.t("simulation.focusTags.plotBalance");
}

function resolveVariant(
  item: EstrategiaRotacaoSugerida,
  index: number
): RecommendationCardVariant {
  const riskLower = (item.water_risk || "").toLowerCase();
  if (
    item.viability < 0.48 ||
    riskLower.includes("high") ||
    riskLower.includes("critical") ||
    riskLower.includes("alto") ||
    riskLower.includes("critico") ||
    riskLower.includes("crítico")
  ) {
    return "risk";
  }
  if (index === 0) return "recommended";
  return "standard";
}

const PT_FARMER_SIMPLIFICATIONS: Array<[RegExp, string]> = [
  [
    /Aptidão FAO GAEZ v5(?:\s*\([^)]+\))?\s+de\s+\d+%\s*\((?:produtividade atingível média\s*)?(~?\d+\s*kg\/ha)\)\s*(?:com\s+fixação biológica de nitrogênio)?/gi,
    "Combina bem com a terra da região (pode render perto de $1) e ajuda a adubar o solo naturalmente",
  ],
  [
    /Aptidão FAO GAEZ v5(?:\s*\([^)]+\))?\s+de\s+\d+%/gi,
    "Combina bem com a terra da região",
  ],
  [
    /\(GAEZ v5:\s*aptidão\s*\d+%,\s*(~?\d+\s*kg\/ha)\)/gi,
    "— pode render perto de $1 na região",
  ],
  [/com fixação biológica de nitrogênio/gi, "e ajuda a adubar a terra naturalmente"],
  [/fixação biológica de nitrogênio/gi, "ajuda a adubar a terra"],
  [/fixa nitrogênio/gi, "ajuda a adubar a terra"],
  [
    /Mercado estabelecido e cadeia de comercialização consolidada/gi,
    "Tem boa saída e venda fácil na região",
  ],
  [/Melhora a estrutura do solo/gi, "Deixa a terra mais fofa e fértil"],
  [
    /Rústica, cobre o solo e controla nematoides/gi,
    "Planta forte, cobre bem o chão e protege as raízes",
  ],
  [
    /Aproveitamento dos dados ambientais para manejo preventivo de recursos/gi,
    "Usa os dados de chuva e solo da sua área para evitar perdas na safra",
  ],
  [
    /Terreno com prioridade hídrica '([^']+)' frente ao consumo estimado de (\d+)\s*mm/gi,
    "Sua área tem pouca água e essa opção pede mais rega (cerca de $2 mm)",
  ],
];

const EN_BENEFIT_PHRASES: Array<[string, string]> = [
  [
    "Tem boa saída e venda fácil na região",
    "Easy to sell with steady demand in the region",
  ],
  [
    "Mercado estabelecido e cadeia de comercialização consolidada",
    "Easy to sell with steady demand in the region",
  ],
  [
    "Aguenta bem a seca e ajuda a adubar a terra",
    "Handles drought well and naturally enriches the soil",
  ],
  [
    "Alta tolerância à seca, ajuda a adubar a terra",
    "Handles drought well and naturally enriches the soil",
  ],
  [
    "Alta tolerância à seca, fixa nitrogênio",
    "Handles drought well and naturally enriches the soil",
  ],
  ["Deixa a terra mais fofa e fértil", "Makes the soil looser and healthier"],
  ["Melhora a estrutura do solo", "Makes the soil looser and healthier"],
  [
    "Planta forte, cobre bem o chão e protege as raízes",
    "Hardy crop that covers the ground and protects roots",
  ],
  [
    "Rústica, cobre o solo e controla nematoides",
    "Hardy crop that covers the ground and protects roots",
  ],
  [
    "O feijão aduba a terra para o milho que vem depois",
    "Beans enrich the soil for the corn planted next",
  ],
  [
    "Feijão fixa nitrogênio para o milho seguinte",
    "Beans enrich the soil for the corn planted next",
  ],
  ["Prática atual do produtor", "Your current farm practice"],
  [
    "Rotação preferencial cadastrada pelo produtor",
    "Preferred rotation saved by you",
  ],
  [
    "Combina bem com a terra da região",
    "Fits your local soil and weather well",
  ],
  [
    "Usa os dados de chuva e solo da sua área para evitar perdas na safra",
    "Uses your area's rain and soil conditions to protect your harvest",
  ],
  [
    "Usa os dados de chuva e solo da terra para ajudar a não perder a safra",
    "Uses your area's rain and soil conditions to protect your harvest",
  ],
];

function stripRawMarkdownAndFluff(text: string, strategyName = ""): string {
  if (!text) return "";
  let out = text
    .replace(/\*\*(.+?)\*\*/gs, "$1")
    .replace(/__(.+?)__/gs, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    .replace(/\*{2,}/g, "")
    .trim();

  // Remove saudação longa gerada por LLM quando há explicação substantiva após ela
  const withoutGreeting = out
    .replace(
      /^(?:(?:olá|oi|bom dia|boa tarde|boa noite|hello|hi)\b[^.!?\n]*[.!?]\s*)(?:(?:que bom|vamos dar uma olhada|confira abaixo|aqui estão|let's look|here are)[^.!?\n]*[.!?]\s*)*/i,
      ""
    )
    .trim();
  if (withoutGreeting.length >= 25) {
    out = withoutGreeting;
  }

  // Remove prefixo literal "Estratégia: ..." sem perder a leitura
  out = out.replace(/^(?:estratégia|strategy|opção|option)\s*:\s*/i, "").trim();
  if (strategyName) {
    const lower = out.toLowerCase();
    const targetLower = strategyName.toLowerCase();
    if (lower.startsWith(targetLower)) {
      const rest = out.slice(strategyName.length).replace(/^[\s:—-]+/, "").trim();
      if (rest && rest.toLowerCase().includes(targetLower)) {
        out = rest;
      }
    }
  }

  // Remove aviso repetitivo de "decisão final" de dentro de cada card (fica uma única vez no rodapé)
  out = out
    .replace(
      /\s*(?:Lembre-se(?:\s+que|\s*:)?[^.!?\n]*(?:decisão final[^.!?\n]*[.!?]|experiência local[^.!?\n]*[.!?])\s*(?:A decisão final é sempre sua\.?)?)/gi,
      ""
    )
    .replace(/\s*A decisão final é sempre sua\.?\s*/gi, "")
    .replace(
      /\s*(?:Remember(?:\s*:)?[^.!?\n]*(?:final decision[^.!?\n]*[.!?]|local experience[^.!?\n]*[.!?])\s*(?:The final decision is always yours\.?)?)/gi,
      ""
    )
    .replace(/\s*The final decision is always yours\.?\s*/gi, "");

  return out.replace(/[ \t]{2,}/g, " ").trim();
}

function translateKnownBenefit(benefit: string, isEnglish: boolean): string {
  if (!benefit) return benefit;
  let simplified = stripRawMarkdownAndFluff(benefit);
  for (const [pattern, replacement] of PT_FARMER_SIMPLIFICATIONS) {
    simplified = simplified.replace(pattern, replacement);
  }
  if (!isEnglish) return simplified;

  let translated = simplified;
  for (const [pt, en] of EN_BENEFIT_PHRASES) {
    if (translated.includes(pt)) {
      translated = translated.replace(pt, en);
    }
  }
  return translated
    .replace(/pode render perto de\s*(~?\d+\s*kg\/ha)/gi, "expected harvest around $1")
    .replace(/rende perto de\s*(~?\d+\s*kg\/ha)/gi, "expected harvest around $1")
    .replace(/na região/gi, "in your region")
    .replace(/e ajuda a adubar o solo naturalmente/gi, "and naturally enriches the soil")
    .replace(/e ajuda a adubar a terra naturalmente/gi, "and naturally enriches the soil")
    .replace(/e ajuda a adubar o solo/gi, "and helps enrich the soil")
    .replace(/ajuda a adubar a terra/gi, "helps enrich the soil")
    .replace(
      /Sua área tem pouca água e essa opção pede mais rega\s*\((?:cerca de\s*)?([^)]+)\)/gi,
      "Your land is short on water and this option needs more watering ($1)"
    )
    .replace(
      /Sua terra tem pouca água e essa planta pede mais rega\s*\(([^)]+)\)/gi,
      "Your land is short on water and this crop needs more watering ($1)"
    )
    .replace(/—/g, "-");
}

function readBreakdownNumber(
  breakdown: Record<string, unknown> | null | undefined,
  key: string
): number | null {
  if (!breakdown) return null;
  const value = breakdown[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function buildProsAndCons(
  item: EstrategiaRotacaoSugerida,
  response: SimulacaoResponse,
  variant: RecommendationCardVariant,
  isEnglish: boolean
): { pros: string[]; cons: string[] } {
  const pros: string[] = [];
  const cons: string[] = [];
  const pushPro = (text: string) => {
    const clean = text.trim();
    if (clean && !pros.includes(clean) && pros.length < 3) {
      pros.push(clean);
    }
  };
  const pushCon = (text: string) => {
    const clean = text.trim();
    if (clean && !cons.includes(clean) && cons.length < 2) {
      cons.push(clean);
    }
  };

  if (item.benefits) {
    pushPro(localizeCropNamesInText(translateKnownBenefit(item.benefits, isEnglish), isEnglish));
  }

  const waterFit = readBreakdownNumber(item.score_breakdown, "water_fit");
  const heatFit = readBreakdownNumber(item.score_breakdown, "heat_fit");
  const soilBenefit = readBreakdownNumber(item.score_breakdown, "soil_benefit");

  if (waterFit !== null && waterFit >= 0.72) {
    pushPro(
      isEnglish
        ? "Fits the rain and water available on your land"
        : "Combina bem com a quantidade de chuva e água da sua área"
    );
  }
  if (
    soilBenefit !== null &&
    soilBenefit >= 0.75 &&
    !pros.some((p) => /solo|terra|soil|adub|enrich/i.test(p))
  ) {
    pushPro(
      isEnglish
        ? "Helps protect and restore soil strength"
        : "Ajuda a proteger e dar mais força para a terra"
    );
  }
  if (
    heatFit !== null &&
    heatFit >= 0.75 &&
    !pros.some((p) => /calor|seca|heat|drought/i.test(p))
  ) {
    pushPro(
      isEnglish
        ? "Handles warm days in your region well"
        : "Aguenta bem os dias mais quentes da região"
    );
  }

  for (const beneficio of response.beneficios_esperados) {
    if (pros.length >= 2) break;
    // Pula frases técnicas com siglas (ECOCROP/CMIP6/GAEZ) na leitura rápida do card
    if (/\b(GAEZ|ECOCROP|CMIP6|AGROFIT|FAO|LRLM)\b/i.test(beneficio)) continue;
    pushPro(translateKnownBenefit(localizeCropNamesInText(beneficio, isEnglish), isEnglish));
  }
  if (pros.length === 0) {
    pushPro(
      isEnglish
        ? "Helps balance the soil and reduce crop losses."
        : "Ajuda a cuidar da terra e diminuir perdas na roça."
    );
  }

  // Avisos reais desta opção específica (evita misturar risco alto global em opções médias/baixas)
  const riskLower = (item.water_risk || "").trim().toLowerCase();
  if (
    variant === "risk" ||
    riskLower === "high" ||
    riskLower === "alto" ||
    riskLower === "critical" ||
    riskLower === "crítico"
  ) {
    pushCon(
      isEnglish
        ? "Warning: high risk of water shortage — needs more watering if rain fails."
        : "Atenção: risco alto de faltar água — pede mais rega se falhar chuva."
    );
  } else if (
    riskLower === "medium" ||
    riskLower === "moderate" ||
    riskLower === "médio" ||
    riskLower === "medio"
  ) {
    pushCon(
      isEnglish
        ? "Moderate dry-spell risk: keep mulch on the ground and water in cooler hours."
        : "Risco médio de faltar água: mantenha palhada no chão e regue cedo ou à tardinha."
    );
  }

  if (item.score_breakdown?.same_family_as_history === true) {
    pushCon(
      isEnglish
        ? "Same plant family as your last crop — watch leaves closely for pests."
        : "Mesma família do último cultivo — olhe as folhas toda semana para evitar pragas."
    );
  }

  for (const risco of response.riscos_identificados) {
    if (cons.length >= 2) break;
    // Evita repetir ou contradizer o risco hídrico específico da opção já exibido acima
    if (/risco hídrico|water risk|risco (?:alto|médio|baixo) de faltar água|chance of (?:water shortage|dry spells)/i.test(risco)) {
      continue;
    }
    if (/\b(ECOCROP|CMIP6|AGROFIT|GAEZ|z=)\b/i.test(risco)) continue;
    pushCon(translateKnownBenefit(localizeCropNamesInText(risco, isEnglish), isEnglish));
  }

  if (cons.length === 0) {
    pushCon(
      isEnglish
        ? "Keep checking soil moisture and crop leaves each week."
        : "Vale conferir a umidade da terra e olhar as folhas toda semana."
    );
  }

  return { pros, cons };
}

function buildNpkTable(
  steps: RotationTrackStep[],
  breakdown?: Record<string, unknown> | null,
  isEnglish = false
): TechnicalNpkRow[] {
  const hasLegume = steps.some((s) => {
    const n = s.name.toLowerCase();
    return (
      n.includes("feij") ||
      n.includes("bean") ||
      n.includes("cowpea") ||
      n.includes("soy") ||
      n.includes("crotal") ||
      n.includes("sunn") ||
      n.includes("guandu") ||
      n.includes("pigeon") ||
      n.includes("soja") ||
      n.includes("amendoim") ||
      n.includes("peanut")
    );
  });

  const soilBonus =
    typeof breakdown?.soil_health === "number" ? breakdown.soil_health : null;

  return [
    {
      nutrient: isEnglish ? "Nitrogen (N)" : "Nitrogênio (N)",
      requirementLevel: hasLegume
        ? isEnglish
          ? "Low"
          : "Baixo"
        : isEnglish
          ? "High"
          : "Alto",
      impact: hasLegume
        ? isEnglish
          ? "Legumes in the rotation help fix nitrogen in the soil."
          : "Leguminosas da rotação ajudam a fixar nitrogênio no solo."
        : isEnglish
          ? "Requires top-dressing nitrogen fertilization to maintain vigor."
          : "Exige adubação nitrogenada de cobertura para manter vigor.",
    },
    {
      nutrient: isEnglish ? "Phosphorus (P)" : "Fósforo (P)",
      requirementLevel: isEnglish ? "Medium" : "Médio",
      impact:
        soilBonus && soilBonus > 0.7
          ? isEnglish
            ? "Good root uptake with the suggested rotation."
            : "Bom aproveitamento radicular com a rotação sugerida."
          : isEnglish
            ? "Supports early rooting and seedling establishment."
            : "Favorece o enraizamento inicial e pegamento das mudas.",
    },
    {
      nutrient: isEnglish ? "Potassium (K)" : "Potássio (K)",
      requirementLevel: isEnglish ? "Medium" : "Médio",
      impact: isEnglish
        ? "Supports drought resistance and harvest quality."
        : "Contribui para resistência à falta de água e qualidade da colheita.",
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
  const isEnglish = (i18n.language || "").toLowerCase().startsWith("en");
  const lastCropName = onboarding.cropHistory?.naoLembro
    ? null
    : onboarding.cropHistory?.ultimoCultivo
      ? translateCropStepName(
          onboarding.cropHistory.ultimoCultivo.officialName,
          isEnglish
        )
      : null;

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
      translateCropStepName(rawStepNames[0], isEnglish).toLowerCase() !==
        lastCropName.toLowerCase()
        ? [lastCropName, ...rawStepNames]
        : rawStepNames;

    const steps: RotationTrackStep[] = stepNames.map((name, stepIndex) => {
      const isFirstLastCrop =
        lastCropName !== null &&
        stepIndex === 0 &&
        name.toLowerCase() === lastCropName.toLowerCase();
      const isRest = isRestStepName(name);
      const isCover = isCoverStepName(name);

      let statusLabel = i18n.t("simulation.stepStatus.after");
      if (isFirstLastCrop) {
        statusLabel = onboarding.cropHistory?.cultivoEmAndamento
          ? i18n.t("simulation.stepStatus.plantedNow")
          : i18n.t("simulation.stepStatus.alreadyHarvested");
      } else if (
        stepIndex === 0 ||
        (lastCropName !== null && stepIndex === 1)
      ) {
        statusLabel = i18n.t("simulation.stepStatus.next");
      }

      const displayName = translateCropStepName(name, isEnglish);

      return {
        id: `sim-${idx}-step-${stepIndex}-${name.toLowerCase().replace(/\s+/g, "-")}`,
        name: displayName,
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
    const { pros, cons } = buildProsAndCons(item, response, variant, isEnglish);
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
      optionBadge: i18n.t(`simulation.optionBadges.${idx + 1}`, {
        defaultValue: i18n.t("simulation.optionBadge", { count: idx + 1 }),
      }),
      focusTag: mapFocusTag(onboarding.priority, idx),
      variant,
      steps,
      aiJustification: translateKnownBenefit(
        localizeCropNamesInText(
          stripRawMarkdownAndFluff(
            item.explicacao ||
              response.explicacao_ia ||
              response.explicacao_textual ||
              (isEnglish
                ? "Suggested based on what you planted before and local weather."
                : "Sugestão feita pelo que você plantou antes e pelo tempo da região."),
            item.strategy
          ),
          isEnglish
        ),
        isEnglish
      ),
      pros,
      cons,
      ctaLabel:
        variant === "risk"
          ? i18n.t("simulation.chooseAnyway")
          : i18n.t("simulation.choosePlan"),
      technicalDetails: {
        cycleDurationDays: i18n.t("simulation.days", { count: cycleDays }),
        waterDemandMm: `${waterMm} mm (${translateWaterRisk(item.water_risk, isEnglish)})`,
        nasaClimateNote:
          response.explicacao_textual ||
          (isEnglish
            ? `Climate analysis (${response.origem}) with ${translateWaterRisk(item.water_risk, true)} water risk.`
            : `Análise climática (${response.origem}) com risco hídrico ${translateWaterRisk(item.water_risk, false)}.`),
        npkTable: buildNpkTable(steps, item.score_breakdown, isEnglish),
        agrofitAlerts:
          response.riscos_identificados.length > 0
            ? response.riscos_identificados
            : [
                isEnglish
                  ? "Monitor early pests during the first 3 weeks after planting."
                  : "Monitore pragas iniciais nas primeiras 3 semanas após o plantio.",
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

function inferActivityPeriod(
  tipoAtividade: string,
  isEnglish = false
): {
  period: ActivityPeriodId;
  periodLabel: string;
} {
  const tipo = tipoAtividade.trim().toLowerCase();
  if (tipo === "inspecao" || tipo === "plantio" || tipo === "adubacao" || tipo === "colheita") {
    return {
      period: "manha",
      periodLabel: isEnglish ? "Early morning" : "Manhã cedo",
    };
  }
  if (tipo === "irrigacao") {
    return {
      period: "tarde",
      periodLabel: isEnglish ? "Late afternoon" : "Fim de tarde",
    };
  }
  return {
    period: "qualquer-momento",
    periodLabel: isEnglish ? "Anytime" : "Qualquer momento",
  };
}

export function adaptAtividadesToDashboardItems(
  atividades: AtividadeCalendarioResponse[],
  todayIso: string,
  isEnglish = false
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
      atividade.tipo_atividade,
      isEnglish
    );
    return {
      id: String(atividade.id),
      backendId: atividade.id,
      period,
      periodLabel,
      title: localizeCalendarActivityText(atividade.titulo, isEnglish),
      description: atividade.descricao
        ? localizeCalendarActivityText(atividade.descricao, isEnglish)
        : isEnglish
          ? `${atividade.tipo_atividade} activity (${atividade.data_programada}).`
          : `Atividade de ${atividade.tipo_atividade} (${atividade.data_programada}).`,
      completed: atividade.concluida,
      paused: atividade.ajustada_por_alerta && !atividade.concluida,
      pausedReason: atividade.motivo_ajuste
        ? localizeCalendarActivityText(atividade.motivo_ajuste, isEnglish)
        : undefined,
    };
  });
}

const EN_ALERT_TEXT_MAP: Array<[RegExp, string]> = [
  [/Relato de campo:\s*chuva não prevista/gi, "Field report: unexpected rain"],
  [/Relato de campo:\s*falta de chuva/gi, "Field report: lack of rain"],
  [/Relato de campo:\s*ocorrência de praga/gi, "Field report: pest occurrence"],
  [
    /O produtor informou chuva não prevista na área\.\s*Ajustar atividades sensíveis\.?/gi,
    "Producer reported unexpected rain in the area. Adjust sensitive activities.",
  ],
  [
    /O produtor informou que não choveu como esperado\.\s*Avaliar necessidade de irrigação e cobertura\.?/gi,
    "Producer reported it did not rain as expected. Assess irrigation and soil cover needs.",
  ],
  [
    /O produtor identificou sinais de praga na área\.\s*Priorizar inspeção e manejo fitossanitário\.?/gi,
    "Producer identified signs of pests in the area. Prioritize inspection and phytosanitary management.",
  ],
  [
    /Manter o planejamento de rotação atual com monitoramento semanal do calendário\.?/gi,
    "Maintain the current rotation plan with weekly calendar monitoring.",
  ],
  [
    /Priorizar cobertura morta e culturas rústicas resistentes à seca\/calor\.?/gi,
    "Prioritize mulch and hardy crops resistant to drought/heat.",
  ],
  [
    /Acompanhar alertas diários e reforçar irrigação suplementar em horários amenos\.?/gi,
    "Follow daily alerts and reinforce supplemental irrigation during cooler hours.",
  ],
  [
    /O calendário adaptou automaticamente (\d+) atividade\(s\) frente a eventos climáticos no período\.?/gi,
    "The calendar automatically adapted $1 activity(ies) in response to weather events during this period.",
  ],
];

function localizeAlertText(text: string, isEnglish: boolean): string {
  if (!isEnglish || !text) return text;
  let out = text;
  for (const [pattern, replacement] of EN_ALERT_TEXT_MAP) {
    out = out.replace(pattern, replacement);
  }
  return out;
}

export function adaptRelatorioAndAlertasToWeather(
  relatorio: RelatorioAdaptacaoResponse | null,
  alertas: AlertaClimaticoResponse[],
  isEnglish = false
): AreaWeatherSummary {
  const latestAlert = alertas[0];
  const resumo = relatorio?.resumo_climatico;

  const tempStr = resumo
    ? isEnglish
      ? `${Math.round(resumo.temperatura_media_c)}°C (max ${Math.round(resumo.temperatura_max_c)}°C)`
      : `${Math.round(resumo.temperatura_media_c)}°C (máx ${Math.round(resumo.temperatura_max_c)}°C)`
    : isEnglish
      ? "Monitored weather"
      : "Clima monitorado";
  const rainStr = resumo
    ? isEnglish
      ? `Accumulated rain: ${Math.round(resumo.precipitacao_total_mm)} mm`
      : `Chuva acumulada: ${Math.round(resumo.precipitacao_total_mm)} mm`
    : isEnglish
      ? "No heavy rain expected"
      : "Sem chuva forte prevista";

  let headline = isEnglish ? "Stable weather in the area" : "Tempo estável na área";
  if (latestAlert) {
    headline = localizeAlertText(latestAlert.titulo, isEnglish);
  } else if (resumo && resumo.precipitacao_total_mm > 25) {
    headline = isEnglish ? "Recent rain recorded" : "Chuva recente registrada";
  } else if (resumo && resumo.umidade_media_solo < 0.22) {
    headline = isEnglish ? "Low soil moisture" : "Solo com umidade baixa";
  }

  return {
    headline,
    details: `${tempStr} · ${rainStr}`,
    weatherNotice: localizeAlertText(
      latestAlert?.orientacao_pratica ||
        latestAlert?.resumo_adaptacao ||
        relatorio?.recomendacoes_manejo[0] ||
        "",
      isEnglish
    ) || undefined,
    sourceLabel: relatorio?.origem_dados
      ? `${isEnglish ? "Source" : "Fonte"}: ${relatorio.origem_dados}`
      : undefined,
  };
}

export function adaptAtividadesToCropProgress(
  atividades: AtividadeCalendarioResponse[],
  todayIso: string,
  fallbackCropName?: string,
  isEnglish = false
): AreaCropProgress {
  const resolvedFallback =
    fallbackCropName || (isEnglish ? "Active crop" : "Cultivo em andamento");
  if (atividades.length === 0) {
    return {
      cropName: translateCropStepName(resolvedFallback, isEnglish),
      dayLabel: isEnglish ? "No schedule" : "Sem cronograma",
    };
  }

  const sorted = [...atividades].sort((a, b) =>
    a.data_programada.localeCompare(b.data_programada)
  );
  const firstDate = sorted[0].data_programada;
  const startMs = new Date(`${firstDate}T12:00:00`).getTime();
  const todayMs = new Date(`${todayIso}T12:00:00`).getTime();
  const diffDays = Math.max(1, Math.round((todayMs - startMs) / 86400000) + 1);

  const stageMatch = sorted[0].titulo.match(/\[(?:Etapa|Stage)\s+\d+\s*-\s*([^\]]+)\]/i);
  const rawCropName = stageMatch?.[1]?.trim() || resolvedFallback;
  const cropName = translateCropStepName(rawCropName, isEnglish);

  return {
    cropName,
    dayLabel:
      todayIso < firstDate
        ? isEnglish
          ? `Starts ${firstDate}`
          : `Inicia em ${firstDate}`
        : isEnglish
          ? `Day ${diffDays}`
          : `Dia ${diffDays}`,
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

function extractStageCrop(titulo: string, isEnglish = false): string {
  const match = titulo.match(/\[(?:Etapa|Stage)\s+\d+\s*-\s*([^\]]+)\]/i);
  if (match?.[1]) return match[1].trim();
  return isEnglish ? "Main cycle" : "Ciclo principal";
}

function localizeCalendarActivityText(text: string, isEnglish: boolean): string {
  if (!isEnglish || !text) return text;
  let out = text
    .replace(/\[Etapa\s+(\d+)\s*-\s*([^\]]+)\]/gi, "[Stage $1 - $2]")
    .replace(/\[Etapa\s+(\d+)\]/gi, "[Stage $1]")
    .replace(
      /Preparo do canteiro e semeadura\/plantio de\s+([^.]+)\.?/gi,
      "Seedbed preparation and sowing/planting of $1."
    )
    .replace(
      /Preparo inicial do solo e semeadura de\s+([^.]+)\.?/gi,
      "Initial soil preparation and sowing of $1."
    )
    .replace(
      /Rega de estabelecimento para garantir germinação uniforme\.?/gi,
      "Establishment watering to ensure uniform germination."
    )
    .replace(
      /Verificação preventiva de pragas, doenças e umidade do solo\.?/gi,
      "Preventive check for pests, diseases, and soil moisture."
    )
    .replace(
      /Verificar germinação, umidade perto da raiz e sinais iniciais de pragas\.?/gi,
      "Check germination, root-zone moisture, and early signs of pests."
    )
    .replace(
      /Reforço nutricional conforme desenvolvimento vegetativo\.?/gi,
      "Nutritional boost according to vegetative development."
    )
    .replace(
      /Avaliação do ponto ideal e realização da colheita\.?/gi,
      "Evaluation of the ideal harvest point and harvesting."
    )
    .replace(
      /Encerramento estimado do ciclo de\s+([^.]+)\.?/gi,
      "Estimated end of the $1 cycle."
    )
    .replace(/Controle hídrico\s*\(/gi, "Water control (")
    .replace(
      /Atenção ao risco hídrico simulado: priorize cobertura do solo\.?/gi,
      "Attention to simulated water risk: prioritize soil cover."
    )
    .replace(
      /Inspeção de drenagem e escoamento pós-chuva/gi,
      "Post-rain drainage and runoff inspection"
    )
    .replace(
      /Verificar acúmulo de água, erosão em canteiros e condição das raízes após evento de\s+([^.]+)\.?/gi,
      "Check for water pooling, bed erosion, and root condition after $1."
    )
    .replace(
      /Irrigação suplementar e proteção térmica do solo/gi,
      "Supplemental irrigation and soil thermal protection"
    )
    .replace(
      /Reforçar cobertura morta e realizar irrigação nos horários mais frescos para mitigar\s+([^.]+)\.?/gi,
      "Reinforce mulch and irrigate during cooler hours to mitigate $1."
    )
    .replace(
      /Inspeção fitossanitária e manejo de praga/gi,
      "Phytosanitary inspection and pest management"
    )
    .replace(
      /Avaliar nível de infestação nas folhas e caules, isolar reboleiras e definir manejo integrado\.?/gi,
      "Assess infestation level on leaves and stems, isolate hotspots, and define integrated management."
    )
    .replace(
      /Proteção emergencial da lavoura contra\s+/gi,
      "Emergency crop protection against "
    )
    .replace(
      /Adotar barreiras de proteção ou cobertura temporária antes do pico do evento extremo\.?/gi,
      "Set up protective barriers or temporary cover before the extreme event peaks."
    )
    .replace(
      /Preparo conservacionista do solo/gi,
      "Conservation soil preparation"
    )
    .replace(
      /Irrigação suplementar prioritária/gi,
      "Priority supplemental irrigation"
    )
    .replace(
      /Inspeção de umidade radicular/gi,
      "Root-zone moisture inspection"
    )
    .replace(/Plantio em contorno de\s+/gi, "Contour planting of ")
    .replace(
      /Vistoria de drenagem superficial/gi,
      "Surface drainage inspection"
    )
    .replace(/\bPlantio de\s+/gi, "Planting of ")
    .replace(/\bIrrigação inicial\s*—\s*/gi, "Initial irrigation — ")
    .replace(/\bInspeção fitossanitária\s*—\s*/gi, "Phytosanitary inspection — ")
    .replace(/\bAdubação de cobertura\s*—\s*/gi, "Top-dressing fertilization — ")
    .replace(/\bColheita de\s+/gi, "Harvest of ")
    .replace(/\bVistoria inicial de\s+/gi, "Initial inspection of ")
    .replace(/\bManejo e rega de\s+/gi, "Management and watering of ");

  return localizeCropNamesInText(out, true);
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
  todayIso: string,
  isEnglish = false
): AreaCalendarData {
  const grouped = new Map<string, AtividadeCalendarioResponse[]>();
  for (const item of atividades) {
    const cropName = extractStageCrop(item.titulo, isEnglish);
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
        objectiveLabel: isEnglish
          ? idx === 0
            ? "Current plan stage"
            : `Rotation stage ${idx + 1}`
          : idx === 0
            ? "Etapa atual do plano"
            : `Etapa ${idx + 1} da rotação`,
        startDate: dates[0] ?? todayIso,
        endDate: dates[dates.length - 1] ?? todayIso,
        ...palette,
      };
    }
  );

  const highlights: Record<string, CalendarDayHighlight> = {};
  const defaultTemp = relatorio
    ? `${Math.round(relatorio.resumo_climatico.temperatura_media_c)}°C`
    : isEnglish
      ? "Monitored weather"
      : "Clima monitorado";

  for (const item of atividades) {
    const existing = highlights[item.data_programada];
    const milestoneType = mapMilestoneType(item.tipo_atividade);
    const localizedTitle = localizeCalendarActivityText(item.titulo, isEnglish);
    const localizedDesc = localizeCalendarActivityText(
      item.descricao || item.titulo,
      isEnglish
    );
    const localizedReason = item.motivo_ajuste
      ? localizeCalendarActivityText(item.motivo_ajuste, isEnglish)
      : undefined;

    highlights[item.data_programada] = {
      date: item.data_programada,
      milestoneType: existing?.milestoneType ?? milestoneType,
      milestoneLabel: existing?.milestoneLabel ?? localizedTitle,
      weatherHeadline:
        existing?.weatherHeadline ??
        (isEnglish ? "Scheduled activity" : "Atividade programada"),
      weatherDetails:
        existing?.weatherDetails ?? `${defaultTemp} · ${localizedDesc}`,
      weatherKind: existing?.weatherKind ?? "sun",
      importantNotice:
        existing?.importantNotice ??
        (item.ajustada_por_alerta ? localizedReason : undefined),
    };
  }

  for (const alerta of alertas) {
    const existing = highlights[alerta.data_evento];
    const isRain = alerta.tipo_evento.includes("chuva");
    const localizedHeadline = localizeAlertText(alerta.titulo, isEnglish);
    const localizedMessage = localizeAlertText(alerta.mensagem, isEnglish);
    highlights[alerta.data_evento] = {
      date: alerta.data_evento,
      milestoneType: existing?.milestoneType,
      milestoneLabel: existing?.milestoneLabel,
      weatherHeadline: localizedHeadline,
      weatherDetails: localizedMessage,
      weatherKind: isRain ? "rain" : "cloud",
      importantNotice:
        alerta.orientacao_pratica ||
        alerta.resumo_adaptacao ||
        localizedMessage,
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
  todayIso: string,
  isEnglish = false
): AlertaGatilhoRequest {
  const idioma = isEnglish ? "en" : "pt";
  if (reportId === "choveu_nao_previsto") {
    return {
      terreno_id: terrenoId,
      tipo_evento: "chuva_intensa",
      severidade: "alta",
      data_evento: todayIso,
      origem_gatilho: "manual",
      titulo: isEnglish
        ? "Field report: unexpected rain"
        : "Relato de campo: chuva não prevista",
      mensagem: isEnglish
        ? "Producer reported unexpected rain in the area. Adjust sensitive activities."
        : "O produtor informou chuva não prevista na área. Ajustar atividades sensíveis.",
      dias_adiamento: 2,
      idioma,
    };
  }

  if (reportId === "nao_choveu_esperado") {
    return {
      terreno_id: terrenoId,
      tipo_evento: "seca",
      severidade: "alta",
      data_evento: todayIso,
      origem_gatilho: "manual",
      titulo: isEnglish
        ? "Field report: lack of rain"
        : "Relato de campo: falta de chuva",
      mensagem: isEnglish
        ? "Producer reported it did not rain as expected. Assess irrigation and soil cover needs."
        : "O produtor informou que não choveu como esperado. Avaliar necessidade de irrigação e cobertura.",
      dias_adiamento: 1,
      idioma,
    };
  }

  return {
    terreno_id: terrenoId,
    tipo_evento: "praga",
    severidade: "alta",
    data_evento: todayIso,
    origem_gatilho: "manual",
    titulo: isEnglish
      ? "Field report: pest occurrence"
      : "Relato de campo: ocorrência de praga",
    mensagem: isEnglish
      ? "Producer identified signs of pests in the area. Prioritize inspection and phytosanitary management."
      : "O produtor identificou sinais de praga na área. Priorizar inspeção e manejo fitossanitário.",
    dias_adiamento: 1,
    idioma,
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
  cropHistory?: CropHistoryData | null,
  isEnglish = false
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
    todayIso,
    isEnglish
  );
  const cropProgress = adaptAtividadesToCropProgress(
    syntheticAtividades,
    todayIso,
    firstCropName,
    isEnglish
  );
  const calendarData = adaptAtividadesToCalendarData(
    areaName,
    syntheticAtividades,
    [],
    null,
    todayIso,
    isEnglish
  );

  const headline =
    scenario.variant === "risk"
      ? `${isEnglish ? "Water attention" : "Atenção hídrica"} · ${scenario.focusTag}`
      : `${scenario.optionBadge} · ${scenario.focusTag}`;
  const detailsParts = [
    `${isEnglish ? "Cycle" : "Ciclo"}: ${scenario.technicalDetails.cycleDurationDays}`,
    `${isEnglish ? "Water" : "Água"}: ${scenario.technicalDetails.waterDemandMm}`,
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


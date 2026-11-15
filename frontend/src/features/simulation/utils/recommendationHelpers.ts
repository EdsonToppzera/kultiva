import type { CropHistoryData } from "../../onboarding/types/cropHistory.types";
import type { PriorityData } from "../../onboarding/types/priority.types";
import type { SoilTypeData } from "../../onboarding/types/soilType.types";
import type { WaterDistributionData } from "../../onboarding/types/waterDistribution.types";
import type {
  AreaSummaryInfo,
  RotationAlternativeCrop,
} from "../types/recommendations.types";

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

/**
 * Constrói o resumo da área a partir das escolhas do onboarding.
 */
export function buildAreaSummaryFromOnboarding({
  cropHistory,
  waterDistribution,
  soilType,
  priority,
}: {
  cropHistory: CropHistoryData | null;
  waterDistribution: WaterDistributionData | null;
  soilType: SoilTypeData | null;
  priority: PriorityData | null;
}): AreaSummaryInfo {
  const lastCrop = cropHistory?.ultimoCultivo ?? null;
  const lastCropName = lastCrop?.officialName ?? "Sem histórico";
  const waterTitle = waterDistribution?.metodoIrrigacao.title ?? "";
  const soilTitle = soilType?.tipoSolo.title ?? "";
  const priorityTitle = priority?.prioridade.title ?? "";

  return {
    areaName: "",
    lastCropName,
    tagsLine: [waterTitle, soilTitle, priorityTitle].filter(Boolean).join(" · "),
  };
}

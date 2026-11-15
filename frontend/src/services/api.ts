import { CROPS_DICTIONARY } from "../data/cropsDictionary";
import type { CropHistoryData, CropOption } from "../features/onboarding/types/cropHistory.types";
import type { WaterDistributionId } from "../features/onboarding/types/waterDistribution.types";

const RAW_API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.trim() || "http://localhost:8000/api/v1";

export const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, "");
export const DEFAULT_USUARIO_ID = 1;

export interface CoordenadaApi {
  lat: number;
  lng: number;
}

export interface TerrenoCreatePayload {
  nome_propriedade: string;
  usuario_id: number;
  coordenadas_poligono: CoordenadaApi[];
  area_hectares?: number;
  localizacao_central?: CoordenadaApi;
  prioridades?: Record<string, unknown>;
}

export interface TerrenoUpdatePayload {
  nome_propriedade?: string;
  usuario_id?: number;
  coordenadas_poligono?: CoordenadaApi[];
  area_hectares?: number;
  localizacao_central?: CoordenadaApi;
  prioridades?: Record<string, unknown>;
}

export interface TerrenoResponse {
  id: number;
  nome_propriedade: string;
  usuario_id: number;
  coordenadas_poligono: CoordenadaApi[];
  area_hectares?: number | null;
  localizacao_central?: CoordenadaApi | null;
  prioridades?: Record<string, unknown> | null;
}

export interface EstrategiaRotacaoSugerida {
  strategy: string;
  viability: number;
  water_risk: string;
  benefits?: string | null;
  score_breakdown?: Record<string, unknown> | null;
  explicacao?: string | null;
}

export interface EtapaRotacaoSimulada {
  ordem: number;
  cultura: string;
  duracao_dias: number;
  consumo_agua_estimado_mm: number;
  viabilidade_score: number;
  risco_hidrico: string;
}

export interface SimulacaoRequestPayload {
  terreno_id?: number;
  nome_propriedade?: string;
  coordenadas_poligono?: CoordenadaApi[];
  cultura_id?: number;
  nome_cultura?: string;
  culturas_rotacao?: string[];
  historico_cultivos?: string[] | Record<string, unknown>;
  perfil_climatico?: string;
  prioridades?: Record<string, unknown>;
  dados_solo?: Record<string, unknown>;
  dados_climaticos?: Record<string, unknown>;
}

export interface SimulacaoResponse {
  terreno_id?: number | null;
  nome_propriedade: string;
  cultura_principal: string;
  viability_score: number;
  water_risk: string;
  tempo_colheita_dias: number;
  consumo_agua_mm: number;
  metricas_geoespaciais: Record<string, unknown>;
  beneficios_esperados: string[];
  riscos_identificados: string[];
  explicacao_ia: string;
  explicacao_textual: string;
  origem: string;
  fallback_usado: boolean;
  rotacoes_sugeridas: EstrategiaRotacaoSugerida[];
  plano_rotacao: EtapaRotacaoSimulada[];
}

export interface DemoSeedResponse {
  status: string;
  reset_executado: boolean;
  idempotente: boolean;
  usuario_id: number;
  terrenos_ids: number[];
  culturas_total: number;
  rotacoes_total: number;
  metricas_total: number;
  atividades_total: number;
  alertas_total: number;
  resumo: string;
}

export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(message: string, status: number, detail?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const response = await fetch(`${API_BASE_URL}${normalizedPath}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const errorBody = (await response.json()) as { detail?: unknown };
      if (typeof errorBody?.detail === "string") {
        detail = errorBody.detail;
      }
    } catch {
      // Resposta sem payload JSON estruturado
    }
    throw new ApiError(
      detail || `Erro na API (${response.status})`,
      response.status,
      detail
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  if (!text) {
    return undefined as T;
  }

  return JSON.parse(text) as T;
}

export function listarTerrenos(usuarioId?: number): Promise<TerrenoResponse[]> {
  const query =
    usuarioId !== undefined ? `?usuario_id=${encodeURIComponent(usuarioId)}` : "";
  return requestJson<TerrenoResponse[]>(`/terrenos/${query}`);
}

export function buscarTerreno(terrenoId: number): Promise<TerrenoResponse> {
  return requestJson<TerrenoResponse>(`/terrenos/${terrenoId}`);
}

export function criarTerreno(
  payload: TerrenoCreatePayload
): Promise<TerrenoResponse> {
  return requestJson<TerrenoResponse>("/terrenos/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function atualizarTerreno(
  terrenoId: number,
  payload: TerrenoUpdatePayload
): Promise<TerrenoResponse> {
  return requestJson<TerrenoResponse>(`/terrenos/${terrenoId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function excluirTerreno(terrenoId: number): Promise<void> {
  return requestJson<void>(`/terrenos/${terrenoId}`, {
    method: "DELETE",
  });
}

export function simularRotacao(
  payload: SimulacaoRequestPayload
): Promise<SimulacaoResponse> {
  return requestJson<SimulacaoResponse>("/simular-rotacao", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function executarDemoSeed(reset = false): Promise<DemoSeedResponse> {
  const query = `?reset=${reset ? "true" : "false"}`;
  return requestJson<DemoSeedResponse>(`/demo/seed${query}`, {
    method: "POST",
  });
}

export function formatarAreaHectares(areaHectares?: number | null): string {
  if (
    areaHectares === undefined ||
    areaHectares === null ||
    Number.isNaN(areaHectares) ||
    areaHectares <= 0
  ) {
    return "Área a definir";
  }

  const isCloseToInt = Math.abs(areaHectares - Math.round(areaHectares)) < 0.05;
  const formatted = isCloseToInt
    ? String(Math.round(areaHectares))
    : areaHectares.toLocaleString("pt-BR", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 2,
      });

  const unit = Math.abs(areaHectares - 1) < 0.05 ? "hectare" : "hectares";
  return `${formatted} ${unit}`;
}

export function converterHistoricoParaLista(
  cropHistory?: CropHistoryData | null
): string[] {
  if (!cropHistory || cropHistory.naoLembro) {
    return [];
  }

  const lista: string[] = [];
  if (cropHistory.cultivoAnterior?.officialName) {
    lista.push(cropHistory.cultivoAnterior.officialName);
  }
  if (cropHistory.ultimoCultivo?.officialName) {
    lista.push(cropHistory.ultimoCultivo.officialName);
  }
  return lista;
}

const IRRIGATION_PRIORITY_MAP: Record<
  WaterDistributionId,
  { agua: "escassa" | "moderada" | "abundante"; water_conservation: boolean }
> = {
  chuva: { agua: "escassa", water_conservation: true },
  caminhao_pipa: { agua: "escassa", water_conservation: true },
  poco_caixa: { agua: "moderada", water_conservation: false },
  gotejamento: { agua: "moderada", water_conservation: true },
  aspersao: { agua: "abundante", water_conservation: false },
  sulco: { agua: "abundante", water_conservation: false },
};

export function mapearPrioridadesIrrigacao(
  metodoId: WaterDistributionId,
  cropHistory?: CropHistoryData | null
): Record<string, unknown> {
  const mapped = IRRIGATION_PRIORITY_MAP[metodoId];
  const prioridades: Record<string, unknown> = {
    agua: mapped.agua,
    water_conservation: mapped.water_conservation,
    metodo_irrigacao: metodoId,
  };

  if (cropHistory) {
    prioridades.historico_cultivos = converterHistoricoParaLista(cropHistory);
    prioridades.nao_lembra_historico = cropHistory.naoLembro;
  }

  return prioridades;
}

function findCropOptionByName(name: string): CropOption | null {
  const normalized = name.trim().toLowerCase();
  if (!normalized) return null;

  return (
    CROPS_DICTIONARY.find(
      (item) =>
        item.officialName.toLowerCase() === normalized ||
        item.id.toLowerCase() === normalized ||
        item.popularNames.some((alias) => alias.toLowerCase() === normalized)
    ) ?? {
      id: normalized.replace(/\s+/g, "-"),
      officialName: name.trim(),
      popularNames: [name.trim()],
      imageUrl: null,
    }
  );
}

export function restaurarHistoricoDoTerreno(
  prioridades?: Record<string, unknown> | null
): Partial<CropHistoryData> | undefined {
  if (!prioridades) return undefined;

  const naoLembro = Boolean(prioridades.nao_lembra_historico);
  const rawList = Array.isArray(prioridades.historico_cultivos)
    ? prioridades.historico_cultivos
        .map((item) => String(item).trim())
        .filter(Boolean)
    : [];

  if (!naoLembro && rawList.length === 0) {
    return undefined;
  }

  if (naoLembro) {
    return {
      ultimoCultivo: null,
      cultivoAnterior: null,
      naoLembro: true,
    };
  }

  if (rawList.length === 1) {
    return {
      ultimoCultivo: findCropOptionByName(rawList[0]),
      cultivoAnterior: null,
      naoLembro: false,
    };
  }

  return {
    cultivoAnterior: findCropOptionByName(rawList[rawList.length - 2]),
    ultimoCultivo: findCropOptionByName(rawList[rawList.length - 1]),
    naoLembro: false,
  };
}

const VALID_WATER_IDS: WaterDistributionId[] = [
  "chuva",
  "poco_caixa",
  "caminhao_pipa",
  "gotejamento",
  "aspersao",
  "sulco",
];

export function extrairMetodoIrrigacao(
  prioridades?: Record<string, unknown> | null
): WaterDistributionId | null {
  if (!prioridades) return null;

  const metodo = prioridades.metodo_irrigacao;
  if (
    typeof metodo === "string" &&
    VALID_WATER_IDS.includes(metodo as WaterDistributionId)
  ) {
    return metodo as WaterDistributionId;
  }

  const agua = typeof prioridades.agua === "string" ? prioridades.agua.toLowerCase() : "";
  if (agua === "escassa" || agua === "baixa" || agua === "limitada") {
    return "chuva";
  }
  if (agua === "moderada") {
    return "poco_caixa";
  }
  if (agua === "abundante") {
    return "aspersao";
  }

  return null;
}

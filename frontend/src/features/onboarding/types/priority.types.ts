import type { LucideIcon } from "lucide-react";
import type { CropOption } from "./cropHistory.types";

export type PriorityId =
  | "recuperar_terra"
  | "retorno_rapido"
  | "consumo_racao"
  | "plantar_especifico"
  | "gastar_minimo"
  | "limpar_terra";

export interface PriorityOption {
  id: PriorityId;
  title: string;
  subtitle: string;
  icon: LucideIcon;
  requiresCropSelection?: boolean;
}

export interface PriorityData {
  prioridade: PriorityOption;
  culturaDesejada: CropOption | null;
}


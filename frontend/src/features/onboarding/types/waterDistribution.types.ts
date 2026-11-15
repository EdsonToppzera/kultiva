import type { LucideIcon } from "lucide-react";

export type WaterDistributionId =
  | "chuva"
  | "poco_caixa"
  | "caminhao_pipa"
  | "gotejamento"
  | "aspersao"
  | "sulco";

export interface WaterDistributionOption {
  id: WaterDistributionId;
  title: string;
  subtitle: string;
  icon: LucideIcon;
}

export interface WaterDistributionData {
  metodoIrrigacao: WaterDistributionOption;
}


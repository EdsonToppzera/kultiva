export type SoilTypeId =
  | "areia"
  | "barro"
  | "terra_preta"
  | "cascalho"
  | "terra_mista";

export interface SoilTypeOption {
  id: SoilTypeId;
  title: string;
  subtitle: string;
  imageUrl?: string | null;
  fallbackColor: string;
}

export interface SoilHandTestItem {
  id: SoilTypeId;
  name: string;
  description: string;
  swatchColor: string;
}

export interface SoilTypeData {
  tipoSolo: SoilTypeOption;
}


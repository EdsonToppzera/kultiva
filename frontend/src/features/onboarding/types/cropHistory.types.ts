export interface CropOption {
  id: string;
  officialName: string;
  popularNames: string[];
  imageUrl?: string | null;
}

export interface CropHistoryData {
  ultimoCultivo: CropOption | null;
  cultivoAnterior: CropOption | null;
  naoLembro: boolean;
}

export type NetworkSyncStatus = "salvo" | "sincronizando" | "offline";


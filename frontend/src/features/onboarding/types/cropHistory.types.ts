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
  cultivoEmAndamento?: boolean;
  dataInicioCultivo?: string | null;
}

export type NetworkSyncStatus = "salvo" | "sincronizando" | "offline";


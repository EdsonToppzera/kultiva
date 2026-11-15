import { RefreshCw, Wifi, WifiOff } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { NetworkSyncStatus } from "../features/onboarding/types/cropHistory.types";
import { useNetworkStatus } from "../hooks/useNetworkStatus";
import { cn } from "../lib/utils";
import { Badge } from "./ui/badge";

const NETWORK_BADGE_CONFIG: Record<
  NetworkSyncStatus,
  {
    labelKey: string;
    variant: "saved" | "offline" | "outline";
    icon: typeof Wifi;
  }
> = {
  salvo: { labelKey: "network.saved", variant: "saved", icon: Wifi },
  sincronizando: {
    labelKey: "network.saving",
    variant: "outline",
    icon: RefreshCw,
  },
  offline: { labelKey: "network.offline", variant: "offline", icon: WifiOff },
};

export interface NetworkStatusBadgeProps {
  /** Estado opcional de sincronização em andamento. Nunca sobrescreve offline real. */
  status?: NetworkSyncStatus;
  isSyncing?: boolean;
  className?: string;
}

/**
 * Badge unificada de conectividade que reflete o estado real da rede do usuário.
 */
export function NetworkStatusBadge({
  status,
  isSyncing = false,
  className,
}: NetworkStatusBadgeProps) {
  const { t } = useTranslation();
  const isOnline = useNetworkStatus();

  const resolvedStatus: NetworkSyncStatus = !isOnline
    ? "offline"
    : isSyncing || status === "sincronizando"
      ? "sincronizando"
      : status === "offline"
        ? "offline"
        : "salvo";

  const badgeInfo = NETWORK_BADGE_CONFIG[resolvedStatus];
  const Icon = badgeInfo.icon;

  return (
    <Badge variant={badgeInfo.variant} aria-live="polite" className={className}>
      <Icon
        className={cn(
          "h-3.5 w-3.5 shrink-0",
          resolvedStatus === "sincronizando" && "animate-spin"
        )}
        aria-hidden="true"
      />
      <span>{t(badgeInfo.labelKey)}</span>
    </Badge>
  );
}


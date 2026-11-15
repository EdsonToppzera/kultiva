import * as React from "react";
import {
  ArrowRight,
  Check,
  ChevronLeft,
  CloudRain,
  Droplets,
  Pipette,
  RefreshCw,
  ShowerHead,
  Truck,
  Waves,
  Wifi,
  WifiOff,
} from "lucide-react";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import { RadioGroup, RadioGroupItem } from "../../../components/ui/radio-group";
import { cn } from "../../../lib/utils";
import type { NetworkSyncStatus } from "../types/cropHistory.types";
import type {
  WaterDistributionData,
  WaterDistributionId,
  WaterDistributionOption,
} from "../types/waterDistribution.types";

export const WATER_DISTRIBUTION_OPTIONS: WaterDistributionOption[] = [
  {
    id: "chuva",
    title: "Chuva",
    subtitle: "Sequeiro, sem irrigação",
    icon: CloudRain,
  },
  {
    id: "poco_caixa",
    title: "Poço ou caixa-d'água",
    subtitle: "Rega quando precisa",
    icon: Droplets,
  },
  {
    id: "caminhao_pipa",
    title: "Caminhão-pipa",
    subtitle: "Água comprada ou trazida de fora.",
    icon: Truck,
  },
  {
    id: "gotejamento",
    title: "Gotejamento",
    subtitle: "Água aos poucos, junto à raiz",
    icon: Pipette,
  },
  {
    id: "aspersao",
    title: "Aspersão",
    subtitle: "Jatos de água por cima das plantas.",
    icon: ShowerHead,
  },
  {
    id: "sulco",
    title: "Sulco",
    subtitle: "Água correndo por valetas na terra.",
    icon: Waves,
  },
];

const NETWORK_BADGE_CONFIG: Record<
  NetworkSyncStatus,
  {
    label: string;
    variant: "saved" | "offline" | "outline";
    icon: React.ComponentType<{ className?: string }>;
  }
> = {
  salvo: { label: "Salvo", variant: "saved", icon: Wifi },
  sincronizando: { label: "Salvando", variant: "outline", icon: RefreshCw },
  offline: { label: "Sem internet", variant: "offline", icon: WifiOff },
};

export interface WaterDistributionStepProps {
  options?: WaterDistributionOption[];
  initialValue?: WaterDistributionId | null;
  networkStatus?: NetworkSyncStatus;
  onBack?: () => void;
  onContinue?: (data: WaterDistributionData) => void;
}

/**
 * Tela de Onboarding — Passo 2: Distribuição Hídrica.
 * Permite selecionar o método único de irrigação ou captação de água via cartões em RadioGroup.
 */
export function WaterDistributionStep({
  options = WATER_DISTRIBUTION_OPTIONS,
  initialValue = null,
  networkStatus,
  onBack,
  onContinue,
}: WaterDistributionStepProps) {
  const [isOnline, setIsOnline] = React.useState<boolean>(() =>
    typeof navigator !== "undefined" ? navigator.onLine : true
  );

  React.useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const resolvedNetworkStatus: NetworkSyncStatus =
    networkStatus ?? (isOnline ? "salvo" : "offline");

  const [selectedId, setSelectedId] = React.useState<WaterDistributionId | null>(
    initialValue
  );

  const badgeInfo = NETWORK_BADGE_CONFIG[resolvedNetworkStatus];
  const NetworkIcon = badgeInfo.icon;

  const selectedOption = React.useMemo(
    () => options.find((item) => item.id === selectedId) ?? null,
    [options, selectedId]
  );

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedOption) return;
    onContinue?.({ metodoIrrigacao: selectedOption });
  };

  return (
    <div className="min-h-dvh w-full bg-[#F7F6F0] text-[#1F1C18] md:flex md:items-center md:justify-center md:bg-[#EFECE3] md:p-6">
      <form
        onSubmit={handleSubmit}
        className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-between bg-[#F7F6F0] px-5 pb-8 pt-6 md:min-h-[680px] md:rounded-3xl md:border md:border-[#E6E4DA] md:px-7 md:py-8 md:shadow-sm"
      >
        <div>
          {/* Header */}
          <header className="flex items-center justify-between gap-4">
            <span className="text-2xl font-extrabold tracking-tight text-[#511D4E]">
              Kultiva
            </span>

            <Badge variant={badgeInfo.variant} aria-live="polite">
              <NetworkIcon
                className={cn(
                  "h-3.5 w-3.5",
                  resolvedNetworkStatus === "sincronizando" && "animate-spin"
                )}
                aria-hidden="true"
              />
              <span>{badgeInfo.label}</span>
            </Badge>
          </header>

          {/* Indicador de Progresso */}
          <section aria-label="Progresso do cadastro" className="mt-6">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold uppercase tracking-wider text-[#6D6960]">
                SUA ÁREA
              </span>
              <span className="font-medium text-[#511D4E]">Passo 2 de 4</span>
            </div>

            <div
              role="progressbar"
              aria-label="Passo 2 de 4"
              aria-valuemin={1}
              aria-valuemax={4}
              aria-valuenow={2}
              className="mt-2 grid grid-cols-4 gap-2"
            >
              <span className="h-1 rounded-full bg-[#511D4E]" />
              <span className="h-1 rounded-full bg-[#511D4E]" />
              <span className="h-1 rounded-full bg-[#E3E1D8]" />
              <span className="h-1 rounded-full bg-[#E3E1D8]" />
            </div>
          </section>

          {/* Conteúdo Principal */}
          <main className="mt-8">
            <h1 className="text-[26px] font-bold leading-tight tracking-tight text-[#511D4E] sm:text-[28px]">
              Distribuição Hídrica
            </h1>
            <p className="mt-1.5 text-sm text-[#6D6960] sm:text-base">
              Indique como a água chega a sua plantação.
            </p>

            <RadioGroup
              aria-label="Distribuição Hídrica"
              value={selectedId}
              onValueChange={(value) =>
                setSelectedId(value as WaterDistributionId)
              }
              className="mt-6 flex flex-col gap-3"
            >
              {options.map((option) => {
                const OptionIcon = option.icon;

                return (
                  <RadioGroupItem
                    key={option.id}
                    value={option.id}
                    className={cn(
                      "flex min-h-[72px] w-full items-center justify-between gap-3 rounded-2xl border px-4 py-3.5 text-left transition-colors",
                      selectedId === option.id
                        ? "border-[#511D4E] bg-[#511D4E]/[0.06] ring-1 ring-[#511D4E]"
                        : "border-[#E6E4DA] bg-white hover:border-[#511D4E]/50 hover:bg-white/95"
                    )}
                  >
                    {({ checked }) => (
                      <>
                        <div className="flex min-w-0 items-center gap-3.5">
                          <div
                            className={cn(
                              "flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-colors",
                              checked
                                ? "bg-[#511D4E]/12 text-[#511D4E]"
                                : "bg-[#F7F6F0] text-[#6D6960]"
                            )}
                            aria-hidden="true"
                          >
                            <OptionIcon className="h-5 w-5" />
                          </div>

                          <div className="min-w-0">
                            <p
                              className={cn(
                                "text-base font-bold leading-snug",
                                checked ? "text-[#511D4E]" : "text-[#1F1C18]"
                              )}
                            >
                              {option.title}
                            </p>
                            <p className="mt-0.5 text-xs text-[#6D6960] sm:text-sm">
                              {option.subtitle}
                            </p>
                          </div>
                        </div>

                        <span
                          aria-hidden="true"
                          className={cn(
                            "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                            checked
                              ? "border-[#511D4E] bg-[#511D4E] text-white"
                              : "border-[#D2CFC4] bg-white"
                          )}
                        >
                          {checked && <Check className="h-3.5 w-3.5 stroke-[3]" />}
                        </span>
                      </>
                    )}
                  </RadioGroupItem>
                );
              })}
            </RadioGroup>
          </main>
        </div>

        {/* Footer */}
        <footer className="mt-8 flex flex-col items-center gap-3 pt-4">
          <Button
            type="submit"
            variant="primary"
            size="lg"
            disabled={!selectedOption}
            className="w-full"
          >
            <span>Continuar</span>
            <ArrowRight className="h-5 w-5" aria-hidden="true" />
          </Button>

          <Button
            type="button"
            variant="ghost"
            onClick={onBack}
            className="w-full max-w-[200px] text-sm font-semibold text-[#511D4E]"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            <span>Voltar</span>
          </Button>
        </footer>
      </form>
    </div>
  );
}

export default WaterDistributionStep;


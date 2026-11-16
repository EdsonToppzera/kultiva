import { useTranslation } from "react-i18next";
import { X } from "lucide-react";
import { useSimulation } from "../contexts/SimulationContext";
import { cn } from "../lib/utils";

export interface CancelSimulationButtonProps {
  onClick?: () => void;
  className?: string;
}

/**
 * Botão compacto para encerrar o modo simulação a partir de qualquer tela ativa.
 */
export function CancelSimulationButton({
  onClick,
  className,
}: CancelSimulationButtonProps) {
  const { t } = useTranslation();
  const { isSimulationMode, cancelSimulation } = useSimulation();
  const handleCancel = onClick ?? (isSimulationMode ? cancelSimulation : null);

  if (!handleCancel) return null;

  return (
    <button
      type="button"
      onClick={handleCancel}
      className={cn(
        "inline-flex shrink-0 cursor-pointer items-center gap-1 whitespace-nowrap rounded-full border border-[#E6E4DA] bg-white px-2.5 py-1 text-xs font-semibold text-[#511D4E] shadow-2xs transition-colors hover:border-[#511D4E]/50 hover:bg-[#F7F6F0] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E]",
        className
      )}
    >
      <X className="h-3.5 w-3.5 text-[#511D4E]" aria-hidden="true" />
      <span>{t("dashboard.cancelSimulation")}</span>
    </button>
  );
}

export interface SimulationBannerProps {
  className?: string;
}

/**
 * Faixa discreta exibida quando o modo simulação está ativo em telas sem cabeçalho de área.
 */
export function SimulationBanner({ className }: SimulationBannerProps) {
  const { t } = useTranslation();
  const { isSimulationMode, cancelSimulation } = useSimulation();

  if (!isSimulationMode || !cancelSimulation) return null;

  return (
    <div
      role="region"
      aria-label={t("simulation.activeModeLabel")}
      className={cn(
        "flex items-center justify-between gap-2 rounded-2xl border border-[#CAD17A]/70 bg-[#FCF59B]/35 px-3.5 py-2",
        className
      )}
    >
      <span className="truncate text-xs font-semibold text-[#511D4E]">
        {t("simulation.activeModeLabel")}
      </span>
      <CancelSimulationButton onClick={cancelSimulation} />
    </div>
  );
}

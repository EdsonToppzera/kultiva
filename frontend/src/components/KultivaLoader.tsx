import { cn } from "../lib/utils";

const LOADER_WIDTH_CLASS = {
  sm: "w-[88px]",
  md: "w-[130px]",
  lg: "w-[170px]",
} as const;

export interface KultivaLoaderProps {
  fullscreen?: boolean;
  size?: "sm" | "md" | "lg";
  label?: string;
  className?: string;
  onClosePreview?: () => void;
}

export function KultivaLoader({
  fullscreen = true,
  size,
  label = "Carregando...",
  className,
  onClosePreview,
}: KultivaLoaderProps) {
  const resolvedSize = size ?? (fullscreen ? "lg" : "md");
  const isCompact = resolvedSize === "sm";

  return (
    <div
      className={cn(
        "k-loader",
        fullscreen && "k-loader--fullscreen",
        className
      )}
      role="status"
      aria-label={label}
    >
      <div
        className={cn(
          "flex flex-col items-center",
          isCompact ? "gap-1.5" : "gap-3"
        )}
      >
        <video
          src="/images/kultiva-loader.webm"
          autoPlay
          loop
          muted
          playsInline
          disablePictureInPicture
          aria-hidden="true"
          className={cn(
            "pointer-events-none h-auto select-none object-contain",
            LOADER_WIDTH_CLASS[resolvedSize]
          )}
        />

        {label && (
          <span
            className={cn(
              "font-semibold text-[#511D4E]",
              isCompact ? "text-xs" : "text-sm"
            )}
          >
            {label}
          </span>
        )}

        {onClosePreview && (
          <button
            type="button"
            onClick={onClosePreview}
            className="mt-2 rounded-full border border-[#511D4E]/30 bg-white px-4 py-1.5 text-xs font-semibold text-[#511D4E] shadow-xs transition-colors hover:bg-[#511D4E]/10"
          >
            Fechar preview
          </button>
        )}
      </div>
    </div>
  );
}

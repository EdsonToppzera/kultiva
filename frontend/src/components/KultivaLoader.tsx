import { cn } from "../lib/utils";

export interface KultivaLoaderProps {
  fullscreen?: boolean;
  label?: string;
  className?: string;
  onClosePreview?: () => void;
}

export function KultivaLoader({
  fullscreen = true,
  label = "Carregando...",
  className,
  onClosePreview,
}: KultivaLoaderProps) {
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
      <div className="flex flex-col items-center gap-3">
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
            fullscreen ? "w-[170px]" : "w-[130px]"
          )}
        />

        {label && (
          <span className="text-sm font-semibold text-[#511D4E]">{label}</span>
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

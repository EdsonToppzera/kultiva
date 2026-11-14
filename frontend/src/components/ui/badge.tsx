import * as React from "react";
import { cn } from "../../lib/utils";

export type BadgeVariant =
  | "default"
  | "saved"
  | "offline"
  | "outline"
  | "warning";

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: BadgeVariant;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  default: "bg-[#511D4E] text-white border-transparent",
  saved: "bg-[#CAD17A]/35 text-[#3D4928] border-[#CAD17A]/60",
  offline: "bg-[#FCF59B]/75 text-[#4A3B12] border-[#CAD17A]",
  outline: "bg-transparent text-[#511D4E] border-[#D8D5CA]",
  warning: "bg-[#C42311]/10 text-[#C42311] border-[#C42311]/30",
};

/**
 * Componente Badge compatível com a interface Shadcn UI.
 */
export const Badge = React.forwardRef<HTMLDivElement, BadgeProps>(
  ({ className, variant = "default", ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold leading-none transition-colors",
          VARIANT_CLASSES[variant],
          className
        )}
        {...props}
      />
    );
  }
);

Badge.displayName = "Badge";


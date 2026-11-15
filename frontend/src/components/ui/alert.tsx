import * as React from "react";
import { cn } from "../../lib/utils";

export type AlertVariant = "default" | "warning" | "info" | "destructive";

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: AlertVariant;
}

const VARIANT_CLASSES: Record<AlertVariant, string> = {
  default: "border-[#E6E4DA] bg-white text-[#1F1C18]",
  warning: "border-[#CAD17A] bg-[#FCF59B]/55 text-[#3B3314]",
  info: "border-[#91C494]/60 bg-[#91C494]/20 text-[#1E3B21]",
  destructive: "border-[#C42311]/40 bg-[#C42311]/10 text-[#8E180B]",
};

/**
 * Componente Alert compatível com a interface Shadcn UI.
 */
export const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
  ({ className, variant = "default", ...props }, ref) => {
    return (
      <div
        ref={ref}
        role="alert"
        className={cn(
          "relative flex w-full items-start gap-3 rounded-2xl border p-4 text-sm leading-relaxed",
          VARIANT_CLASSES[variant],
          className
        )}
        {...props}
      />
    );
  }
);

Alert.displayName = "Alert";

export type AlertTitleProps = React.HTMLAttributes<HTMLHeadingElement>;

/**
 * Título opcional exibido dentro de um Alert.
 */
export const AlertTitle = React.forwardRef<HTMLHeadingElement, AlertTitleProps>(
  ({ className, ...props }, ref) => {
    return (
      <h5
        ref={ref}
        className={cn("mb-1 font-bold leading-none tracking-tight", className)}
        {...props}
      />
    );
  }
);

AlertTitle.displayName = "AlertTitle";

export type AlertDescriptionProps = React.HTMLAttributes<HTMLParagraphElement>;

/**
 * Conteúdo descritivo exibido dentro de um Alert.
 */
export const AlertDescription = React.forwardRef<
  HTMLParagraphElement,
  AlertDescriptionProps
>(({ className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      className={cn("text-xs leading-relaxed sm:text-sm", className)}
      {...props}
    />
  );
});

AlertDescription.displayName = "AlertDescription";


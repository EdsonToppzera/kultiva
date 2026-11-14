import * as React from "react";
import { cn } from "../../lib/utils";

export type ButtonVariant =
  | "primary"
  | "default"
  | "outline"
  | "ghost"
  | "link"
  | "destructive";

export type ButtonSize = "default" | "sm" | "lg" | "icon";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary:
    "bg-[#511D4E] text-white shadow-sm hover:bg-[#41163E] active:bg-[#351133] disabled:bg-[#511D4E]/40 disabled:text-white/80",
  default:
    "bg-[#511D4E] text-white shadow-sm hover:bg-[#41163E] active:bg-[#351133] disabled:bg-[#511D4E]/40 disabled:text-white/80",
  outline:
    "border border-[#D8D5CA] bg-white text-[#1F1C18] hover:border-[#511D4E] hover:bg-[#FCF59B]/15",
  ghost:
    "bg-transparent text-[#511D4E] hover:bg-[#511D4E]/10 active:bg-[#511D4E]/15",
  link: "h-auto p-0 bg-transparent text-[#511D4E] underline-offset-4 hover:underline",
  destructive:
    "bg-[#C42311] text-white shadow-sm hover:bg-[#A81D0E] active:bg-[#8E180B]",
};

const SIZE_CLASSES: Record<ButtonSize, string> = {
  default: "min-h-[48px] px-5 py-3 text-base",
  sm: "min-h-[38px] px-3.5 py-2 text-sm",
  lg: "min-h-[54px] px-6 py-3.5 text-base",
  icon: "h-11 w-11 p-0",
};

/**
 * Retorna as classes Tailwind para o botão no padrão Shadcn UI.
 */
export function buttonVariants({
  variant = "primary",
  size = "default",
  className,
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
} = {}): string {
  return cn(
    "inline-flex items-center justify-center gap-2 rounded-full font-semibold transition-colors",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E] focus-visible:ring-offset-2 focus-visible:ring-offset-[#F7F6F0]",
    "disabled:pointer-events-none disabled:cursor-not-allowed",
    VARIANT_CLASSES[variant],
    variant === "link" ? "rounded-md" : SIZE_CLASSES[size],
    className
  );
}

/**
 * Componente Button compatível com a interface Shadcn UI e otimizado para toque em campo.
 */
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "default", type = "button", ...props }, ref) => {
    return (
      <button
        ref={ref}
        type={type}
        className={buttonVariants({ variant, size, className })}
        {...props}
      />
    );
  }
);

Button.displayName = "Button";


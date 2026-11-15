import { cn } from "../lib/utils";

export interface KultivaLogoProps {
  className?: string;
}

export function KultivaLogo({ className }: KultivaLogoProps) {
  return (
    <img
      src="/images/kultiva-logo.png"
      alt="Kultiva"
      className={cn("h-10 w-auto shrink-0 select-none object-contain", className)}
    />
  );
}

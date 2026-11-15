import * as React from "react";
import { Check, ChevronDown, Globe } from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "./ui/popover";
import { cn } from "../lib/utils";
import { type AppLanguage, useLanguage } from "../contexts/LanguageContext";

const LANGUAGE_OPTIONS: { code: AppLanguage; shortLabel: string; label: string }[] = [
  { code: "pt", shortLabel: "PT-BR", label: "Português (PT-BR)" },
  { code: "en", shortLabel: "EN", label: "English (EN)" },
];

export function LanguageSelector({ className }: { className?: string }) {
  const { language, setLanguage } = useLanguage();
  const [open, setOpen] = React.useState(false);

  const current =
    LANGUAGE_OPTIONS.find((opt) => opt.code === language) ?? LANGUAGE_OPTIONS[0];

  return (
    <Popover open={open} onOpenChange={setOpen} className="w-auto shrink-0">
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label="Selecionar idioma"
          aria-expanded={open}
          className={cn(
            "inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full border border-[#E6E4DA] bg-white px-2.5 py-1 text-xs font-semibold text-[#511D4E] shadow-2xs transition-colors hover:border-[#511D4E]/50 hover:bg-[#F7F6F0] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E]",
            className
          )}
        >
          <Globe className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
          <span>{current.shortLabel}</span>
          <ChevronDown
            className={cn(
              "h-3 w-3 shrink-0 transition-transform",
              open && "rotate-180"
            )}
            aria-hidden="true"
          />
        </button>
      </PopoverTrigger>

      <PopoverContent
        align="end"
        sideOffset={6}
        style={{ width: "max-content", minWidth: "190px" }}
        className="rounded-2xl border border-[#E6E4DA] bg-white p-1.5 shadow-md"
      >
        <div role="menu" aria-label="Idiomas disponíveis" className="flex flex-col gap-0.5">
          {LANGUAGE_OPTIONS.map((opt) => {
            const isActive = opt.code === language;
            return (
              <button
                key={opt.code}
                type="button"
                role="menuitemradio"
                aria-checked={isActive}
                onClick={() => {
                  setLanguage(opt.code);
                  setOpen(false);
                }}
                className={cn(
                  "flex w-full items-center justify-between gap-3 whitespace-nowrap rounded-xl px-3 py-2 text-left text-xs font-semibold transition-colors",
                  isActive
                    ? "bg-[#FCF59B]/45 text-[#511D4E]"
                    : "text-[#1F1C18] hover:bg-[#F7F6F0]"
                )}
              >
                <span>{opt.label}</span>
                {isActive && (
                  <Check className="h-3.5 w-3.5 shrink-0 text-[#511D4E]" aria-hidden="true" />
                )}
              </button>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}


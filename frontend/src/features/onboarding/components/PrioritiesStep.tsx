import * as React from "react";
import {
  ArrowRight,
  Bug,
  Check,
  ChevronLeft,
  ChevronRight,
  Home,
  Leaf,
  PiggyBank,
  RefreshCw,
  Search,
  Sprout,
  Target,
  TrendingUp,
  Wifi,
  WifiOff,
} from "lucide-react";
import { Badge } from "../../../components/ui/badge";
import { Button } from "../../../components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "../../../components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "../../../components/ui/popover";
import { RadioGroup, RadioGroupItem } from "../../../components/ui/radio-group";
import {
  CROPS_DICTIONARY,
  formatPopularNames,
} from "../../../data/cropsDictionary";
import { cn } from "../../../lib/utils";
import type {
  CropOption,
  NetworkSyncStatus,
} from "../types/cropHistory.types";
import type {
  PriorityData,
  PriorityId,
  PriorityOption,
} from "../types/priority.types";

export const PRIORITY_OPTIONS: PriorityOption[] = [
  {
    id: "plantar_especifico",
    title: "Quero plantar algo específico",
    subtitle: "Já sei o que quero colher, me ajude a preparar a terra.",
    icon: Target,
    requiresCropSelection: true,
  },
  {
    id: "recuperar_terra",
    title: "Recuperar a terra",
    subtitle: "Deixar o solo forte para os próximos cultivos.",
    icon: Leaf,
  },
  {
    id: "retorno_rapido",
    title: "Ter retorno mais rápido",
    subtitle: "Priorizar uma colheita para venda.",
    icon: TrendingUp,
  },
  {
    id: "consumo_racao",
    title: "Consumo ou ração",
    subtitle: "Produzir para a família ou os animais.",
    icon: Home,
  },
  {
    id: "gastar_minimo",
    title: "Gastar o mínimo possível",
    subtitle: "Culturas rústicas que exigem pouca água, adubo ou defensivos.",
    icon: PiggyBank,
  },
  {
    id: "limpar_terra",
    title: "Limpar a terra",
    subtitle: "Tive problemas com insetos ou doenças na última colheita.",
    icon: Bug,
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

interface CropThumbnailProps {
  crop: CropOption;
  size?: "md" | "sm";
}

function CropThumbnail({ crop, size = "md" }: CropThumbnailProps) {
  const [hasError, setHasError] = React.useState(false);

  React.useEffect(() => {
    setHasError(false);
  }, [crop.imageUrl]);

  const sizeClasses = size === "sm" ? "h-12 w-12" : "h-14 w-14";

  if (!crop.imageUrl || hasError) {
    return (
      <div
        className={cn(
          "flex shrink-0 items-center justify-center rounded-xl border border-[#91C494]/40 bg-[#91C494]/25 text-[#511D4E]",
          sizeClasses
        )}
        aria-hidden="true"
      >
        <Sprout className="h-6 w-6" />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "shrink-0 overflow-hidden rounded-xl border border-[#E6E4DA] bg-[#F2F1EA]",
        sizeClasses
      )}
    >
      <img
        src={crop.imageUrl}
        alt={crop.officialName}
        onError={() => setHasError(true)}
        className="h-full w-full object-cover"
      />
    </div>
  );
}

interface TargetCropComboboxProps {
  value: CropOption | null;
  crops: CropOption[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectCrop: (crop: CropOption) => void;
}

function TargetCropCombobox({
  value,
  crops,
  open,
  onOpenChange,
  onSelectCrop,
}: TargetCropComboboxProps) {
  const [searchQuery, setSearchQuery] = React.useState("");
  const inputRef = React.useRef<HTMLInputElement>(null);

  React.useEffect(() => {
    if (open) {
      const frame = window.requestAnimationFrame(() => {
        inputRef.current?.focus();
      });
      return () => window.cancelAnimationFrame(frame);
    }
    setSearchQuery("");
  }, [open]);

  const handleSelect = (crop: CropOption) => {
    onSelectCrop(crop);
    setSearchQuery("");
    onOpenChange(false);
  };

  return (
    <div
      onKeyDown={(event) => event.stopPropagation()}
      className="ml-2 border-l-2 border-[#511D4E]/25 pl-3 pt-1"
    >
      <label
        htmlFor="cultura-especifica-trigger"
        className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-[#6D6960]"
      >
        QUAL CULTURA VOCÊ QUER PLANTAR?
      </label>

      <Popover open={open} onOpenChange={onOpenChange}>
        <PopoverTrigger asChild>
          {value ? (
            <button
              id="cultura-especifica-trigger"
              type="button"
              className={cn(
                "flex min-h-[74px] w-full items-center justify-between gap-3 rounded-2xl border bg-white p-3 text-left shadow-sm transition-colors",
                open
                  ? "border-[#511D4E] ring-2 ring-[#511D4E]/15"
                  : "border-[#E6E4DA] hover:border-[#511D4E]/60",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E]"
              )}
            >
              <div className="flex min-w-0 items-center gap-3">
                <CropThumbnail crop={value} />
                <div className="min-w-0">
                  <p className="truncate text-base font-bold text-[#1F1C18]">
                    {value.officialName}
                  </p>
                  <p className="mt-0.5 line-clamp-2 text-xs text-[#7A756B]">
                    {formatPopularNames(value.popularNames)}
                  </p>
                </div>
              </div>
              <ChevronRight
                className="h-5 w-5 shrink-0 text-[#511D4E]"
                aria-hidden="true"
              />
            </button>
          ) : (
            <button
              id="cultura-especifica-trigger"
              type="button"
              className={cn(
                "flex min-h-[56px] w-full items-center justify-between gap-3 rounded-2xl border bg-white/90 px-4 py-3 text-left transition-colors",
                open
                  ? "border-[1.5px] border-[#511D4E] bg-white"
                  : "border-[#D5D1C5] hover:border-[#511D4E] hover:bg-white",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E]"
              )}
            >
              <span className="flex items-center gap-3 text-sm font-medium text-[#6D6960] sm:text-base">
                <Search
                  className="h-5 w-5 shrink-0 text-[#511D4E]"
                  aria-hidden="true"
                />
                <span>Buscar cultivo...</span>
              </span>
              <ChevronRight
                className="h-5 w-5 shrink-0 text-[#6D6960]"
                aria-hidden="true"
              />
            </button>
          )}
        </PopoverTrigger>

        <PopoverContent align="start" sideOffset={8}>
          <Command value={searchQuery} onValueChange={setSearchQuery}>
            <CommandInput
              ref={inputRef}
              placeholder="Ex: Macaxeira, milho, feijão..."
              aria-label="Buscar cultura desejada"
            />

            <CommandList>
              <CommandEmpty>
                Nenhum cultivo encontrado para &ldquo;{searchQuery}&rdquo;. Escolha
                uma opção da lista ou tente outro nome regional.
              </CommandEmpty>

              <CommandGroup>
                {crops.map((crop) => {
                  const isSelected = value?.id === crop.id;

                  return (
                    <CommandItem
                      key={crop.id}
                      value={crop.officialName}
                      keywords={crop.popularNames}
                      onSelect={() => handleSelect(crop)}
                      className={cn(
                        isSelected && "border-[#511D4E] bg-[#FCF59B]/25"
                      )}
                    >
                      <CropThumbnail crop={crop} size="sm" />

                      <div className="min-w-0 flex-1">
                        <p className="truncate text-base font-bold text-[#1F1C18]">
                          {crop.officialName}
                        </p>
                        <p className="mt-0.5 line-clamp-2 text-xs text-[#7A756B]">
                          {formatPopularNames(crop.popularNames)}
                        </p>
                      </div>

                      {isSelected ? (
                        <Check
                          className="h-5 w-5 shrink-0 text-[#511D4E]"
                          aria-hidden="true"
                        />
                      ) : (
                        <ChevronRight
                          className="h-5 w-5 shrink-0 text-[#511D4E]"
                          aria-hidden="true"
                        />
                      )}
                    </CommandItem>
                  );
                })}
              </CommandGroup>
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>
    </div>
  );
}

export interface PrioritiesStepProps {
  options?: PriorityOption[];
  crops?: CropOption[];
  initialValue?: PriorityId | null;
  initialTargetCrop?: CropOption | null;
  networkStatus?: NetworkSyncStatus;
  onBack?: () => void;
  onContinue?: (data: PriorityData) => void;
}

/**
 * Tela de Onboarding — Passo 4: Prioridades.
 * Permite selecionar o objetivo principal e buscar uma cultura específica via Combobox fuzzy quando aplicável.
 */
export function PrioritiesStep({
  options = PRIORITY_OPTIONS,
  crops = CROPS_DICTIONARY,
  initialValue = null,
  initialTargetCrop = null,
  networkStatus,
  onBack,
  onContinue,
}: PrioritiesStepProps) {
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

  const [selectedId, setSelectedId] = React.useState<PriorityId | null>(
    initialValue
  );
  const [specificCrop, setSpecificCrop] = React.useState<CropOption | null>(
    initialTargetCrop
  );
  const [cropPickerOpen, setCropPickerOpen] = React.useState(false);

  const badgeInfo = NETWORK_BADGE_CONFIG[resolvedNetworkStatus];
  const NetworkIcon = badgeInfo.icon;

  const selectedOption = React.useMemo(
    () => options.find((item) => item.id === selectedId) ?? null,
    [options, selectedId]
  );

  const canContinue =
    selectedOption !== null &&
    (!selectedOption.requiresCropSelection || specificCrop !== null);

  const handlePriorityChange = (nextValue: string) => {
    const nextId = nextValue as PriorityId;
    setSelectedId(nextId);
    const nextOption = options.find((item) => item.id === nextId);
    if (!nextOption?.requiresCropSelection) {
      setCropPickerOpen(false);
    }
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedOption || !canContinue) return;

    onContinue?.({
      prioridade: selectedOption,
      culturaDesejada: selectedOption.requiresCropSelection ? specificCrop : null,
    });
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
              <span className="font-medium text-[#511D4E]">Passo 4 de 4</span>
            </div>

            <div
              role="progressbar"
              aria-label="Passo 4 de 4"
              aria-valuemin={1}
              aria-valuemax={4}
              aria-valuenow={4}
              className="mt-2 grid grid-cols-4 gap-2"
            >
              <span className="h-1 rounded-full bg-[#511D4E]" />
              <span className="h-1 rounded-full bg-[#511D4E]" />
              <span className="h-1 rounded-full bg-[#511D4E]" />
              <span className="h-1 rounded-full bg-[#511D4E]" />
            </div>
          </section>

          {/* Conteúdo Principal */}
          <main className="mt-8">
            <h1 className="text-[26px] font-bold leading-tight tracking-tight text-[#511D4E] sm:text-[28px]">
              Prioridades
            </h1>
            <p className="mt-1.5 text-sm text-[#6D6960] sm:text-base">
              Escolha sua prioridade. Vamos comparar caminhos possíveis para sua
              área.
            </p>

            <RadioGroup
              aria-label="Prioridades"
              value={selectedId}
              onValueChange={handlePriorityChange}
              className="mt-6 flex flex-col gap-3"
            >
              {options.map((option) => {
                const OptionIcon = option.icon;
                const isSelected = selectedId === option.id;

                return (
                  <div key={option.id} className="flex flex-col gap-2.5">
                    <RadioGroupItem
                      value={option.id}
                      className={cn(
                        "flex min-h-[76px] w-full items-center justify-between gap-3 rounded-2xl border px-4 py-3.5 text-left transition-colors",
                        isSelected
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
                                  : "bg-[#F7F6F0] text-[#511D4E]/80"
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
                              <p className="mt-0.5 text-xs leading-snug text-[#6D6960] sm:text-sm">
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
                            {checked && (
                              <Check className="h-3.5 w-3.5 stroke-[3]" />
                            )}
                          </span>
                        </>
                      )}
                    </RadioGroupItem>

                    {isSelected && option.requiresCropSelection && (
                      <TargetCropCombobox
                        value={specificCrop}
                        crops={crops}
                        open={cropPickerOpen}
                        onOpenChange={setCropPickerOpen}
                        onSelectCrop={setSpecificCrop}
                      />
                    )}
                  </div>
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
            disabled={!canContinue}
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

export default PrioritiesStep;


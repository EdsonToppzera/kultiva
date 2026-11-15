import * as React from "react";
import { useTranslation } from "react-i18next";
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
import { KultivaLogo } from "../../../components/KultivaLogo";
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
  formatPopularNames,
} from "../../../data/cropsDictionary";
import {
  type PestOption,
} from "../../../data/pestsDictionary";
import { useCatalogSearch } from "../../../hooks/useCatalogSearch";
import { cn } from "../../../lib/utils";
import {
  type TerrenoResponse,
  atualizarTerreno,
  buscarCulturasCatalogo,
  buscarPragasCatalogo,
} from "../../../services/api";
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
    requiresPestSelection: true,
  },
];

const NETWORK_BADGE_CONFIG: Record<
  NetworkSyncStatus,
  {
    labelKey: string;
    variant: "saved" | "offline" | "outline";
    icon: React.ComponentType<{ className?: string }>;
  }
> = {
  salvo: { labelKey: "network.saved", variant: "saved", icon: Wifi },
  sincronizando: { labelKey: "network.saving", variant: "outline", icon: RefreshCw },
  offline: { labelKey: "network.offline", variant: "offline", icon: WifiOff },
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
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = React.useState("");
  const inputRef = React.useRef<HTMLInputElement>(null);
  const filteredCrops = useCatalogSearch(
    open,
    searchQuery,
    crops,
    buscarCulturasCatalogo
  );

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
        {t("onboarding.priorities.targetCropLabel")}
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
                <span>{t("onboarding.priorities.targetCropSearch")}</span>
              </span>
              <ChevronRight
                className="h-5 w-5 shrink-0 text-[#6D6960]"
                aria-hidden="true"
              />
            </button>
          )}
        </PopoverTrigger>

        <PopoverContent align="start" sideOffset={8}>
          <Command
            shouldFilter={false}
            value={searchQuery}
            onValueChange={setSearchQuery}
          >
            <CommandInput
              ref={inputRef}
              placeholder={t("onboarding.priorities.targetCropPlaceholder")}
              aria-label={t("onboarding.priorities.targetCropSearch")}
            />

            <CommandList>
              <CommandEmpty>
                {t("onboarding.priorities.targetCropEmpty", {
                  query: searchQuery,
                })}
              </CommandEmpty>

              <CommandGroup>
                {filteredCrops.map((crop) => {
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

interface TargetPestComboboxProps {
  value: PestOption | null;
  pests: PestOption[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectPest: (pest: PestOption) => void;
}

function TargetPestCombobox({
  value,
  pests,
  open,
  onOpenChange,
  onSelectPest,
}: TargetPestComboboxProps) {
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = React.useState("");
  const inputRef = React.useRef<HTMLInputElement>(null);
  const filteredPests = useCatalogSearch(
    open,
    searchQuery,
    pests,
    buscarPragasCatalogo
  );

  React.useEffect(() => {
    if (open) {
      const frame = window.requestAnimationFrame(() => {
        inputRef.current?.focus();
      });
      return () => window.cancelAnimationFrame(frame);
    }
    setSearchQuery("");
  }, [open]);

  const handleSelect = (pest: PestOption) => {
    onSelectPest(pest);
    setSearchQuery("");
    onOpenChange(false);
  };

  return (
    <div className="mt-1 flex flex-col gap-2 pl-2">
      <label
        htmlFor="praga-especifica-trigger"
        className="text-[11px] font-semibold uppercase tracking-wider text-[#6D6960]"
      >
        {t("onboarding.priorities.targetPestLabel")}
      </label>

      <Popover open={open} onOpenChange={onOpenChange}>
        <PopoverTrigger asChild>
          {value ? (
            <button
              id="praga-especifica-trigger"
              type="button"
              className={cn(
                "flex min-h-[72px] w-full items-center justify-between gap-3 rounded-2xl border bg-white p-3 text-left shadow-sm transition-colors",
                open
                  ? "border-[#511D4E] ring-2 ring-[#511D4E]/15"
                  : "border-[#E6E4DA] hover:border-[#511D4E]/60",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E]"
              )}
            >
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-[#E6E4DA] bg-[#F2F1EA] text-[#511D4E]">
                  <Bug className="h-5 w-5" aria-hidden="true" />
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <p className="truncate text-base font-bold text-[#1F1C18]">
                      {value.officialName}
                    </p>
                    {value.category && (
                      <span className="inline-flex shrink-0 items-center rounded-full bg-[#EFECE3] px-2 py-0.5 text-[10px] font-semibold text-[#511D4E]">
                        {value.category}
                      </span>
                    )}
                  </div>
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
              id="praga-especifica-trigger"
              type="button"
              className={cn(
                "flex min-h-[58px] w-full items-center justify-between gap-3 rounded-2xl border bg-white/90 px-4 py-3 text-left shadow-xs transition-colors",
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
                <span>{t("onboarding.priorities.targetPestSearch")}</span>
              </span>
              <ChevronRight
                className="h-5 w-5 shrink-0 text-[#6D6960]"
                aria-hidden="true"
              />
            </button>
          )}
        </PopoverTrigger>

        <PopoverContent align="start" sideOffset={8}>
          <Command
            shouldFilter={false}
            value={searchQuery}
            onValueChange={setSearchQuery}
          >
            <CommandInput
              ref={inputRef}
              placeholder={t("onboarding.priorities.targetPestPlaceholder")}
              aria-label={t("onboarding.priorities.targetPestSearch")}
            />

            <CommandList>
              <CommandEmpty>
                {t("onboarding.priorities.targetPestEmpty", {
                  query: searchQuery,
                })}
              </CommandEmpty>

              <CommandGroup>
                {filteredPests.map((pest) => {
                  const isSelected = value?.id === pest.id;

                  return (
                    <CommandItem
                      key={pest.id}
                      value={pest.officialName}
                      keywords={pest.popularNames}
                      onSelect={() => handleSelect(pest)}
                      className={cn(
                        isSelected && "border-[#511D4E] bg-[#FCF59B]/25"
                      )}
                    >
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-[#E6E4DA] bg-[#F2F1EA] text-[#511D4E]">
                        <Bug className="h-5 w-5" aria-hidden="true" />
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <p className="truncate text-base font-bold text-[#1F1C18]">
                            {pest.officialName}
                          </p>
                          {pest.category && (
                            <span className="inline-flex shrink-0 items-center rounded-full bg-[#EFECE3] px-2 py-0.5 text-[10px] font-semibold text-[#511D4E]">
                              {pest.category}
                            </span>
                          )}
                        </div>
                        <p className="mt-0.5 line-clamp-2 text-xs text-[#7A756B]">
                          {formatPopularNames(pest.popularNames)}
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
  pests?: PestOption[];
  initialValue?: PriorityId | null;
  initialTargetCrop?: CropOption | null;
  initialTargetPest?: PestOption | null;
  networkStatus?: NetworkSyncStatus;
  terrenoId?: number | null;
  existingPrioridades?: Record<string, unknown> | null;
  onTerrenoUpdated?: (terreno: TerrenoResponse) => void;
  onBack?: () => void;
  onContinue?: (data: PriorityData) => void;
}

/**
 * Tela de Onboarding — Passo 4: Prioridades.
 * Permite selecionar o objetivo principal e buscar uma cultura específica via Combobox fuzzy quando aplicável.
 */
export function PrioritiesStep({
  options = PRIORITY_OPTIONS,
  crops = [],
  pests = [],
  initialValue = null,
  initialTargetCrop = null,
  initialTargetPest = null,
  networkStatus,
  terrenoId,
  existingPrioridades,
  onTerrenoUpdated,
  onBack,
  onContinue,
}: PrioritiesStepProps) {
  const { t } = useTranslation();
  const [isOnline, setIsOnline] = React.useState<boolean>(() =>
    typeof navigator !== "undefined" ? navigator.onLine : true
  );
  const [syncState, setSyncState] = React.useState<NetworkSyncStatus | null>(
    null
  );
  const [isSaving, setIsSaving] = React.useState(false);

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
    syncState ?? networkStatus ?? (isOnline ? "salvo" : "offline");

  const [selectedId, setSelectedId] = React.useState<PriorityId | null>(
    initialValue
  );
  const [specificCrop, setSpecificCrop] = React.useState<CropOption | null>(
    initialTargetCrop
  );
  const [cropPickerOpen, setCropPickerOpen] = React.useState(false);
  const [specificPest, setSpecificPest] = React.useState<PestOption | null>(
    initialTargetPest
  );
  const [pestPickerOpen, setPestPickerOpen] = React.useState(false);

  const badgeInfo = NETWORK_BADGE_CONFIG[resolvedNetworkStatus];
  const NetworkIcon = badgeInfo.icon;

  const selectedOption = React.useMemo(
    () => options.find((item) => item.id === selectedId) ?? null,
    [options, selectedId]
  );

  const canContinue =
    selectedOption !== null &&
    (!selectedOption.requiresCropSelection || specificCrop !== null) &&
    (!selectedOption.requiresPestSelection || specificPest !== null);

  const handlePriorityChange = (nextValue: string) => {
    const nextId = nextValue as PriorityId;
    setSelectedId(nextId);
    const nextOption = options.find((item) => item.id === nextId);
    if (!nextOption?.requiresCropSelection) {
      setCropPickerOpen(false);
    }
    if (!nextOption?.requiresPestSelection) {
      setPestPickerOpen(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedOption || !canContinue || isSaving) return;

    const targetCrop = selectedOption.requiresCropSelection
      ? specificCrop
      : null;
    const targetPest = selectedOption.requiresPestSelection
      ? specificPest
      : null;

    if (terrenoId != null) {
      setIsSaving(true);
      setSyncState("sincronizando");
      try {
        const updated = await atualizarTerreno(terrenoId, {
          prioridades: {
            ...(existingPrioridades ?? {}),
            prioridade: selectedOption.id,
            objetivo_principal: selectedOption.id,
            cultura_desejada: targetCrop?.officialName ?? null,
            praga_alvo: targetPest?.officialName ?? null,
          },
        });
        setSyncState("salvo");
        onTerrenoUpdated?.(updated);
      } catch {
        setSyncState("offline");
      } finally {
        setIsSaving(false);
      }
    }

    onContinue?.({
      prioridade: selectedOption,
      culturaDesejada: targetCrop,
      pragaAlvo: targetPest,
    });
  };

  return (
    <div className="min-h-dvh w-full bg-[#F7F6F0] text-[#1F1C18] md:flex md:items-center md:justify-center md:bg-[#EFECE3] md:p-6">
      <form
        onSubmit={(event) => void handleSubmit(event)}
        className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-between bg-[#F7F6F0] px-5 pb-8 pt-6 md:min-h-[680px] md:rounded-3xl md:border md:border-[#E6E4DA] md:px-7 md:py-8 md:shadow-sm"
      >
        <div>
          {/* Header */}
          <header className="flex items-center justify-between gap-4">
            <KultivaLogo />

            <div className="flex items-center gap-2">
              <Badge variant={badgeInfo.variant} aria-live="polite">
                <NetworkIcon
                  className={cn(
                    "h-3.5 w-3.5",
                    resolvedNetworkStatus === "sincronizando" && "animate-spin"
                  )}
                  aria-hidden="true"
                />
                <span>{t(badgeInfo.labelKey)}</span>
              </Badge>
            </div>
          </header>

          {/* Indicador de Progresso */}
          <section aria-label={t("onboarding.yourArea")} className="mt-6">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold uppercase tracking-wider text-[#6D6960]">
                {t("onboarding.yourArea")}
              </span>
              <span className="font-medium text-[#511D4E]">
                {t("common.stepOf", { current: 4, total: 4 })}
              </span>
            </div>

            <div
              role="progressbar"
              aria-label={t("common.stepOf", { current: 4, total: 4 })}
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
              {t("onboarding.priorities.title")}
            </h1>
            <p className="mt-1.5 text-sm text-[#6D6960] sm:text-base">
              {t("onboarding.priorities.subtitle")}
            </p>

            <RadioGroup
              aria-label={t("onboarding.priorities.title")}
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
                                {t(
                                  `onboarding.priorities.options.${option.id}.title`,
                                  { defaultValue: option.title }
                                )}
                              </p>
                              <p className="mt-0.5 text-xs leading-snug text-[#6D6960] sm:text-sm">
                                {t(
                                  `onboarding.priorities.options.${option.id}.subtitle`,
                                  { defaultValue: option.subtitle }
                                )}
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

                    {isSelected && option.requiresPestSelection && (
                      <TargetPestCombobox
                        value={specificPest}
                        pests={pests}
                        open={pestPickerOpen}
                        onOpenChange={setPestPickerOpen}
                        onSelectPest={setSpecificPest}
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
            disabled={!canContinue || isSaving}
            className="w-full"
          >
            <span>{t("common.continue")}</span>
            <ArrowRight className="h-5 w-5" aria-hidden="true" />
          </Button>

          <Button
            type="button"
            variant="ghost"
            onClick={onBack}
            className="w-full max-w-[200px] text-sm font-semibold text-[#511D4E]"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            <span>{t("common.back")}</span>
          </Button>
        </footer>
      </form>
    </div>
  );
}

export default PrioritiesStep;


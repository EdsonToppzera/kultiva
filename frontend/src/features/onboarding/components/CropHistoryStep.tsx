import * as React from "react";
import {
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Search,
  Sprout,
  Wifi,
  WifiOff,
} from "lucide-react";
import { LanguageSelector } from "../../../components/LanguageSelector";
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
import {
  CROPS_DICTIONARY,
  formatPopularNames,
} from "../../../data/cropsDictionary";
import { useCatalogSearch } from "../../../hooks/useCatalogSearch";
import { cn } from "../../../lib/utils";
import {
  type TerrenoResponse,
  atualizarTerreno,
  buscarCulturasCatalogo,
  converterHistoricoParaLista,
} from "../../../services/api";
import type {
  CropHistoryData,
  CropOption,
  NetworkSyncStatus,
} from "../types/cropHistory.types";

export interface CropHistoryStepProps {
  crops?: CropOption[];
  initialData?: Partial<CropHistoryData>;
  networkStatus?: NetworkSyncStatus;
  terrenoId?: number | null;
  existingPrioridades?: Record<string, unknown> | null;
  onTerrenoUpdated?: (terreno: TerrenoResponse) => void;
  onBack?: () => void;
  onContinue?: (data: CropHistoryData) => void;
  onDontRemember?: () => void;
}

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

interface CropComboboxFieldProps {
  id: string;
  label: string;
  value: CropOption | null;
  crops: CropOption[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectCrop: (crop: CropOption) => void;
}

function CropComboboxField({
  id,
  label,
  value,
  crops,
  open,
  onOpenChange,
  onSelectCrop,
}: CropComboboxFieldProps) {
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
    <div className="flex flex-col gap-2">
      <label
        htmlFor={id}
        className="text-[11px] font-semibold uppercase tracking-wider text-[#6D6960]"
      >
        {label}
      </label>

      <Popover open={open} onOpenChange={onOpenChange}>
        <PopoverTrigger asChild>
          {value ? (
            <button
              id={id}
              type="button"
              className={cn(
                "flex min-h-[76px] w-full items-center justify-between gap-3 rounded-2xl border bg-white p-3 text-left shadow-sm transition-colors",
                open
                  ? "border-[#511D4E] ring-2 ring-[#511D4E]/15"
                  : "border-[#E6E4DA] hover:border-[#511D4E]/60",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E]"
              )}
            >
              <div className="flex min-w-0 items-center gap-3.5">
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
              id={id}
              type="button"
              className={cn(
                "flex min-h-[58px] w-full items-center justify-between gap-3 rounded-2xl border bg-white/85 px-4 py-3.5 text-left transition-colors",
                open
                  ? "border-[1.5px] border-[#511D4E] bg-white"
                  : "border-[#D5D1C5] hover:border-[#511D4E] hover:bg-white",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E]"
              )}
            >
              <span className="flex items-center gap-3 text-base text-[#6D6960]">
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
          <Command
            shouldFilter={false}
            value={searchQuery}
            onValueChange={setSearchQuery}
          >
            <CommandInput
              ref={inputRef}
              placeholder="Ex: Macaxeira, milho, feijão..."
              aria-label={`Buscar opção para ${label.toLowerCase()}`}
            />

            <CommandList>
              <CommandEmpty>
                Nenhum cultivo encontrado para &ldquo;{searchQuery}&rdquo;. Escolha
                uma opção da lista ou tente outro nome regional.
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

/**
 * Tela de Onboarding — Passo 1: Histórico de Cultivos.
 * Permite selecionar os dois últimos cultivos via busca fuzzy com sinônimos regionais ou pular caso não lembre.
 */
export function CropHistoryStep({
  crops = CROPS_DICTIONARY,
  initialData,
  networkStatus,
  terrenoId,
  existingPrioridades,
  onTerrenoUpdated,
  onBack,
  onContinue,
  onDontRemember,
}: CropHistoryStepProps) {
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
    networkStatus ?? syncState ?? (isOnline ? "salvo" : "offline");

  const [ultimoCultivo, setUltimoCultivo] = React.useState<CropOption | null>(
    initialData?.ultimoCultivo ?? null
  );
  const [cultivoAnterior, setCultivoAnterior] =
    React.useState<CropOption | null>(initialData?.cultivoAnterior ?? null);
  const [naoLembro, setNaoLembro] = React.useState<boolean>(
    initialData?.naoLembro ?? false
  );
  const [cultivoEmAndamento, setCultivoEmAndamento] = React.useState<boolean>(
    initialData?.cultivoEmAndamento ?? false
  );
  const [dataInicioCultivo, setDataInicioCultivo] = React.useState<string>(
    initialData?.dataInicioCultivo ?? ""
  );
  const [openField, setOpenField] = React.useState<
    "ultimo" | "anterior" | null
  >(null);

  const badgeInfo = NETWORK_BADGE_CONFIG[resolvedNetworkStatus];
  const NetworkIcon = badgeInfo.icon;

  const canContinue =
    (ultimoCultivo !== null && cultivoAnterior !== null) || naoLembro;

  const handleSelectUltimo = (crop: CropOption) => {
    setUltimoCultivo(crop);
    setNaoLembro(false);
  };

  const handleSelectAnterior = (crop: CropOption) => {
    setCultivoAnterior(crop);
    setNaoLembro(false);
  };

  const handleDontRemember = () => {
    setUltimoCultivo(null);
    setCultivoAnterior(null);
    setNaoLembro(true);
    setCultivoEmAndamento(false);
    setDataInicioCultivo("");
    setOpenField(null);
    onDontRemember?.();
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canContinue || isSaving) return;

    const payloadData: CropHistoryData = {
      ultimoCultivo,
      cultivoAnterior,
      naoLembro,
      cultivoEmAndamento,
      dataInicioCultivo:
        cultivoEmAndamento && dataInicioCultivo ? dataInicioCultivo : null,
    };

    if (terrenoId != null) {
      setIsSaving(true);
      setSyncState("sincronizando");
      try {
        const historicoCultivos = converterHistoricoParaLista(payloadData);
        const updated = await atualizarTerreno(terrenoId, {
          prioridades: {
            ...(existingPrioridades ?? {}),
            historico_cultivos: historicoCultivos,
            nao_lembra_historico: naoLembro,
            cultivo_em_andamento: cultivoEmAndamento,
            data_inicio_cultivo:
              cultivoEmAndamento && dataInicioCultivo
                ? dataInicioCultivo
                : null,
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

    onContinue?.(payloadData);
  };

  return (
    <div className="min-h-dvh w-full bg-[#F7F6F0] text-[#1F1C18] md:flex md:items-center md:justify-center md:bg-[#EFECE3] md:p-6">
      <form
        onSubmit={(event) => void handleSubmit(event)}
        className="mx-auto flex min-h-dvh w-full max-w-md flex-col justify-between bg-[#F7F6F0] px-5 pb-8 pt-6 md:min-h-[680px] md:max-w-lg md:rounded-3xl md:border md:border-[#E6E4DA] md:px-8 md:py-8 md:shadow-sm lg:max-w-xl"
      >
        <div>
          {/* Header */}
          <header className="flex items-center justify-between gap-4">
            <span className="text-2xl font-extrabold tracking-tight text-[#511D4E]">
              Kultiva
            </span>

            <div className="flex items-center gap-2">
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
              <LanguageSelector />
            </div>
          </header>

          {/* Indicador de Progresso */}
          <section aria-label="Progresso do cadastro" className="mt-6">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold uppercase tracking-wider text-[#6D6960]">
                SUA ÁREA
              </span>
              <span className="font-medium text-[#511D4E]">Passo 1 de 4</span>
            </div>

            <div
              role="progressbar"
              aria-label="Passo 1 de 4"
              aria-valuemin={1}
              aria-valuemax={4}
              aria-valuenow={1}
              className="mt-2 grid grid-cols-4 gap-2"
            >
              <span className="h-1 rounded-full bg-[#511D4E]" />
              <span className="h-1 rounded-full bg-[#E3E1D8]" />
              <span className="h-1 rounded-full bg-[#E3E1D8]" />
              <span className="h-1 rounded-full bg-[#E3E1D8]" />
            </div>
          </section>

          {/* Conteúdo Principal */}
          <main className="mt-8">
            <h1 className="text-[26px] font-bold leading-tight tracking-tight text-[#511D4E] sm:text-[28px]">
              Histórico de Cultivos
            </h1>
            <p className="mt-1.5 text-sm text-[#6D6960] sm:text-base">
              Insira os dois últimos cultivos.
            </p>

            <div className="mt-6 flex flex-col gap-5">
              <CropComboboxField
                id="ultimo-cultivo-trigger"
                label="ÚLTIMO CULTIVO"
                value={ultimoCultivo}
                crops={crops}
                open={openField === "ultimo"}
                onOpenChange={(isOpen) =>
                  setOpenField(isOpen ? "ultimo" : null)
                }
                onSelectCrop={handleSelectUltimo}
              />

              {/* Switch: Cultivo em andamento */}
              <div className="rounded-2xl border border-[#E6E4DA] bg-white p-4 shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <label
                      htmlFor="cultivo-em-andamento-switch"
                      className="block cursor-pointer text-sm font-bold text-[#1F1C18]"
                    >
                      O cultivo está em andamento?
                    </label>
                    <p className="mt-0.5 text-xs text-[#6D6960]">
                      Marque se você já plantou e ainda vai colher.
                    </p>
                  </div>

                  <button
                    id="cultivo-em-andamento-switch"
                    type="button"
                    role="switch"
                    aria-checked={cultivoEmAndamento}
                    onClick={() => {
                      setCultivoEmAndamento((prev) => !prev);
                      setNaoLembro(false);
                    }}
                    className={cn(
                      "relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E] focus-visible:ring-offset-2",
                      cultivoEmAndamento ? "bg-[#511D4E]" : "bg-[#D8D5C9]"
                    )}
                  >
                    <span
                      className={cn(
                        "inline-block h-5 w-5 transform rounded-full bg-white shadow-xs transition-transform",
                        cultivoEmAndamento ? "translate-x-5" : "translate-x-0.5"
                      )}
                    />
                  </button>
                </div>

                {cultivoEmAndamento && (
                  <div className="mt-4 border-t border-[#E6E4DA] pt-3.5">
                    <label
                      htmlFor="data-inicio-cultivo"
                      className="block text-[11px] font-semibold uppercase tracking-wider text-[#6D6960]"
                    >
                      DATA DE INÍCIO DO CULTIVO
                    </label>
                    <input
                      id="data-inicio-cultivo"
                      type="date"
                      value={dataInicioCultivo}
                      onChange={(e) => setDataInicioCultivo(e.target.value)}
                      className="mt-1.5 w-full rounded-xl border border-[#E6E4DA] bg-[#F7F6F0]/60 px-3 py-2.5 text-sm font-medium text-[#1F1C18] focus:border-[#511D4E] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#511D4E]/15"
                    />
                  </div>
                )}
              </div>

              <CropComboboxField
                id="cultivo-anterior-trigger"
                label="CULTIVO ANTERIOR"
                value={cultivoAnterior}
                crops={crops}
                open={openField === "anterior"}
                onOpenChange={(isOpen) =>
                  setOpenField(isOpen ? "anterior" : null)
                }
                onSelectCrop={handleSelectAnterior}
              />
            </div>

            <div className="mt-6 flex flex-col items-start gap-2">
              <Button
                type="button"
                variant="link"
                onClick={handleDontRemember}
                aria-pressed={naoLembro}
                className="text-left text-sm font-semibold text-[#511D4E]"
              >
                Não lembro dos cultivos anteriores
              </Button>

              {naoLembro && (
                <p
                  role="status"
                  className="rounded-xl border border-[#CAD17A] bg-[#CAD17A]/20 px-3 py-2 text-xs font-medium text-[#3D4928]"
                >
                  Sem problema — seguiremos sem histórico anterior. Toque em
                  Continuar para avançar.
                </p>
              )}
            </div>
          </main>
        </div>

        {/* Footer */}
        <footer className="mt-10 flex flex-col items-center gap-3 pt-4">
          <Button
            type="submit"
            variant="primary"
            size="lg"
            disabled={!canContinue || isSaving}
            className="w-full"
          >
            <span>{isSaving ? "Salvando..." : "Continuar"}</span>
            <ArrowRight className="h-5 w-5" aria-hidden="true" />
          </Button>

          <Button
            type="button"
            variant="ghost"
            onClick={onBack}
            disabled={isSaving}
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

export default CropHistoryStep;

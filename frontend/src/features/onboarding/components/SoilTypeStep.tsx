import * as React from "react";
import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  Check,
  ChevronLeft,
  HelpCircle,
  Info,
  Layers,
} from "lucide-react";
import { SimulationBanner } from "../../../components/CancelSimulationButton";
import { KultivaLogo } from "../../../components/KultivaLogo";
import { NetworkStatusBadge } from "../../../components/NetworkStatusBadge";
import { Button } from "../../../components/ui/button";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "../../../components/ui/drawer";
import { RadioGroup, RadioGroupItem } from "../../../components/ui/radio-group";
import { cn } from "../../../lib/utils";
import {
  type TerrenoResponse,
  atualizarTerreno,
} from "../../../services/api";
import type { NetworkSyncStatus } from "../types/cropHistory.types";
import type {
  SoilHandTestItem,
  SoilTypeData,
  SoilTypeId,
  SoilTypeOption,
} from "../types/soilType.types";

export const SOIL_TYPE_OPTIONS: SoilTypeOption[] = [
  {
    id: "areia",
    title: "Areia",
    subtitle: "Solta e seca rápido.",
    imageUrl: "/images/soil/Areia.png",
    fallbackColor: "#D8C39E",
  },
  {
    id: "barro",
    title: "Barro",
    subtitle: "Gruda e segura a água.",
    imageUrl: "/images/soil/Barro.png",
    fallbackColor: "#8C4530",
  },
  {
    id: "terra_preta",
    title: "Terra preta",
    subtitle: "Escura, fofa e rica.",
    imageUrl: "/images/soil/Terra_preta.png",
    fallbackColor: "#3D322C",
  },
  {
    id: "cascalho",
    title: "Cascalho",
    subtitle: "Cheia de pedras, a água escorre rápido.",
    imageUrl: "/images/soil/Cascalho.png",
    fallbackColor: "#9A8978",
  },
  {
    id: "terra_mista",
    title: "Terra mista",
    subtitle: "Mistura de areia e barro. Boa para plantar.",
    imageUrl: "/images/soil/Terra_mista.png",
    fallbackColor: "#7C5E44",
  },
];

export const SOIL_HAND_TEST_GUIDE: SoilHandTestItem[] = [
  {
    id: "areia",
    name: "Areia",
    description:
      "A terra esfarela toda. Não forma bolinha nem minhoca de jeito nenhum. A sensação é áspera, arranhando a mão.",
    swatchColor: "#D8C39E",
  },
  {
    id: "barro",
    name: "Barro",
    description:
      'A terra vira uma "massinha de modelar". Gruda bastante na mão, suja os dedos e permite fazer uma minhoca fina e comprida que não quebra com facilidade.',
    swatchColor: "#8C4530",
  },
  {
    id: "terra_mista",
    name: "Terra Mista",
    description:
      'É o meio-termo. Forma uma bolinha firme ou uma minhoca mais grossa, mas se tentar afinar ou dobrar, ela quebra em pedaços. Tem a "liga" do barro, mas com um pouco da aspereza da areia.',
    swatchColor: "#7C5E44",
  },
  {
    id: "terra_preta",
    name: "Terra Preta",
    description:
      "O destaque é a cor escura e o cheiro forte de terra (matéria orgânica). Lembra um pouco pó de café úmido. É muito fofa, forma um torrão na mão, mas se desmancha facilmente se apertar.",
    swatchColor: "#3D322C",
  },
  {
    id: "cascalho",
    name: "Cascalho",
    description:
      "Cheio de pedrinhas visíveis. Não dá liga nenhuma com a água, é solto, duro e raspa a mão.",
    swatchColor: "#9A8978",
  },
];

interface SoilThumbnailProps {
  soil: SoilTypeOption;
}

function SoilThumbnail({ soil }: SoilThumbnailProps) {
  const [hasError, setHasError] = React.useState(false);

  React.useEffect(() => {
    setHasError(false);
  }, [soil.imageUrl]);

  if (!soil.imageUrl || hasError) {
    return (
      <div
        aria-hidden="true"
        style={{ backgroundColor: soil.fallbackColor }}
        className="relative flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-black/10 shadow-inner sm:h-[70px] sm:w-[70px]"
      >
        <span className="absolute inset-0 bg-gradient-to-br from-white/15 via-transparent to-black/25" />
        <Layers className="relative h-6 w-6 text-white/90 drop-shadow-sm" />
      </div>
    );
  }

  return (
    <div className="h-16 w-16 shrink-0 overflow-hidden rounded-xl border border-[#E6E4DA] bg-[#EAE6DC] sm:h-[70px] sm:w-[70px]">
      <img
        src={soil.imageUrl}
        alt={soil.title}
        onError={() => setHasError(true)}
        className="h-full w-full object-cover"
      />
    </div>
  );
}

export interface SoilTypeStepProps {
  options?: SoilTypeOption[];
  initialValue?: SoilTypeId | null;
  networkStatus?: NetworkSyncStatus;
  terrenoId?: number | null;
  existingPrioridades?: Record<string, unknown> | null;
  onTerrenoUpdated?: (terreno: TerrenoResponse) => void;
  onBack?: () => void;
  onContinue?: (data: SoilTypeData) => void;
}

/**
 * Tela de Onboarding — Passo 3: Tipo de Solo.
 * Exibe seleção visual única via RadioGroup e Drawer educativo ("teste da mão") com alerta técnico.
 */
export function SoilTypeStep({
  options = SOIL_TYPE_OPTIONS,
  initialValue = null,
  networkStatus,
  terrenoId,
  existingPrioridades,
  onTerrenoUpdated,
  onBack,
  onContinue,
}: SoilTypeStepProps) {
  const { t } = useTranslation();
  const [isSaving, setIsSaving] = React.useState(false);

  const [selectedId, setSelectedId] = React.useState<SoilTypeId | null>(
    initialValue
  );

  const selectedOption = React.useMemo(
    () => options.find((item) => item.id === selectedId) ?? null,
    [options, selectedId]
  );

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedOption || isSaving) return;

    if (terrenoId != null) {
      setIsSaving(true);
      try {
        const updated = await atualizarTerreno(terrenoId, {
          prioridades: {
            ...(existingPrioridades ?? {}),
            tipo_solo: selectedOption.id,
          },
        });
        onTerrenoUpdated?.(updated);
      } catch {
        // Mantém fluxo offline-first se a API falhar
      } finally {
        setIsSaving(false);
      }
    }

    onContinue?.({ tipoSolo: selectedOption });
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
              <NetworkStatusBadge status={networkStatus} isSyncing={isSaving} />
            </div>
          </header>

          <SimulationBanner className="mt-4" />

          {/* Indicador de Progresso */}
          <section aria-label={t("onboarding.yourArea")} className="mt-6">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold uppercase tracking-wider text-[#6D6960]">
                {t("onboarding.yourArea")}
              </span>
              <span className="font-medium text-[#511D4E]">
                {t("common.stepOf", { current: 3, total: 4 })}
              </span>
            </div>

            <div
              role="progressbar"
              aria-label={t("common.stepOf", { current: 3, total: 4 })}
              aria-valuemin={1}
              aria-valuemax={4}
              aria-valuenow={3}
              className="mt-2 grid grid-cols-4 gap-2"
            >
              <span className="h-1 rounded-full bg-[#511D4E]" />
              <span className="h-1 rounded-full bg-[#511D4E]" />
              <span className="h-1 rounded-full bg-[#511D4E]" />
              <span className="h-1 rounded-full bg-[#E3E1D8]" />
            </div>
          </section>

          {/* Conteúdo Principal */}
          <main className="mt-8">
            <h1 className="text-[26px] font-bold leading-tight tracking-tight text-[#511D4E] sm:text-[28px]">
              {t("onboarding.soil.title")}
            </h1>

            <p className="mt-1.5 text-sm text-[#6D6960] sm:text-base">
              {t("onboarding.soil.subtitle")}
            </p>

            <div className="mt-3">
              <Drawer>
                <DrawerTrigger asChild>
                  <button
                    type="button"
                    className="inline-flex items-center gap-2 rounded-full border border-[#CAD17A] bg-[#CAD17A]/25 px-3.5 py-2 text-xs font-bold text-[#511D4E] transition-colors hover:bg-[#CAD17A]/45 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E] focus-visible:ring-offset-2 focus-visible:ring-offset-[#F7F6F0] sm:text-sm"
                  >
                    <HelpCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
                    <span>{t("onboarding.soil.helpTrigger")}</span>
                  </button>
                </DrawerTrigger>

                <DrawerContent className="max-h-[85dvh] overflow-y-auto">
                  <DrawerHeader>
                    <DrawerTitle>{t("onboarding.soil.drawerTitle")}</DrawerTitle>
                    <DrawerDescription className="mt-2 rounded-2xl border border-[#E6E4DA] bg-white p-3.5 text-sm leading-relaxed text-[#3D3933]">
                      {t("onboarding.soil.drawerSubtitle")}
                    </DrawerDescription>
                  </DrawerHeader>

                  <ul className="mt-4 flex flex-col gap-2.5">
                    {SOIL_HAND_TEST_GUIDE.map((item) => (
                      <li
                        key={item.id}
                        className="flex items-start gap-3 rounded-2xl border border-[#E6E4DA] bg-white p-3.5"
                      >
                        <span
                          aria-hidden="true"
                          style={{ backgroundColor: item.swatchColor }}
                          className="mt-0.5 h-6 w-6 shrink-0 rounded-full border border-black/15 shadow-inner"
                        />
                        <div className="min-w-0 text-sm leading-snug text-[#1F1C18]">
                          <strong className="font-bold text-[#511D4E]">
                            {t(`onboarding.soil.options.${item.id}.title`, {
                              defaultValue: item.name,
                            })}
                            :
                          </strong>{" "}
                          <span className="text-[#4E4A43]">
                            {t(`onboarding.soil.options.${item.id}.handDesc`, {
                              defaultValue: item.description,
                            })}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>

                  <div
                    role="note"
                    className="mt-4 rounded-2xl border border-[#E6E4DA] border-l-4 border-l-[#511D4E] bg-[#F7F6F0] p-4 shadow-xs"
                  >
                    <div className="flex items-center gap-2 text-xs font-bold tracking-wide text-[#511D4E] uppercase">
                      <Info className="h-4 w-4 shrink-0" aria-hidden="true" />
                      <span>{t("onboarding.soil.techNoteTitle")}</span>
                    </div>
                    <p className="mt-1.5 text-xs leading-relaxed text-[#4E4A43] sm:text-sm">
                      {t("onboarding.soil.techNoteBody")}
                    </p>
                  </div>

                  <DrawerFooter>
                    <DrawerClose asChild>
                      <Button type="button" variant="primary" className="w-full">
                        {t("common.understood")}
                      </Button>
                    </DrawerClose>
                  </DrawerFooter>
                </DrawerContent>
              </Drawer>
            </div>

            <RadioGroup
              aria-label={t("onboarding.soil.title")}
              value={selectedId}
              onValueChange={(value) => setSelectedId(value as SoilTypeId)}
              className="mt-6 flex flex-col gap-3"
            >
              {options.map((soil) => (
                <RadioGroupItem
                  key={soil.id}
                  value={soil.id}
                  className={cn(
                    "flex min-h-[86px] w-full items-center justify-between gap-3 rounded-2xl border p-3 text-left transition-colors",
                    selectedId === soil.id
                      ? "border-[#511D4E] bg-[#511D4E]/[0.06] ring-1 ring-[#511D4E]"
                      : "border-[#E6E4DA] bg-white hover:border-[#511D4E]/50 hover:bg-white/95"
                  )}
                >
                  {({ checked }) => (
                    <>
                      <div className="flex min-w-0 items-center gap-3.5">
                        <SoilThumbnail soil={soil} />

                        <div className="min-w-0">
                          <p
                            className={cn(
                              "text-base font-bold leading-snug",
                              checked ? "text-[#511D4E]" : "text-[#1F1C18]"
                            )}
                          >
                            {t(`onboarding.soil.options.${soil.id}.title`, {
                              defaultValue: soil.title,
                            })}
                          </p>
                          <p className="mt-0.5 text-xs leading-snug text-[#6D6960] sm:text-sm">
                            {t(`onboarding.soil.options.${soil.id}.subtitle`, {
                              defaultValue: soil.subtitle,
                            })}
                          </p>
                        </div>
                      </div>

                      <span
                        aria-hidden="true"
                        className={cn(
                          "mr-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                          checked
                            ? "border-[#511D4E] bg-[#511D4E] text-white"
                            : "border-[#D2CFC4] bg-white"
                        )}
                      >
                        {checked && <Check className="h-3.5 w-3.5 stroke-[3]" />}
                      </span>
                    </>
                  )}
                </RadioGroupItem>
              ))}
            </RadioGroup>
          </main>
        </div>

        {/* Footer */}
        <footer className="mt-8 flex flex-col items-center gap-3 pt-4">
          <Button
            type="submit"
            variant="primary"
            size="lg"
            disabled={!selectedOption}
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

export default SoilTypeStep;


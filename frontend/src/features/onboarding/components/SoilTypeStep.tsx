import * as React from "react";
import {
  AlertTriangle,
  ArrowRight,
  Check,
  ChevronLeft,
  HelpCircle,
  Layers,
  RefreshCw,
  Wifi,
  WifiOff,
} from "lucide-react";
import { Alert, AlertDescription } from "../../../components/ui/alert";
import { Badge } from "../../../components/ui/badge";
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
    description: "Se esfarelar e não formar uma bola.",
    swatchColor: "#D8C39E",
  },
  {
    id: "barro",
    name: "Barro",
    description: "Se formar uma bola dura e sujar muito a mão.",
    swatchColor: "#8C4530",
  },
  {
    id: "terra_mista",
    name: "Terra mista",
    description: "Se formar uma bola, mas quebrar fácil com o dedo.",
    swatchColor: "#7C5E44",
  },
  {
    id: "terra_preta",
    name: "Terra preta",
    description: "Se for escura, macia e cheirar a mato úmido.",
    swatchColor: "#3D322C",
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
  onBack,
  onContinue,
}: SoilTypeStepProps) {
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

  const [selectedId, setSelectedId] = React.useState<SoilTypeId | null>(
    initialValue
  );

  const badgeInfo = NETWORK_BADGE_CONFIG[resolvedNetworkStatus];
  const NetworkIcon = badgeInfo.icon;

  const selectedOption = React.useMemo(
    () => options.find((item) => item.id === selectedId) ?? null,
    [options, selectedId]
  );

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!selectedOption) return;
    onContinue?.({ tipoSolo: selectedOption });
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
              <span className="font-medium text-[#511D4E]">Passo 3 de 4</span>
            </div>

            <div
              role="progressbar"
              aria-label="Passo 3 de 4"
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
            <div className="flex items-center gap-2.5">
              <h1 className="text-[26px] font-bold leading-tight tracking-tight text-[#511D4E] sm:text-[28px]">
                Tipo de Solo
              </h1>

              <Drawer>
                <DrawerTrigger asChild>
                  <button
                    type="button"
                    aria-label="Como descobrir o tipo de solo na mão"
                    className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#CAD17A]/35 text-[#511D4E] transition-colors hover:bg-[#CAD17A]/55 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E] focus-visible:ring-offset-2 focus-visible:ring-offset-[#F7F6F0]"
                  >
                    <HelpCircle className="h-5 w-5" aria-hidden="true" />
                  </button>
                </DrawerTrigger>

                <DrawerContent>
                  <DrawerHeader>
                    <DrawerTitle>Como descobrir sua terra na mão</DrawerTitle>
                    <DrawerDescription>
                      Pegue um punhado de terra umedecida e aperte na mão:
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
                            {item.name}:
                          </strong>{" "}
                          <span className="text-[#4E4A43]">
                            {item.description}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>

                  <Alert variant="warning" className="mt-4">
                    <AlertTriangle
                      className="mt-0.5 h-5 w-5 shrink-0 text-[#8A6D14]"
                      aria-hidden="true"
                    />
                    <AlertDescription>
                      <strong>Atenção:</strong> O Kultiva auxilia no dia a dia,
                      mas não substitui assistência técnica profissional ou
                      análise de laboratório. Para recomendações precisas de
                      adubação, procure um Extensionista Rural (Emater, Senar ou
                      Secretaria de Agricultura) na sua região.
                    </AlertDescription>
                  </Alert>

                  <DrawerFooter>
                    <DrawerClose asChild>
                      <Button type="button" variant="primary" className="w-full">
                        Entendi
                      </Button>
                    </DrawerClose>
                  </DrawerFooter>
                </DrawerContent>
              </Drawer>
            </div>

            <p className="mt-1.5 text-sm text-[#6D6960] sm:text-base">
              Escolha a foto mais parecida. Não precisa de análise de
              laboratório.
            </p>

            <RadioGroup
              aria-label="Tipo de Solo"
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
                            {soil.title}
                          </p>
                          <p className="mt-0.5 text-xs leading-snug text-[#6D6960] sm:text-sm">
                            {soil.subtitle}
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

export default SoilTypeStep;


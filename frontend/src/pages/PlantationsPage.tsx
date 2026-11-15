import * as React from "react";
import { Database, Plus, RefreshCw, Trash2, WifiOff } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../components/ui/alert-dialog";
import { LanguageSelector } from "../components/LanguageSelector";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
  type CoordenadaApi,
  type TerrenoResponse,
  executarDemoSeed,
  excluirTerreno,
  formatarAreaHectares,
  listarTerrenos,
} from "../services/api";

export interface PlantationArea {
  id: string;
  name: string;
  sizeLabel: string;
  terrenoId?: number;
  areaHectares?: number | null;
  coordenadasPoligono?: CoordenadaApi[];
  prioridades?: Record<string, unknown> | null;
}

const INITIAL_AREAS: PlantationArea[] = [
  {
    id: "area-1",
    name: "Sítio do Lobato iaiaô",
    sizeLabel: "2 hectares",
  },
  {
    id: "area-2",
    name: "Sítio Boa Esperança - Área 1",
    sizeLabel: "5 hectares",
  },
];

function mapTerrenoToArea(terreno: TerrenoResponse): PlantationArea {
  return {
    id: String(terreno.id),
    terrenoId: terreno.id,
    name: terreno.nome_propriedade,
    sizeLabel: formatarAreaHectares(terreno.area_hectares),
    areaHectares: terreno.area_hectares ?? null,
    coordenadasPoligono: terreno.coordenadas_poligono,
    prioridades: terreno.prioridades ?? null,
  };
}

export interface PlantationsPageProps {
  onCreateArea?: () => void;
  onSelectArea?: (area: PlantationArea) => void;
  onAreaDeleted?: (area: PlantationArea) => void;
  simulationBanner?: React.ReactNode;
}

export function PlantationsPage({
  onCreateArea,
  onSelectArea,
  onAreaDeleted,
  simulationBanner,
}: PlantationsPageProps) {
  const [areas, setAreas] = React.useState<PlantationArea[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isOfflineFallback, setIsOfflineFallback] = React.useState(false);
  const [isSeedingDemo, setIsSeedingDemo] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [apiError, setApiError] = React.useState<string | null>(null);
  const [deleteModalOpen, setDeleteModalOpen] = React.useState(false);
  const [areaToDelete, setAreaToDelete] = React.useState<PlantationArea | null>(
    null
  );

  const fetchAreas = React.useCallback(async () => {
    setIsLoading(true);
    setApiError(null);
    try {
      const terrenos = await listarTerrenos();
      setAreas(terrenos.map(mapTerrenoToArea));
      setIsOfflineFallback(false);
    } catch {
      setAreas((prev) => (prev.length > 0 ? prev : INITIAL_AREAS));
      setIsOfflineFallback(true);
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void fetchAreas();
  }, [fetchAreas]);

  const handleLoadDemo = async () => {
    setIsSeedingDemo(true);
    setApiError(null);
    try {
      await executarDemoSeed(false);
      await fetchAreas();
    } catch (error) {
      setApiError(
        error instanceof Error
          ? error.message
          : "Não foi possível carregar os dados de demonstração."
      );
    } finally {
      setIsSeedingDemo(false);
    }
  };

  const handleOpenDeleteModal = (area: PlantationArea) => {
    setAreaToDelete(area);
    setDeleteModalOpen(true);
  };

  const handleCancelDelete = () => {
    if (isDeleting) return;
    setDeleteModalOpen(false);
    setAreaToDelete(null);
  };

  const handleConfirmDelete = async () => {
    if (!areaToDelete) return;
    setApiError(null);

    if (areaToDelete.terrenoId !== undefined) {
      setIsDeleting(true);
      try {
        await excluirTerreno(areaToDelete.terrenoId);
      } catch (error) {
        setApiError(
          error instanceof Error
            ? error.message
            : "Não foi possível excluir a área no servidor."
        );
        setIsDeleting(false);
        return;
      } finally {
        setIsDeleting(false);
      }
    }

    const removedArea = areaToDelete;
    setAreas((prev) => prev.filter((item) => item.id !== removedArea.id));
    setDeleteModalOpen(false);
    setAreaToDelete(null);
    onAreaDeleted?.(removedArea);
  };

  const formattedCount = String(areas.length).padStart(2, "0");

  return (
    <div className="min-h-screen bg-[#F7F6F0] md:bg-[#EFECE3] md:py-6">
      <div className="mx-auto flex min-h-screen max-w-md flex-col justify-between bg-[#F7F6F0] px-5 pt-7 pb-8 text-[#1F1C18] md:min-h-[820px] md:rounded-[32px] md:border md:border-[#E6E4DA] md:shadow-sm">
        <div>
          <header className="flex items-center justify-between gap-2">
            <span className="font-['Nunito',ui-rounded,system-ui,sans-serif] text-[24px] font-black tracking-tight text-[#511D4E]">
              Kultiva
            </span>

            <div className="flex items-center gap-2">
              {isOfflineFallback ? (
                <Badge variant="offline">
                  <WifiOff className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>Offline</span>
                </Badge>
              ) : (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleLoadDemo}
                  disabled={isSeedingDemo || isLoading}
                  className="border-[#E6E4DA] bg-white text-xs text-[#511D4E]"
                >
                  <Database className="h-3.5 w-3.5" aria-hidden="true" />
                  <span>{isSeedingDemo ? "Carregando..." : "Demo"}</span>
                </Button>
              )}

              <LanguageSelector />

              <button
                type="button"
                onClick={() => void fetchAreas()}
                disabled={isLoading}
                aria-label="Atualizar lista de terrenos"
                className="flex h-9 w-9 items-center justify-center rounded-full border border-[#E6E4DA] bg-white text-[#511D4E] transition-colors hover:bg-[#EFECE3] disabled:opacity-50"
              >
                <RefreshCw
                  className={isLoading ? "h-4 w-4 animate-spin" : "h-4 w-4"}
                  aria-hidden="true"
                />
              </button>
            </div>
          </header>

          <section className="mt-7">
            <h1 className="text-[32px] font-bold tracking-tight text-[#511D4E] leading-tight">
              Plantações
            </h1>
            <p className="mt-1.5 text-[15px] text-[#6D6960]">Seus terrenos.</p>
          </section>

          {apiError && (
            <div
              role="alert"
              className="mt-4 rounded-2xl border border-[#C42311]/30 bg-[#C42311]/10 px-4 py-3 text-xs font-medium text-[#C42311]"
            >
              {apiError}
            </div>
          )}

          {isOfflineFallback && (
            <div className="mt-4 rounded-2xl border border-[#CAD17A] bg-[#FCF59B]/40 px-4 py-3 text-xs text-[#4A3B12]">
              API indisponível no momento. Exibindo áreas de exemplo locais.
            </div>
          )}

          {simulationBanner && <div className="mt-5">{simulationBanner}</div>}

          <section className="mt-8">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold tracking-[0.08em] text-[#6D6960] uppercase">
                ÁREAS CADASTRADAS
              </span>
              <span className="text-[14px] font-bold text-[#511D4E]">
                {formattedCount}
              </span>
            </div>

            {isLoading && areas.length === 0 ? (
              <div className="mt-4 rounded-2xl border border-[#E6E4DA] bg-white/70 px-4 py-8 text-center text-sm text-[#6D6960]">
                Carregando terrenos cadastrados...
              </div>
            ) : areas.length > 0 ? (
              <ul className="mt-3 space-y-3">
                {areas.map((area) => (
                  <li
                    key={area.id}
                    className="flex items-center justify-between gap-3 rounded-2xl border border-[#E6E4DA] bg-white px-4 py-4 shadow-[0_1px_2px_rgba(31,28,24,0.03)]"
                  >
                    <button
                      type="button"
                      onClick={() => onSelectArea?.(area)}
                      className="min-w-0 flex-1 text-left focus-visible:outline-none"
                    >
                      <p className="truncate text-[16px] font-bold text-[#1F1C18]">
                        {area.name}
                      </p>
                      <p className="mt-1 text-[14px] text-[#6D6960]">
                        {area.sizeLabel}
                      </p>
                    </button>

                    <button
                      type="button"
                      onClick={() => handleOpenDeleteModal(area)}
                      aria-label={`Excluir ${area.name}`}
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-red-50 text-red-600 transition-colors hover:bg-red-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-600"
                    >
                      <Trash2 className="h-[18px] w-[18px]" aria-hidden="true" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="mt-4 rounded-2xl border border-dashed border-[#E6E4DA] bg-white/70 px-4 py-8 text-center">
                <p className="text-[15px] font-semibold text-[#1F1C18]">
                  Nenhuma área cadastrada
                </p>
                <p className="mt-1 text-[13px] text-[#6D6960]">
                  Crie uma nova área abaixo ou carregue áreas de demonstração
                  para começar seu planejamento.
                </p>
              </div>
            )}
          </section>
        </div>

        <footer className="mt-8 flex flex-col gap-2.5 pt-2">
          <Button
            type="button"
            variant="primary"
            size="lg"
            onClick={onCreateArea}
            className="w-full"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
            Criar Nova Área
          </Button>
        </footer>
      </div>

      <AlertDialog
        open={deleteModalOpen}
        onOpenChange={(open) => {
          if (!open) {
            handleCancelDelete();
          } else {
            setDeleteModalOpen(true);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <div
              className="flex h-11 w-11 items-center justify-center rounded-2xl bg-red-50 text-lg font-extrabold text-red-600"
              aria-hidden="true"
            >
              !
            </div>
            <AlertDialogTitle className="mt-4 text-[22px] font-bold text-[#1F1C18]">
              Excluir Área?
            </AlertDialogTitle>
            <AlertDialogDescription className="mt-2 text-[14px] leading-relaxed text-[#6D6960]">
              Tem certeza? Esta ação apagará todo o histórico e não pode ser
              desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>

          <AlertDialogFooter className="mt-6">
            <AlertDialogCancel
              onClick={handleCancelDelete}
              disabled={isDeleting}
            >
              Cancelar
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => void handleConfirmDelete()}
              disabled={isDeleting}
              className="bg-red-600 text-white hover:bg-red-700"
            >
              {isDeleting ? "Excluindo..." : "Sim, Excluir"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

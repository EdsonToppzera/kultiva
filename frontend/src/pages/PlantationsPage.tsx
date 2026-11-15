import * as React from "react";
import { Plus, Trash2 } from "lucide-react";
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
import { Button } from "../components/ui/button";

export interface PlantationArea {
  id: string;
  name: string;
  sizeLabel: string;
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

export interface PlantationsPageProps {
  onCreateArea?: () => void;
  onSelectArea?: (area: PlantationArea) => void;
}

export function PlantationsPage({
  onCreateArea,
  onSelectArea,
}: PlantationsPageProps) {
  const [areas, setAreas] = React.useState<PlantationArea[]>(INITIAL_AREAS);
  const [deleteModalOpen, setDeleteModalOpen] = React.useState(false);
  const [areaToDelete, setAreaToDelete] = React.useState<PlantationArea | null>(
    null
  );

  const handleOpenDeleteModal = (area: PlantationArea) => {
    setAreaToDelete(area);
    setDeleteModalOpen(true);
  };

  const handleCancelDelete = () => {
    setDeleteModalOpen(false);
    setAreaToDelete(null);
  };

  const handleConfirmDelete = () => {
    if (!areaToDelete) return;
    setAreas((prev) => prev.filter((item) => item.id !== areaToDelete.id));
    setDeleteModalOpen(false);
    setAreaToDelete(null);
  };

  const formattedCount = String(areas.length).padStart(2, "0");

  return (
    <div className="min-h-screen bg-[#F7F6F0] md:bg-[#EFECE3] md:py-6">
      <div className="mx-auto flex min-h-screen max-w-md flex-col justify-between bg-[#F7F6F0] px-5 pt-7 pb-8 text-[#1F1C18] md:min-h-[820px] md:rounded-[32px] md:border md:border-[#E6E4DA] md:shadow-sm">
        <div>
          <header className="flex items-center justify-between">
            <span className="font-['Nunito',ui-rounded,system-ui,sans-serif] text-[24px] font-black tracking-tight text-[#511D4E]">
              Kultiva
            </span>
          </header>

          <section className="mt-7">
            <h1 className="text-[32px] font-bold tracking-tight text-[#511D4E] leading-tight">
              Plantações
            </h1>
            <p className="mt-1.5 text-[15px] text-[#6D6960]">Seus terrenos.</p>
          </section>

          <section className="mt-8">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold tracking-[0.08em] text-[#6D6960] uppercase">
                ÁREAS CADASTRADAS
              </span>
              <span className="text-[14px] font-bold text-[#511D4E]">
                {formattedCount}
              </span>
            </div>

            {areas.length > 0 ? (
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
                  Crie uma nova área abaixo para começar seu planejamento.
                </p>
              </div>
            )}
          </section>
        </div>

        <footer className="mt-8 pt-2">
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
            <AlertDialogCancel onClick={handleCancelDelete}>
              Cancelar
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleConfirmDelete}
              className="bg-red-600 text-white hover:bg-red-700"
            >
              Sim, Excluir
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}


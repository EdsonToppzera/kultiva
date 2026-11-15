import * as React from "react";

/**
 * Busca itens de catálogo no backend com debounce quando o combobox está aberto,
 * mantendo os itens iniciais como fallback imediato.
 */
export function useCatalogSearch<T>(
  open: boolean,
  query: string,
  initialItems: T[],
  fetcher: (query: string, limit?: number, signal?: AbortSignal) => Promise<T[]>,
  limit = 30
): T[] {
  const [items, setItems] = React.useState<T[]>(initialItems);

  React.useEffect(() => {
    setItems(initialItems);
  }, [initialItems]);

  React.useEffect(() => {
    if (!open) return;

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const result = await fetcher(query, limit, controller.signal);
        if (!controller.signal.aborted) {
          setItems(result);
        }
      } catch (err) {
        if (!(err instanceof DOMException && err.name === "AbortError")) {
          // Fallback silencioso para os itens locais já carregados
        }
      }
    }, 180);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [open, query, fetcher, limit]);

  return items;
}


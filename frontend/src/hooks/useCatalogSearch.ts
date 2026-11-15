import * as React from "react";
import { type AppLanguage, useLanguage } from "../contexts/LanguageContext";

export interface UseCatalogSearchResult<T> {
  items: T[];
  isLoading: boolean;
}

/**
 * Busca itens de catálogo no backend com debounce quando o combobox está aberto,
 * reagindo à troca de idioma (PT-BR / EN) e mantendo os itens iniciais como fallback.
 */
export function useCatalogSearch<T>(
  open: boolean,
  query: string,
  initialItems: T[],
  fetcher: (
    query: string,
    limit?: number,
    signal?: AbortSignal,
    lang?: AppLanguage
  ) => Promise<T[]>,
  limit = 30
): UseCatalogSearchResult<T> {
  const { language } = useLanguage();
  const [items, setItems] = React.useState<T[]>(initialItems);
  const [resolvedKey, setResolvedKey] = React.useState<string | null>(null);
  const requestKey = `${language}:${query}`;
  const isLoading = open && resolvedKey !== requestKey;

  React.useEffect(() => {
    setItems(initialItems);
    setResolvedKey(null);
  }, [initialItems]);

  React.useEffect(() => {
    if (!open) return;

    const controller = new AbortController();
    const delayMs = query.trim() === "" ? 0 : 180;
    const timer = window.setTimeout(async () => {
      try {
        const result = await fetcher(query, limit, controller.signal, language);
        if (!controller.signal.aborted) {
          setItems(result);
          setResolvedKey(requestKey);
        }
      } catch (err) {
        if (!(err instanceof DOMException && err.name === "AbortError")) {
          if (!controller.signal.aborted) {
            setItems([]);
            setResolvedKey(requestKey);
          }
        }
      }
    }, delayMs);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [open, query, fetcher, limit, language, requestKey]);

  return { items, isLoading };
}


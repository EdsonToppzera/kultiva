import * as React from "react";
import { Search, X } from "lucide-react";
import { cn } from "../../lib/utils";

/**
 * Normaliza texto removendo acentos, hífens e maiúsculas para comparação fuzzy.
 */
export function normalizeSearchText(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[-_]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function levenshteinDistance(a: string, b: string): number {
  const rows = a.length + 1;
  const cols = b.length + 1;
  const dp: number[][] = Array.from({ length: rows }, () =>
    Array<number>(cols).fill(0)
  );

  for (let i = 0; i < rows; i += 1) dp[i][0] = i;
  for (let j = 0; j < cols; j += 1) dp[0][j] = j;

  for (let i = 1; i < rows; i += 1) {
    for (let j = 1; j < cols; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      dp[i][j] = Math.min(
        dp[i - 1][j] + 1,
        dp[i][j - 1] + 1,
        dp[i - 1][j - 1] + cost
      );
    }
  }

  return dp[a.length][b.length];
}

function isOrderedSubsequenceTight(query: string, target: string): boolean {
  if (query.length < 3) return false;
  let qi = 0;
  let firstMatch = -1;
  let lastMatch = -1;

  for (let ti = 0; ti < target.length && qi < query.length; ti += 1) {
    if (target[ti] === query[qi]) {
      if (firstMatch === -1) firstMatch = ti;
      lastMatch = ti;
      qi += 1;
    }
  }

  if (qi !== query.length) return false;
  return lastMatch - firstMatch + 1 <= Math.ceil(query.length * 1.6);
}

/**
 * Calcula pontuação fuzzy entre a busca do usuário, o valor do item e seus sinônimos.
 * Retorna `0` quando não há correspondência.
 */
export function fuzzyMatchScore(
  rawQuery: string,
  value: string,
  keywords: string[] = []
): number {
  const query = normalizeSearchText(rawQuery);
  if (!query) return 1;

  const candidates = [value, ...keywords]
    .map(normalizeSearchText)
    .filter(Boolean);

  let bestScore = 0;

  for (const candidate of candidates) {
    if (candidate === query) {
      return 120;
    }

    const index = candidate.indexOf(query);
    if (index !== -1) {
      bestScore = Math.max(bestScore, index === 0 ? 100 : 85 - index * 0.1);
      continue;
    }

    const queryTokens = query.split(" ").filter(Boolean);
    const candidateTokens = candidate.split(" ").filter(Boolean);

    if (queryTokens.length > 1) {
      const allTokensMatch = queryTokens.every((qt) =>
        candidateTokens.some((ct) => fuzzyMatchScore(qt, ct) > 0)
      );
      if (allTokensMatch) {
        bestScore = Math.max(bestScore, 70);
        continue;
      }
    }

    if (query.length >= 3) {
      const maxEdits = query.length >= 6 ? 2 : 1;
      for (const token of [candidate, ...candidateTokens]) {
        if (Math.abs(token.length - query.length) <= maxEdits) {
          const distance = levenshteinDistance(query, token);
          if (distance <= maxEdits) {
            bestScore = Math.max(bestScore, 65 - distance * 10);
          }
        }
        if (isOrderedSubsequenceTight(query, token)) {
          bestScore = Math.max(bestScore, 45);
        }
      }
    }
  }

  return bestScore;
}

interface CommandContextValue {
  search: string;
  setSearch: (next: string) => void;
  shouldFilter: boolean;
  activeValue: string | null;
  setActiveValue: (val: string | null) => void;
  visibleCount: number;
  reportVisibility: (id: string, visible: boolean) => void;
  listRef: React.MutableRefObject<HTMLDivElement | null>;
}

const CommandContext = React.createContext<CommandContextValue | null>(null);

function useCommandContext(): CommandContextValue {
  const ctx = React.useContext(CommandContext);
  if (!ctx) {
    throw new Error("Command components must be used inside <Command />.");
  }
  return ctx;
}

export interface CommandProps extends React.HTMLAttributes<HTMLDivElement> {
  shouldFilter?: boolean;
  value?: string;
  onValueChange?: (value: string) => void;
}

/**
 * Container Command compatível com Shadcn UI e equipado com Fuzzy Search local.
 */
export const Command = React.forwardRef<HTMLDivElement, CommandProps>(
  (
    {
      className,
      shouldFilter = true,
      value: controlledSearch,
      onValueChange,
      children,
      ...props
    },
    ref
  ) => {
    const [uncontrolledSearch, setUncontrolledSearch] = React.useState("");
    const [activeValue, setActiveValue] = React.useState<string | null>(null);
    const [visibleIds, setVisibleIds] = React.useState<Set<string>>(
      () => new Set()
    );
    const listRef = React.useRef<HTMLDivElement | null>(null);

    const isControlled = controlledSearch !== undefined;
    const search = isControlled ? controlledSearch : uncontrolledSearch;

    const setSearch = React.useCallback(
      (next: string) => {
        if (!isControlled) {
          setUncontrolledSearch(next);
        }
        onValueChange?.(next);
      },
      [isControlled, onValueChange]
    );

    const reportVisibility = React.useCallback(
      (id: string, visible: boolean) => {
        setVisibleIds((prev) => {
          const exists = prev.has(id);
          if (exists === visible) return prev;
          const next = new Set(prev);
          if (visible) next.add(id);
          else next.delete(id);
          return next;
        });
      },
      []
    );

    return (
      <CommandContext.Provider
        value={{
          search,
          setSearch,
          shouldFilter,
          activeValue,
          setActiveValue,
          visibleCount: visibleIds.size,
          reportVisibility,
          listRef,
        }}
      >
        <div
          ref={ref}
          className={cn(
            "flex w-full flex-col overflow-hidden bg-transparent text-[#1F1C18]",
            className
          )}
          {...props}
        >
          {children}
        </div>
      </CommandContext.Provider>
    );
  }
);

Command.displayName = "Command";

export interface CommandInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "value"> {
  value?: string;
  onValueChange?: (value: string) => void;
  wrapperClassName?: string;
  showClearButton?: boolean;
}

/**
 * Campo de busca do Command com suporte a atalhos de teclado (setas e Enter).
 */
export const CommandInput = React.forwardRef<HTMLInputElement, CommandInputProps>(
  (
    {
      className,
      wrapperClassName,
      value: propValue,
      onValueChange,
      showClearButton = true,
      onKeyDown,
      ...props
    },
    ref
  ) => {
    const { search, setSearch, activeValue, setActiveValue, listRef } =
      useCommandContext();

    const currentValue = propValue !== undefined ? propValue : search;

    const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
      const next = event.target.value;
      setSearch(next);
      onValueChange?.(next);
    };

    const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
      onKeyDown?.(event);
      if (event.defaultPrevented) return;

      const items = Array.from(
        listRef.current?.querySelectorAll<HTMLElement>('[data-command-item="true"]') ??
          []
      );
      if (items.length === 0) return;

      const currentIndex = items.findIndex(
        (el) => el.dataset.value === activeValue
      );

      if (event.key === "ArrowDown") {
        event.preventDefault();
        const nextItem = items[(currentIndex + 1) % items.length];
        setActiveValue(nextItem.dataset.value ?? null);
        nextItem.scrollIntoView({ block: "nearest" });
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        const prevIndex =
          currentIndex <= 0 ? items.length - 1 : currentIndex - 1;
        const prevItem = items[prevIndex];
        setActiveValue(prevItem.dataset.value ?? null);
        prevItem.scrollIntoView({ block: "nearest" });
      } else if (event.key === "Enter") {
        event.preventDefault();
        const target = items[currentIndex >= 0 ? currentIndex : 0];
        target?.click();
      }
    };

    return (
      <div
        className={cn(
          "flex min-h-[52px] items-center gap-2.5 rounded-2xl border-[1.5px] border-[#511D4E] bg-white px-3.5 shadow-sm",
          wrapperClassName
        )}
      >
        <Search
          className="h-5 w-5 shrink-0 text-[#511D4E]"
          aria-hidden="true"
        />
        <input
          ref={ref}
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded="true"
          value={currentValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          className={cn(
            "w-full bg-transparent py-2.5 text-base text-[#1F1C18] placeholder:text-[#8E897E] focus:outline-none",
            className
          )}
          {...props}
        />
        {showClearButton && currentValue.length > 0 && (
          <button
            type="button"
            aria-label="Limpar busca"
            onClick={() => {
              setSearch("");
              onValueChange?.("");
            }}
            className="rounded-full p-1 text-[#6F6B63] hover:bg-[#511D4E]/10 hover:text-[#511D4E] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E]"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        )}
      </div>
    );
  }
);

CommandInput.displayName = "CommandInput";

export type CommandListProps = React.HTMLAttributes<HTMLDivElement>;

/**
 * Área rolável que agrupa e exibe as opções filtradas do Command.
 */
export const CommandList = React.forwardRef<HTMLDivElement, CommandListProps>(
  ({ className, children, ...props }, ref) => {
    const { listRef } = useCommandContext();

    const assignRef = (node: HTMLDivElement | null) => {
      listRef.current = node;
      if (typeof ref === "function") {
        ref(node);
      } else if (ref) {
        ref.current = node;
      }
    };

    return (
      <div
        ref={assignRef}
        role="listbox"
        className={cn(
          "mt-2.5 max-h-[280px] overflow-y-auto overscroll-contain pr-0.5",
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }
);

CommandList.displayName = "CommandList";

export type CommandEmptyProps = React.HTMLAttributes<HTMLDivElement>;

/**
 * Estado vazio exibido quando nenhum item da lista corresponde à busca.
 */
export const CommandEmpty = React.forwardRef<HTMLDivElement, CommandEmptyProps>(
  ({ className, children, ...props }, ref) => {
    const { visibleCount } = useCommandContext();

    if (visibleCount > 0) return null;

    return (
      <div
        ref={ref}
        className={cn(
          "rounded-2xl border border-dashed border-[#D8D5CA] bg-white/80 px-4 py-6 text-center text-sm text-[#6B665E]",
          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }
);

CommandEmpty.displayName = "CommandEmpty";

export interface CommandGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  heading?: React.ReactNode;
}

/**
 * Agrupamento semântico de opções dentro do CommandList.
 */
export const CommandGroup = React.forwardRef<HTMLDivElement, CommandGroupProps>(
  ({ className, heading, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        role="group"
        className={cn("flex flex-col gap-2", className)}
        {...props}
      >
        {heading && (
          <div className="px-1 text-[11px] font-semibold uppercase tracking-wider text-[#6D6960]">
            {heading}
          </div>
        )}
        {children}
      </div>
    );
  }
);

CommandGroup.displayName = "CommandGroup";

export interface CommandItemProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onSelect"> {
  value: string;
  keywords?: string[];
  onSelect?: (value: string) => void;
}

/**
 * Item selecionável do Command que valida correspondência fuzzy e proíbe entrada livre fora da lista.
 */
export const CommandItem = React.forwardRef<HTMLButtonElement, CommandItemProps>(
  (
    {
      className,
      value,
      keywords,
      onSelect,
      onClick,
      onMouseEnter,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const itemId = React.useId();
    const { search, shouldFilter, activeValue, setActiveValue, reportVisibility } =
      useCommandContext();

    const isMatch =
      !shouldFilter || fuzzyMatchScore(search, value, keywords) > 0;

    React.useLayoutEffect(() => {
      reportVisibility(itemId, isMatch);
      return () => {
        reportVisibility(itemId, false);
      };
    }, [itemId, isMatch, reportVisibility]);

    if (!isMatch) return null;

    const isActive = activeValue === value;

    return (
      <button
        ref={ref}
        type="button"
        role="option"
        aria-selected={isActive}
        data-command-item="true"
        data-value={value}
        data-active={isActive ? "true" : "false"}
        disabled={disabled}
        onMouseEnter={(event) => {
          setActiveValue(value);
          onMouseEnter?.(event);
        }}
        onClick={(event) => {
          onClick?.(event);
          if (!event.defaultPrevented && !disabled) {
            onSelect?.(value);
          }
        }}
        className={cn(
          "flex w-full items-center gap-3 rounded-2xl border border-[#E6E4DA] bg-white p-3 text-left transition-colors",
          "hover:border-[#511D4E] hover:bg-[#FCF59B]/15",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#511D4E]",
          isActive && "border-[#511D4E] bg-[#FCF59B]/20",
          disabled && "pointer-events-none opacity-50",
          className
        )}
        {...props}
      >
        {children}
      </button>
    );
  }
);

CommandItem.displayName = "CommandItem";

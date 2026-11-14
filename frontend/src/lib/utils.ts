export type ClassValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | ClassValue[]
  | Record<string, boolean | null | undefined>;

function toClassNames(value: ClassValue): string[] {
  if (!value && value !== 0) return [];
  if (typeof value === "string" || typeof value === "number") {
    return String(value).trim().split(/\s+/).filter(Boolean);
  }
  if (Array.isArray(value)) {
    return value.flatMap(toClassNames);
  }
  if (typeof value === "object") {
    return Object.entries(value)
      .filter(([, enabled]) => Boolean(enabled))
      .flatMap(([key]) => key.trim().split(/\s+/).filter(Boolean));
  }
  return [];
}

/**
 * Combina classes CSS condicionalmente no padrão dos utilitários Shadcn UI.
 */
export function cn(...inputs: ClassValue[]): string {
  return inputs.flatMap(toClassNames).join(" ");
}


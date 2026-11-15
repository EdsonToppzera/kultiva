import type { CropOption } from "../features/onboarding/types/cropHistory.types";

/**
 * Dicionário local de culturas com sinônimos regionais para suporte Offline-First e Fuzzy Search.
 */
export const CROPS_DICTIONARY: CropOption[] = [
  {
    id: "milho",
    officialName: "Milho",
    popularNames: ["Milho"],
    imageUrl: "/images/crops/milho.jpg",
  },
  {
    id: "mandioca",
    officialName: "Mandioca",
    popularNames: ["Mandioca", "Macaxeira", "Aipim"],
    imageUrl: "/images/crops/mandioca.jpg",
  },
  {
    id: "feijao-carioca",
    officialName: "Feijão-carioca",
    popularNames: ["Feijão-carioca", "Feijão carioquinha"],
    imageUrl: "/images/crops/feijao-carioca.jpg",
  },
  {
    id: "feijao-caupi",
    officialName: "Feijão-caupi",
    popularNames: ["Feijão-de-corda", "Feijão-macassar", "Feijão fradinho"],
    imageUrl: "/images/crops/feijao-caupi.jpg",
  },
  {
    id: "feijao-de-porco",
    officialName: "Feijão-de-porco",
    popularNames: ["Feijão-de-porco", "Adubação verde"],
    imageUrl: null,
  },
  {
    id: "abobora",
    officialName: "Abóbora",
    popularNames: ["Abóbora", "Jerimum", "Abóbora-cabotiá"],
    imageUrl: "/images/crops/abobora.jpg",
  },
  {
    id: "batata-doce",
    officialName: "Batata-doce",
    popularNames: ["Batata-doce", "Batata da terra"],
    imageUrl: "/images/crops/batata-doce.jpg",
  },
  {
    id: "sorgo",
    officialName: "Sorgo",
    popularNames: ["Sorgo", "Milho-alvo", "Sorgo forrageiro"],
    imageUrl: null,
  },
  {
    id: "crotalaria",
    officialName: "Crotalária",
    popularNames: ["Crotalária", "Chocalho-de-cascavel", "Adubo verde"],
    imageUrl: null,
  },
  {
    id: "amendoim",
    officialName: "Amendoim",
    popularNames: ["Amendoim", "Mendubi"],
    imageUrl: "/images/crops/amendoim.jpg",
  },
  {
    id: "milheto",
    officialName: "Milheto",
    popularNames: ["Milheto", "Capim-pé-de-galinha"],
    imageUrl: null,
  },
  {
    id: "pousio",
    officialName: "Descanso da terra",
    popularNames: ["Descanso da terra", "Pousio", "Terra parada"],
    imageUrl: null,
  },
];

/**
 * Formata a lista de nomes populares entre aspas em português (ex.: `"Mandioca", "Macaxeira" e "Aipim"`).
 * Quando houver mais de `maxItems` nomes, limita a exibição e adiciona reticências (`...`).
 */
export function formatPopularNames(
  popularNames: string[],
  maxItems = 3
): string {
  if (popularNames.length === 0) return "";
  const visible = popularNames.slice(0, maxItems);
  const quoted = visible.map((name) => `"${name}"`);
  if (popularNames.length > maxItems) {
    return `${quoted.join(", ")}, ...`;
  }
  if (quoted.length === 1) return quoted[0];
  if (quoted.length === 2) return `${quoted[0]} e ${quoted[1]}`;
  return `${quoted.slice(0, -1).join(", ")} e ${quoted[quoted.length - 1]}`;
}


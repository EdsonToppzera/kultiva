export interface PestOption {
  id: string;
  officialName: string;
  popularNames: string[];
  category: string;
}

export const PESTS_DICTIONARY: PestOption[] = [
  {
    id: "lagarta-do-cartucho",
    officialName: "Lagarta-do-cartucho",
    popularNames: ["spodoptera", "lagarta do milho", "lagarta-rosca"],
    category: "Inseto",
  },
  {
    id: "cigarrinha-do-milho",
    officialName: "Cigarrinha-do-milho",
    popularNames: ["cigarrinha", "enfezamento"],
    category: "Inseto",
  },
  {
    id: "mosca-branca",
    officialName: "Mosca-branca",
    popularNames: ["mosquinha branca", "bemisia"],
    category: "Inseto",
  },
  {
    id: "pulgao",
    officialName: "Pulgão",
    popularNames: ["piolho de planta", "afídeo"],
    category: "Inseto",
  },
  {
    id: "formiga-cortadeira",
    officialName: "Formiga-cortadeira",
    popularNames: ["saúva", "quenquém", "formiga de roça"],
    category: "Inseto",
  },
  {
    id: "nematoides",
    officialName: "Nematoides",
    popularNames: ["nematoide das galhas", "caroço na raiz", "verme de raiz"],
    category: "Solo / Raiz",
  },
  {
    id: "podridao-radicular",
    officialName: "Podridão de raiz",
    popularNames: ["mela", "podridão radicular", "fungo de solo"],
    category: "Doença",
  },
  {
    id: "antracnose",
    officialName: "Antracnose",
    popularNames: ["mancha preta", "queima das folhas"],
    category: "Doença",
  },
  {
    id: "broca-da-raiz",
    officialName: "Broca-da-raiz",
    popularNames: ["broca da mandioca", "besouro"],
    category: "Inseto",
  },
  {
    id: "percevejo",
    officialName: "Percevejo",
    popularNames: ["maria-fedida", "fedorento", "percevejo marrom"],
    category: "Inseto",
  },
  {
    id: "acaro",
    officialName: "Ácaro",
    popularNames: ["ácaro rajado", "ácaro vermelho", "teia na folha"],
    category: "Praga",
  },
  {
    id: "murcha-bacteriana",
    officialName: "Murcha-bacteriana",
    popularNames: ["murchadeira", "murcha do solo"],
    category: "Doença",
  },
];

export const PESTS_DICTIONARY_EN: PestOption[] = [
  {
    id: "lagarta-do-cartucho",
    officialName: "Fall armyworm",
    popularNames: ["spodoptera", "corn leafworm", "cutworm"],
    category: "Insect",
  },
  {
    id: "cigarrinha-do-milho",
    officialName: "Corn leafhopper",
    popularNames: ["leafhopper", "corn stunt"],
    category: "Insect",
  },
  {
    id: "mosca-branca",
    officialName: "Whitefly",
    popularNames: ["silverleaf whitefly", "bemisia"],
    category: "Insect",
  },
  {
    id: "pulgao",
    officialName: "Aphid",
    popularNames: ["plant louse", "greenfly"],
    category: "Insect",
  },
  {
    id: "formiga-cortadeira",
    officialName: "Leafcutter ant",
    popularNames: ["saúva ant", "quenquém", "leaf ant"],
    category: "Insect",
  },
  {
    id: "nematoides",
    officialName: "Nematodes",
    popularNames: ["root-knot nematode", "root galls", "root worms"],
    category: "Soil / Root",
  },
  {
    id: "podridao-radicular",
    officialName: "Root rot",
    popularNames: ["damping off", "root blight", "soil fungus"],
    category: "Disease",
  },
  {
    id: "antracnose",
    officialName: "Anthracnose",
    popularNames: ["black spot", "leaf blight"],
    category: "Disease",
  },
  {
    id: "broca-da-raiz",
    officialName: "Root borer",
    popularNames: ["cassava borer", "root beetle"],
    category: "Insect",
  },
  {
    id: "percevejo",
    officialName: "Stink bug",
    popularNames: ["brown stink bug", "shield bug"],
    category: "Insect",
  },
  {
    id: "acaro",
    officialName: "Mite",
    popularNames: ["two-spotted spider mite", "red mite", "spider web mite"],
    category: "Pest",
  },
  {
    id: "murcha-bacteriana",
    officialName: "Bacterial wilt",
    popularNames: ["wilt disease", "soil wilt"],
    category: "Disease",
  },
];

export function getPestsDictionary(lang: "pt" | "en"): PestOption[] {
  return lang === "en" ? PESTS_DICTIONARY_EN : PESTS_DICTIONARY;
}


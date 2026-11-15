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


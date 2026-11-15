"""Collect and clean FAO EcoCrop data from the OpenCLIM repository.

Produces two UTF-8 CSV files in ``data/processed/``:
- ``ecocrop_culturas_limites.csv``: biological, thermal, hydric, and cycle limits
  for ``culturas_limites``.
- ``ecocrop_culturas_sinonimos.csv``: normalized ``(scientific_name, synonym)``
  pairs extracted from ``COMNAME`` for ``culturas_sinonimos`` fuzzy search.
"""

from __future__ import annotations

import argparse
import csv
import re
import unicodedata
import urllib.request
from pathlib import Path
from typing import Set

ECOCROP_RAW_URL = "https://raw.githubusercontent.com/OpenCLIM/ecocrop/main/EcoCrop_DB.csv"

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RAW_PATH = ROOT_DIR / "data" / "raw" / "EcoCrop_DB.csv"
DEFAULT_PROCESSED_DIR = ROOT_DIR / "data" / "processed"

MISSING_TOKENS = {"", "NA", "na", "N/A", "NULL", "null", "None"}

_EN_SHORT = {
    "yam", "pea", "oat", "rye", "tea", "fig", "nut", "soy", "taro", "okra",
    "corn", "flax", "rice", "bean", "plum", "pear", "lime", "date", "kale",
    "leek", "beet", "sage", "mint", "dill", "rose", "pine", "palm", "tree",
    "herb", "weed", "vine", "cane", "wood", "seed", "root", "leaf", "bark",
    "gum",
}
_EN_EXCLUDE = {
    "frijol", "haricot", "pois", "yuca", "yautia", "gombo", "okro", "oker",
    "bhindi", "bindi", "bumbo", "sana", "pini", "saka", "tori", "okay",
    "manihot", "manioc", "maiz", "ketmie", "kopi", "arab",
}
_PT_WORDS = {
    "de", "da", "do", "das", "dos", "e", "em", "com",
    "milho", "feijao", "mandioca", "macaxeira", "aipim", "quiabo", "abobora",
    "abobrinha", "jerimum", "arroz", "soja", "trigo", "batata", "algodao",
    "amendoim", "cana", "cafe", "cacau", "tomate", "alface", "cebola", "alho",
    "cenoura", "couve", "repolho", "melao", "melancia", "mamao", "banana",
    "laranja", "limao", "uva", "manga", "abacate", "caju", "goiaba", "maracuja",
    "pimenta", "pimentao", "capim", "erva", "arvore", "palmeira", "fruta",
    "raiz", "folha", "semente", "flor", "branco", "branca", "preto", "preta",
    "vermelho", "vermelha", "verde", "amarelo", "amarela", "doce", "bravo",
    "brava", "grande", "pequeno", "pequena", "salsa", "cheiro", "cheiroso",
    "roxo", "roxa", "rosa", "dourado", "silvestre", "comum", "forrageiro",
    "forrageira", "miudo", "miuda", "gigante", "rasteiro", "rasteira", "sorgo",
    "milheto", "crotalaria", "aveia", "centeio", "cevada", "mamona", "gergelim",
    "girassol", "fumo", "tabaco", "seringueira", "eucalipto", "pinus", "acacia",
    "acai", "acerola", "abacaxi", "berinjela", "beterraba", "brocolis", "caqui",
    "chuchu", "ervilha", "espinafre", "figo", "inhame", "cara", "jilo",
    "lentilha", "nabo", "pepino", "pera", "pessego", "rabanete", "rucula",
    "vagem", "guandu", "fava", "mungo", "pousio", "adubo", "adubacao",
    "cobertura", "pastagem", "pasto", "grama", "macadamia", "castanha",
    "cupuacu", "graviola", "pitanga", "jabuticaba", "tamarindo", "umbu",
    "caja", "seriguela", "carambola", "morango",
}
_NON_PT_EN_CHARS = set("ñüäößèìòùîûëïœæøåčšžćđłńśźż")
_PT_DISTINCT_CHARS = set("ãõç")
_BAD_PARENS = (
    "fiji", "tonga", "simbo", "solomon", "pohnpei", "tuvalu", "french",
    "spanish", "german", "dutch", "hindi", "malay", "thai", "java",
    "china", "japan", "korea", "africa",
)


def _load_english_words() -> Set[str]:
    words_path = Path("/usr/share/dict/words")
    en_words: Set[str] = set(_EN_SHORT)
    if words_path.exists():
        with words_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                w = line.strip()
                if w.islower() and len(w) >= 3 and w.isalpha():
                    en_words.add(w)
    return en_words - _EN_EXCLUDE


_EN_WORDS = _load_english_words()


def _strip_accents(text: str) -> str:
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def is_pt_or_en(phrase: str) -> bool:
    """Keep only popular names in Portuguese or English."""
    p = phrase.strip()
    if not p:
        return False
    low = p.lower()
    if "(" in low and ")" not in low or ")" in low and "(" not in low:
        return False
    if any(ch in _NON_PT_EN_CHARS for ch in low):
        return False
    for tag in re.findall(r"\(([^)]+)\)", low):
        if any(bad in tag for bad in _BAD_PARENS):
            return False
    clean = re.sub(r"\([^)]*\)", "", low)
    if any(ch in _PT_DISTINCT_CHARS for ch in clean):
        return True
    tokens = re.findall(r"[a-zãõçáéíóúâêô']+", clean)
    if not tokens:
        return False
    norm_tokens = []
    for t in tokens:
        t_clean = t[:-2] if t.endswith("'s") else t
        t_ascii = _strip_accents(t_clean)
        if len(t_ascii) >= 2:
            norm_tokens.append(t_ascii)
    if not norm_tokens:
        return False
    if len(norm_tokens) == 1:
        t = norm_tokens[0]
        return t in _PT_WORDS or (len(t) >= 4 and t in _EN_WORDS) or t in _EN_SHORT
    return all(t in _PT_WORDS or t in _EN_WORDS for t in norm_tokens)


def download_raw_csv(dest: Path, force: bool = False) -> Path:
    """Download the raw EcoCrop CSV if missing or when ``force`` is True."""
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(ECOCROP_RAW_URL, dest)
    return dest


def clean_str(value: str | None) -> str:
    """Normalize missing tokens and whitespace."""
    if value is None:
        return ""
    text = value.strip()
    return "" if text in MISSING_TOKENS else text


def clean_float(value: str | None, *, positive_only: bool = False) -> str:
    """Parse numeric field to a clean string representation, or empty if invalid."""
    text = clean_str(value)
    if not text:
        return ""
    try:
        num = float(text)
    except ValueError:
        return ""
    if positive_only and num <= 0:
        return ""
    return str(int(num)) if num.is_integer() else str(num)


def extract_family(famname: str) -> str:
    """Extract the botanical family name from EcoCrop's colon-delimited taxonomy."""
    cleaned = clean_str(famname)
    if not cleaned:
        return ""
    return cleaned.split(":")[-1].strip()


def process_ecocrop(raw_path: Path, processed_dir: Path) -> tuple[int, int]:
    """Clean EcoCrop_DB.csv and write limits and synonyms CSVs.

    Returns:
        Tuple of ``(species_count, synonym_count)``.
    """
    processed_dir.mkdir(parents=True, exist_ok=True)
    limites_path = processed_dir / "ecocrop_culturas_limites.csv"
    sinonimos_path = processed_dir / "ecocrop_culturas_sinonimos.csv"

    limites_headers = [
        "ecoport_code",
        "scientific_name",
        "famname_raw",
        "family",
        "comname",
        "tmin",
        "tmax",
        "topmn",
        "topmx",
        "rmin",
        "rmax",
        "ropmn",
        "ropmx",
        "gmin",
        "gmax",
        "lispa",
        "cat",
    ]

    species_count = 0
    synonym_count = 0

    with (
        raw_path.open("r", encoding="cp1252", errors="replace", newline="") as src,
        limites_path.open("w", encoding="utf-8", newline="") as lim_out,
        sinonimos_path.open("w", encoding="utf-8", newline="") as syn_out,
    ):
        reader = csv.DictReader(src)
        lim_writer = csv.DictWriter(lim_out, fieldnames=limites_headers)
        lim_writer.writeheader()

        syn_writer = csv.DictWriter(syn_out, fieldnames=["scientific_name", "synonym"])
        syn_writer.writeheader()

        for row in reader:
            sci_name = clean_str(row.get("ScientificName"))
            if not sci_name:
                continue

            famname_raw = clean_str(row.get("FAMNAME"))
            comname_raw = clean_str(row.get("COMNAME"))

            filtered_syns = []
            if comname_raw:
                seen: set[str] = set()
                for part in comname_raw.split(","):
                    syn = part.strip()
                    key = syn.lower()
                    if syn and key not in seen and is_pt_or_en(syn):
                        seen.add(key)
                        filtered_syns.append(syn)

            lim_writer.writerow(
                {
                    "ecoport_code": clean_str(row.get("EcoPortCode")),
                    "scientific_name": sci_name,
                    "famname_raw": famname_raw,
                    "family": extract_family(famname_raw),
                    "comname": ", ".join(filtered_syns),
                    "tmin": clean_float(row.get("TMIN")),
                    "tmax": clean_float(row.get("TMAX")),
                    "topmn": clean_float(row.get("TOPMN")),
                    "topmx": clean_float(row.get("TOPMX")),
                    "rmin": clean_float(row.get("RMIN")),
                    "rmax": clean_float(row.get("RMAX")),
                    "ropmn": clean_float(row.get("ROPMN")),
                    "ropmx": clean_float(row.get("ROPMX")),
                    "gmin": clean_float(row.get("GMIN"), positive_only=True),
                    "gmax": clean_float(row.get("GMAX"), positive_only=True),
                    "lispa": clean_str(row.get("LISPA")),
                    "cat": clean_str(row.get("CAT")),
                }
            )
            species_count += 1

            for syn in filtered_syns:
                syn_writer.writerow({"scientific_name": sci_name, "synonym": syn})
                synonym_count += 1

    return species_count, synonym_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect and clean FAO EcoCrop data.")
    parser.add_argument("--raw-path", type=Path, default=DEFAULT_RAW_PATH)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--force-download", action="store_true")
    args = parser.parse_args()

    raw_path = download_raw_csv(args.raw_path, force=args.force_download)
    species_count, synonym_count = process_ecocrop(raw_path, args.processed_dir)
    print(f"Processed {species_count} species and {synonym_count} synonyms.")


if __name__ == "__main__":
    main()


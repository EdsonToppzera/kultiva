"""Collect AGROFIT phytosanitary data and cross-reference with FAO EcoCrop.

Reads ``data/raw/agrofitprodutosformulados.csv`` (downloading from MAPA Dados Abertos
if missing), strips all chemical/commercial/toxicological columns, and extracts the
relational vulnerability mapping:
  - ``cultura_agrofit`` (CULTURA)
  - ``praga_nome_cientifico`` (PRAGA_NOME_CIENTIFICO)
  - ``praga_nome_comum`` (PRAGA_NOME_COMUM)

Cross-references ``CULTURA`` against EcoCrop's ``ecocrop_culturas_limites.csv`` and
``ecocrop_culturas_sinonimos.csv`` to produce:
  - ``data/processed/agrofit_cultura_pragas.csv``: all deduplicated AGROFIT pairs
    with resolved ``scientific_name`` and ``family`` when available.
  - ``data/processed/cultura_pragas_ecocrop_join.csv``: inner-joined rows ready to
    seed ``cultura_pragas`` with guaranteed FK integrity to ``culturas_limites``.
"""

from __future__ import annotations

import argparse
import csv
import unicodedata
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

AGROFIT_RAW_URL = (
    "https://dados.agricultura.gov.br/dataset/6c913699-e82e-4da3-a0a1-fb6c431e367f/"
    "resource/d30b30d7-e256-484e-9ab8-cd40974e1238/download/"
    "agrofitprodutosformulados.csv"
)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RAW_PATH = ROOT_DIR / "data" / "raw" / "agrofitprodutosformulados.csv"
DEFAULT_PROCESSED_DIR = ROOT_DIR / "data" / "processed"

# Curated mapping from Brazilian Portuguese AGROFIT crop names to EcoCrop ScientificName
PT_CROP_TO_ECOCROP: Dict[str, str] = {
    "abacate": "Persea americana",
    "abobora": "Cucurbita maxima",
    "abobrinha": "Cucurbita pepo",
    "acelga": "Beta vulgaris",
    "agriao": "Nasturtium officinale",
    "alface": "Lactuca sativa var. capitata",
    "algodao ogm": "Gossypium hirsutum",
    "almeirao": "Cichorium intybus",
    "amendoim": "Arachis hypogaea",
    "arroz irrigado": "Oryza sativa",
    "arroz sequeiro": "Oryza sativa",
    "arroz - armazenado": "Oryza sativa",
    "aveia": "Avena sativa",
    "aveia branca": "Avena sativa",
    "azeitona": "Olea europaea",
    "azevem": "Lolium multiflorum",
    "batata-doce": "Ipomoea batatas",
    "batata-salsa": "Arracacia xanthorrhiza",
    "berinjela": "Solanum melongena",
    "beterraba": "Beta vulgaris",
    "brocolis": "Brassica oleracea var. italica",
    "cacau": "Theobroma cacao",
    "cafe": "Coffea arabica",
    "cana-de-acucar": "Saccharum officinarum",
    "caqui": "Diospyros kaki",
    "castanha-do-para": "Bertholletia excelsa",
    "cenoura": "Daucus carota",
    "centeio": "Secale cereale",
    "chalota": "Allium cepa",
    "citros": "Citrus sinensis",
    "couve": "Brassica oleracea var. acephala",
    "couve-chinesa": "Brassica rapa Pak Choi",
    "couve-de-bruxelas": "Brassica oleracea var. gemmifera",
    "couve-flor": "Brassica oleracea var. botrytis",
    "espinafre": "Spinacia oleracea",
    "estevia": "Stevia rebaudiana",
    "feijao": "Phaseolus vulgaris",
    "feijao-caupi": "Vigna unguiculata",
    "feijao-fava": "Vicia faba",
    "feijao-guandu": "Cajanus cajan",
    "feijao-mungo": "Vigna radiata",
    "feijao-vagem": "Phaseolus vulgaris",
    "feijoes": "Phaseolus vulgaris",
    "fumo": "Nicotiana tabacum",
    "grao-de-bico": "Cicer arietinum",
    "jilo": "Solanum aethiopicum",
    "kiwi": "Actinidia chinensis",
    "lentilha": "Lens culinaris",
    "lichia": "Litchi chinensis",
    "linhaca": "Linum usitatissimum",
    "lupulo": "Humulus lupulus",
    "macadamia": "Macadamia integrifolia",
    "mamao": "Carica papaya",
    "mamona": "Ricinus communis",
    "mandioquinha-salsa": "Arracacia xanthorrhiza",
    "melao": "Cucumis melo",
    "milheto": "Pennisetum glaucum",
    "milho": "Zea mays",
    "milho ogm": "Zea mays",
    "mostarda": "Brassica juncea",
    "nabo": "Brassica rapa var. rapifera",
    "nectarina": "Prunus persica",
    "nespera": "Eriobotrya japonica",
    "noz-peca": "Carya illinoensis",
    "rabanete": "Raphanus sativus",
    "repolho": "Brassica oleracea var. capitata",
    "seriguela": "Spondias purpurea",
    "soja": "Glycine max",
    "soja ogm": "Glycine max",
    "trigo": "Triticum aestivum",
    "uva de mesa": "Vitis vinifera",
}


def normalize_text(text: str) -> str:
    """Lowercase, strip accents, and collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    return " ".join(ascii_only.lower().split())


def download_raw_csv(dest: Path, force: bool = False) -> Path:
    """Download the raw AGROFIT CSV if missing or when ``force`` is True."""
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        AGROFIT_RAW_URL,
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp, dest.open("wb") as out:
        while chunk := resp.read(1024 * 256):
            out.write(chunk)
    return dest


def load_ecocrop_lookup(
    processed_dir: Path,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Load EcoCrop ``scientific_name -> family`` and ``normalized_synonym -> scientific_name``."""
    limites_csv = processed_dir / "ecocrop_culturas_limites.csv"
    sinonimos_csv = processed_dir / "ecocrop_culturas_sinonimos.csv"

    sci_to_family: Dict[str, str] = {}
    with limites_csv.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            sci = (row.get("scientific_name") or "").strip()
            if sci:
                sci_to_family[sci] = (row.get("family") or "").strip()

    syn_to_sci: Dict[str, str] = {}
    if sinonimos_csv.exists():
        with sinonimos_csv.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                sci = (row.get("scientific_name") or "").strip()
                syn = normalize_text(row.get("synonym") or "")
                if syn and sci in sci_to_family and syn not in syn_to_sci:
                    syn_to_sci[syn] = sci

    return sci_to_family, syn_to_sci


def resolve_scientific_name(
    cultura: str,
    sci_to_family: Dict[str, str],
    syn_to_sci: Dict[str, str],
) -> str:
    """Resolve an AGROFIT crop name to an EcoCrop ``scientific_name``, or empty string."""
    key = normalize_text(cultura)
    if key in PT_CROP_TO_ECOCROP:
        candidate = PT_CROP_TO_ECOCROP[key]
        if candidate in sci_to_family:
            return candidate
    if key in syn_to_sci:
        return syn_to_sci[key]
    return ""


def process_agrofit(
    raw_path: Path, processed_dir: Path
) -> Tuple[int, int, int, int]:
    """Extract (cultura, praga) pairs from AGROFIT and join with EcoCrop.

    Returns:
        Tuple ``(raw_rows, unique_agrofit_pairs, joined_pairs, matched_crops)``.
    """
    sci_to_family, syn_to_sci = load_ecocrop_lookup(processed_dir)

    seen_pairs: Set[Tuple[str, str, str]] = set()
    raw_rows = 0

    with raw_path.open("r", encoding="utf-8", errors="replace", newline="") as src:
        reader = csv.DictReader(src, delimiter=";")
        for row in reader:
            raw_rows += 1
            cultura = " ".join((row.get("CULTURA") or "").split())
            praga_sci = " ".join((row.get("PRAGA_NOME_CIENTIFICO") or "").split())
            praga_comum = " ".join((row.get("PRAGA_NOME_COMUM") or "").split())
            if not cultura or (not praga_sci and not praga_comum):
                continue
            seen_pairs.add((cultura, praga_sci, praga_comum))

    all_out_path = processed_dir / "agrofit_cultura_pragas.csv"
    join_out_path = processed_dir / "cultura_pragas_ecocrop_join.csv"

    all_headers = [
        "cultura_agrofit",
        "scientific_name",
        "family",
        "praga_nome_cientifico",
        "praga_nome_comum",
    ]
    join_headers = [
        "scientific_name",
        "family",
        "cultura_agrofit",
        "praga_nome_cientifico",
        "praga_nome_comum",
    ]

    joined_pairs = 0
    matched_crops: Set[str] = set()
    seen_join: Set[Tuple[str, str, str, str]] = set()

    with (
        all_out_path.open("w", encoding="utf-8", newline="") as all_f,
        join_out_path.open("w", encoding="utf-8", newline="") as join_f,
    ):
        all_writer = csv.DictWriter(all_f, fieldnames=all_headers)
        all_writer.writeheader()

        join_writer = csv.DictWriter(join_f, fieldnames=join_headers)
        join_writer.writeheader()

        for cultura, praga_sci, praga_comum in sorted(seen_pairs):
            sci = resolve_scientific_name(cultura, sci_to_family, syn_to_sci)
            family = sci_to_family.get(sci, "") if sci else ""

            all_writer.writerow(
                {
                    "cultura_agrofit": cultura,
                    "scientific_name": sci,
                    "family": family,
                    "praga_nome_cientifico": praga_sci,
                    "praga_nome_comum": praga_comum,
                }
            )

            if sci:
                matched_crops.add(cultura)
                join_key = (sci, cultura, praga_sci, praga_comum)
                if join_key not in seen_join:
                    seen_join.add(join_key)
                    join_writer.writerow(
                        {
                            "scientific_name": sci,
                            "family": family,
                            "cultura_agrofit": cultura,
                            "praga_nome_cientifico": praga_sci,
                            "praga_nome_comum": praga_comum,
                        }
                    )
                    joined_pairs += 1

    return raw_rows, len(seen_pairs), joined_pairs, len(matched_crops)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect AGROFIT crop-pest data and cross-reference with EcoCrop."
    )
    parser.add_argument("--raw-path", type=Path, default=DEFAULT_RAW_PATH)
    parser.add_argument("--processed-dir", type=Path, default=DEFAULT_PROCESSED_DIR)
    parser.add_argument("--force-download", action="store_true")
    args = parser.parse_args()

    raw_path = download_raw_csv(args.raw_path, force=args.force_download)
    raw_rows, unique_pairs, joined_pairs, matched_crops = process_agrofit(
        raw_path, args.processed_dir
    )
    print(
        f"Processed {raw_rows} AGROFIT rows -> {unique_pairs} unique pairs; "
        f"joined {joined_pairs} pairs across {matched_crops} EcoCrop-matched crops."
    )


if __name__ == "__main__":
    main()


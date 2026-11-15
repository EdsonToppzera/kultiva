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
import urllib.request
from pathlib import Path

ECOCROP_RAW_URL = "https://raw.githubusercontent.com/OpenCLIM/ecocrop/main/EcoCrop_DB.csv"

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RAW_PATH = ROOT_DIR / "data" / "raw" / "EcoCrop_DB.csv"
DEFAULT_PROCESSED_DIR = ROOT_DIR / "data" / "processed"

MISSING_TOKENS = {"", "NA", "na", "N/A", "NULL", "null", "None"}


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
            comname = clean_str(row.get("COMNAME"))

            lim_writer.writerow(
                {
                    "ecoport_code": clean_str(row.get("EcoPortCode")),
                    "scientific_name": sci_name,
                    "famname_raw": famname_raw,
                    "family": extract_family(famname_raw),
                    "comname": comname,
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

            if comname:
                seen: set[str] = set()
                for part in comname.split(","):
                    syn = part.strip()
                    key = syn.lower()
                    if syn and key not in seen:
                        seen.add(key)
                        syn_writer.writerow(
                            {"scientific_name": sci_name, "synonym": syn}
                        )
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


import csv
import io
import logging
import os
from typing import Any

import httpx

from backend.services.gaez_service import GAEZ_SUITABILITY_CROPS, _normalize_text

logger = logging.getLogger(__name__)

ECOCROP_CSV_URL = os.getenv(
    "ECOCROP_CSV_URL",
    "https://raw.githubusercontent.com/OpenCLIM/ecocrop/main/EcoCrop_DB.csv",
)

# Dicionário botânico (nome popular PT/EN -> Scientific Name) para cruzar com ECOCROP/AGROFIT
# sem inventar parâmetros agronômicos.
CROP_SCIENTIFIC_ALIASES: dict[str, str] = {
    "milho": "Zea mays",
    "maize": "Zea mays",
    "corn": "Zea mays",
    "mandioca": "Manihot esculenta",
    "macaxeira": "Manihot esculenta",
    "aipim": "Manihot esculenta",
    "cassava": "Manihot esculenta",
    "feijao caupi": "Vigna unguiculata",
    "feijao-caupi": "Vigna unguiculata",
    "feijao macacar": "Vigna unguiculata",
    "feijao de corda": "Vigna unguiculata",
    "feijao fradinho": "Vigna unguiculata",
    "cowpea": "Vigna unguiculata",
    "feijao carioca": "Phaseolus vulgaris",
    "feijao-carioca": "Phaseolus vulgaris",
    "feijao comum": "Phaseolus vulgaris",
    "feijao": "Phaseolus vulgaris",
    "phaseolus bean": "Phaseolus vulgaris",
    "sorgo": "Sorghum bicolor",
    "sorgo forrageiro": "Sorghum bicolor",
    "sorghum": "Sorghum bicolor",
    "milheto": "Pennisetum glaucum",
    "pearl millet": "Pennisetum glaucum",
    "amendoim": "Arachis hypogaea",
    "mendubi": "Arachis hypogaea",
    "groundnut": "Arachis hypogaea",
    "peanut": "Arachis hypogaea",
    "soja": "Glycine max",
    "soybean": "Glycine max",
    "batata doce": "Ipomoea batatas",
    "batata-doce": "Ipomoea batatas",
    "sweet potato": "Ipomoea batatas",
    "guandu": "Cajanus cajan",
    "feijao guandu": "Cajanus cajan",
    "feijao-guandu": "Cajanus cajan",
    "pigeonpea": "Cajanus cajan",
    "crotalaria": "Crotalaria juncea",
    "abobora": "Cucurbita moschata",
    "jerimum": "Cucurbita moschata",
    "abobora cabotia": "Cucurbita moschata",
    "melancia": "Citrullus lanatus",
    "watermelon": "Citrullus lanatus",
    "gergelim": "Sesamum indicum",
    "sesame": "Sesamum indicum",
    "girassol": "Helianthus annuus",
    "sunflower": "Helianthus annuus",
    "arroz": "Oryza sativa",
    "rice": "Oryza sativa",
    "trigo": "Triticum aestivum",
    "wheat": "Triticum aestivum",
    "algodao": "Gossypium hirsutum",
    "cotton": "Gossypium hirsutum",
    "cafe": "Coffea arabica",
    "coffee": "Coffea arabica",
    "cana de acucar": "Saccharum officinarum",
    "tomate": "Lycopersicon esculentum",
    "feijao de porco": "Canavalia ensiformis",
    "feijao-de-porco": "Canavalia ensiformis",
    "mucuna": "Mucuna pruriens",
    "aveia": "Avena sativa",
}

_FAMILY_SYNONYMS: dict[str, str] = {
    "leguminosae": "Fabaceae",
    "fabaceae": "Fabaceae",
    "gramineae": "Poaceae",
    "poaceae": "Poaceae",
    "compositae": "Asteraceae",
    "asteraceae": "Asteraceae",
    "cruciferae": "Brassicaceae",
    "brassicaceae": "Brassicaceae",
    "umbelliferae": "Apiaceae",
    "apiaceae": "Apiaceae",
    "palmae": "Arecaceae",
    "arecaceae": "Arecaceae",
    "labiatae": "Lamiaceae",
    "lamiaceae": "Lamiaceae",
}


def normalize_botanical_family(family: str | None) -> str | None:
    """Normaliza nomes históricos de família botânica (ex.: Leguminosae -> Fabaceae)."""
    if not family:
        return None
    raw = str(family).strip()
    if not raw:
        return None
    if ":" in raw:
        raw = raw.split(":")[-1].strip()
    return _FAMILY_SYNONYMS.get(raw.lower(), raw)


def _extract_family_parts(famname: str | None) -> tuple[str | None, str | None, str | None]:
    raw = str(famname or "").strip()
    if not raw or raw.upper() == "NA":
        return None, None, None
    family = raw.split(":")[-1].strip() if ":" in raw else raw
    canonical = normalize_botanical_family(family)
    return family or None, canonical, raw


def _parse_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    raw = str(value).strip()
    if not raw or raw.upper() == "NA":
        return None
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        return None


def _parse_int(value: Any, *, allow_zero: bool = True) -> int | None:
    parsed = _parse_float(value)
    if parsed is None:
        return None
    val = int(round(parsed))
    if not allow_zero and val <= 0:
        return None
    return val


def resolve_scientific_name(query: str) -> str | None:
    """
    Resolve nome popular em português/inglês, código GAEZ (ex.: MZE) ou
    nome científico já formatado para o `Scientific Name` canônico.
    """
    raw = str(query or "").strip()
    if not raw:
        return None

    upper = raw.upper()
    if upper in GAEZ_SUITABILITY_CROPS:
        sci = GAEZ_SUITABILITY_CROPS[upper].get("scientific_name")
        if sci:
            return str(sci)

    norm = _normalize_text(raw)
    norm_hyphen = norm.replace(" ", "-")
    for candidate_key in (norm, norm_hyphen):
        if candidate_key in CROP_SCIENTIFIC_ALIASES:
            return CROP_SCIENTIFIC_ALIASES[candidate_key]

    for meta in GAEZ_SUITABILITY_CROPS.values():
        names = [meta.get("nome", ""), meta.get("gaez_caption", ""), *meta.get("aliases", [])]
        for alias in names:
            alias_norm = _normalize_text(str(alias))
            if alias_norm and (norm == alias_norm or alias_norm in norm):
                sci = meta.get("scientific_name")
                if sci:
                    return str(sci)

    # Verifica correspondência parcial em CROP_SCIENTIFIC_ALIASES (ex.: "Milho Safrinha")
    for alias, sci in sorted(CROP_SCIENTIFIC_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True):
        if alias in norm:
            return sci

    return None


def _parse_ecocrop_row(row: dict[str, Any]) -> dict[str, Any] | None:
    sci = str(row.get("ScientificName") or row.get("scientific_name") or "").strip()
    if not sci:
        return None

    family, family_canonical, family_taxonomy = _extract_family_parts(
        row.get("FAMNAME") or row.get("family")
    )
    comname_raw = str(row.get("COMNAME") or "").strip()
    common_names = [
        part.strip()
        for part in comname_raw.split(",")
        if part.strip() and part.strip().upper() != "NA"
    ]

    return {
        "ecoport_code": str(row.get("EcoPortCode") or "").strip() or None,
        "scientific_name": sci,
        "family": family,
        "family_canonical": family_canonical,
        "family_taxonomy": family_taxonomy,
        "common_names": common_names[:12],
        "tmin": _parse_float(row.get("TMIN")),
        "tmax": _parse_float(row.get("TMAX")),
        "topmin": _parse_float(row.get("TOPMN") if "TOPMN" in row else row.get("TOPMIN")),
        "topmax": _parse_float(row.get("TOPMX") if "TOPMX" in row else row.get("TOPMAX")),
        "rmin": _parse_float(row.get("RMIN")),
        "rmax": _parse_float(row.get("RMAX")),
        "ropmin": _parse_float(row.get("ROPMN") if "ROPMN" in row else row.get("ROPMIN")),
        "ropmax": _parse_float(row.get("ROPMX") if "ROPMX" in row else row.get("ROPMAX")),
        "gmin": _parse_int(row.get("GMIN"), allow_zero=False),
        "gmax": _parse_int(row.get("GMAX"), allow_zero=False),
        "phmin": _parse_float(row.get("PHMIN")),
        "phmax": _parse_float(row.get("PHMAX")),
        "phopmin": _parse_float(row.get("PHOPMN") if "PHOPMN" in row else row.get("PHOPMIN")),
        "phopmax": _parse_float(row.get("PHOPMX") if "PHOPMX" in row else row.get("PHOPMAX")),
        "climate_zones": str(row.get("CLIZ") or "").strip() or None,
        "synonyms": str(row.get("SYNO") or "").strip() or None,
    }


def evaluate_climate_comfort(
    crop_profile: dict[str, Any] | None,
    temp_c: float | None,
    annual_rain_mm: float | None,
    cycle_days: int | None = None,
) -> dict[str, Any]:
    """
    Avalia se temperatura média e chuva anual estimada estão dentro da faixa ótima
    (`TOPMIN`/`TOPMAX`, `ROPMIN`/`ROPMAX`) ou absoluta (`TMIN`/`TMAX`, `RMIN`/`RMAX`)
    do ECOCROP. Retorna estrutura objetiva sem inventar parâmetros ausentes.
    """
    if not isinstance(crop_profile, dict):
        return {
            "status": "unknown",
            "temperature_status": "unknown",
            "rainfall_status": "unknown",
            "comfort_score": None,
            "warnings": [],
        }

    warnings: list[str] = []
    temp_status = "unknown"
    temp_score: float | None = None
    tmin = _parse_float(crop_profile.get("tmin"))
    tmax = _parse_float(crop_profile.get("tmax"))
    topmin = _parse_float(crop_profile.get("topmin"))
    topmax = _parse_float(crop_profile.get("topmax"))

    if temp_c is not None and (tmin is not None or tmax is not None):
        if (tmin is not None and temp_c < tmin) or (tmax is not None and temp_c > tmax):
            temp_status = "outside_absolute"
            temp_score = 0.15
            warnings.append(
                f"Temperatura ({temp_c:.1f} °C) fora do limite absoluto ECOCROP "
                f"({tmin}–{tmax} °C) para {crop_profile.get('scientific_name')}."
            )
        elif (
            topmin is not None
            and topmax is not None
            and topmin <= temp_c <= topmax
        ):
            temp_status = "optimal"
            temp_score = 1.0
        elif topmin is not None and topmax is not None:
            temp_status = "suboptimal"
            temp_score = 0.65
            warnings.append(
                f"Temperatura ({temp_c:.1f} °C) fora da faixa ótima ECOCROP "
                f"({topmin}–{topmax} °C) para {crop_profile.get('scientific_name')}."
            )
        else:
            temp_status = "within_absolute"
            temp_score = 0.8

    rain_status = "unknown"
    rain_score: float | None = None
    rmin = _parse_float(crop_profile.get("rmin"))
    rmax = _parse_float(crop_profile.get("rmax"))
    ropmin = _parse_float(crop_profile.get("ropmin"))
    ropmax = _parse_float(crop_profile.get("ropmax"))

    if annual_rain_mm is not None and (rmin is not None or rmax is not None):
        if (rmin is not None and annual_rain_mm < rmin) or (
            rmax is not None and annual_rain_mm > rmax
        ):
            rain_status = "outside_absolute"
            rain_score = 0.2
            warnings.append(
                f"Pluviosidade anual estimada ({annual_rain_mm:.0f} mm) fora do limite absoluto "
                f"ECOCROP ({rmin}–{rmax} mm) para {crop_profile.get('scientific_name')}."
            )
        elif (
            ropmin is not None
            and ropmax is not None
            and ropmin <= annual_rain_mm <= ropmax
        ):
            rain_status = "optimal"
            rain_score = 1.0
        elif ropmin is not None and ropmax is not None:
            rain_status = "suboptimal"
            rain_score = 0.65
        else:
            rain_status = "within_absolute"
            rain_score = 0.8

    gmin = _parse_int(crop_profile.get("gmin"), allow_zero=False)
    gmax = _parse_int(crop_profile.get("gmax"), allow_zero=False)
    if cycle_days is not None and gmin is not None and gmax is not None:
        if cycle_days < gmin or cycle_days > gmax:
            warnings.append(
                f"Ciclo planejado ({cycle_days} dias) fora da janela ECOCROP ({gmin}–{gmax} dias)."
            )

    scores = [s for s in (temp_score, rain_score) if s is not None]
    comfort_score = round(sum(scores) / len(scores), 3) if scores else None
    if temp_status == "outside_absolute" or rain_status == "outside_absolute":
        overall = "stress"
    elif temp_status == "optimal" and rain_status in {"optimal", "unknown", "within_absolute"}:
        overall = "optimal"
    elif scores:
        overall = "marginal" if comfort_score is not None and comfort_score < 0.8 else "optimal"
    else:
        overall = "unknown"

    return {
        "status": overall,
        "temperature_status": temp_status,
        "rainfall_status": rain_status,
        "comfort_score": comfort_score,
        "warnings": warnings,
    }


class EcoCropDataProvider:
    """
    Provedor direto da base FAO ECOCROP (`EcoCrop_DB.csv`) com cache local em disco.
    Nunca inventa faixas térmicas, pluviométricas ou famílias quando o CSV não está disponível.
    """

    def __init__(
        self,
        data_path: str = "data",
        csv_url: str | None = None,
        timeout: float = 15.0,
    ):
        self.data_path = data_path
        self.csv_url = csv_url
        self.timeout = float(timeout)
        self._records_cache: list[dict[str, Any]] | None = None
        self._loaded_source: str | None = None

    def _cache_dir(self) -> str:
        return os.path.join(self.data_path, "ecocrop_cache")

    def _cache_csv_path(self) -> str:
        return os.path.join(self._cache_dir(), "EcoCrop_DB.csv")

    def _active_csv_url(self) -> str:
        return self.csv_url if self.csv_url is not None else ECOCROP_CSV_URL

    @staticmethod
    def _parse_csv_text(raw_text: str) -> list[dict[str, Any]]:
        if not raw_text or "ScientificName" not in raw_text:
            return []
        reader = csv.DictReader(io.StringIO(raw_text))
        records: list[dict[str, Any]] = []
        for row in reader:
            parsed = _parse_ecocrop_row(row)
            if parsed is not None:
                records.append(parsed)
        return records

    def _load_records(self) -> tuple[str, list[dict[str, Any]]]:
        source = self._active_csv_url()
        if self._records_cache is not None and self._loaded_source == source:
            return "ecocrop_csv", self._records_cache

        cache_file = self._cache_csv_path()
        if os.path.exists(cache_file):
            try:
                with open(cache_file, encoding="utf-8", errors="replace") as fp:
                    records = self._parse_csv_text(fp.read())
                if records:
                    self._records_cache = records
                    self._loaded_source = source
                    return "ecocrop_csv", records
            except Exception as exc:
                logger.warning("Falha ao ler cache ECOCROP em disco: %s", exc)

        raw_text: str | None = None
        if os.path.exists(source):
            try:
                with open(source, encoding="utf-8", errors="replace") as fp:
                    raw_text = fp.read()
            except Exception as exc:
                logger.warning("Falha ao ler arquivo ECOCROP local '%s': %s", source, exc)
                return "no_data", []
        else:
            try:
                resp = httpx.get(source, timeout=self.timeout)
                resp.raise_for_status()
                raw_text = resp.text
            except Exception as exc:
                logger.warning("Falha ao consultar ECOCROP em '%s': %s", source, exc)
                return "no_data", []

        records = self._parse_csv_text(raw_text or "")
        if not records:
            return "no_data", []

        try:
            os.makedirs(self._cache_dir(), exist_ok=True)
            with open(cache_file, "w", encoding="utf-8", newline="") as fp:
                fp.write(raw_text or "")
        except Exception as exc:
            logger.warning("Não foi possível salvar cache ECOCROP em disco: %s", exc)

        self._records_cache = records
        self._loaded_source = source
        return "ecocrop_csv", records

    def _find_match(
        self, query: str, records: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        raw = str(query or "").strip()
        if not raw:
            return None

        # 1. EcoPortCode exato
        if raw.isdigit():
            for rec in records:
                if rec.get("ecoport_code") == raw:
                    return rec

        # 2. Mapeamento via alias / código GAEZ -> Scientific Name exato
        resolved_sci = resolve_scientific_name(raw)
        if resolved_sci:
            resolved_low = resolved_sci.lower()
            for rec in records:
                if rec["scientific_name"].lower() == resolved_low:
                    return rec

        # 3. Correspondência exata por ScientificName
        raw_low = raw.lower()
        for rec in records:
            if rec["scientific_name"].lower() == raw_low:
                return rec

        # 4. Prefixo em ScientificName ou match em COMNAME / SYNO
        norm_query = _normalize_text(raw)
        for rec in records:
            if rec["scientific_name"].lower().startswith(raw_low):
                return rec
        for rec in records:
            if any(_normalize_text(c) == norm_query for c in rec.get("common_names", [])):
                return rec
        for rec in records:
            syno = _normalize_text(rec.get("synonyms") or "")
            if norm_query and norm_query in syno:
                return rec
        return None

    def lookup_crop(self, query: str) -> dict[str, Any]:
        """Consulta uma espécie/cultura diretamente na base ECOCROP."""
        data_quality, records = self._load_records()
        if data_quality == "no_data":
            return {
                "origem": "fao_ecocrop",
                "data_quality": "no_data",
                "query": query,
                "found": False,
                "crop": None,
            }

        match = self._find_match(query, records)
        return {
            "origem": "fao_ecocrop",
            "data_quality": "ecocrop_csv",
            "query": query,
            "found": match is not None,
            "crop": match,
        }

    def extract_crops_map(self, queries: list[str]) -> dict[str, Any]:
        """Consulta em lote uma lista de culturas/nomes científicos para o simulador [M3]."""
        data_quality, records = self._load_records()
        if data_quality == "no_data":
            return {
                "origem": "fao_ecocrop",
                "data_quality": "no_data",
                "crops": {},
            }

        crops_map: dict[str, dict[str, Any]] = {}
        for q in queries:
            clean = str(q or "").strip()
            if not clean:
                continue
            match = self._find_match(clean, records)
            if match is not None:
                key = _normalize_text(clean)
                crops_map[key] = match
                crops_map[match["scientific_name"].lower()] = match

        return {
            "origem": "fao_ecocrop",
            "data_quality": "ecocrop_csv",
            "crops": crops_map,
        }

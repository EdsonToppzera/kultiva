from concurrent.futures import ThreadPoolExecutor
import json
import logging
import math
import os
from typing import Any
import unicodedata

import httpx
import rasterio

from backend.services.geospatial import calcular_geometria_terreno

logger = logging.getLogger(__name__)

# Garante leitura direta via HTTP Range Request em Cloud-Optimized GeoTIFFs (COG)
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")

GAEZ_BASE_URL = "https://storage.googleapis.com/fao-gismgr-gaez-v5-data/DATA/GAEZ-V5"
GAEZ_CROP_DIMENSION_URL = f"{GAEZ_BASE_URL}/DIMENSION/GAEZ-V5.CROP-RES05.json"

# Catálogo de sementes/culturas baseado no Módulo V ("Suitability and Attainable Yield" - GAEZ-V5.CROP-RES05)
GAEZ_SUITABILITY_CROPS: dict[str, dict[str, Any]] = {
    "MZE": {
        "crop_code": "MZE",
        "gaez_caption": "Maize",
        "scientific_name": "Zea mays",
        "nome": "Milho",
        "aliases": ["milho", "maize"],
        "group": "graminea",
        "fixes_nitrogen": False,
        "consumo_agua_mm": 500.0,
        "tempo_colheita_dias": 95,
        "market": 0.95,
        "soil_benefit": 0.45,
        "heat_tolerance": 0.55,
        "water_demand": 0.72,
    },
    "CSV": {
        "crop_code": "CSV",
        "gaez_caption": "Cassava",
        "scientific_name": "Manihot esculenta",
        "nome": "Mandioca",
        "aliases": ["mandioca", "macaxeira", "aipim", "cassava"],
        "group": "tuberculo",
        "fixes_nitrogen": False,
        "consumo_agua_mm": 400.0,
        "tempo_colheita_dias": 270,
        "market": 0.75,
        "soil_benefit": 0.55,
        "heat_tolerance": 0.85,
        "water_demand": 0.45,
    },
    "COW": {
        "crop_code": "COW",
        "gaez_caption": "Cowpea",
        "scientific_name": "Vigna unguiculata",
        "nome": "Feijão-caupi",
        "aliases": [
            "feijao-caupi",
            "feijao caupi",
            "feijao macacar",
            "feijao-macacar",
            "feijao-de-corda",
            "feijao de corda",
            "feijao fradinho",
            "cowpea",
        ],
        "group": "leguminosa",
        "fixes_nitrogen": True,
        "consumo_agua_mm": 300.0,
        "tempo_colheita_dias": 70,
        "market": 0.75,
        "soil_benefit": 0.88,
        "heat_tolerance": 0.90,
        "water_demand": 0.35,
    },
    "PHB": {
        "crop_code": "PHB",
        "gaez_caption": "Phaseolus bean",
        "scientific_name": "Phaseolus vulgaris",
        "nome": "Feijão-carioca",
        "aliases": [
            "feijao-carioca",
            "feijao carioca",
            "feijao",
            "feijao comum",
            "phaseolus bean",
        ],
        "group": "leguminosa",
        "fixes_nitrogen": True,
        "consumo_agua_mm": 380.0,
        "tempo_colheita_dias": 85,
        "market": 0.88,
        "soil_benefit": 0.80,
        "heat_tolerance": 0.60,
        "water_demand": 0.58,
    },
    "SRG": {
        "crop_code": "SRG",
        "gaez_caption": "Sorghum",
        "scientific_name": "Sorghum bicolor",
        "nome": "Sorgo",
        "aliases": ["sorgo", "sorghum", "sorgo forrageiro"],
        "group": "graminea",
        "fixes_nitrogen": False,
        "consumo_agua_mm": 320.0,
        "tempo_colheita_dias": 90,
        "market": 0.68,
        "soil_benefit": 0.65,
        "heat_tolerance": 0.90,
        "water_demand": 0.36,
    },
    "PML": {
        "crop_code": "PML",
        "gaez_caption": "Pearl millet",
        "scientific_name": "Pennisetum glaucum",
        "nome": "Milheto",
        "aliases": ["milheto", "pearl millet"],
        "group": "graminea",
        "fixes_nitrogen": False,
        "consumo_agua_mm": 280.0,
        "tempo_colheita_dias": 65,
        "market": 0.60,
        "soil_benefit": 0.82,
        "heat_tolerance": 0.90,
        "water_demand": 0.35,
    },
    "GRD": {
        "crop_code": "GRD",
        "gaez_caption": "Groundnut",
        "scientific_name": "Arachis hypogaea",
        "nome": "Amendoim",
        "aliases": ["amendoim", "groundnut", "mendubi"],
        "group": "leguminosa",
        "fixes_nitrogen": True,
        "consumo_agua_mm": 420.0,
        "tempo_colheita_dias": 100,
        "market": 0.78,
        "soil_benefit": 0.82,
        "heat_tolerance": 0.78,
        "water_demand": 0.56,
    },
    "SOY": {
        "crop_code": "SOY",
        "gaez_caption": "Soybean",
        "scientific_name": "Glycine max",
        "nome": "Soja",
        "aliases": ["soja", "soybean"],
        "group": "leguminosa",
        "fixes_nitrogen": True,
        "consumo_agua_mm": 550.0,
        "tempo_colheita_dias": 115,
        "market": 0.96,
        "soil_benefit": 0.75,
        "heat_tolerance": 0.60,
        "water_demand": 0.82,
    },
    "SPO": {
        "crop_code": "SPO",
        "gaez_caption": "Sweet potato",
        "scientific_name": "Ipomoea batatas",
        "nome": "Batata-doce",
        "aliases": ["batata-doce", "batata doce", "sweet potato"],
        "group": "tuberculo",
        "fixes_nitrogen": False,
        "consumo_agua_mm": 360.0,
        "tempo_colheita_dias": 110,
        "market": 0.74,
        "soil_benefit": 0.62,
        "heat_tolerance": 0.80,
        "water_demand": 0.50,
    },
    "PIG": {
        "crop_code": "PIG",
        "gaez_caption": "Pigeonpea",
        "scientific_name": "Cajanus cajan",
        "nome": "Crotalária / Guandu",
        "aliases": [
            "crotalaria",
            "feijao-de-porco",
            "feijao de porco",
            "guandu",
            "feijao-guandu",
            "pigeonpea",
            "adubo verde",
            "adubacao verde",
        ],
        "group": "leguminosa",
        "fixes_nitrogen": True,
        "consumo_agua_mm": 250.0,
        "tempo_colheita_dias": 65,
        "market": 0.55,
        "soil_benefit": 0.95,
        "heat_tolerance": 0.88,
        "water_demand": 0.34,
    },
    "WMEL": {
        "crop_code": "WMEL",
        "gaez_caption": "Watermelon",
        "scientific_name": "Citrullus lanatus",
        "nome": "Abóbora / Melancia",
        "aliases": ["abobora", "jerimum", "abobora-cabotia", "melancia", "watermelon"],
        "group": "cucurbitacea",
        "fixes_nitrogen": False,
        "consumo_agua_mm": 380.0,
        "tempo_colheita_dias": 90,
        "market": 0.72,
        "soil_benefit": 0.68,
        "heat_tolerance": 0.82,
        "water_demand": 0.52,
    },
    "SES": {
        "crop_code": "SES",
        "gaez_caption": "Sesame",
        "scientific_name": "Sesamum indicum",
        "nome": "Gergelim",
        "aliases": ["gergelim", "sesame"],
        "group": "oleaginosa",
        "fixes_nitrogen": False,
        "consumo_agua_mm": 280.0,
        "tempo_colheita_dias": 95,
        "market": 0.72,
        "soil_benefit": 0.65,
        "heat_tolerance": 0.92,
        "water_demand": 0.36,
    },
    "SFL": {
        "crop_code": "SFL",
        "gaez_caption": "Sunflower",
        "scientific_name": "Helianthus annuus",
        "nome": "Girassol",
        "aliases": ["girassol", "sunflower"],
        "group": "oleaginosa",
        "fixes_nitrogen": False,
        "consumo_agua_mm": 420.0,
        "tempo_colheita_dias": 100,
        "market": 0.76,
        "soil_benefit": 0.68,
        "heat_tolerance": 0.75,
        "water_demand": 0.55,
    },
}

HWSD_SOIL_CLASSES: dict[int, str] = {
    1: "Acrisols - AC (Argissolos)",
    2: "Alisols - AL",
    3: "Andosols - AN",
    4: "Arenosols - AR (Neossolos Quartzarênicos)",
    5: "Anthrosols - AT (Antrossolos)",
    6: "Chernozems - CH (Chernossolos)",
    7: "Calcisols - CL",
    8: "Cambisols - CM (Cambissolos)",
    9: "Cryosols - CR",
    10: "Fluvisols - FL (Neossolos Flúvicos)",
    11: "Ferralsols - FR (Latossolos)",
    12: "Glaciers - GG",
    13: "Gleysols - GL (Gleissolos)",
    14: "Gypsisols - GY",
    15: "Histosols - HS (Organossolos)",
    16: "Islands - IS",
    17: "Kastanozems - KS",
    18: "Leptosols - LP (Neossolos Litólicos)",
    19: "Luvisols - LV (Luvissolos)",
    20: "Lixisols - LX (Lixissolos)",
    21: "Nitisols - NT (Nitossolos)",
    22: "Phaeozems - PH",
    23: "Planosols - PL (Planossolos)",
    24: "Plinthosols - PT (Plintossolos)",
    25: "Podzols - PZ (Espodossolos)",
    26: "Regosols - RG (Neossolos Regolíticos)",
    27: "Retisols - RT",
    28: "Solonchaks - SC",
    29: "Solonetz - SN",
    30: "Stagnosols - ST",
    31: "Technosols - TC",
    32: "Umbrisols - UM",
    33: "Vertisols - VR (Vertissolos)",
    34: "Open Water - WR",
}

SQ_IDX_LIMITING_FACTORS: dict[int, str] = {
    1: "Sem restrições ou com restrições leves (SQ1)",
    2: "Disponibilidade/retenção natural de nutrientes (SQ2)",
    3: "Condições de enraizamento (SQ3)",
    4: "Disponibilidade de oxigênio e drenagem para raízes (SQ4)",
    5: "Excesso de sais e sodicidade (SQ5)",
    6: "Presença de calcário e toxidez por gesso (SQ6)",
    7: "Trabalhabilidade e manejo físico do solo (SQ7)",
    8: "Declividade acentuada do terreno (SQ8)",
    9: "Solo congelado/geleira",
    10: "Unidade mista ou sem informação pedológica pontual",
    11: "Corpo d'água",
}

SLOPE_MED_CLASSES: dict[int, tuple[str, str]] = {
    1: ("0.0 - 0.5%", "baixo"),
    2: ("0.5 - 2%", "baixo"),
    3: ("2 - 5%", "baixo"),
    4: ("5 - 8%", "medio"),
    5: ("8 - 12%", "medio"),
    6: ("12 - 16%", "alto"),
    7: ("16 - 24%", "alto"),
    8: ("24 - 30%", "critico"),
    9: ("30 - 45%", "critico"),
    10: ("> 45%", "critico"),
}

_IRRIGATED_KEYWORDS = (
    "gotejamento",
    "aspersao",
    "sulco",
    "irrigad",
    "pivo",
    "microaspersao",
    "irrigated",
)
_HIGH_INPUT_KEYWORDS = (
    "alto",
    "high",
    "mecanizad",
    "tecnificad",
    "him",
    "hrlm",
    "hilm",
)
_VALID_INPUT_LEVELS = {"LRLM", "HRLM", "LILM", "HILM"}


def _normalize_text(text: str) -> str:
    cleaned = (
        str(text or "")
        .strip()
        .lower()
        .replace("(atual)", "")
        .replace("_", " ")
        .strip()
    )
    decomposed = unicodedata.normalize("NFKD", cleaned)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_text.split())


def resolve_crop_code(crop_name_or_code: str) -> str | None:
    """Resolve um código GAEZ v5 (ex.: MZE) ou nome popular/oficial em português para código GAEZ."""
    raw = str(crop_name_or_code or "").strip()
    if not raw:
        return None
    upper = raw.upper()
    if upper in GAEZ_SUITABILITY_CROPS:
        return upper

    norm = _normalize_text(raw)
    norm_hyphen = norm.replace(" ", "-")
    for code, meta in GAEZ_SUITABILITY_CROPS.items():
        candidates = [meta["nome"], meta["gaez_caption"], *meta.get("aliases", [])]
        for alias in candidates:
            alias_norm = _normalize_text(alias)
            if (
                norm == alias_norm
                or norm_hyphen == alias_norm.replace(" ", "-")
                or alias_norm in norm
            ):
                return code
    return None


def classify_suitability_index(score_100: float) -> str:
    """Classifica o índice de aptidão GAEZ v5 (0–100) segundo GAEZ-V5.SIX.json."""
    if score_100 > 85.0:
        return "very_high"
    if score_100 > 70.0:
        return "high"
    if score_100 > 55.0:
        return "good"
    if score_100 > 40.0:
        return "medium"
    if score_100 > 25.0:
        return "moderate"
    if score_100 > 10.0:
        return "marginal"
    if score_100 > 0.0:
        return "very_marginal"
    return "not_suitable"


def resolve_gaez_input_level(prioridades: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Mapeia prioridades/irrigação do produtor para os 4 regimes oficiais do GAEZ v5:
    - LRLM: Sequeiro + Baixo insumo
    - HRLM: Sequeiro + Alto insumo
    - LILM: Irrigado + Baixo insumo
    - HILM: Irrigado + Alto insumo
    """
    p = prioridades or {}
    explicit = str(p.get("gaez_input_level", "")).strip().upper()
    if explicit in _VALID_INPUT_LEVELS:
        is_irrigated = explicit in {"LILM", "HILM"}
        is_high_input = explicit in {"HRLM", "HILM"}
        return {
            "input_level": explicit,
            "im_sq": "HIM" if is_high_input else "LIM",
            "future_input_level": "HILM" if is_irrigated else "HRLM",
            "is_irrigated": is_irrigated,
            "is_high_input": is_high_input,
        }

    water_tokens = " ".join(
        _normalize_text(str(p.get(k, "")))
        for k in ("metodo_irrigacao", "irrigacao", "agua", "sistema_hidrico")
        if p.get(k) is not None
    )
    input_tokens = " ".join(
        _normalize_text(str(p.get(k, "")))
        for k in ("nivel_insumo", "insumo", "equipamento", "manejo")
        if p.get(k) is not None
    )

    is_irrigated = any(kw in water_tokens for kw in _IRRIGATED_KEYWORDS)
    if isinstance(p.get("irrigado"), bool):
        is_irrigated = bool(p["irrigado"])

    is_high_input = any(kw in input_tokens for kw in _HIGH_INPUT_KEYWORDS)
    if is_irrigated and is_high_input:
        level = "HILM"
    elif is_irrigated:
        level = "LILM"
    elif is_high_input:
        level = "HRLM"
    else:
        level = "LRLM"

    return {
        "input_level": level,
        "im_sq": "HIM" if is_high_input else "LIM",
        "future_input_level": "HILM" if is_irrigated else "HRLM",
        "is_irrigated": is_irrigated,
        "is_high_input": is_high_input,
    }


class GAEZDataProvider:
    """
    Cliente direto para os rasters Cloud-Optimized GeoTIFF (COG) e dimensões do
    FAO GAEZ v5 (Suitability and Attainable Yield, HWSD v2.01, SQ-IDX, SQX, SLOPE-MED),
    sem fallbacks determinísticos regionais.
    """

    def __init__(
        self,
        data_path: str = "data",
        ssp: str = "SSP370",
        max_workers: int = 8,
    ):
        self.data_path = data_path
        self.ssp = str(ssp or "SSP370").strip().upper()
        self.max_workers = max(1, int(max_workers))

    def _cache_dir(self) -> str:
        return os.path.join(self.data_path, "gaez_cache")

    def fetch_dimension_crops(self) -> list[dict[str, Any]]:
        """Consulta as culturas oficiais do Módulo V (GAEZ-V5.CROP-RES05.json) com cache local."""
        cache_path = os.path.join(self._cache_dir(), "dimension_crop_res05.json")
        if os.path.exists(cache_path):
            try:
                with open(cache_path, encoding="utf-8") as fp:
                    cached = json.load(fp)
                    if isinstance(cached, list) and cached:
                        return cached
            except Exception:
                pass

        try:
            resp = httpx.get(GAEZ_CROP_DIMENSION_URL, timeout=10.0)
            resp.raise_for_status()
            payload = resp.json()
            rows = payload if isinstance(payload, list) else payload.get("members", [])
            if isinstance(rows, list) and rows:
                os.makedirs(self._cache_dir(), exist_ok=True)
                with open(cache_path, "w", encoding="utf-8") as fp:
                    json.dump(rows, fp, ensure_ascii=False)
                return rows
        except Exception as exc:
            logger.warning("Falha ao consultar dimensão CROP-RES05 do FAO GAEZ v5: %s", exc)
        return []

    @staticmethod
    def _sample_cog_point(
        relative_path: str, lon: float, lat: float
    ) -> tuple[bool, float | None]:
        """
        Amostra 1 pixel (lon, lat) via HTTP Range Request no COG oficial da FAO.
        Retorna (request_succeeded, numeric_value_or_none_if_nodata).
        """
        url = f"{GAEZ_BASE_URL}/{relative_path.lstrip('/')}"
        try:
            with rasterio.open(url) as src:
                sampled = list(src.sample([(lon, lat)]))
                if not sampled:
                    return True, None
                raw_val = float(sampled[0][0])
                nodata = src.nodata
                if not math.isfinite(raw_val):
                    return True, None
                if nodata is not None and math.isfinite(float(nodata)) and abs(raw_val - float(nodata)) < 1e-6:
                    return True, None
                return True, raw_val
        except Exception as exc:
            logger.warning("Falha ao amostrar COG GAEZ %s: %s", relative_path, exc)
            return False, None

    @staticmethod
    def _extract_centroid(polygon_coords: Any) -> tuple[float, float] | None:
        if isinstance(polygon_coords, dict):
            lat = polygon_coords.get("lat")
            lng = polygon_coords.get("lng", polygon_coords.get("lon"))
            if lat is not None and lng is not None:
                return float(lat), float(lng)
            return None

        geo = calcular_geometria_terreno(polygon_coords)
        if geo.get("total_vertices", 0) > 0:
            center = geo["localizacao_central"]
            return float(center["lat"]), float(center["lng"])
        return None

    def extract_gaez_metrics(
        self,
        polygon_coords: Any,
        prioridades: dict[str, Any] | None = None,
        crop_codes: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Extrai dados reais de Suitability (`RES05-SUX`), Attainable Yield (`RES05-YLX`),
        projeção futura CMIP6 (`FP2140`), solo (`HWSDV201`, `SQ-IDX`, `SQX.SQ0`) e
        declividade (`SLOPE-MED`) diretamente do bucket FAO GAEZ v5 para o ponto do terreno.
        """
        regime = resolve_gaez_input_level(prioridades)
        input_level = regime["input_level"]
        im_sq = regime["im_sq"]
        future_input_level = regime["future_input_level"]

        centroid = self._extract_centroid(polygon_coords)
        if centroid is None:
            return {
                "data_quality": "no_data",
                "origem": "fao_gaez_v5",
                "input_level": input_level,
                "ssp_scenario": self.ssp,
                "centroid": None,
                "crops": {},
                "soil": {},
            }

        lat, lng = centroid
        codes = [
            str(c).strip().upper()
            for c in (crop_codes or list(GAEZ_SUITABILITY_CROPS.keys()))
            if str(c).strip().upper() in GAEZ_SUITABILITY_CROPS
        ]
        if not codes:
            codes = list(GAEZ_SUITABILITY_CROPS.keys())

        # Cache espacial alinhado à grade de 5 arc-min (~9 km) do RES05
        lat_cell = round(lat * 12.0) / 12.0
        lng_cell = round(lng * 12.0) / 12.0
        codes_tag = "all" if set(codes) == set(GAEZ_SUITABILITY_CROPS.keys()) else "_".join(sorted(codes))
        cache_file = f"gaez_{lat_cell:.3f}_{lng_cell:.3f}_{input_level}_{self.ssp}_{codes_tag}.json"
        cache_path = os.path.join(self._cache_dir(), cache_file)

        if os.path.exists(cache_path):
            try:
                with open(cache_path, encoding="utf-8") as fp:
                    cached = json.load(fp)
                    if isinstance(cached, dict) and cached.get("data_quality") == "gaez_v5_cog":
                        return cached
            except Exception:
                pass

        # Monta lista de caminhos COG para amostragem paralela direta
        tasks: dict[str, str] = {
            "soil:hwsd": "MAP/GAEZ-V5.HWSDV201.tif",
            "soil:sq_idx": f"MAPSET/SQ-IDX/GAEZ-V5.SQ-IDX.{im_sq}.tif",
            "soil:sq0": f"MAPSET/SQX/GAEZ-V5.SQX.SQ0.{im_sq}.tif",
            "soil:slope": "MAP/GAEZ-V5.SLOPE-MED.tif",
        }
        for code in codes:
            tasks[f"crop:{code}:sux"] = (
                f"MAPSET/RES05-SUX/GAEZ-V5.RES05-SUX.HP0120.AGERA5.HIST.{code}.{input_level}.tif"
            )
            tasks[f"crop:{code}:ylx"] = (
                f"MAPSET/RES05-YLX/GAEZ-V5.RES05-YLX.HP0120.AGERA5.HIST.{code}.{input_level}.tif"
            )
            tasks[f"crop:{code}:fut_sux"] = (
                f"MAPSET/RES05-SUX/GAEZ-V5.RES05-SUX.FP2140.ENSEMBLE.{self.ssp}.{code}.{future_input_level}.tif"
            )
            tasks[f"crop:{code}:fut_ylx"] = (
                f"MAPSET/RES05-YLX/GAEZ-V5.RES05-YLX.FP2140.ENSEMBLE.{self.ssp}.{code}.{future_input_level}.tif"
            )
            if input_level != future_input_level:
                tasks[f"crop:{code}:hist_fut_sux"] = (
                    f"MAPSET/RES05-SUX/GAEZ-V5.RES05-SUX.HP0120.AGERA5.HIST.{code}.{future_input_level}.tif"
                )

        keys = list(tasks.keys())
        paths = list(tasks.values())

        def _worker(rel_path: str) -> tuple[bool, float | None]:
            return self._sample_cog_point(rel_path, lng, lat)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            sampled_results = dict(zip(keys, executor.map(_worker, paths)))

        crop_requests_ok = sum(
            1
            for k, (ok, _val) in sampled_results.items()
            if ok and k.startswith("crop:") and k.endswith((":sux", ":ylx"))
        )

        if crop_requests_ok == 0:
            return {
                "data_quality": "no_data",
                "origem": "fao_gaez_v5",
                "input_level": input_level,
                "ssp_scenario": self.ssp,
                "centroid": {"lat": round(lat, 6), "lng": round(lng, 6)},
                "crops": {},
                "soil": {},
            }

        def _get_val(key: str) -> tuple[bool, float | None]:
            return sampled_results.get(key, (False, None))

        # Decodifica solo (HWSD v2.01, SQ-IDX, SQX.SQ0, SLOPE-MED)
        _, raw_hwsd = _get_val("soil:hwsd")
        _, raw_sq_idx = _get_val("soil:sq_idx")
        _, raw_sq0 = _get_val("soil:sq0")
        _, raw_slope = _get_val("soil:slope")

        hwsd_code = int(round(raw_hwsd)) if raw_hwsd is not None and 0 < raw_hwsd < 65535 else None
        soil_group = HWSD_SOIL_CLASSES.get(hwsd_code) if hwsd_code is not None else None

        sq_idx_code = int(round(raw_sq_idx)) if raw_sq_idx is not None and raw_sq_idx > 0 else None
        limiting_factor = (
            SQ_IDX_LIMITING_FACTORS.get(sq_idx_code) if sq_idx_code is not None else None
        )

        # GAEZ-V5.SQX.SQ0 codifica classes 1..10 representando faixas 0.0-0.1 .. 0.9-1.0
        sq0_code = int(round(raw_sq0)) if raw_sq0 is not None and raw_sq0 > 0 else None
        soil_quality_index: float | None = None
        if sq0_code is not None and 1 <= sq0_code <= 10:
            soil_quality_index = round((sq0_code - 0.5) / 10.0, 2)
        elif sq0_code == 11:
            soil_quality_index = 0.15

        slope_code = int(round(raw_slope)) if raw_slope is not None and 1 <= raw_slope <= 10 else None
        slope_range_pct, erosion_risk = (
            SLOPE_MED_CLASSES.get(slope_code, ("não informado", "medio"))
            if slope_code is not None
            else ("não informado", "medio")
        )

        soil_payload = {
            "hwsd_code": hwsd_code,
            "soil_group": soil_group,
            "limiting_factor_code": sq_idx_code,
            "limiting_factor": limiting_factor,
            "soil_quality_class": sq0_code,
            "soil_quality_index": soil_quality_index,
            "slope_class": slope_code,
            "slope_range_pct": slope_range_pct,
            "erosion_risk": erosion_risk,
        }

        # Decodifica culturas ("Suitability and Attainable Yield")
        crops_payload: dict[str, dict[str, Any]] = {}
        for code in codes:
            ok_sux, raw_sux = _get_val(f"crop:{code}:sux")
            ok_ylx, raw_ylx = _get_val(f"crop:{code}:ylx")
            if not ok_sux and not ok_ylx:
                continue

            sux_raw = max(0.0, float(raw_sux)) if raw_sux is not None else 0.0
            ylx_raw = max(0.0, float(raw_ylx)) if raw_ylx is not None else 0.0
            suit_01 = round(max(0.0, min(1.0, sux_raw / 10000.0)), 4)
            suit_100 = round(max(0.0, min(100.0, sux_raw / 100.0)), 2)

            ok_fut_sux, raw_fut_sux = _get_val(f"crop:{code}:fut_sux")
            ok_fut_ylx, raw_fut_ylx = _get_val(f"crop:{code}:fut_ylx")
            fut_suit_01 = (
                round(max(0.0, min(1.0, max(0.0, float(raw_fut_sux)) / 10000.0)), 4)
                if ok_fut_sux and raw_fut_sux is not None
                else None
            )
            fut_yield = (
                round(max(0.0, float(raw_fut_ylx)), 1)
                if ok_fut_ylx and raw_fut_ylx is not None
                else None
            )

            cmip6_delta = 0.0
            if fut_suit_01 is not None:
                if input_level == future_input_level:
                    cmip6_delta = round(fut_suit_01 - suit_01, 4)
                else:
                    ok_hfut, raw_hfut = _get_val(f"crop:{code}:hist_fut_sux")
                    if ok_hfut and raw_hfut is not None:
                        base_fut_01 = max(0.0, min(1.0, max(0.0, float(raw_hfut)) / 10000.0))
                        cmip6_delta = round(fut_suit_01 - base_fut_01, 4)

            if cmip6_delta >= 0.03:
                climate_resilience = "ganho"
            elif cmip6_delta <= -0.10:
                climate_resilience = "perda_severa"
            elif cmip6_delta <= -0.03:
                climate_resilience = "perda_moderada"
            else:
                climate_resilience = "estavel"

            meta = GAEZ_SUITABILITY_CROPS[code]
            crops_payload[code] = {
                "crop_code": code,
                "gaez_caption": meta["gaez_caption"],
                "scientific_name": meta.get("scientific_name"),
                "nome": meta["nome"],
                "group": meta["group"],
                "fixes_nitrogen": meta["fixes_nitrogen"],
                "suitability_raw": round(sux_raw, 1),
                "suitability_index": suit_01,
                "suitability_score_100": suit_100,
                "suitability_class": classify_suitability_index(suit_100),
                "attainable_yield_kg_ha": round(ylx_raw, 1),
                "cmip6_future_suitability_index": fut_suit_01,
                "cmip6_suitability_delta": cmip6_delta,
                "cmip6_future_yield_kg_ha": fut_yield,
                "climate_resilience": climate_resilience,
                "consumo_agua_mm": meta["consumo_agua_mm"],
                "tempo_colheita_dias": meta["tempo_colheita_dias"],
                "market": meta["market"],
                "soil_benefit": meta["soil_benefit"],
                "heat_tolerance": meta["heat_tolerance"],
                "water_demand": meta["water_demand"],
            }

        if not crops_payload:
            return {
                "data_quality": "no_data",
                "origem": "fao_gaez_v5",
                "input_level": input_level,
                "ssp_scenario": self.ssp,
                "centroid": {"lat": round(lat, 6), "lng": round(lng, 6)},
                "crops": {},
                "soil": {},
            }

        result = {
            "data_quality": "gaez_v5_cog",
            "origem": "fao_gaez_v5",
            "centroid": {"lat": round(lat, 6), "lng": round(lng, 6)},
            "input_level": input_level,
            "future_input_level": future_input_level,
            "is_irrigated": regime["is_irrigated"],
            "is_high_input": regime["is_high_input"],
            "ssp_scenario": self.ssp,
            "soil": soil_payload,
            "crops": crops_payload,
        }

        try:
            os.makedirs(self._cache_dir(), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as fp:
                json.dump(result, fp, ensure_ascii=False)
        except Exception as exc:
            logger.warning("Não foi possível salvar cache GAEZ em disco: %s", exc)

        return result

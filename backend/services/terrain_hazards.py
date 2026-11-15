import csv
from concurrent.futures import ThreadPoolExecutor
import io
import json
import logging
import math
import os
from typing import Any

import httpx

from backend.services.geospatial import calcular_geometria_terreno

logger = logging.getLogger(__name__)

OPEN_METEO_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
NASA_FIRMS_AREA_CSV_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"


def _haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calcula distância aproximada em metros entre duas coordenadas WGS84."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * r * math.asin(min(1.0, math.sqrt(a)))


def _normalize_points(polygon_coords: Any) -> tuple[dict[str, float] | None, list[tuple[float, float]]]:
    """Extrai centroide e lista de pontos (lat, lng) a partir de polígono ou ponto."""
    if isinstance(polygon_coords, dict):
        lat = polygon_coords.get("lat")
        lng = polygon_coords.get("lng", polygon_coords.get("lon"))
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            c = {"lat": float(lat), "lng": float(lng)}
            return c, [(c["lat"], c["lng"])]
        return None, []

    if not isinstance(polygon_coords, list) or not polygon_coords:
        return None, []

    pts: list[tuple[float, float]] = []
    for item in polygon_coords:
        if isinstance(item, dict):
            lat = item.get("lat")
            lng = item.get("lng", item.get("lon"))
            if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                pts.append((float(lat), float(lng)))
    if not pts:
        return None, []

    geom = calcular_geometria_terreno(
        [{"lat": lat, "lng": lng} for lat, lng in pts]
    )
    center = geom.get("localizacao_central") or {
        "lat": sum(p[0] for p in pts) / len(pts),
        "lng": sum(p[1] for p in pts) / len(pts),
    }
    return {"lat": float(center["lat"]), "lng": float(center["lng"])}, pts


class TerrainHazardsProvider:
    """
    Provedor leve de relevo (SRTM/Copernicus DEM via Open-Meteo Elevation API, sem login)
    e focos de calor em tempo real (NASA FIRMS Area CSV API via FIRMS_MAP_KEY).
    Sem fallbacks determinísticos inventados: retorna no_data / missing_map_key.
    """

    def __init__(
        self,
        data_path: str = "data",
        firms_map_key: str | None = None,
        firms_source: str | None = None,
        firms_days_back: int = 5,
    ):
        self.data_path = data_path
        self.cache_dir = os.path.join(data_path, "terrain_cache")
        self.firms_map_key = (
            firms_map_key
            if firms_map_key is not None
            else os.getenv("FIRMS_MAP_KEY", "").strip()
        )
        self.firms_source = (
            firms_source
            or os.getenv("FIRMS_SOURCE", "VIIRS_SNPP_NRT").strip()
            or "VIIRS_SNPP_NRT"
        )
        self.firms_days_back = max(1, min(5, int(firms_days_back)))

    def _read_cache(self, filename: str) -> dict[str, Any] | None:
        path = os.path.join(self.cache_dir, filename)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except Exception:
            return None
        return None

    def _write_cache(self, filename: str, payload: dict[str, Any]) -> None:
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            path = os.path.join(self.cache_dir, filename)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.debug("Não foi possível gravar cache em terrain_cache: %s", exc)

    def extract_srtm_elevation(self, polygon_coords: Any) -> dict[str, Any]:
        """Consulta elevação e calcula declividade (%) e risco de erosão do terreno."""
        center, pts = _normalize_points(polygon_coords)
        if center is None:
            return {
                "origem": "srtm",
                "data_quality": "no_data",
                "elevation_m": None,
                "elevation_min_m": None,
                "elevation_max_m": None,
                "slope_pct": None,
                "erosion_risk": None,
            }

        cache_name = f"srtm_{center['lat']:.3f}_{center['lng']:.3f}_{len(pts)}.json"
        cached = self._read_cache(cache_name)
        if cached is not None and cached.get("data_quality") == "srtm_api":
            return cached

        sample_pts: list[tuple[float, float]] = [(center["lat"], center["lng"])]
        for lat, lng in pts:
            if (round(lat, 5), round(lng, 5)) not in {
                (round(p[0], 5), round(p[1], 5)) for p in sample_pts
            }:
                sample_pts.append((lat, lng))

        if len(sample_pts) == 1:
            d = 0.001  # ~111 m para estimar declividade em torno de ponto único
            c_lat, c_lng = sample_pts[0]
            sample_pts.extend(
                [
                    (c_lat + d, c_lng),
                    (c_lat - d, c_lng),
                    (c_lat, c_lng + d),
                    (c_lat, c_lng - d),
                ]
            )
        sample_pts = sample_pts[:50]

        try:
            resp = httpx.get(
                OPEN_METEO_ELEVATION_URL,
                params={
                    "latitude": ",".join(f"{p[0]:.6f}" for p in sample_pts),
                    "longitude": ",".join(f"{p[1]:.6f}" for p in sample_pts),
                },
                timeout=8.0,
            )
            resp.raise_for_status()
            elevs_raw = resp.json().get("elevation")
        except Exception as exc:
            logger.warning("Falha ao consultar API SRTM/Open-Meteo Elevation: %s", exc)
            return {
                "origem": "srtm",
                "data_quality": "no_data",
                "elevation_m": None,
                "elevation_min_m": None,
                "elevation_max_m": None,
                "slope_pct": None,
                "erosion_risk": None,
            }

        if not isinstance(elevs_raw, list) or not elevs_raw:
            return {
                "origem": "srtm",
                "data_quality": "no_data",
                "elevation_m": None,
                "elevation_min_m": None,
                "elevation_max_m": None,
                "slope_pct": None,
                "erosion_risk": None,
            }

        valid_pairs = [
            (pt, float(el))
            for pt, el in zip(sample_pts, elevs_raw)
            if isinstance(el, (int, float)) and not math.isnan(float(el))
        ]
        if not valid_pairs:
            return {
                "origem": "srtm",
                "data_quality": "no_data",
                "elevation_m": None,
                "elevation_min_m": None,
                "elevation_max_m": None,
                "slope_pct": None,
                "erosion_risk": None,
            }

        elevations = [el for _, el in valid_pairs]
        max_slope_pct = 0.0
        for i in range(len(valid_pairs)):
            (lat1, lng1), el1 = valid_pairs[i]
            for j in range(i + 1, len(valid_pairs)):
                (lat2, lng2), el2 = valid_pairs[j]
                dist_m = _haversine_meters(lat1, lng1, lat2, lng2)
                if dist_m >= 10.0:
                    slope = abs(el2 - el1) / dist_m * 100.0
                    if slope > max_slope_pct:
                        max_slope_pct = slope

        slope_rounded = round(max_slope_pct, 2)
        if slope_rounded < 5.0:
            erosion_risk = "baixo"
        elif slope_rounded <= 15.0:
            erosion_risk = "moderado"
        else:
            erosion_risk = "alto"

        result = {
            "origem": "srtm_open_meteo",
            "data_quality": "srtm_api",
            "elevation_m": round(sum(elevations) / len(elevations), 1),
            "elevation_min_m": round(min(elevations), 1),
            "elevation_max_m": round(max(elevations), 1),
            "slope_pct": slope_rounded,
            "erosion_risk": erosion_risk,
        }
        self._write_cache(cache_name, result)
        return result

    def extract_firms_hotspots(self, polygon_coords: Any) -> dict[str, Any]:
        """Consulta focos de calor recentes na API NASA FIRMS para o entorno do terreno."""
        center, pts = _normalize_points(polygon_coords)
        if center is None:
            return {
                "origem": "nasa_firms",
                "data_quality": "no_data",
                "hotspots_count": None,
                "nearest_fire_km": None,
                "max_frp_mw": None,
                "fire_risk": "desconhecido",
            }

        if not self.firms_map_key:
            return {
                "origem": "nasa_firms",
                "data_quality": "missing_map_key",
                "hotspots_count": None,
                "nearest_fire_km": None,
                "max_frp_mw": None,
                "fire_risk": "desconhecido",
                "mensagem": "Configure FIRMS_MAP_KEY para consultar focos de calor na NASA FIRMS.",
            }

        buffer_deg = 0.10  # ~11 km ao redor do polígono
        lats = [p[0] for p in pts]
        lngs = [p[1] for p in pts]
        west = max(-180.0, min(lngs) - buffer_deg)
        south = max(-90.0, min(lats) - buffer_deg)
        east = min(180.0, max(lngs) + buffer_deg)
        north = min(90.0, max(lats) + buffer_deg)

        cache_name = f"firms_{center['lat']:.2f}_{center['lng']:.2f}_{self.firms_source}_{self.firms_days_back}.json"
        cached = self._read_cache(cache_name)
        if cached is not None and cached.get("data_quality") == "nasa_firms_api":
            return cached

        area_str = f"{west:.4f},{south:.4f},{east:.4f},{north:.4f}"
        url = (
            f"{NASA_FIRMS_AREA_CSV_URL}/{self.firms_map_key}/"
            f"{self.firms_source}/{area_str}/{self.firms_days_back}"
        )

        try:
            resp = httpx.get(url, timeout=10.0)
            resp.raise_for_status()
            text = resp.text.strip()
        except Exception as exc:
            logger.warning("Falha ao consultar API NASA FIRMS: %s", exc)
            return {
                "origem": "nasa_firms",
                "data_quality": "no_data",
                "hotspots_count": None,
                "nearest_fire_km": None,
                "max_frp_mw": None,
                "fire_risk": "desconhecido",
            }

        if not text or "invalid" in text.lower()[:80]:
            return {
                "origem": "nasa_firms",
                "data_quality": "no_data",
                "hotspots_count": None,
                "nearest_fire_km": None,
                "max_frp_mw": None,
                "fire_risk": "desconhecido",
            }

        reader = csv.DictReader(io.StringIO(text))
        distances_km: list[float] = []
        frps: list[float] = []
        for row in reader:
            try:
                f_lat = float(row.get("latitude") or "")
                f_lng = float(row.get("longitude") or "")
            except (TypeError, ValueError):
                continue
            dist_km = _haversine_meters(center["lat"], center["lng"], f_lat, f_lng) / 1000.0
            distances_km.append(dist_km)
            try:
                frp_val = float(row.get("frp") or 0.0)
                frps.append(frp_val)
            except (TypeError, ValueError):
                pass

        count = len(distances_km)
        nearest_km = round(min(distances_km), 2) if distances_km else None
        max_frp = round(max(frps), 1) if frps else None

        if count == 0:
            fire_risk = "baixo"
        elif (nearest_km is not None and nearest_km <= 3.0) or count >= 3:
            fire_risk = "alto"
        else:
            fire_risk = "moderado"

        result = {
            "origem": "nasa_firms",
            "source": self.firms_source,
            "data_quality": "nasa_firms_api",
            "days_back": self.firms_days_back,
            "hotspots_count": count,
            "nearest_fire_km": nearest_km,
            "max_frp_mw": max_frp,
            "fire_risk": fire_risk,
        }
        self._write_cache(cache_name, result)
        return result

    def extract_terrain_and_hazards(self, polygon_coords: Any) -> dict[str, Any]:
        """Executa SRTM e NASA FIRMS em paralelo para o polígono informado."""
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_srtm = pool.submit(self.extract_srtm_elevation, polygon_coords)
            fut_firms = pool.submit(self.extract_firms_hotspots, polygon_coords)
            return {
                "srtm": fut_srtm.result(),
                "firms": fut_firms.result(),
            }

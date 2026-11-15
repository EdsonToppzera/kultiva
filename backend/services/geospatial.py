from datetime import date, datetime, timedelta, timezone
import importlib
import json
import logging
import math
import os
from abc import ABC, abstractmethod
from typing import Any

import geopandas as gpd
import httpx
import numpy as np
import pandas as pd
import rioxarray  # noqa: F401 - registra o accessor .rio no xarray
import xarray as xr
from shapely.geometry import LineString, Point, Polygon

from backend.services.mock_nasa_data import (
    ECOSTRESS_FILE,
    GPM_FILE,
    SMAP_FILE,
    generate_synthetic_netcdf,
)

logger = logging.getLogger(__name__)

_DEFAULT_BRAZIL_POLYGON = [
    (-50.0, -15.0),
    (-45.0, -15.0),
    (-45.0, -10.0),
    (-50.0, -10.0),
]


def _parse_polygon_points(polygon_coords: Any) -> list[tuple[float, float]]:
    """Extrai pares (lon, lat) da entrada sem aplicar fallback para lista vazia."""
    if not isinstance(polygon_coords, (list, tuple)) or not polygon_coords:
        return []

    points: list[tuple[float, float]] = []
    for item in polygon_coords:
        if isinstance(item, dict):
            lat = item.get("lat")
            lng = item.get("lng", item.get("lon"))
            if lat is not None and lng is not None:
                points.append((float(lng), float(lat)))
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            x, y = float(item[0]), float(item[1])
            # Corrige pares (lat, lon) invertidos dentro da faixa do Brasil
            if x > -34.0 and y < -34.0:
                x, y = y, x
            points.append((x, y))

    return points


def _normalize_polygon_coords(polygon_coords: Any) -> list[tuple[float, float]]:
    """Normaliza coordenadas de entrada para pares (lon, lat) válidos no Brasil."""
    return _parse_polygon_points(polygon_coords) or _DEFAULT_BRAZIL_POLYGON


def calcular_geometria_terreno(polygon_coords: Any) -> dict[str, Any]:
    """Calcula área em hectares e centroide geográfico (lat/lng) de um polígono."""
    points = _parse_polygon_points(polygon_coords)
    total_vertices = len(points)
    if total_vertices == 0:
        return {
            "area_hectares": 0.0,
            "localizacao_central": {"lat": 0.0, "lng": 0.0},
            "total_vertices": 0,
        }

    mean_lng = sum(p[0] for p in points) / total_vertices
    mean_lat = sum(p[1] for p in points) / total_vertices

    if total_vertices < 3:
        return {
            "area_hectares": 0.0,
            "localizacao_central": {
                "lat": round(float(mean_lat), 6),
                "lng": round(float(mean_lng), 6),
            },
            "total_vertices": total_vertices,
        }

    poly = Polygon(points)
    if not poly.is_valid:
        poly = poly.buffer(0)

    if poly.is_empty or poly.area == 0:
        ref_lng, ref_lat = mean_lng, mean_lat
    else:
        centroid = poly.centroid
        ref_lng, ref_lat = float(centroid.x), float(centroid.y)

    # Projeção métrica local no centroide evita erro de grau->metro em latitudes brasileiras.
    m_per_deg_lat = 111_132.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(ref_lat))
    metric_points = [
        ((lon - ref_lng) * m_per_deg_lon, (lat - ref_lat) * m_per_deg_lat)
        for lon, lat in points
    ]
    metric_poly = Polygon(metric_points)
    if not metric_poly.is_valid:
        metric_poly = metric_poly.buffer(0)

    raw_area = float(metric_poly.area) / 10_000.0 if not metric_poly.is_empty else 0.0
    area_hectares = round(raw_area, 2) if math.isfinite(raw_area) else 0.0

    return {
        "area_hectares": area_hectares,
        "localizacao_central": {
            "lat": round(ref_lat, 6),
            "lng": round(ref_lng, 6),
        },
        "total_vertices": total_vertices,
    }


def _build_polygon_geometry(points: list[tuple[float, float]]) -> Polygon:
    """Constrói um Polygon Shapely válido mesmo quando há menos de 3 vértices."""
    if len(points) == 1:
        return Point(points[0]).buffer(0.05)
    if len(points) == 2:
        return LineString(points).buffer(0.05)

    geom = Polygon(points)
    if not geom.is_valid or geom.area == 0:
        return geom.buffer(0.05)
    return geom


class INASADataProvider(ABC):
    """
    CONTRATO MODULAR: Qualquer provedor de dados da NASA (Real ou Mock)
    deve implementar obrigatoriamente estes métodos.
    """

    @abstractmethod
    def extract_field_metrics(
        self, polygon_coords: Any, dataset: Any = None, profile: str | None = None
    ) -> dict[str, Any]:
        pass

    def calculate_field_geometry(self, polygon_coords: Any) -> dict[str, Any]:
        """Calcula área em hectares e centroide do polígono informado."""
        return calcular_geometria_terreno(polygon_coords)


class MockNASADataProvider(INASADataProvider):
    """Implementação temporária usando os NetCDFs sintéticos com clip espacial."""

    def __init__(self, data_path: str = "data", profile: str | None = None):
        self.data_path = data_path
        self.profile = profile

    def load_and_harmonize_netcdf(
        self,
        file_path: str,
        target_resolution: dict[str, float] | None = None,
        dataset_type: str = "SMAP",
    ) -> xr.Dataset:
        """Carrega dados sintéticos NetCDF via xarray."""
        _ = (target_resolution, dataset_type)
        return xr.open_dataset(file_path)

    # Heurística do mock para "solo exposto": solo muito seco e quente.
    BARE_MOISTURE_MAX = 0.12
    BARE_TEMP_MIN_C = 33.0

    @staticmethod
    def _reduce_spatial(ds: xr.Dataset, var: str, gdf: Any, geom: Any):
        """Média espacial por passo de tempo. Retorna (série, qualidade) ou (None, 'no_data')."""
        try:
            clipped = ds.rio.clip(gdf.geometry, gdf.crs, drop=True, all_touched=True)
            series = clipped[var].mean(dim=["lat", "lon"], skipna=True)
            if bool(series.isnull().all()):
                raise ValueError("clip sem células válidas")
            return series, "clip"
        except Exception as exc:
            # Polígono menor que a célula da grade (ou fora dela): usa a célula
            # mais próxima do centroide em vez de devolver 0.0.
            logger.info("Clip vazio/falhou (%s); usando célula mais próxima.", exc)
            try:
                c = geom.centroid
                series = ds[var].sel(lat=c.y, lon=c.x, method="nearest")
                return series, "nearest_cell"
            except Exception as exc2:
                logger.warning("Falha ao extrair %s do NetCDF mock: %s", var, exc2)
                return None, "no_data"

    def extract_field_metrics(
        self,
        polygon_coords: Any,
        dataset: Any = None,
        profile: str | None = None,
    ) -> dict[str, Any]:
        """
        Contrato `field_metrics`: avg_soil_moisture_smap, avg_surface_temp_ecostress,
        avg_precipitation_gpm (mm/dia), is_bare_field_period, data_quality
        (clip | nearest_cell | no_data), time_series (lista por dia) e coordinates.
        """
        _ = dataset
        norm_coords = _normalize_polygon_coords(polygon_coords)
        geom = _build_polygon_geometry(norm_coords)
        gdf = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[geom])

        sources = {
            "soil_moisture": (SMAP_FILE, "soil_moisture"),
            "surface_temp": (ECOSTRESS_FILE, "surface_temp"),
            "precipitation": (GPM_FILE, "precipitation"),
        }
        paths = {k: os.path.join(self.data_path, v[0]) for k, v in sources.items()}
        effective_profile = profile if profile is not None else self.profile
        marker_path = os.path.join(self.data_path, ".climate_profile")
        if (
            not all(os.path.exists(p) for p in paths.values())
            or effective_profile is not None
            or os.getenv("NASA_MOCK_PROFILE")
            or os.path.exists(marker_path)
        ):
            generate_synthetic_netcdf(self.data_path, profile=effective_profile)

        series: dict[str, Any] = {}
        qualities: list[str] = []
        for key, (_fname, var) in sources.items():
            path = paths[key]
            if not os.path.exists(path):
                series[key] = None
                qualities.append("no_data")
                continue
            with xr.open_dataset(path) as ds:
                ds.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
                ds.rio.write_crs("EPSG:4326", inplace=True)
                serie, quality = self._reduce_spatial(ds, var, gdf, geom)
                series[key] = serie.load() if serie is not None else None
                qualities.append(quality)

        def _mean(key: str) -> float:
            s = series.get(key)
            return float(s.mean().item()) if s is not None else 0.0

        if "no_data" in qualities:
            data_quality = "no_data"
        elif "nearest_cell" in qualities:
            data_quality = "nearest_cell"
        else:
            data_quality = "clip"

        avg_moisture = _mean("soil_moisture")
        avg_temp = _mean("surface_temp")
        avg_precip = _mean("precipitation")

        time_series: list[dict[str, Any]] = []
        if all(s is not None for s in series.values()):
            times = series["soil_moisture"]["time"].values
            for i, t in enumerate(times):
                time_series.append(
                    {
                        "data": str(pd.Timestamp(t).date()),
                        "soil_moisture": float(series["soil_moisture"].values[i]),
                        "surface_temp_c": float(series["surface_temp"].values[i]),
                        "precipitation_mm": float(series["precipitation"].values[i]),
                    }
                )

        is_bare = (
            data_quality != "no_data"
            and avg_moisture < self.BARE_MOISTURE_MAX
            and avg_temp >= self.BARE_TEMP_MIN_C
        )

        return {
            "coordinates": polygon_coords,
            "avg_soil_moisture_smap": avg_moisture,
            "avg_surface_temp_ecostress": avg_temp,
            "avg_precipitation_gpm": avg_precip,
            "is_bare_field_period": bool(is_bare),
            "data_quality": data_quality,
            "time_series": time_series,
        }


def _is_truthy_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "sim", "on"}


class RealNASADataProvider(INASADataProvider):
    """
    Provedor real de dados da NASA com suporte multi-fonte:
    1. Arquivos NetCDF/HDF5 reais locais em `{data_path}/real/`
    2. NASA Earthdata (`earthaccess` + `xarray.open_mfdataset`)
    3. API agroclimatológica oficial NASA POWER (sem login, com cache em disco)

    Mantém exatamente o mesmo contrato `field_metrics` de 7 chaves do `MockNASADataProvider`.
    """

    POWER_API_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
    _REAL_FILE_EXTENSIONS = (".nc", ".nc4", ".h5", ".hdf5")
    _KEY_PATH_HINTS: dict[str, tuple[str, ...]] = {
        "soil_moisture": ("soil_moisture", "spl3smp", "smap", "gwettop"),
        "surface_temp": ("surface_temp", "eco2lste", "ecostress", "lst"),
        "precipitation": ("precipitation", "gpm", "imerg", "prectot"),
        "ndvi": ("ndvi", "mod13", "modis"),
    }

    COLLECTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
        "soil_moisture": (
            "SPL3SMP_E",
            (
                "soil_moisture",
                "Soil_Moisture_Retrieval_Data_AM_soil_moisture",
                "Soil_Moisture_Retrieval_Data_PM_soil_moisture_pm",
                "sm_surface",
                "GWETTOP",
            ),
        ),
        "surface_temp": (
            "ECO2LSTE",
            ("surface_temp", "LST", "SDS_LST", "LST_Day_1km", "TS"),
        ),
        "precipitation": (
            "GPM_3IMERGDF",
            (
                "precipitation",
                "precipitationCal",
                "HQprecipitation",
                "precipitation_cnt",
                "PRECTOTCORR",
            ),
        ),
        "ndvi": (
            "MOD13Q1",
            ("ndvi", "NDVI", "250m_16_days_NDVI", "_250m_16_days_NDVI"),
        ),
    }
    _PRIMARY_KEYS = ("soil_moisture", "surface_temp", "precipitation")
    BARE_NDVI_MAX = 0.25
    BARE_MOISTURE_MAX = MockNASADataProvider.BARE_MOISTURE_MAX
    BARE_TEMP_MIN_C = MockNASADataProvider.BARE_TEMP_MIN_C

    def __init__(
        self,
        credentials: dict[str, Any] | None = None,
        data_path: str = "data",
        days_back: int | None = None,
        enable_nasa_power: bool | None = None,
    ):
        if credentials is None:
            credentials = {
                "username": os.getenv("EARTHDATA_USERNAME"),
                "password": os.getenv("EARTHDATA_PASSWORD"),
                "token": os.getenv("EARTHDATA_TOKEN"),
            }
        self.credentials = credentials
        self.data_path = data_path
        if days_back is None:
            try:
                days_back = int(os.getenv("NASA_REAL_DAYS_BACK", "5"))
            except ValueError:
                days_back = 5
        self.days_back = max(1, int(days_back))
        self.enable_nasa_power = (
            bool(enable_nasa_power)
            if enable_nasa_power is not None
            else _is_truthy_env("NASA_POWER_FALLBACK", False)
        )

    @staticmethod
    def _load_earthaccess() -> Any | None:
        try:
            return importlib.import_module("earthaccess")
        except ImportError:
            logger.warning(
                "Pacote earthaccess não instalado; usando fontes locais/NASA POWER quando habilitadas."
            )
            return None

    def _authenticate(self, ea: Any) -> bool:
        try:
            if self.credentials.get("username"):
                os.environ["EARTHDATA_USERNAME"] = str(self.credentials["username"])
            if self.credentials.get("password"):
                os.environ["EARTHDATA_PASSWORD"] = str(self.credentials["password"])
            if self.credentials.get("token"):
                os.environ["EARTHDATA_TOKEN"] = str(self.credentials["token"])

            try:
                auth = ea.login(strategy="environment")
            except Exception:
                auth = ea.login()

            if auth is None:
                return True
            return bool(getattr(auth, "authenticated", auth))
        except Exception as exc:
            logger.warning("Falha ao autenticar no NASA Earthdata: %s", exc)
            return False

    @staticmethod
    def _open_single_dataset(file_obj: Any) -> xr.Dataset:
        try:
            return xr.open_dataset(file_obj)
        except Exception:
            if isinstance(file_obj, (str, os.PathLike)) and str(file_obj).lower().endswith(
                (".h5", ".hdf5", ".nc4")
            ):
                return xr.open_dataset(file_obj, engine="h5netcdf")
            raise

    @classmethod
    def _open_mfdataset(cls, files: list[Any]) -> xr.Dataset:
        try:
            return xr.open_mfdataset(files, combine="by_coords")
        except ImportError as exc:
            logger.info(
                "xr.open_mfdataset indisponível (%s); usando open_dataset + combine.",
                exc,
            )
            opened = [cls._open_single_dataset(f).load() for f in files]
            try:
                if len(opened) == 1:
                    return opened[0]
                try:
                    combined = xr.combine_by_coords(opened, combine_attrs="override")
                except Exception:
                    combined = xr.concat(opened, dim="time")
                return combined.load()
            finally:
                for ds in opened:
                    ds.close()

    def _discover_local_real_sources(self) -> dict[str, list[str]]:
        """Descobre arquivos NetCDF/HDF5 reais locais em `{data_path}/real/`."""
        real_dir = os.path.join(self.data_path, "real")
        if not os.path.isdir(real_dir):
            return {}

        found: dict[str, list[str]] = {k: [] for k in self.COLLECTIONS}

        # 1) Subpastas explícitas por chave ou nome da coleção NASA
        for key, (short_name, _candidates) in self.COLLECTIONS.items():
            for sub_name in (key, short_name, short_name.lower()):
                sub_dir = os.path.join(real_dir, sub_name)
                if os.path.isdir(sub_dir):
                    for fname in sorted(os.listdir(sub_dir)):
                        if fname.lower().endswith(self._REAL_FILE_EXTENSIONS):
                            found[key].append(os.path.join(sub_dir, fname))

        # 2) Arquivos soltos diretamente em `data/real/` identificados por prefixo/hint
        for fname in sorted(os.listdir(real_dir)):
            fpath = os.path.join(real_dir, fname)
            if not os.path.isfile(fpath) or not fname.lower().endswith(
                self._REAL_FILE_EXTENSIONS
            ):
                continue
            lower = fname.lower()
            for key, hints in self._KEY_PATH_HINTS.items():
                if any(hint in lower for hint in hints):
                    if fpath not in found[key]:
                        found[key].append(fpath)
                    break

        return {k: paths for k, paths in found.items() if paths}

    def _open_collection_dataset(
        self,
        key: str,
        short_name: str,
        bbox: tuple[float, float, float, float],
        temporal: tuple[str, str],
        dataset: Any,
        ea: Any,
        authenticated: bool,
        local_sources: dict[str, list[str]] | None = None,
    ) -> tuple[xr.Dataset | None, bool]:
        if isinstance(dataset, xr.Dataset):
            return dataset, False

        if isinstance(dataset, dict):
            source = dataset.get(key) or dataset.get(short_name)
            if source is not None:
                return self._open_source(source)

        if isinstance(dataset, (list, tuple)) and dataset:
            return self._open_source(dataset)

        if isinstance(dataset, (str, os.PathLike)):
            return self._open_single_dataset(dataset).load(), True

        if dataset is None and local_sources and local_sources.get(key):
            return self._open_source(local_sources[key])

        if ea is None or not authenticated:
            return None, False

        try:
            granules = ea.search_data(
                short_name=short_name,
                bounding_box=bbox,
                temporal=temporal,
            )
            if not granules:
                return None, False
            files = ea.open(granules)
            if not files:
                return None, False
            return self._open_mfdataset(list(files)), True
        except Exception as exc:
            logger.warning("Falha ao consultar coleção NASA %s: %s", short_name, exc)
            return None, False

    def _open_source(self, source: Any) -> tuple[xr.Dataset | None, bool]:
        if isinstance(source, xr.Dataset):
            return source, False
        if isinstance(source, (str, os.PathLike)):
            return self._open_single_dataset(source).load(), True
        if isinstance(source, (list, tuple)) and source:
            if all(isinstance(item, xr.Dataset) for item in source):
                try:
                    return xr.combine_by_coords(list(source), combine_attrs="override"), False
                except Exception:
                    return xr.concat(list(source), dim="time"), False
            return self._open_mfdataset(list(source)), True
        return None, False

    @staticmethod
    def _prepare_dataset(
        ds: xr.Dataset, candidates: tuple[str, ...]
    ) -> tuple[xr.Dataset | None, str | None]:
        var_name = next((name for name in candidates if name in ds.data_vars), None)
        if var_name is None:
            return None, None

        rename_map: dict[str, str] = {}
        if "lat" not in ds.coords and "lat" not in ds.dims:
            for alt in ("latitude", "y", "lat_1"):
                if alt in ds.coords or alt in ds.dims:
                    rename_map[alt] = "lat"
                    break
        if "lon" not in ds.coords and "lon" not in ds.dims:
            for alt in ("longitude", "x", "lon_1"):
                if alt in ds.coords or alt in ds.dims:
                    rename_map[alt] = "lon"
                    break

        prepared = ds.rename(rename_map) if rename_map else ds
        da = prepared[var_name]

        # Remove sentinelas inválidas (-9999 / -999 / valores não finitos) típicas de HDF/NetCDF reais
        da = da.where(np.isfinite(da) & (da > -900.0) & (da < 1e20))

        # Normaliza longitudes 0..360 para -180..180 quando necessário
        if "lon" in da.coords and float(da["lon"].max()) > 180.0:
            da = da.assign_coords(lon=(((da["lon"] + 180.0) % 360.0) - 180.0)).sortby(
                "lon"
            )
        if "lat" in da.coords and len(da["lat"]) > 1 and bool(da["lat"][0] > da["lat"][-1]):
            da = da.sortby("lat")

        # Harmoniza eixos espaciais transpostos (ex.: GPM IMERG vem como (time, lon, lat))
        if "lat" in da.dims and "lon" in da.dims:
            non_spatial = [dim for dim in da.dims if dim not in ("lat", "lon")]
            expected_order = (*non_spatial, "lat", "lon")
            if tuple(da.dims) != expected_order:
                da = da.transpose(*expected_order)

        clean_ds = xr.Dataset({var_name: da})
        clean_ds.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
        clean_ds.rio.write_crs("EPSG:4326", inplace=True)
        return clean_ds, var_name

    @staticmethod
    def _series_by_date(serie: xr.DataArray, fallback_date: str) -> dict[str, float]:
        if "time" in serie.dims or "time" in serie.coords:
            times = np.atleast_1d(serie["time"].values)
            vals = np.atleast_1d(serie.values)
            return {
                str(pd.Timestamp(t).date()): float(v)
                for t, v in zip(times, vals)
                if not np.isnan(v)
            }
        return {fallback_date: float(serie.mean().item())}

    def _fetch_nasa_power_series(
        self,
        center_lat: float,
        center_lng: float,
        end_dt: date,
    ) -> list[dict[str, Any]] | None:
        """
        Consulta a API pública oficial NASA POWER (sem necessidade de login/token)
        e armazena cache local em `{data_path}/power_cache/`.
        Retorna até `self.days_back` observações diárias válidas.
        """
        lookback = max(self.days_back + 7, 12)
        start_dt = end_dt - timedelta(days=lookback)
        cache_dir = os.path.join(self.data_path, "power_cache")
        cache_name = (
            f"power_{center_lat:.2f}_{center_lng:.2f}_"
            f"{start_dt.strftime('%Y%m%d')}_{end_dt.strftime('%Y%m%d')}.json"
        )
        cache_path = os.path.join(cache_dir, cache_name)

        payload: dict[str, Any] | None = None
        if os.path.exists(cache_path):
            try:
                with open(cache_path, encoding="utf-8") as fp:
                    payload = json.load(fp)
            except Exception:
                payload = None

        if payload is None:
            params = {
                "parameters": "GWETTOP,TS,PRECTOTCORR",
                "community": "AG",
                "longitude": round(center_lng, 4),
                "latitude": round(center_lat, 4),
                "start": start_dt.strftime("%Y%m%d"),
                "end": end_dt.strftime("%Y%m%d"),
                "format": "JSON",
            }
            try:
                resp = httpx.get(self.POWER_API_URL, params=params, timeout=10.0)
                resp.raise_for_status()
                payload = resp.json()
                os.makedirs(cache_dir, exist_ok=True)
                with open(cache_path, "w", encoding="utf-8") as fp:
                    json.dump(payload, fp)
            except Exception as exc:
                logger.warning("Falha ao consultar API NASA POWER: %s", exc)
                return None

        params_data = (
            (payload or {}).get("properties", {}).get("parameter", {})
        )
        gwettop = params_data.get("GWETTOP") or {}
        ts_map = params_data.get("TS") or {}
        precip_map = params_data.get("PRECTOTCORR") or {}

        all_dates = sorted(set(gwettop) & set(ts_map) & set(precip_map))
        valid_points: list[dict[str, Any]] = []
        for raw_d in all_dates:
            m_val = float(gwettop[raw_d])
            t_val = float(ts_map[raw_d])
            p_val = float(precip_map[raw_d])
            if m_val <= -900.0 or t_val <= -900.0 or p_val <= -900.0:
                continue
            iso_date = (
                f"{raw_d[:4]}-{raw_d[4:6]}-{raw_d[6:8]}"
                if len(raw_d) == 8 and raw_d.isdigit()
                else str(raw_d)
            )
            valid_points.append(
                {
                    "data": iso_date,
                    # GWETTOP (0-1 índice de saturação superficial) convertido para m³/m³ (~0.02..0.50)
                    "soil_moisture": round(max(0.02, min(0.50, m_val * 0.50)), 4),
                    "surface_temp_c": round(t_val, 2),
                    "precipitation_mm": round(max(0.0, p_val), 2),
                }
            )

        if not valid_points:
            return None
        return valid_points[-self.days_back :]

    def extract_field_metrics(
        self, polygon_coords: Any, dataset: Any = None, profile: str | None = None
    ) -> dict[str, Any]:
        _ = profile
        norm_coords = _normalize_polygon_coords(polygon_coords)
        geom = _build_polygon_geometry(norm_coords)
        gdf = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[geom])
        minx, miny, maxx, maxy = geom.bounds
        bbox = (float(minx), float(miny), float(maxx), float(maxy))

        end_dt = datetime.now(timezone.utc).date()
        start_dt = end_dt - timedelta(days=self.days_back)
        temporal = (start_dt.isoformat(), end_dt.isoformat())

        local_sources = self._discover_local_real_sources() if dataset is None else {}

        ea = None
        authenticated = False
        if not isinstance(dataset, xr.Dataset):
            ea = self._load_earthaccess()
            if ea is not None:
                authenticated = self._authenticate(ea)

        series: dict[str, xr.DataArray | None] = {}
        qualities: dict[str, str] = {}

        for key, (short_name, candidates) in self.COLLECTIONS.items():
            ds, should_close = self._open_collection_dataset(
                key=key,
                short_name=short_name,
                bbox=bbox,
                temporal=temporal,
                dataset=dataset,
                ea=ea,
                authenticated=authenticated,
                local_sources=local_sources,
            )
            if ds is None:
                series[key] = None
                qualities[key] = "no_data"
                continue

            try:
                prepared, var_name = self._prepare_dataset(ds, candidates)
                if prepared is None or var_name is None:
                    series[key] = None
                    qualities[key] = "no_data"
                    continue

                serie, quality = MockNASADataProvider._reduce_spatial(
                    prepared, var_name, gdf, geom
                )
                if serie is None or bool(serie.isnull().all()):
                    series[key] = None
                    qualities[key] = "no_data"
                    continue

                loaded = serie.load()
                mean_val = float(loaded.mean(skipna=True).item())
                if key == "surface_temp":
                    if mean_val > 5000.0:
                        loaded = loaded * 0.02 - 273.15
                    elif mean_val > 150.0:
                        loaded = loaded - 273.15
                elif key == "ndvi" and abs(mean_val) > 2.0:
                    loaded = loaded * 0.0001

                series[key] = loaded
                qualities[key] = quality
            finally:
                if should_close:
                    ds.close()

        primary_qualities = [qualities[k] for k in self._PRIMARY_KEYS]
        has_missing_primary = "no_data" in primary_qualities
        all_primary_missing = all(q == "no_data" for q in primary_qualities)

        power_series: list[dict[str, Any]] | None = None
        if has_missing_primary and self.enable_nasa_power:
            c = geom.centroid
            power_series = self._fetch_nasa_power_series(
                center_lat=float(c.y),
                center_lng=float(c.x),
                end_dt=end_dt,
            )

        if all_primary_missing and not power_series:
            return {
                "coordinates": polygon_coords,
                "avg_soil_moisture_smap": 0.0,
                "avg_surface_temp_ecostress": 0.0,
                "avg_precipitation_gpm": 0.0,
                "is_bare_field_period": False,
                "data_quality": "no_data",
                "time_series": [],
            }

        def _mean(key: str, power_field: str) -> float:
            s = series.get(key)
            if s is not None:
                return float(s.mean(skipna=True).item())
            if power_series:
                return float(np.mean([pt[power_field] for pt in power_series]))
            return 0.0

        avg_moisture = _mean("soil_moisture", "soil_moisture")
        avg_temp = _mean("surface_temp", "surface_temp_c")
        avg_precip = _mean("precipitation", "precipitation_mm")

        if has_missing_primary:
            data_quality = "nearest_cell"
        elif "nearest_cell" in primary_qualities:
            data_quality = "nearest_cell"
        else:
            data_quality = "clip"

        time_series: list[dict[str, Any]] = []
        if all_primary_missing and power_series:
            time_series = power_series
        else:
            fallback_date = end_dt.isoformat()
            power_by_date = (
                {pt["data"]: pt for pt in power_series} if power_series else {}
            )
            m_map = (
                self._series_by_date(series["soil_moisture"], fallback_date)
                if series.get("soil_moisture") is not None
                else {d: pt["soil_moisture"] for d, pt in power_by_date.items()}
            )
            t_map = (
                self._series_by_date(series["surface_temp"], fallback_date)
                if series.get("surface_temp") is not None
                else {d: pt["surface_temp_c"] for d, pt in power_by_date.items()}
            )
            p_map = (
                self._series_by_date(series["precipitation"], fallback_date)
                if series.get("precipitation") is not None
                else {d: pt["precipitation_mm"] for d, pt in power_by_date.items()}
            )

            all_dates = sorted(set(m_map) | set(t_map) | set(p_map))
            for d_str in all_dates:
                time_series.append(
                    {
                        "data": d_str,
                        "soil_moisture": m_map.get(d_str, avg_moisture),
                        "surface_temp_c": t_map.get(d_str, avg_temp),
                        "precipitation_mm": p_map.get(d_str, avg_precip),
                    }
                )

        if series.get("ndvi") is not None:
            is_bare = float(series["ndvi"].mean(skipna=True).item()) < self.BARE_NDVI_MAX
        else:
            is_bare = (
                avg_moisture < self.BARE_MOISTURE_MAX
                and avg_temp >= self.BARE_TEMP_MIN_C
            )

        return {
            "coordinates": polygon_coords,
            "avg_soil_moisture_smap": avg_moisture,
            "avg_surface_temp_ecostress": avg_temp,
            "avg_precipitation_gpm": avg_precip,
            "is_bare_field_period": bool(is_bare),
            "data_quality": data_quality,
            "time_series": time_series,
        }


def get_nasa_data_provider(
    data_path: str = "data",
    provider_type: str | None = None,
    credentials: dict[str, Any] | None = None,
    profile: str | None = None,
    enable_nasa_power: bool | None = None,
) -> INASADataProvider:
    """Seleciona MockNASADataProvider (padrão) ou RealNASADataProvider via NASA_PROVIDER / profile='real'."""
    selected = (
        provider_type
        if provider_type is not None
        else os.getenv("NASA_PROVIDER", "mock")
    )
    selected_norm = str(selected).strip().lower()
    profile_norm = str(profile).strip().lower() if profile is not None else ""

    if selected_norm == "real" or profile_norm == "real":
        use_power = (
            enable_nasa_power
            if enable_nasa_power is not None
            else (True if profile_norm == "real" else None)
        )
        return RealNASADataProvider(
            credentials=credentials,
            data_path=data_path,
            enable_nasa_power=use_power,
        )
    return MockNASADataProvider(data_path=data_path, profile=profile)


create_nasa_provider = get_nasa_data_provider

# Alias de compatibilidade com chamadas legadas
NasaDataProcessor = MockNASADataProvider

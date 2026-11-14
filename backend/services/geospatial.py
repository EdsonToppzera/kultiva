import logging
import os
from abc import ABC, abstractmethod
from typing import Any

import geopandas as gpd
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


def _normalize_polygon_coords(polygon_coords: Any) -> list[tuple[float, float]]:
    """Normaliza coordenadas de entrada para pares (lon, lat) válidos no Brasil."""
    if not isinstance(polygon_coords, (list, tuple)) or not polygon_coords:
        return _DEFAULT_BRAZIL_POLYGON

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

    return points or _DEFAULT_BRAZIL_POLYGON


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
        self, polygon_coords: Any, dataset: Any = None
    ) -> dict[str, Any]:
        pass


class MockNASADataProvider(INASADataProvider):
    """Implementação temporária usando os NetCDFs sintéticos com clip espacial."""

    def __init__(self, data_path: str = "data"):
        self.data_path = data_path

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
        if not all(os.path.exists(p) for p in paths.values()):
            generate_synthetic_netcdf(self.data_path)

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


class RealNASADataProvider(INASADataProvider):
    """
    FUTURA IMPLEMENTAÇÃO REAL.
    Aqui entrará o earthaccess, download via API e xr.open_mfdataset.
    """

    def __init__(self, credentials: dict):
        self.credentials = credentials

    def extract_field_metrics(
        self, polygon_coords: Any, dataset: Any = None
    ) -> dict[str, Any]:
        _ = (polygon_coords, dataset)
        raise NotImplementedError(
            "A integração real com NASA Earthdata será implementada aqui."
        )


# Alias de compatibilidade com chamadas legadas
NasaDataProcessor = MockNASADataProvider

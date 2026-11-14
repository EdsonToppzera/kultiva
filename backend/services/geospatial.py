import logging
import os
from abc import ABC, abstractmethod
from typing import Any

import geopandas as gpd
import rioxarray  # noqa: F401 - registra o accessor .rio no xarray
import xarray as xr
from shapely.geometry import LineString, Point, Polygon

from backend.services.mock_nasa_data import generate_synthetic_netcdf

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

    def extract_field_metrics(
        self,
        polygon_coords: Any,
        dataset: Any = None,
    ) -> dict[str, Any]:
        _ = dataset
        norm_coords = _normalize_polygon_coords(polygon_coords)
        geom = _build_polygon_geometry(norm_coords)
        gdf = gpd.GeoDataFrame(index=[0], crs="EPSG:4326", geometry=[geom])

        smap_path = os.path.join(self.data_path, "smap_mock.nc")
        eco_path = os.path.join(self.data_path, "ecostress_mock.nc")

        if not (os.path.exists(smap_path) and os.path.exists(eco_path)):
            generate_synthetic_netcdf(self.data_path)

        avg_moisture = 0.0
        avg_temp = 0.0
        data_quality = "no_data"

        if os.path.exists(smap_path) and os.path.exists(eco_path):
            with xr.open_dataset(smap_path) as ds_smap, xr.open_dataset(eco_path) as ds_eco:
                ds_smap.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
                ds_smap.rio.write_crs("EPSG:4326", inplace=True)

                ds_eco.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)
                ds_eco.rio.write_crs("EPSG:4326", inplace=True)

                try:
                    clipped_smap = ds_smap.rio.clip(
                        gdf.geometry, gdf.crs, drop=True, all_touched=True
                    )
                    clipped_eco = ds_eco.rio.clip(
                        gdf.geometry, gdf.crs, drop=True, all_touched=True
                    )

                    avg_moisture = float(clipped_smap["soil_moisture"].mean().item())
                    avg_temp = float(clipped_eco["surface_temp"].mean().item())
                    data_quality = "clip"
                except Exception as exc:
                    # Polígono menor que a célula da grade (ou fora dela): usa a
                    # célula mais próxima do centroide em vez de devolver 0.0.
                    logger.info("Clip vazio/falhou (%s); usando célula mais próxima.", exc)
                    try:
                        c = geom.centroid
                        pt = {"lat": c.y, "lon": c.x}
                        avg_moisture = float(
                            ds_smap["soil_moisture"].sel(**pt, method="nearest").mean().item()
                        )
                        avg_temp = float(
                            ds_eco["surface_temp"].sel(**pt, method="nearest").mean().item()
                        )
                        data_quality = "nearest_cell"
                    except Exception as exc2:
                        logger.warning("Falha ao extrair métricas NASA mock: %s", exc2)
                        data_quality = "no_data"

        return {
            "coordinates": polygon_coords,
            "avg_soil_moisture_smap": avg_moisture,
            "avg_surface_temp_ecostress": avg_temp,
            "is_bare_field_period": False,
            "data_quality": data_quality,
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

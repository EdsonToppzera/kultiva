import os

import numpy as np
import pandas as pd
import xarray as xr

# Grade ~0.25° (~28 km) cobrindo o Brasil: pequenos polígonos ainda caem em
# pelo menos uma célula (o provider faz fallback "nearest" quando o clip é vazio).
_LATS = np.linspace(-34.0, 6.0, 161)
_LONS = np.linspace(-74.0, -34.0, 161)
_SEED = 42


def generate_synthetic_netcdf(output_dir: str = "data", force: bool = False) -> str:
    """
    Gera arquivos NetCDF mockados simulando dados da NASA (determinísticos, seed fixa).
    Não sobrescreve arquivos existentes, a menos que force=True.
    """
    os.makedirs(output_dir, exist_ok=True)
    smap_path = os.path.join(output_dir, "smap_mock.nc")
    eco_path = os.path.join(output_dir, "ecostress_mock.nc")

    if not force and os.path.exists(smap_path) and os.path.exists(eco_path):
        return "Dados sintéticos (NetCDF) já existentes em data/."

    rng = np.random.default_rng(_SEED)
    times = pd.date_range("2026-01-01", periods=5)
    shape = (len(times), len(_LATS), len(_LONS))

    # SMAP mock (umidade do solo, m³/m³)
    ds_smap = xr.Dataset(
        {"soil_moisture": (["time", "lat", "lon"], rng.random(shape) * 0.5)},
        coords={"time": times, "lat": _LATS, "lon": _LONS},
    )
    ds_smap.to_netcdf(smap_path)

    # ECOSTRESS mock (temperatura de superfície, °C, faixa realista 15–45)
    ds_eco = xr.Dataset(
        {"surface_temp": (["time", "lat", "lon"], 15.0 + rng.random(shape) * 30.0)},
        coords={"time": times, "lat": _LATS, "lon": _LONS},
    )
    ds_eco.to_netcdf(eco_path)

    return "Dados sintéticos (NetCDF) gerados com sucesso na pasta data/."


if __name__ == "__main__":
    print(generate_synthetic_netcdf(force=True))

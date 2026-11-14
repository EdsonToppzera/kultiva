import os

import numpy as np
import pandas as pd
import xarray as xr

# Grade ~0.25° (~28 km) cobrindo o Brasil: pequenos polígonos ainda caem em
# pelo menos uma célula (o provider faz fallback "nearest" quando o clip é vazio).
_LATS = np.linspace(-34.0, 6.0, 161)
_LONS = np.linspace(-74.0, -34.0, 161)
_SEED = 42

SMAP_FILE = "smap_mock.nc"
ECOSTRESS_FILE = "ecostress_mock.nc"
GPM_FILE = "gpm_mock.nc"
_ALL_FILES = (SMAP_FILE, ECOSTRESS_FILE, GPM_FILE)


def generate_synthetic_netcdf(output_dir: str = "data", force: bool = False) -> str:
    """
    Gera NetCDFs mockados (SMAP, ECOSTRESS e GPM/IMERG), determinísticos (seed fixa).
    Com padrão espacial grosseiro (mais chuva/umidade na faixa amazônica, mais calor
    ao norte) para que terrenos diferentes produzam métricas diferentes.
    Não sobrescreve arquivos existentes, a menos que force=True; se faltar algum
    dos arquivos (ex.: gpm_mock.nc em instalações antigas), regera todos.
    """
    os.makedirs(output_dir, exist_ok=True)
    paths = [os.path.join(output_dir, name) for name in _ALL_FILES]

    if not force and all(os.path.exists(p) for p in paths):
        return "Dados sintéticos (NetCDF) já existentes em data/."

    rng = np.random.default_rng(_SEED)
    times = pd.date_range("2026-01-01", periods=5)
    shape = (len(times), len(_LATS), len(_LONS))
    lat2d, _lon2d = np.meshgrid(_LATS, _LONS, indexing="ij")

    # Precipitação média diária (mm/dia): maior perto de -2° de latitude.
    precip_mean = 2.0 + 5.0 * np.exp(-(((lat2d + 2.0) / 10.0) ** 2))
    precip = rng.gamma(0.7, 1.0, shape) * (precip_mean / 0.7)[None, :, :]

    # SMAP (umidade do solo, m³/m³) correlacionada com a chuva média.
    moisture = 0.12 + 0.03 * precip_mean[None, :, :] + rng.normal(0.0, 0.04, shape)
    moisture = np.clip(moisture, 0.02, 0.5)

    # ECOSTRESS (temperatura de superfície, °C), mais quente ao norte.
    temp = 33.0 - 0.25 * np.abs(lat2d + 5.0)[None, :, :] + rng.normal(0.0, 2.5, shape)
    temp = np.clip(temp, 15.0, 45.0)

    coords = {"time": times, "lat": _LATS, "lon": _LONS}
    dims = ["time", "lat", "lon"]
    xr.Dataset({"soil_moisture": (dims, moisture)}, coords=coords).to_netcdf(paths[0])
    xr.Dataset({"surface_temp": (dims, temp)}, coords=coords).to_netcdf(paths[1])
    xr.Dataset(
        {"precipitation": (dims, precip)}, coords=coords
    ).to_netcdf(paths[2])

    return "Dados sintéticos (NetCDF) gerados com sucesso na pasta data/."


if __name__ == "__main__":
    print(generate_synthetic_netcdf(force=True))

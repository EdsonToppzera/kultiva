import os
import numpy as np
import pandas as pd
import xarray as xr


def generate_synthetic_netcdf(output_dir: str = "data") -> str:
    """Gera arquivos NetCDF mockados simulando dados da NASA."""
    os.makedirs(output_dir, exist_ok=True)
    # Grade sintética
    lats = np.linspace(-30.0, 5.0, 10)
    lons = np.linspace(-70.0, -35.0, 10)
    times = pd.date_range("2026-01-01", periods=5)

    # SMAP mock (umidade)
    smap_data = np.random.rand(5, 10, 10) * 0.5
    ds_smap = xr.Dataset(
        {"soil_moisture": (["time", "lat", "lon"], smap_data)},
        coords={"time": times, "lat": lats, "lon": lons},
    )
    ds_smap.to_netcdf(os.path.join(output_dir, "smap_mock.nc"))

    # ECOSTRESS mock (temperatura/estresse)
    eco_data = np.random.rand(5, 10, 10) * 40.0
    ds_eco = xr.Dataset(
        {"surface_temp": (["time", "lat", "lon"], eco_data)},
        coords={"time": times, "lat": lats, "lon": lons},
    )
    ds_eco.to_netcdf(os.path.join(output_dir, "ecostress_mock.nc"))

    return "Dados sintéticos (NetCDF) gerados com sucesso na pasta data/."


if __name__ == "__main__":
    print(generate_synthetic_netcdf())

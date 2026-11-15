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
_PROFILE_MARKER_FILE = ".climate_profile"

CLIMATE_PROFILES = ("normal", "seca", "chuva_extrema", "onda_de_calor")
_PROFILE_ALIASES = {
    "default": "normal",
    "padrao": "normal",
    "padrão": "normal",
    "chuva_intensa": "chuva_extrema",
    "calor": "onda_de_calor",
    "estiagem": "seca",
}


_REAL_PROFILE_ALIASES = {
    "real": "real",
    "nasa_real": "real",
    "earthdata": "real",
    "nasa_power": "real",
    "power": "real",
}


def normalize_climate_profile(
    profile: str | None = None,
    allow_real: bool = False,
) -> str:
    """Valida e normaliza o perfil climático simulável (parâmetro ou env NASA_MOCK_PROFILE)."""
    raw = profile if profile is not None else os.getenv("NASA_MOCK_PROFILE", "normal")
    key = str(raw or "normal").strip().lower().replace("-", "_").replace(" ", "_")
    if allow_real and key in _REAL_PROFILE_ALIASES:
        return "real"
    canonical = _PROFILE_ALIASES.get(key, key)
    if canonical not in CLIMATE_PROFILES:
        valid_options = (*CLIMATE_PROFILES, "real") if allow_real else CLIMATE_PROFILES
        validos = ", ".join(valid_options)
        raise ValueError(
            f"Perfil climático inválido '{raw}'. Opções válidas: {validos}."
        )
    return canonical


def _generate_profile_arrays(
    profile: str,
    rng: np.random.Generator,
    shape: tuple[int, int, int],
    lat2d: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Gera matrizes sintéticas (moisture, temp, precip) parametrizadas por perfil."""
    if profile == "seca":
        precip = np.clip(rng.gamma(0.5, 0.25, shape), 0.0, 1.0)
        moisture = np.clip(0.07 + rng.normal(0.0, 0.01, shape), 0.03, 0.10)
        temp = np.clip(33.8 + rng.normal(0.0, 0.3, shape), 33.2, 34.6)
        return moisture, temp, precip

    if profile == "chuva_extrema":
        precip_base = 85.0 + 15.0 * np.exp(-(((lat2d + 2.0) / 15.0) ** 2))
        precip = np.clip(
            precip_base[None, :, :] + rng.normal(0.0, 6.0, shape), 65.0, 140.0
        )
        moisture = np.clip(0.42 + rng.normal(0.0, 0.02, shape), 0.35, 0.49)
        temp = np.clip(24.5 + rng.normal(0.0, 1.0, shape), 20.0, 27.5)
        return moisture, temp, precip

    if profile == "onda_de_calor":
        precip = np.clip(rng.gamma(0.6, 0.8, shape), 0.2, 4.0)
        moisture = np.clip(0.18 + rng.normal(0.0, 0.015, shape), 0.16, 0.23)
        temp = np.clip(
            39.0 - 0.1 * np.abs(lat2d + 5.0)[None, :, :] + rng.normal(0.0, 1.2, shape),
            36.5,
            43.5,
        )
        return moisture, temp, precip

    # Perfil padrão ("normal"): equações originais determinísticas.
    precip_mean = 2.0 + 5.0 * np.exp(-(((lat2d + 2.0) / 10.0) ** 2))
    precip = rng.gamma(0.7, 1.0, shape) * (precip_mean / 0.7)[None, :, :]
    moisture = 0.12 + 0.03 * precip_mean[None, :, :] + rng.normal(0.0, 0.04, shape)
    moisture = np.clip(moisture, 0.02, 0.5)
    temp = 33.0 - 0.25 * np.abs(lat2d + 5.0)[None, :, :] + rng.normal(0.0, 2.5, shape)
    temp = np.clip(temp, 15.0, 45.0)
    return moisture, temp, precip


def generate_synthetic_netcdf(
    output_dir: str = "data",
    force: bool = False,
    profile: str | None = None,
) -> str:
    """
    Gera NetCDFs mockados (SMAP, ECOSTRESS e GPM/IMERG), determinísticos (seed fixa).
    Suporta os perfis `normal`, `seca`, `chuva_extrema` e `onda_de_calor` (ou via
    `NASA_MOCK_PROFILE`), preservando idempotência quando o perfil ativo já foi gerado.
    """
    target_profile = normalize_climate_profile(profile)
    os.makedirs(output_dir, exist_ok=True)
    paths = [os.path.join(output_dir, name) for name in _ALL_FILES]
    marker_path = os.path.join(output_dir, _PROFILE_MARKER_FILE)

    if not force and all(os.path.exists(p) for p in paths):
        if os.path.exists(marker_path):
            with open(marker_path, encoding="utf-8") as fp:
                current_profile = fp.read().strip().lower()
        else:
            current_profile = "normal"
        if current_profile == target_profile:
            return "Dados sintéticos (NetCDF) já existentes em data/."

    rng = np.random.default_rng(_SEED)
    times = pd.date_range("2026-01-01", periods=5)
    shape = (len(times), len(_LATS), len(_LONS))
    lat2d, _lon2d = np.meshgrid(_LATS, _LONS, indexing="ij")

    moisture, temp, precip = _generate_profile_arrays(
        target_profile, rng, shape, lat2d
    )

    coords = {"time": times, "lat": _LATS, "lon": _LONS}
    dims = ["time", "lat", "lon"]
    attrs = {"climate_profile": target_profile}
    xr.Dataset({"soil_moisture": (dims, moisture)}, coords=coords, attrs=attrs).to_netcdf(
        paths[0]
    )
    xr.Dataset({"surface_temp": (dims, temp)}, coords=coords, attrs=attrs).to_netcdf(
        paths[1]
    )
    xr.Dataset({"precipitation": (dims, precip)}, coords=coords, attrs=attrs).to_netcdf(
        paths[2]
    )
    with open(marker_path, "w", encoding="utf-8") as fp:
        fp.write(target_profile)

    return f"Dados sintéticos (NetCDF) gerados com sucesso para perfil '{target_profile}' na pasta data/."


if __name__ == "__main__":
    print(generate_synthetic_netcdf(force=True))

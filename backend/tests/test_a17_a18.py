from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import xarray as xr
from fastapi.testclient import TestClient

from backend.api import alertas as alertas_api
from backend.db.database import Base, get_db
from backend.main import app
from backend.schemas.simulacao import EstrategiaRotacaoSugerida
from backend.services import alert_tasks
from backend.services import geospatial as geospatial_mod
from backend.services.geospatial import RealNASADataProvider
from backend.services.llm_agent import (
    DISCLAIMER,
    RotationExplainerAgent,
    build_simulation_evidence,
    build_strategy_evidence,
)
from backend.services.ml_models import ClimateAnomalyDetector
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


POLIGONO_SP = [
    [-22.90, -47.06],
    [-22.90, -47.04],
    [-22.92, -47.04],
    [-22.92, -47.06],
]


def _make_baseline_power_payload(ref_date: date) -> dict:
    gwettop = {}
    ts = {}
    precip = {}
    for yr in range(ref_date.year - 5, ref_date.year):
        for offset in range(-5, 6):
            d = ref_date.replace(year=yr)
            d_ord = date.fromordinal(d.toordinal() + offset)
            key = d_ord.strftime("%Y%m%d")
            gwettop[key] = 0.60 + (offset % 3) * 0.02
            ts[key] = 25.0 + (offset % 3) * 0.5
            precip[key] = 3.0 + (offset % 4) * 0.5
    return {
        "properties": {
            "parameter": {
                "GWETTOP": gwettop,
                "TS": ts,
                "PRECTOTCORR": precip,
            }
        }
    }


def test_a17_real_provider_baseline_e_z_scores(tmp_path):
    today = date.today()
    current_payload = {
        "properties": {
            "parameter": {
                "GWETTOP": {today.strftime("%Y%m%d"): 0.24},
                "TS": {today.strftime("%Y%m%d"): 34.0},
                "PRECTOTCORR": {today.strftime("%Y%m%d"): 25.0},
            }
        }
    }
    baseline_payload = _make_baseline_power_payload(today)

    resp_cur = MagicMock()
    resp_cur.json.return_value = current_payload
    resp_cur.raise_for_status = MagicMock()

    resp_base = MagicMock()
    resp_base.json.return_value = baseline_payload
    resp_base.raise_for_status = MagicMock()

    with patch.object(
        geospatial_mod.httpx, "get", side_effect=[resp_cur, resp_base]
    ) as spy_get:
        prov = RealNASADataProvider(
            data_path=str(tmp_path),
            days_back=2,
            enable_nasa_power=True,
            enable_historical_baseline=True,
        )
        m1 = prov.extract_field_metrics(POLIGONO_SP)
        m2 = prov.extract_field_metrics(POLIGONO_SP)

    assert spy_get.call_count == 2  # cache em disco evita novas chamadas em m2
    assert "baseline_climatology" in m1
    assert "z_scores" in m1
    assert m1["z_scores"]["precipitation_mm"] > 2.0
    assert m1["z_scores"]["surface_temp_c"] > 2.0
    assert m1["z_scores"]["soil_moisture"] < -2.0
    assert m2["z_scores"] == m1["z_scores"]


def test_a17_climate_anomaly_detector_z_score_historico():
    detector = ClimateAnomalyDetector()
    baseline = {
        "precipitation_mm": {"mean": 4.0, "std": 5.0},
        "surface_temp_c": {"mean": 26.0, "std": 2.0},
        "soil_moisture": {"mean": 0.32, "std": 0.04},
    }

    # Chuva de 22 mm está abaixo do limiar absoluto (60 mm), mas z = +3.6 vs histórico
    res_chuva = detector.detect_extremes(
        [{"precipitation_mm": 22.0, "surface_temp_c": 26.0, "soil_moisture": 0.32}],
        baseline=baseline,
    )
    assert res_chuva["anomaly_detected"] is True
    assert res_chuva["tipo_evento"] == "chuva_intensa"
    assert res_chuva["detalhes"]["metodo"] == "z_score_historico"
    assert res_chuva["detalhes"]["z_scores"]["source"] == "historical_baseline"
    assert res_chuva["detalhes"]["z_scores"]["precipitation_mm"] == pytest.approx(3.6, abs=1e-2)

    # Umidade 0.21 está acima do limiar absoluto (0.15), mas z = -2.75 vs histórico
    res_seca = detector.detect_extremes(
        [{"precipitation_mm": 1.0, "surface_temp_c": 27.0, "soil_moisture": 0.21}],
        baseline=baseline,
    )
    assert res_seca["anomaly_detected"] is True
    assert res_seca["tipo_evento"] == "seca"
    assert res_seca["detalhes"]["metodo"] == "z_score_historico"
    assert res_seca["detalhes"]["z_scores"]["soil_moisture"] == pytest.approx(-2.75, abs=1e-2)


def test_a17_m5_propaga_z_scores_alertas():
    baseline = {
        "precipitation_mm": {"mean": 3.0, "std": 4.0},
        "surface_temp_c": {"mean": 25.0, "std": 2.0},
        "soil_moisture": {"mean": 0.30, "std": 0.05},
    }
    res = alertas_api._executar_detector_anomalias(
        [{"precipitation_mm": 18.0, "surface_temp_c": 25.0, "soil_moisture": 0.30}],
        baseline_climatology=baseline,
    )
    assert res is not None
    assert res["z_scores"]["precipitation_mm"] == pytest.approx(3.75, abs=1e-2)
    assert res["resultado_ml"]["tipo_evento"] == "chuva_intensa"

    avaliacao = alert_tasks._avaliar_anomalia_climatica(
        {
            "precipitation_mm": 18.0,
            "surface_temp_c": 25.0,
            "soil_moisture": 0.30,
            "baseline_climatology": baseline,
        }
    )
    assert avaliacao["anomaly_detected"] is True
    assert avaliacao["tipo_evento"] == "chuva_intensa"
    assert avaliacao["z_scores"]["precipitation_mm"] == pytest.approx(3.75, abs=1e-2)


def test_a18_srtm_e_hls_offline_sem_valores_falsos(tmp_path):
    prov = RealNASADataProvider(
        data_path=str(tmp_path),
        enable_nasa_power=False,
    )
    with patch.object(prov, "_load_earthaccess", return_value=None):
        metrics = prov.extract_field_metrics(POLIGONO_SP)

    assert metrics["data_quality"] == "no_data"
    assert "srtm" not in metrics
    assert "hls" not in metrics


def test_a18_srtm_e_hls_locais_extraidos_corretamente(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir(parents=True, exist_ok=True)

    lats = np.array([-22.93, -22.91, -22.89], dtype=float)
    lons = np.array([-47.07, -47.05, -47.03], dtype=float)

    ds_srtm = xr.Dataset(
        {"elevation": (("lat", "lon"), np.full((3, 3), 642.5, dtype=float))},
        coords={"lat": lats, "lon": lons},
    )
    ds_srtm.to_netcdf(real_dir / "srtm_30m_sp.nc")

    ds_hls = xr.Dataset(
        {"ndvi": (("lat", "lon"), np.full((3, 3), 0.18, dtype=float))},
        coords={"lat": lats, "lon": lons},
    )
    ds_hls.to_netcdf(real_dir / "hlsl30_sp.nc")

    # Precipitação local para não cair em all_primary_missing
    ds_rain = xr.Dataset(
        {"precipitation": (("lat", "lon"), np.full((3, 3), 8.5, dtype=float))},
        coords={"lat": lats, "lon": lons},
    )
    ds_rain.to_netcdf(real_dir / "gpm_sp.nc")

    prov = RealNASADataProvider(data_path=str(tmp_path), enable_nasa_power=False)
    with patch.object(prov, "_load_earthaccess", return_value=None):
        metrics = prov.extract_field_metrics(POLIGONO_SP)

    assert metrics["srtm"]["elevation_m"] == pytest.approx(642.5, abs=1e-2)
    assert metrics["srtm"]["resolution_m"] == 30
    assert metrics["hls"]["ndvi_mean"] == pytest.approx(0.18, abs=1e-3)
    assert metrics["hls"]["is_bare_soil"] is True
    assert metrics["is_bare_field_period"] is True


def test_a18_rotation_explainer_structured_e_endpoint_simulacao():
    field_metrics = {
        "avg_soil_moisture_smap": 0.28,
        "avg_surface_temp_ecostress": 27.5,
        "avg_precipitation_gpm": 5.2,
        "z_scores": {
            "soil_moisture": -0.4,
            "surface_temp_c": 0.8,
            "precipitation_mm": 0.3,
            "source": "historical_baseline",
        },
        "srtm": {"elevation_m": 640.0, "resolution_m": 30},
        "hls": {"ndvi_mean": 0.45, "resolution_m": 30},
    }
    strategies = [
        EstrategiaRotacaoSugerida(
            strategy="Milho + Braquiária",
            viability=0.84,
            water_risk="low",
            benefits="Cobertura e retenção de umidade",
            score_breakdown={
                "water_fit": 0.88,
                "heat_fit": 0.81,
                "ecocrop_comfort": 0.90,
                "agrofit_pests_count": 3,
                "agrofit_pests_sample": ["Spodoptera frugiperda"],
            },
        )
    ]

    agent = RotationExplainerAgent()
    structured = agent.explain_strategies_structured(
        strategies=strategies,
        field_metrics=field_metrics,
        farmer_priorities={"agua": "escassa"},
    )
    assert len(structured) == 1
    assert DISCLAIMER in structured[0]["explicacao"]
    ev = structured[0]["evidencias"]
    assert ev["viability_pct"] == pytest.approx(84.0)
    assert ev["score_breakdown"]["ecocrop_comfort"] == pytest.approx(0.9)
    assert ev["agrofit"]["pests_count"] == 3
    assert ev["srtm"]["elevation_m"] == pytest.approx(640.0)
    assert ev["hls"]["ndvi_mean"] == pytest.approx(0.45)
    assert ev["z_scores"]["source"] == "historical_baseline"

    sim_ev = build_simulation_evidence(field_metrics, strategies)
    assert sim_ev["clima"]["soil_moisture"] == pytest.approx(0.28)
    assert sim_ev["srtm"]["elevation_m"] == pytest.approx(640.0)
    assert len(sim_ev["estrategias"]) == 1

    # Teste integrado na rota /api/v1/simulacao/
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/simulacoes/",
                json={
                    "nome_propriedade": "Sítio Evidência",
                    "coordenadas_poligono": [
                        {"lat": p[0], "lng": p[1]} for p in POLIGONO_SP
                    ],
                    "prioridades": {"agua": "escassa"},
                    "nome_cultura": "Milho",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert DISCLAIMER in body["explicacao_ia"]
        assert body["evidencias_estruturadas"] is not None
        assert "clima" in body["evidencias_estruturadas"]
        assert len(body["rotacoes_sugeridas"]) >= 1
        assert body["rotacoes_sugeridas"][0]["evidencias_numericas"] is not None
        assert "viability_pct" in body["rotacoes_sugeridas"][0]["evidencias_numericas"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

from unittest.mock import MagicMock, patch

import pytest


def test_srtm_elevation_slope_cache_e_no_data(tmp_path):
    from backend.services import terrain_hazards

    provider = terrain_hazards.TerrainHazardsProvider(data_path=str(tmp_path / "cache"))
    coords = [
        {"lat": -15.800, "lng": -47.900},
        {"lat": -15.805, "lng": -47.900},
        {"lat": -15.805, "lng": -47.895},
    ]

    fake_resp = MagicMock()
    fake_resp.json.return_value = {"elevation": [1000.0, 1000.0, 1045.0, 1010.0]}
    fake_resp.raise_for_status = MagicMock()

    with patch.object(terrain_hazards.httpx, "get", return_value=fake_resp) as mock_get:
        res1 = provider.extract_srtm_elevation(coords)
        assert res1["data_quality"] == "srtm_api"
        assert res1["elevation_m"] == pytest.approx(1013.8, abs=0.2)
        assert res1["slope_pct"] > 5.0
        assert res1["erosion_risk"] in {"moderado", "alto"}
        assert mock_get.call_count == 1

        # Segunda chamada deve usar cache em disco sem chamar HTTP novamente
        res2 = provider.extract_srtm_elevation(coords)
        assert res2 == res1
        assert mock_get.call_count == 1

    # Sem fallback inventado quando a API falha (outro ponto fora do cache)
    with patch.object(terrain_hazards.httpx, "get", side_effect=RuntimeError("offline")):
        res_err = provider.extract_srtm_elevation([{"lat": -7.2, "lng": -35.8}])
        assert res_err["data_quality"] == "no_data"
        assert res_err["elevation_m"] is None


def test_nasa_firms_hotspots_sem_key_e_com_csv_mockado(monkeypatch, tmp_path):
    from backend.services import terrain_hazards

    monkeypatch.delenv("FIRMS_MAP_KEY", raising=False)
    coords = [
        {"lat": -12.00, "lng": -48.00},
        {"lat": -12.01, "lng": -48.00},
        {"lat": -12.01, "lng": -47.99},
    ]

    prov_sem_key = terrain_hazards.TerrainHazardsProvider(data_path=str(tmp_path / "c1"))
    res_sem_key = prov_sem_key.extract_firms_hotspots(coords)
    assert res_sem_key["data_quality"] == "missing_map_key"
    assert res_sem_key["hotspots_count"] is None

    prov_com_key = terrain_hazards.TerrainHazardsProvider(
        data_path=str(tmp_path / "c2"), firms_map_key="demo-key-123"
    )
    csv_body = (
        "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,confidence,version,bright_t31,frp,daynight\n"
        "-12.012,-48.002,332.1,0.4,0.4,2026-11-14,1730,N,VIIRS,h,2.0NRT,295.0,18.4,D\n"
        "-12.040,-48.030,320.5,0.4,0.4,2026-11-14,1730,N,VIIRS,n,2.0NRT,292.0,7.2,D\n"
    )
    fake_resp = MagicMock()
    fake_resp.text = csv_body
    fake_resp.raise_for_status = MagicMock()

    with patch.object(terrain_hazards.httpx, "get", return_value=fake_resp) as mock_get:
        res = prov_com_key.extract_firms_hotspots(coords)
        assert res["data_quality"] == "nasa_firms_api"
        assert res["hotspots_count"] == 2
        assert res["nearest_fire_km"] <= 3.0
        assert res["max_frp_mw"] == pytest.approx(18.4)
        assert res["fire_risk"] == "alto"
        assert mock_get.call_count == 1


def test_simulacao_e_explainer_integram_srtm_e_firms(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from backend.api import simulacao
    from backend.db import models
    from backend.db.database import Base, get_db
    from backend.main import app
    from backend.services import geospatial as geospatial_mod
    from backend.services import terrain_hazards
    from backend.services.llm_agent import RotationExplainerAgent, build_simulation_evidence
    from backend.services.ml_models import CropSimulator

    monkeypatch.setenv("GAEZ_ENABLED", "false")
    monkeypatch.setenv("ECOCROP_ENABLED", "false")
    monkeypatch.setenv("AGROFIT_ENABLED", "false")
    monkeypatch.setenv("TERRAIN_HAZARDS_ENABLED", "true")

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

    with TestingSessionLocal() as db:
        db.add(models.Usuario(nome="Produtor SRTM", email="srtm@kultiva.local"))
        db.add(models.Cultura(nome="Milho", consumo_agua_mm=500.0, tempo_colheita_dias=90))
        db.commit()

    hazards_prov = terrain_hazards.TerrainHazardsProvider(
        data_path=str(tmp_path / "hazards"), firms_map_key="test-key"
    )
    mock_nasa = geospatial_mod.MockNASADataProvider(data_path=str(tmp_path / "nasa"))
    simulacao._SERVICE_CACHE.clear()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[simulacao.get_nasa_processor] = lambda: mock_nasa
    app.dependency_overrides[simulacao.get_crop_simulator] = lambda: CropSimulator()
    app.dependency_overrides[simulacao.get_rotation_explainer] = (
        lambda: RotationExplainerAgent()
    )
    app.dependency_overrides[simulacao.get_terrain_hazards_provider] = (
        lambda: hazards_prov
    )

    try:
        with patch.object(
            hazards_prov,
            "extract_terrain_and_hazards",
            return_value={
                "srtm": {
                    "origem": "srtm_open_meteo",
                    "data_quality": "srtm_api",
                    "elevation_m": 820.0,
                    "slope_pct": 8.4,
                    "erosion_risk": "moderado",
                },
                "firms": {
                    "origem": "nasa_firms",
                    "data_quality": "nasa_firms_api",
                    "hotspots_count": 1,
                    "nearest_fire_km": 2.1,
                    "max_frp_mw": 14.5,
                    "fire_risk": "alto",
                },
            },
        ):
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/simular-rotacao",
                    json={
                        "nome_propriedade": "Sítio Morro Alto",
                        "coordenadas_poligono": [
                            {"lat": -15.80, "lng": -47.90},
                            {"lat": -15.81, "lng": -47.90},
                            {"lat": -15.81, "lng": -47.89},
                        ],
                        "nome_cultura": "Milho",
                    },
                )
                assert resp.status_code == 200
                body = resp.json()
                assert body["metricas_geoespaciais"]["srtm"]["elevation_m"] == pytest.approx(820.0)
                assert body["metricas_geoespaciais"]["srtm"]["slope_pct"] == pytest.approx(8.4)
                assert body["metricas_geoespaciais"]["firms"]["hotspots_count"] == 1
                assert any("NASA FIRMS" in r for r in body["riscos_identificados"])
                assert body["evidencias_estruturadas"]["firms"]["fire_risk"] == "alto"

                ev = build_simulation_evidence(body["metricas_geoespaciais"], body["rotacoes_sugeridas"])
                assert ev["srtm"]["erosion_risk"] == "moderado"
                assert ev["firms"]["nearest_fire_km"] == pytest.approx(2.1)
    finally:
        simulacao._SERVICE_CACHE.clear()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

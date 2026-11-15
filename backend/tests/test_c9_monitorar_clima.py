from datetime import date, timedelta
from types import ModuleType
import sys
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db import models
from backend.db.database import Base, get_db
from backend.main import app


def test_c9_monitorar_clima_com_perfil_climatico_dispara_alerta_e_adapta_calendario(
    monkeypatch,
):
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

    with TestingSessionLocal() as db:
        db.add(models.Usuario(nome="Produtor C9", email="c9@kultiva.local"))
        db.commit()

    fake_geo_mod = ModuleType("backend.services.geospatial")
    fake_provider = MagicMock()
    fake_provider.extract_field_metrics.return_value = {
        "data_quality": "clip",
        "avg_soil_moisture_smap": 0.09,
        "avg_surface_temp_ecostress": 38.0,
        "avg_precipitation_gpm": 0.2,
        "time_series": [
            {
                "data": "2026-11-14",
                "soil_moisture": 0.09,
                "surface_temp_c": 38.0,
                "precipitation_mm": 0.2,
            }
        ],
    }
    fake_geo_mod.get_nasa_data_provider = MagicMock(return_value=fake_provider)
    monkeypatch.setitem(sys.modules, "backend.services.geospatial", fake_geo_mod)

    fake_ml_mod = ModuleType("backend.services.ml_models")
    fake_detector = MagicMock()
    fake_detector.detect_extremes.return_value = {
        "anomaly_detected": True,
        "tipo_evento": "seca",
        "severidade": "alta",
    }
    fake_ml_mod.ClimateAnomalyDetector = MagicMock(return_value=fake_detector)
    monkeypatch.setitem(sys.modules, "backend.services.ml_models", fake_ml_mod)

    fake_llm_mod = ModuleType("backend.services.llm_agent")
    fake_agent = MagicMock()
    fake_agent.explain_alert.return_value = (
        "Mantenha cobertura morta no solo. A decisão final é sempre sua."
    )
    fake_llm_mod.RotationExplainerAgent = MagicMock(return_value=fake_agent)
    monkeypatch.setitem(sys.modules, "backend.services.llm_agent", fake_llm_mod)

    try:
        with TestClient(app) as client:
            resp_t = client.post(
                "/api/v1/terrenos/",
                json={
                    "nome_propriedade": "Sítio Demo C9",
                    "usuario_id": 1,
                    "coordenadas_poligono": [
                        {"lat": -3.73, "lng": -38.52},
                        {"lat": -3.74, "lng": -38.53},
                        {"lat": -3.75, "lng": -38.51},
                    ],
                },
            )
            terreno_id = resp_t.json()["id"]

            amanha = (date.today() + timedelta(days=1)).isoformat()
            resp_act = client.post(
                "/api/v1/calendario/atividades",
                json={
                    "terreno_id": terreno_id,
                    "titulo": "Irrigação programada",
                    "tipo_atividade": "irrigacao",
                    "data_programada": amanha,
                    "prioridade": "media",
                },
            )
            irr_id = resp_act.json()["id"]

            resp_mon = client.post(
                "/api/v1/alertas/monitorar-clima",
                json={"terreno_id": terreno_id, "perfil_climatico": "seca"},
            )
            assert resp_mon.status_code == 202
            assert resp_mon.json()["perfil_climatico"] == "seca"
            fake_geo_mod.get_nasa_data_provider.assert_called_once_with(
                data_path="data", profile="seca"
            )

            alertas = client.get(
                "/api/v1/alertas/", params={"terreno_id": terreno_id}
            ).json()
            assert len(alertas) == 1
            assert alertas[0]["tipo_evento"] == "seca"
            assert "cobertura morta" in alertas[0]["orientacao_pratica"].lower()
            assert "decisão final" in alertas[0]["orientacao_pratica"].lower()

            irr_atualizada = client.get(
                f"/api/v1/calendario/atividades/{irr_id}"
            ).json()
            assert irr_atualizada["ajustada_por_alerta"] is True
            assert irr_atualizada["prioridade"] == "critica"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

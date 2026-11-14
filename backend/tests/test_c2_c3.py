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
from backend.services import alert_tasks


def _setup_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        usuario = models.Usuario(nome="Produtor C2", email="c2@kultiva.local")
        db.add(usuario)
        db.commit()
        db.refresh(usuario)

        t1 = models.Terreno(
            nome_propriedade="Terreno Norte (Seco)",
            usuario_id=usuario.id,
            coordenadas_poligono=[
                {"lat": -3.0, "lng": -40.0},
                {"lat": -3.1, "lng": -40.1},
                {"lat": -3.2, "lng": -40.0},
            ],
            prioridades={"agua": "escassa"},
        )
        t2 = models.Terreno(
            nome_propriedade="Terreno Sul (Normal)",
            usuario_id=usuario.id,
            coordenadas_poligono=[
                {"lat": -23.0, "lng": -47.0},
                {"lat": -23.1, "lng": -47.1},
                {"lat": -23.2, "lng": -47.0},
            ],
            prioridades={"agua": "normal"},
        )
        db.add_all([t1, t2])
        db.commit()
        db.refresh(t1)
        db.refresh(t2)
        return engine, TestingSessionLocal, t1.id, t2.id


def test_c2_monitoramento_por_terreno_e_somente_com_anomalia(monkeypatch):
    engine, TestingSessionLocal, t1_id, t2_id = _setup_db()
    try:
        fake_geo_mod = ModuleType("backend.services.geospatial")
        fake_provider = MagicMock()

        def fake_extract(polygon_coords, dataset=None):
            lat0 = polygon_coords[0]["lat"]
            if lat0 > -10:
                return {
                    "data_quality": "clip",
                    "avg_soil_moisture_smap": 0.10,
                    "avg_surface_temp_ecostress": 38.5,
                    "avg_precipitation_gpm": 0.5,
                    "time_series": [
                        {"data": "2026-11-14", "soil_moisture": 0.10, "surface_temp_c": 38.5, "precipitation_mm": 0.5}
                    ],
                }
            return {
                "data_quality": "clip",
                "avg_soil_moisture_smap": 0.35,
                "avg_surface_temp_ecostress": 25.0,
                "avg_precipitation_gpm": 5.0,
                "time_series": [
                    {"data": "2026-11-14", "soil_moisture": 0.35, "surface_temp_c": 25.0, "precipitation_mm": 5.0}
                ],
            }

        fake_provider.extract_field_metrics.side_effect = fake_extract
        fake_geo_mod.MockNASADataProvider = MagicMock(return_value=fake_provider)
        monkeypatch.setitem(sys.modules, "backend.services.geospatial", fake_geo_mod)

        fake_ml_mod = ModuleType("backend.services.ml_models")
        fake_detector = MagicMock()

        def fake_detect(data):
            ponto = data[0] if isinstance(data, list) else data
            if ponto["surface_temp_c"] >= 35.0:
                return {
                    "anomaly_detected": True,
                    "tipo_evento": "onda_de_calor",
                    "severidade": "alta",
                }
            return {
                "anomaly_detected": False,
                "tipo_evento": "nenhum",
                "severidade": "baixa",
            }

        fake_detector.detect_extremes.side_effect = fake_detect
        fake_ml_mod.ClimateAnomalyDetector = MagicMock(return_value=fake_detector)
        monkeypatch.setitem(sys.modules, "backend.services.ml_models", fake_ml_mod)

        ids = alert_tasks.executar_ciclo_monitoramento_alertas(
            session_factory=TestingSessionLocal,
        )
        assert len(ids) == 1
        assert fake_provider.extract_field_metrics.call_count == 2

        with TestingSessionLocal() as db:
            alertas = db.query(models.AlertaClimatico).all()
            assert len(alertas) == 1
            assert alertas[0].terreno_id == t1_id
            assert alertas[0].tipo_evento == "onda_de_calor"
            assert t2_id not in [a.terreno_id for a in alertas]
    finally:
        Base.metadata.drop_all(bind=engine)


def test_c3_deduplicacao_dois_ciclos_e_gatilho_e_intervalo_env(monkeypatch):
    engine, TestingSessionLocal, t1_id, _ = _setup_db()
    try:
        fake_geo_mod = ModuleType("backend.services.geospatial")
        fake_provider = MagicMock()
        fake_provider.extract_field_metrics.return_value = {
            "data_quality": "clip",
            "avg_soil_moisture_smap": 0.12,
            "avg_surface_temp_ecostress": 39.0,
            "avg_precipitation_gpm": 0.0,
            "time_series": [
                {"data": "2026-11-14", "soil_moisture": 0.12, "surface_temp_c": 39.0, "precipitation_mm": 0.0}
            ],
        }
        fake_geo_mod.MockNASADataProvider = MagicMock(return_value=fake_provider)
        monkeypatch.setitem(sys.modules, "backend.services.geospatial", fake_geo_mod)

        fake_ml_mod = ModuleType("backend.services.ml_models")
        fake_detector = MagicMock()
        fake_detector.detect_extremes.return_value = {
            "anomaly_detected": True,
            "tipo_evento": "onda_de_calor",
            "severidade": "alta",
        }
        fake_ml_mod.ClimateAnomalyDetector = MagicMock(return_value=fake_detector)
        monkeypatch.setitem(sys.modules, "backend.services.ml_models", fake_ml_mod)

        # Dois ciclos seguidos não duplicam
        ciclo_1 = alert_tasks.executar_ciclo_monitoramento_alertas(
            terreno_id=t1_id, session_factory=TestingSessionLocal
        )
        ciclo_2 = alert_tasks.executar_ciclo_monitoramento_alertas(
            terreno_id=t1_id, session_factory=TestingSessionLocal
        )
        assert len(ciclo_1) == 1
        assert len(ciclo_2) == 0

        # Intervalo por env e deduplicação no POST /alertas/gatilho
        monkeypatch.setenv("ALERT_MONITOR_INTERVAL_HOURS", "12")
        assert alert_tasks.obter_intervalo_monitoramento_horas() == 12

        def override_get_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as client:
            resp_mon = client.post("/api/v1/alertas/monitorar", json={"terreno_id": t1_id})
            assert resp_mon.status_code == 202
            assert resp_mon.json()["intervalo_horas"] == 12

            amanha = (date.today() + timedelta(days=1)).isoformat()
            resp_dup = client.post(
                "/api/v1/alertas/gatilho",
                json={
                    "terreno_id": t1_id,
                    "tipo_evento": "onda_de_calor",
                    "severidade": "alta",
                    "data_evento": amanha,
                },
            )
            assert resp_dup.status_code == 202
            assert resp_dup.json()["status"] == "deduplicated"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

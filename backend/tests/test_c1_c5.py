from types import ModuleType
import sys
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import simulacao
from backend.db import models
from backend.db.database import Base, get_db
from backend.main import app


def _setup_sqlite_client():
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
        db.add(models.Usuario(nome="Produtor C1", email="c1@kultiva.local"))
        db.add(models.Cultura(nome="Milho", consumo_agua_mm=500.0, tempo_colheita_dias=90))
        db.commit()
    return engine


def test_c1_cache_instancia_unica_e_respeita_sys_modules(monkeypatch):
    simulacao._SERVICE_CACHE.clear()

    mod_a = ModuleType("backend.services.ml_models")
    mod_a.CropSimulator = MagicMock(side_effect=lambda: MagicMock(name="sim_a"))
    monkeypatch.setitem(sys.modules, "backend.services.ml_models", mod_a)

    inst_1 = simulacao.get_crop_simulator()
    inst_2 = simulacao.get_crop_simulator()
    assert inst_1 is inst_2
    assert mod_a.CropSimulator.call_count == 1

    mod_b = ModuleType("backend.services.ml_models")
    mod_b.CropSimulator = MagicMock(side_effect=lambda: MagicMock(name="sim_b"))
    monkeypatch.setitem(sys.modules, "backend.services.ml_models", mod_b)

    inst_3 = simulacao.get_crop_simulator()
    assert inst_3 is not inst_1
    assert mod_b.CropSimulator.call_count == 1
    simulacao._SERVICE_CACHE.clear()


def test_c1_resposta_indica_origem_e_fallback(monkeypatch):
    engine = _setup_sqlite_client()
    try:
        app.dependency_overrides[simulacao.get_nasa_processor] = lambda: None
        app.dependency_overrides[simulacao.get_crop_simulator] = lambda: None
        app.dependency_overrides[simulacao.get_rotation_explainer] = lambda: None

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/simulacoes/",
                json={"nome_propriedade": "Sítio Fallback", "nome_cultura": "Milho"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["fallback_usado"] is True
            assert body["origem"] == "fallback"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

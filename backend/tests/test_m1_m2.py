import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db import models
from backend.db.database import Base, get_db
from backend.main import app


@pytest.fixture()
def client_e_db():
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
        usuario = models.Usuario(nome="Produtor M1", email="m1@kultiva.local")
        cultura = models.Cultura(
            nome="Milho",
            consumo_agua_mm=500.0,
            tempo_colheita_dias=90,
            resistencia_pragas="Média",
        )
        db.add_all([usuario, cultura])
        db.commit()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def test_criar_e_listar_terrenos(client_e_db: TestClient):
    payload = {
        "nome_propriedade": "Fazenda Esperança",
        "usuario_id": 1,
        "coordenadas_poligono": [
            {"lat": -3.73, "lng": -38.52},
            {"lat": -3.74, "lng": -38.53},
            {"lat": -3.75, "lng": -38.51},
        ],
        "area_hectares": 4.5,
        "localizacao_central": {"lat": -3.74, "lng": -38.52},
        "prioridades": {"agua": "escassa", "foco_mercado": "local"},
    }
    resp = client_e_db.post("/api/v1/terrenos/", json=payload)
    assert resp.status_code == 200
    terreno = resp.json()
    assert terreno["id"] == 1
    assert terreno["area_hectares"] == 4.5

    lista = client_e_db.get("/api/v1/terrenos/", params={"usuario_id": 1})
    assert lista.status_code == 200
    assert len(lista.json()) == 1

    detalhe = client_e_db.get("/api/v1/terrenos/1")
    assert detalhe.status_code == 200
    assert detalhe.json()["nome_propriedade"] == "Fazenda Esperança"

    inexistente = client_e_db.get("/api/v1/terrenos/999")
    assert inexistente.status_code == 404


def test_validacoes_terreno(client_e_db: TestClient):
    resp_usuario = client_e_db.post(
        "/api/v1/terrenos/",
        json={
            "nome_propriedade": "Sem Dono",
            "usuario_id": 999,
            "coordenadas_poligono": [
                {"lat": -3.73, "lng": -38.52},
                {"lat": -3.74, "lng": -38.53},
                {"lat": -3.75, "lng": -38.51},
            ],
        },
    )
    assert resp_usuario.status_code == 404

    resp_poligono = client_e_db.post(
        "/api/v1/terrenos/",
        json={
            "nome_propriedade": "Polígono Inválido",
            "usuario_id": 1,
            "coordenadas_poligono": [
                {"lat": -3.73, "lng": -38.52},
                {"lat": -3.74, "lng": -38.53},
            ],
        },
    )
    assert resp_poligono.status_code == 422


def test_catalogo_culturas(client_e_db: TestClient):
    lista = client_e_db.get("/api/v1/culturas/")
    assert lista.status_code == 200
    assert len(lista.json()) == 1
    assert lista.json()[0]["nome"] == "Milho"

    nova = client_e_db.post(
        "/api/v1/culturas/",
        json={
            "nome": "Feijão Macáçar",
            "consumo_agua_mm": 300.0,
            "tempo_colheita_dias": 70,
            "resistencia_pragas": "Alta",
        },
    )
    assert nova.status_code == 200
    assert nova.json()["nome"] == "Feijão Macáçar"

    duplicada = client_e_db.post(
        "/api/v1/culturas/",
        json={
            "nome": "feijão macáçar",
            "consumo_agua_mm": 300.0,
            "tempo_colheita_dias": 70,
        },
    )
    assert duplicada.status_code == 400

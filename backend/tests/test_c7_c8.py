from datetime import date, timedelta
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


def _setup_sqlite():
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
        db.add(models.Usuario(nome="Produtor C7C8", email="c7c8@kultiva.local"))
        db.add(models.Cultura(nome="Milho", consumo_agua_mm=500.0, tempo_colheita_dias=90))
        db.add(models.Cultura(nome="Feijão Macáçar", consumo_agua_mm=300.0, tempo_colheita_dias=70))
        db.commit()
    return engine


def test_c7_historico_cultivos_e_atualizar_cronograma_por_estrategia():
    engine = _setup_sqlite()
    try:
        app.dependency_overrides[simulacao.get_nasa_processor] = lambda: None
        app.dependency_overrides[simulacao.get_crop_simulator] = lambda: None
        app.dependency_overrides[simulacao.get_rotation_explainer] = lambda: None

        with TestClient(app) as client:
            resp_terreno = client.post(
                "/api/v1/terrenos/",
                json={
                    "nome_propriedade": "Sítio C7",
                    "usuario_id": 1,
                    "coordenadas_poligono": [
                        {"lat": -3.73, "lng": -38.52},
                        {"lat": -3.74, "lng": -38.53},
                        {"lat": -3.75, "lng": -38.51},
                    ],
                },
            )
            assert resp_terreno.status_code == 200
            terreno_id = resp_terreno.json()["id"]

            resp_sem_hist = client.post(
                "/api/v1/simulacoes/",
                json={"terreno_id": terreno_id, "nome_cultura": "Milho"},
            )
            resp_com_hist = client.post(
                "/api/v1/simulacoes/",
                json={
                    "terreno_id": terreno_id,
                    "nome_cultura": "Milho",
                    "historico_cultivos": ["Milho", "Milho"],
                },
            )
            assert resp_sem_hist.status_code == 200
            assert resp_com_hist.status_code == 200

            viab_sem = resp_sem_hist.json()["rotacoes_sugeridas"][0]["viability"]
            viab_com = resp_com_hist.json()["rotacoes_sugeridas"][0]["viability"]
            assert viab_com < viab_sem  # Penaliza monocultura de Milho

            # Gera cronograma inicial e depois substitui pela estratégia escolhida
            inicio = date(2026, 11, 20)
            resp_cal_1 = client.post(
                "/api/v1/calendario/gerar-de-simulacao",
                json={
                    "terreno_id": terreno_id,
                    "data_inicio": inicio.isoformat(),
                    "estrategia_rotacao": "Milho -> Feijão Macáçar",
                },
            )
            assert resp_cal_1.status_code == 201
            assert len(resp_cal_1.json()) == 10

            resp_cal_2 = client.post(
                "/api/v1/calendario/gerar-de-simulacao",
                json={
                    "terreno_id": terreno_id,
                    "data_inicio": inicio.isoformat(),
                    "estrategia_rotacao": "Sorgo -> Feijão Macáçar",
                    "substituir_pendentes": True,
                },
            )
            assert resp_cal_2.status_code == 201
            atividades = client.get(
                "/api/v1/calendario/atividades", params={"terreno_id": terreno_id}
            ).json()
            assert len(atividades) == 10
            assert "Sorgo" in atividades[0]["titulo"]
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_c8_orientacao_pratica_explain_alert_e_resumo_nao_lidos(monkeypatch):
    engine = _setup_sqlite()
    try:
        fake_llm_mod = ModuleType("backend.services.llm_agent")
        fake_agent = MagicMock()
        fake_agent.explain_alert.return_value = (
            "Evite irrigar hoje e limpe as valas de drenagem. A decisão final é sempre sua."
        )
        fake_llm_mod.RotationExplainerAgent = MagicMock(return_value=fake_agent)
        monkeypatch.setitem(sys.modules, "backend.services.llm_agent", fake_llm_mod)

        with TestClient(app) as client:
            resp_t1 = client.post(
                "/api/v1/terrenos/",
                json={
                    "nome_propriedade": "Terreno Um",
                    "usuario_id": 1,
                    "coordenadas_poligono": [
                        {"lat": -3.73, "lng": -38.52},
                        {"lat": -3.74, "lng": -38.53},
                        {"lat": -3.75, "lng": -38.51},
                    ],
                },
            )
            t1_id = resp_t1.json()["id"]

            amanha = (date.today() + timedelta(days=1)).isoformat()
            resp_alerta = client.post(
                "/api/v1/alertas/gatilho",
                json={
                    "terreno_id": t1_id,
                    "tipo_evento": "chuva_intensa",
                    "severidade": "critica",
                    "data_evento": amanha,
                },
            )
            assert resp_alerta.status_code == 202
            alerta = resp_alerta.json()["alerta"]
            assert "drenagem" in alerta["orientacao_pratica"].lower()
            assert "decisão final" in alerta["orientacao_pratica"].lower()

            resumo_1 = client.get("/api/v1/alertas/resumo-nao-lidos").json()
            assert resumo_1["total_nao_lidos"] == 1
            assert resumo_1["por_terreno"][0]["terreno_id"] == t1_id
            assert resumo_1["por_terreno"][0]["criticos_nao_lidos"] == 1

            client.patch(f"/api/v1/alertas/{alerta['id']}/ler")
            resumo_2 = client.get("/api/v1/alertas/resumo-nao-lidos").json()
            assert resumo_2["total_nao_lidos"] == 0
            assert resumo_2["por_terreno"] == []
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

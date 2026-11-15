from datetime import date, timedelta
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db import models
from backend.db.database import Base, get_db
from backend.main import app
from backend.services.alert_tasks import aplicar_regras_ajuste_pos_alerta


def test_c4_fluxo_ponta_a_ponta_m1_m3_m4_e_ajuste_alerta():
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
        db.add(models.Usuario(nome="Produtor C4", email="c4@kultiva.local"))
        db.add(models.Cultura(nome="Milho", consumo_agua_mm=500.0, tempo_colheita_dias=90))
        db.add(models.Cultura(nome="Feijão Macáçar", consumo_agua_mm=300.0, tempo_colheita_dias=70))
        db.commit()

    try:
        with TestClient(app) as client:
            # 1. [M1] Criar terreno
            resp_terreno = client.post(
                "/api/v1/terrenos/",
                json={
                    "nome_propriedade": "Sítio Integração C4",
                    "usuario_id": 1,
                    "coordenadas_poligono": [
                        {"lat": -3.73, "lng": -38.52},
                        {"lat": -3.74, "lng": -38.53},
                        {"lat": -3.75, "lng": -38.51},
                    ],
                    "prioridades": {"agua": "escassa"},
                },
            )
            assert resp_terreno.status_code == 200
            terreno_id = resp_terreno.json()["id"]

            # 2. [M3] Simular rotação com múltiplas etapas
            resp_sim = client.post(
                "/api/v1/simulacoes/",
                json={
                    "terreno_id": terreno_id,
                    "nome_cultura": "Milho",
                    "culturas_rotacao": ["Feijão Macáçar"],
                },
            )
            assert resp_sim.status_code == 200
            plano_m3 = resp_sim.json()["plano_rotacao"]
            assert len(plano_m3) == 2

            # 3. [M4] Gerar calendário a partir do plano_rotacao do M3
            inicio = date(2026, 11, 15)
            resp_cal = client.post(
                "/api/v1/calendario/gerar-de-simulacao",
                json={
                    "terreno_id": terreno_id,
                    "data_inicio": inicio.isoformat(),
                    "plano_rotacao": plano_m3,
                },
            )
            assert resp_cal.status_code == 201
            atividades = resp_cal.json()
            assert len(atividades) == 10  # 5 atividades por etapa x 2 etapas
            assert atividades[0]["titulo"].startswith("[Etapa 1] Plantio de Milho")
            assert atividades[5]["titulo"].startswith("[Etapa 2] Plantio de Feijão Macáçar")
            assert atividades[5]["data_programada"] == (inicio + timedelta(days=91)).isoformat()

            # 4. [M5 -> M4] Disparar alerta de chuva intensa na data da irrigação inicial (inicio + 2 dias)
            data_alerta = (inicio + timedelta(days=2)).isoformat()
            resp_alerta = client.post(
                "/api/v1/alertas/gatilho",
                json={
                    "terreno_id": terreno_id,
                    "tipo_evento": "chuva_intensa",
                    "severidade": "alta",
                    "data_evento": data_alerta,
                    "dias_adiamento": 3,
                },
            )
            assert resp_alerta.status_code == 202

            irr_id = atividades[1]["id"]
            irr_atualizada = client.get(f"/api/v1/calendario/atividades/{irr_id}").json()
            assert irr_atualizada["ajustada_por_alerta"] is True
            assert irr_atualizada["data_programada"] == (inicio + timedelta(days=5)).isoformat()
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_c4_regras_ajuste_pos_alerta_unitarias():
    db_mock = MagicMock()
    data_ev = date(2026, 12, 1)

    alerta_calor = models.AlertaClimatico(
        id=10,
        terreno_id=1,
        tipo_evento="onda_de_calor",
        severidade="critica",
        titulo="Calor",
        mensagem="Calor extremo",
        data_evento=data_ev,
    )
    atv_irr = models.Activity(
        id=1,
        terreno_id=1,
        titulo="Irrigação",
        tipo_atividade="irrigacao",
        data_programada=data_ev,
        prioridade="media",
        concluida=False,
    )
    ajustadas, criadas = aplicar_regras_ajuste_pos_alerta(
        db=db_mock,
        alerta=alerta_calor,
        atividades_pendentes=[atv_irr],
        dias_adiamento=2,
    )
    assert ajustadas == 1
    assert criadas == 1
    assert atv_irr.prioridade == "critica"
    assert atv_irr.ajustada_por_alerta is True
    db_mock.add.assert_called_once()

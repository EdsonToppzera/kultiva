import asyncio
from datetime import date, timedelta
from types import ModuleType
import sys
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import simulacao as simulacao_api
from backend.db import models
from backend.db.database import Base, get_db
from backend.main import app
from backend.services import alert_tasks


@pytest.fixture()
def client_e_db(monkeypatch):
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
    monkeypatch.setattr(alert_tasks, "SessionLocal", TestingSessionLocal)

    with TestingSessionLocal() as db:
        usuario = models.Usuario(nome="Produtor Teste", email="produtor@kultiva.local")
        cultura = models.Cultura(
            nome="Milho",
            consumo_agua_mm=500.0,
            tempo_colheita_dias=110,
        )
        db.add_all([usuario, cultura])
        db.commit()

    with TestClient(app) as client:
        yield client, TestingSessionLocal

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def _criar_terreno(client: TestClient) -> int:
    resp = client.post(
        "/api/v1/terrenos/",
        json={
            "nome_propriedade": "Sítio Boa Vista",
            "usuario_id": 1,
            "coordenadas_poligono": [
                {"lat": -23.5505, "lng": -46.6333},
                {"lat": -23.5515, "lng": -46.6343},
                {"lat": -23.5525, "lng": -46.6323},
            ],
            "prioridades": {"agua": "escassa", "foco_mercado": "local"},
        },
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def test_m3_simulacao_com_fallback_e_rotacao(client_e_db):
    client, _ = client_e_db
    terreno_id = _criar_terreno(client)

    resp = client.post(
        "/api/v1/simulacoes/",
        json={
            "terreno_id": terreno_id,
            "nome_cultura": "Feijão Carioca",
            "culturas_rotacao": ["Milho", "Crotalária"],
            "dados_climaticos": {"precipitacao_mm": 480.0, "temperatura_media_c": 26.0},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["terreno_id"] == terreno_id
    assert body["cultura_principal"] == "Feijão Carioca"
    assert body["viability_score"] == 0.85
    assert body["water_risk"] == "low"
    assert body["metricas_geoespaciais"]["total_vertices_poligono"] == 3
    assert "decisão final" in body["explicacao_ia"]
    assert body["explicacao_textual"] == body["explicacao_ia"]
    assert len(body["rotacoes_sugeridas"]) == 3
    assert len(body["plano_rotacao"]) == 3
    assert body["plano_rotacao"][1]["cultura"] == "Milho"
    assert body["plano_rotacao"][1]["duracao_dias"] == 110


def test_m3_simular_rotacao_apenas_com_terreno_e_injecao_dependencias(client_e_db):
    client, _ = client_e_db
    terreno_id = _criar_terreno(client)

    mock_geo = MagicMock()
    mock_geo.extract_field_metrics.return_value = {
        "soil_moisture_smap": 0.33,
        "precipitation_gpm": 490.0,
    }

    mock_sim = MagicMock()
    mock_sim.simulate_rotation_strategies.return_value = [
        {"strategy": "Milho -> Soja (Atual)", "viability": 0.70, "water_risk": "high"},
        {"strategy": "Sorgo -> Feijão-caupi", "viability": 0.88, "water_risk": "low"},
        {"strategy": "Milheto -> Amendoim", "viability": 0.82, "water_risk": "medium"},
    ]
    mock_sim.predict_rotation_viability.return_value = {
        "viability_score": 0.88,
        "water_risk": "low",
    }

    mock_llm = MagicMock()
    mock_llm.generate_explanation.return_value = (
        "Sorgo -> Feijão-caupi otimiza o uso de água na propriedade."
    )

    app.dependency_overrides[simulacao_api.get_nasa_processor] = lambda: mock_geo
    app.dependency_overrides[simulacao_api.get_crop_simulator] = lambda: mock_sim
    app.dependency_overrides[simulacao_api.get_rotation_explainer] = lambda: mock_llm

    resp = client.post(
        "/api/v1/simular-rotacao",
        json={"terreno_id": terreno_id, "prioridades": {"water_conservation": True}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cultura_principal"] == "Sorgo -> Feijão-caupi"
    assert body["viability_score"] == 0.88
    assert body["metricas_geoespaciais"]["soil_moisture_smap"] == 0.33
    assert body["explicacao_textual"] == (
        "Sorgo -> Feijão-caupi otimiza o uso de água na propriedade."
    )
    assert len(body["rotacoes_sugeridas"]) == 3
    mock_geo.extract_field_metrics.assert_called_once()
    mock_sim.simulate_rotation_strategies.assert_called_once()
    mock_sim.predict_rotation_viability.assert_called_once()
    mock_llm.generate_explanation.assert_called_once()


def test_m3_simulacao_integra_servicos_ia_geospatial_ml(client_e_db, monkeypatch):
    client, _ = client_e_db
    terreno_id = _criar_terreno(client)

    fake_geo_mod = ModuleType("backend.services.geospatial")
    fake_geo_instance = MagicMock()
    fake_geo_instance.extract_field_metrics.return_value = {
        "ndvi_medio": 0.72,
        "umidade_smap": 0.39,
    }
    fake_geo_mod.NasaDataProcessor = MagicMock(return_value=fake_geo_instance)

    fake_ml_mod = ModuleType("backend.services.ml_models")
    fake_ml_instance = MagicMock()
    fake_ml_instance.simulate_rotation_strategies.return_value = [
        {"strategy": "Milho -> Feijão", "viability": 0.91, "water_risk": "medium"}
    ]
    fake_ml_instance.predict_rotation_viability.return_value = {
        "viability_score": 0.91,
        "water_risk": "medium",
    }
    fake_ml_mod.CropSimulator = MagicMock(return_value=fake_ml_instance)
    fake_ml_mod.ClimateAnomalyDetector = MagicMock()

    fake_llm_mod = ModuleType("backend.services.llm_agent")
    fake_llm_instance = MagicMock()
    fake_llm_msg = MagicMock()
    fake_llm_msg.content = "Explicação gerada pelo agente Gemini."
    fake_llm_instance.generate_explanation.return_value = fake_llm_msg
    fake_llm_mod.RotationExplainerAgent = MagicMock(return_value=fake_llm_instance)

    monkeypatch.setitem(sys.modules, "backend.services.geospatial", fake_geo_mod)
    monkeypatch.setitem(sys.modules, "backend.services.ml_models", fake_ml_mod)
    monkeypatch.setitem(sys.modules, "backend.services.llm_agent", fake_llm_mod)

    resp = client.post(
        "/api/v1/simulacoes/",
        json={"terreno_id": terreno_id, "cultura_id": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cultura_principal"] == "Milho"
    assert body["viability_score"] == 0.91
    assert body["water_risk"] == "medium"
    assert body["metricas_geoespaciais"]["ndvi_medio"] == 0.72
    assert body["explicacao_ia"] == "Explicação gerada pelo agente Gemini."
    assert body["explicacao_textual"] == "Explicação gerada pelo agente Gemini."
    fake_geo_instance.extract_field_metrics.assert_called_once()
    fake_ml_instance.predict_rotation_viability.assert_called_once()
    fake_llm_instance.generate_explanation.assert_called_once()


def test_m3_simulacao_validacoes_erro(client_e_db):
    client, _ = client_e_db
    terreno_id = _criar_terreno(client)

    resp_404_terreno = client.post(
        "/api/v1/simular-rotacao",
        json={"terreno_id": 999, "nome_cultura": "Milho"},
    )
    assert resp_404_terreno.status_code == 404

    resp_404_cultura = client.post(
        "/api/v1/simular-rotacao",
        json={"terreno_id": terreno_id, "cultura_id": 999},
    )
    assert resp_404_cultura.status_code == 404


def test_m3_simular_rotacao_direta_sem_terreno_no_banco(client_e_db):
    client, _ = client_e_db

    resp = client.post(
        "/api/v1/simular-rotacao",
        json={
            "nome_propriedade": "Área Teste Direto",
            "coordenadas_poligono": [
                {"lat": -23.5505, "lng": -46.6333},
                {"lat": -23.5515, "lng": -46.6343},
                {"lat": -23.5525, "lng": -46.6323},
            ],
            "prioridades": {"agua": "escassa", "water_conservation": True},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["terreno_id"] is None
    assert body["nome_propriedade"] == "Área Teste Direto"
    assert body["metricas_geoespaciais"]["total_vertices_poligono"] == 3
    assert len(body["rotacoes_sugeridas"]) == 3
    assert body["explicacao_textual"] == body["explicacao_ia"]


def test_m4_calendario_activity_status_e_filtro_periodo(client_e_db):
    client, _ = client_e_db
    terreno_id = _criar_terreno(client)
    inicio = date(2026, 11, 15)

    # Verifica alias Activity no módulo models
    assert models.Activity is models.AtividadeCalendario

    # Gerar cronograma inicial
    resp_cron = client.post(
        "/api/v1/calendario/gerar-cronograma",
        json={
            "terreno_id": terreno_id,
            "cultura_id": 1,
            "data_inicio": inicio.isoformat(),
        },
    )
    assert resp_cron.status_code == 201
    atividades = resp_cron.json()
    assert len(atividades) == 5
    assert atividades[0]["status"] == "pendente"
    assert atividades[-1]["data_programada"] == (inicio + timedelta(days=110)).isoformat()

    # Criar atividade vinculada ao usuário (sem terreno_id obrigatório)
    resp_user_act = client.post(
        "/api/v1/calendario/atividades",
        json={
            "usuario_id": 1,
            "titulo": "Revisar estoque de sementes",
            "tipo_atividade": "manejo",
            "data_programada": "2026-11-22",
            "prioridade": "media",
        },
    )
    assert resp_user_act.status_code == 201
    atividade_id = resp_user_act.json()["id"]
    assert resp_user_act.json()["status"] == "pendente"
    assert resp_user_act.json()["concluida"] is False

    # Atualizar status via PATCH /status para concluída
    resp_status = client.patch(
        f"/api/v1/calendario/atividades/{atividade_id}/status",
        json={"status": "concluida"},
    )
    assert resp_status.status_code == 200
    assert resp_status.json()["status"] == "concluida"
    assert resp_status.json()["concluida"] is True
    assert resp_status.json()["data_conclusao"] is not None

    # Leitura filtrada por período e status
    resp_periodo = client.get(
        "/api/v1/calendario/atividades",
        params={
            "usuario_id": 1,
            "status": "concluida",
            "data_inicio": "2026-11-20",
            "data_fim": "2026-11-25",
        },
    )
    assert resp_periodo.status_code == 200
    assert len(resp_periodo.json()) == 1
    assert resp_periodo.json()[0]["id"] == atividade_id

    # Voltar para pendente via PATCH /concluir
    resp_reabrir = client.patch(
        f"/api/v1/calendario/atividades/{atividade_id}/concluir",
        json={"concluida": False},
    )
    assert resp_reabrir.status_code == 200
    assert resp_reabrir.json()["status"] == "pendente"
    assert resp_reabrir.json()["concluida"] is False
    assert resp_reabrir.json()["data_conclusao"] is None

    # Atualizar via PUT
    resp_put = client.put(
        f"/api/v1/calendario/atividades/{atividade_id}",
        json={"prioridade": "alta", "status": "concluida"},
    )
    assert resp_put.status_code == 200
    assert resp_put.json()["prioridade"] == "alta"
    assert resp_put.json()["status"] == "concluida"
    assert resp_put.json()["concluida"] is True

    # Remover atividade
    resp_del = client.delete(f"/api/v1/calendario/atividades/{atividade_id}")
    assert resp_del.status_code == 204


def test_m5_alerta_chuva_intensa_adapta_calendario_em_background(client_e_db):
    client, _ = client_e_db
    terreno_id = _criar_terreno(client)

    resp_irr = client.post(
        "/api/v1/calendario/atividades",
        json={
            "terreno_id": terreno_id,
            "titulo": "Irrigação programada",
            "tipo_atividade": "irrigacao",
            "data_programada": "2026-11-20",
            "prioridade": "media",
        },
    )
    irr_id = resp_irr.json()["id"]

    resp_adub = client.post(
        "/api/v1/calendario/atividades",
        json={
            "terreno_id": terreno_id,
            "titulo": "Adubação foliar",
            "tipo_atividade": "adubacao",
            "data_programada": "2026-11-21",
            "prioridade": "media",
        },
    )
    adub_id = resp_adub.json()["id"]

    resp_conc = client.post(
        "/api/v1/calendario/atividades",
        json={
            "terreno_id": terreno_id,
            "titulo": "Irrigação anterior concluída",
            "tipo_atividade": "irrigacao",
            "data_programada": "2026-11-20",
            "prioridade": "media",
        },
    )
    conc_id = resp_conc.json()["id"]
    client.patch(
        f"/api/v1/calendario/atividades/{conc_id}/concluir",
        json={"concluida": True},
    )

    resp_gatilho = client.post(
        "/api/v1/alertas/gatilho",
        json={
            "terreno_id": terreno_id,
            "tipo_evento": "chuva_intensa",
            "severidade": "alta",
            "data_evento": "2026-11-20",
            "dias_adiamento": 3,
            "serie_temporal_clima": [{"data": "2026-11-20", "precipitacao_mm": 85.0}],
        },
    )
    assert resp_gatilho.status_code == 202
    alerta_id = resp_gatilho.json()["alerta"]["id"]

    resp_alerta = client.get(f"/api/v1/alertas/{alerta_id}")
    assert resp_alerta.status_code == 200
    alerta_data = resp_alerta.json()
    assert alerta_data["processado_background"] is True
    assert "2 atividade(s) ajustada(s)/adiada(s)" in alerta_data["resumo_adaptacao"]

    irr_atualizada = client.get(f"/api/v1/calendario/atividades/{irr_id}").json()
    assert irr_atualizada["data_programada"] == "2026-11-23"
    assert irr_atualizada["ajustada_por_alerta"] is True

    adub_atualizada = client.get(f"/api/v1/calendario/atividades/{adub_id}").json()
    assert adub_atualizada["data_programada"] == "2026-11-24"
    assert adub_atualizada["ajustada_por_alerta"] is True

    conc_atualizada = client.get(f"/api/v1/calendario/atividades/{conc_id}").json()
    assert conc_atualizada["data_programada"] == "2026-11-20"
    assert conc_atualizada["ajustada_por_alerta"] is False

    atividades = client.get(
        "/api/v1/calendario/atividades", params={"terreno_id": terreno_id}
    ).json()
    inspecoes = [
        a
        for a in atividades
        if a["tipo_atividade"] == "inspecao" and a["ajustada_por_alerta"]
    ]
    assert len(inspecoes) == 1
    assert inspecoes[0]["data_programada"] == "2026-11-21"


def test_m5_alerta_onda_de_calor_e_leitura(client_e_db):
    client, _ = client_e_db
    terreno_id = _criar_terreno(client)

    resp_irr = client.post(
        "/api/v1/calendario/atividades",
        json={
            "terreno_id": terreno_id,
            "titulo": "Irrigação regular",
            "tipo_atividade": "irrigacao",
            "data_programada": "2026-11-25",
            "prioridade": "media",
        },
    )
    irr_id = resp_irr.json()["id"]

    resp_gatilho = client.post(
        "/api/v1/alertas/gatilho",
        json={
            "terreno_id": terreno_id,
            "tipo_evento": "onda_de_calor",
            "severidade": "critica",
            "data_evento": "2026-11-25",
        },
    )
    assert resp_gatilho.status_code == 202
    alerta_id = resp_gatilho.json()["alerta"]["id"]

    irr_atualizada = client.get(f"/api/v1/calendario/atividades/{irr_id}").json()
    assert irr_atualizada["prioridade"] == "critica"
    assert irr_atualizada["ajustada_por_alerta"] is True

    atividades = client.get(
        "/api/v1/calendario/atividades", params={"terreno_id": terreno_id}
    ).json()
    emergenciais = [
        a
        for a in atividades
        if a["tipo_atividade"] == "irrigacao"
        and a["prioridade"] == "critica"
        and a["id"] != irr_id
    ]
    assert len(emergenciais) == 1

    resp_lido = client.patch(f"/api/v1/alertas/{alerta_id}/ler")
    assert resp_lido.status_code == 200
    assert resp_lido.json()["lido"] is True


def test_m5_monitoramento_periodico_gera_alerta_no_banco(client_e_db, monkeypatch):
    client, TestingSessionLocal = client_e_db
    terreno_id = _criar_terreno(client)

    # Verifica que o lifespan do FastAPI iniciou a task periódica em segundo plano
    assert hasattr(app.state, "alert_monitor_task")
    assert not app.state.alert_monitor_task.done()

    fake_ml_mod = ModuleType("backend.services.ml_models")
    fake_detector_instance = MagicMock()
    fake_detector_instance.detect_extremes.return_value = {
        "anomaly_detected": True,
        "tipo_evento": "chuva_intensa",
        "severidade": "critica",
    }
    fake_ml_mod.ClimateAnomalyDetector = MagicMock(return_value=fake_detector_instance)
    fake_ml_mod.CropSimulator = MagicMock()
    monkeypatch.setitem(sys.modules, "backend.services.ml_models", fake_ml_mod)

    resp_mon = client.post(
        "/api/v1/alertas/monitorar",
        json={"terreno_id": terreno_id, "intervalo_horas": 6},
    )
    assert resp_mon.status_code == 202
    assert resp_mon.json()["intervalo_horas"] == 6

    alertas = client.get("/api/v1/alertas/", params={"terreno_id": terreno_id}).json()
    assert len(alertas) == 1
    assert alertas[0]["tipo_evento"] == "chuva_intensa"
    assert alertas[0]["severidade"] == "critica"
    assert alertas[0]["origem_gatilho"] == "periodic_synthetic_monitor"
    assert alertas[0]["processado_background"] is True
    fake_detector_instance.detect_extremes.assert_called_once()

    # Valida também o agendador periódico assíncrono com 1 ciclo
    ids_ciclo = asyncio.run(
        alert_tasks.iniciar_monitoramento_periodico(
            intervalo_horas=12,
            max_ciclos=1,
            terreno_id=terreno_id,
            session_factory=TestingSessionLocal,
        )
    )
    assert len(ids_ciclo) == 1
    alertas_apos_ciclo = client.get(
        "/api/v1/alertas/", params={"terreno_id": terreno_id}
    ).json()
    assert len(alertas_apos_ciclo) == 2

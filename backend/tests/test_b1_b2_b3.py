from datetime import date, timedelta
import sys
from types import ModuleType
from unittest.mock import MagicMock

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import simulacao as simulacao_api
from backend.db import models
from backend.db.database import Base, get_db
from backend.main import app, seed_culturas
from backend.services import alert_tasks
from backend.services.ml_models import CropSimulator


def _criar_ambiente_teste(monkeypatch):
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
        db.add(models.Usuario(nome="Produtor Dev B", email="devb@kultiva.local"))
        db.add(
            models.Cultura(
                nome="Milho",
                consumo_agua_mm=500.0,
                tempo_colheita_dias=90,
                resistencia_pragas="Média",
                is_seed=True,
                customizada=False,
            )
        )
        db.add(
            models.Cultura(
                nome="Feijão Macáçar",
                consumo_agua_mm=300.0,
                tempo_colheita_dias=70,
                resistencia_pragas="Alta",
                is_seed=True,
                customizada=False,
            )
        )
        db.add(
            models.RotacaoProdutor(
                nome="Milho -> Soja",
                culturas=["Milho", "Soja"],
                preferencial=False,
                is_seed=True,
                beneficios="Base do sistema",
            )
        )
        db.commit()

    return engine, TestingSessionLocal


def _criar_terreno_exemplo(client: TestClient) -> int:
    resp = client.post(
        "/api/v1/terrenos/",
        json={
            "nome_propriedade": "Sítio Serra Verde",
            "usuario_id": 1,
            "coordenadas_poligono": [
                {"lat": -5.10, "lng": -39.20},
                {"lat": -5.11, "lng": -39.21},
                {"lat": -5.12, "lng": -39.19},
            ],
            "prioridades": {"agua": "escassa", "foco_mercado": "local"},
        },
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def test_b1_crud_culturas_protecao_seed_e_validacoes(monkeypatch):
    engine, TestingSessionLocal = _criar_ambiente_teste(monkeypatch)
    try:
        with TestClient(app) as client:
            # Culturas seed protegidas contra PUT e DELETE
            resp_put_seed = client.put(
                "/api/v1/culturas/1",
                json={"consumo_agua_mm": 120.0},
            )
            assert resp_put_seed.status_code == 403

            resp_del_seed = client.delete("/api/v1/culturas/1")
            assert resp_del_seed.status_code == 403

            # Validações de entrada inválidas (consumo <= 0 ou nome em branco)
            resp_invalido = client.post(
                "/api/v1/culturas/",
                json={
                    "nome": "   ",
                    "consumo_agua_mm": -10,
                    "tempo_colheita_dias": 0,
                },
            )
            assert resp_invalido.status_code == 422

            # Cadastro de cultura customizada
            resp_create = client.post(
                "/api/v1/culturas/",
                json={
                    "nome": "Gergelim",
                    "consumo_agua_mm": 280.0,
                    "tempo_colheita_dias": 95,
                    "resistencia_pragas": "Alta",
                    "usuario_id": 1,
                },
            )
            assert resp_create.status_code == 200
            cultura_custom = resp_create.json()
            assert cultura_custom["is_seed"] is False
            assert cultura_custom["customizada"] is True
            cultura_id = cultura_custom["id"]

            # Filtro por customizada=true retorna apenas a customizada
            resp_list = client.get("/api/v1/culturas/", params={"customizada": True})
            assert resp_list.status_code == 200
            assert [c["nome"] for c in resp_list.json()] == ["Gergelim"]

            # Atualização com conflito de nome retorna 400
            resp_conflito = client.put(
                f"/api/v1/culturas/{cultura_id}",
                json={"nome": "milho"},
            )
            assert resp_conflito.status_code == 400

            # Atualização válida
            resp_update = client.put(
                f"/api/v1/culturas/{cultura_id}",
                json={"nome": "Gergelim BRS", "consumo_agua_mm": 260.0},
            )
            assert resp_update.status_code == 200
            assert resp_update.json()["nome"] == "Gergelim BRS"
            assert resp_update.json()["consumo_agua_mm"] == 260.0

            # Vincula atividade no calendário antes de remover para testar limpeza de FK
            terreno_id = _criar_terreno_exemplo(client)
            resp_ativ = client.post(
                "/api/v1/calendario/atividades",
                json={
                    "terreno_id": terreno_id,
                    "cultura_id": cultura_id,
                    "titulo": "Plantio de Gergelim",
                    "tipo_atividade": "plantio",
                    "data_programada": "2026-11-20",
                },
            )
            assert resp_ativ.status_code == 201

            resp_delete = client.delete(f"/api/v1/culturas/{cultura_id}")
            assert resp_delete.status_code == 204
            assert client.get(f"/api/v1/culturas/{cultura_id}").status_code == 404
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_b1_seed_culturas_marca_is_seed_e_rotacoes_base(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    import backend.main as main_mod

    monkeypatch.setattr(main_mod, "SessionLocal", TestingSessionLocal)
    try:
        seed_culturas()
        with TestingSessionLocal() as db:
            culturas = db.query(models.Cultura).all()
            rotacoes = db.query(models.RotacaoProdutor).all()
            assert len(culturas) == 4
            assert all(c.is_seed is True and c.customizada is False for c in culturas)
            assert len(rotacoes) >= 3
            assert all(r.is_seed is True for r in rotacoes)
    finally:
        Base.metadata.drop_all(bind=engine)


def test_b1_crud_rotacoes_e_entrada_no_simulador(monkeypatch):
    engine, _ = _criar_ambiente_teste(monkeypatch)
    simulacao_api._SERVICE_CACHE.clear()
    try:
        # Contrato unitário direto no CropSimulator preservando 3 estratégias + (Atual)
        estrategias_sim = CropSimulator().simulate_rotation_strategies(
            {
                "avg_soil_moisture_smap": 0.14,
                "avg_surface_temp_ecostress": 34.0,
                "avg_precipitation_gpm": 1.5,
                "data_quality": "clip",
            },
            {
                "agua": "escassa",
                "rotacoes_preferenciais": [
                    {
                        "strategy": "Feijão Macáçar -> Gergelim",
                        "water_demand": 0.38,
                        "heat_tolerance": 0.88,
                        "soil_benefit": 0.82,
                        "market": 0.72,
                        "benefits": "Preferida do produtor",
                    }
                ],
            },
        )
        assert len(estrategias_sim) == 3
        assert any("(Atual)" in e["strategy"] for e in estrategias_sim)
        assert any("Feijão Macáçar -> Gergelim" == e["strategy"] for e in estrategias_sim)

        fake_geo_mod = ModuleType("backend.services.geospatial")
        fake_provider = MagicMock()
        fake_provider.extract_field_metrics.return_value = {
            "data_quality": "clip",
            "avg_soil_moisture_smap": 0.16,
            "avg_surface_temp_ecostress": 33.5,
            "avg_precipitation_gpm": 2.0,
            "is_bare_field_period": False,
            "time_series": [
                {
                    "data": "2026-11-10",
                    "soil_moisture": 0.16,
                    "surface_temp_c": 33.5,
                    "precipitation_mm": 2.0,
                }
            ],
        }
        fake_geo_mod.MockNASADataProvider = MagicMock(return_value=fake_provider)
        monkeypatch.setitem(sys.modules, "backend.services.geospatial", fake_geo_mod)

        with TestClient(app) as client:
            terreno_id = _criar_terreno_exemplo(client)

            # Seed de rotação protegida
            assert client.put("/api/v1/rotacoes/1", json={"preferencial": True}).status_code == 403
            assert client.delete("/api/v1/rotacoes/1").status_code == 403

            # Cria cultura customizada + rotação preferencial vinculada ao terreno
            client.post(
                "/api/v1/culturas/",
                json={
                    "nome": "Crotalária",
                    "consumo_agua_mm": 240.0,
                    "tempo_colheita_dias": 60,
                },
            )
            resp_rot = client.post(
                "/api/v1/rotacoes/",
                json={
                    "culturas": ["Feijão Macáçar", "Crotalária"],
                    "usuario_id": 1,
                    "terreno_id": terreno_id,
                    "preferencial": True,
                    "beneficios": "Rotação adaptada à seca local",
                },
            )
            assert resp_rot.status_code == 201
            rot = resp_rot.json()
            assert rot["nome"] == "Feijão Macáçar -> Crotalária"
            assert rot["is_seed"] is False

            # Atualiza rotação
            resp_put_rot = client.put(
                f"/api/v1/rotacoes/{rot['id']}",
                json={"beneficios": "Baixo consumo hídrico e cobertura de solo"},
            )
            assert resp_put_rot.status_code == 200
            assert "cobertura de solo" in resp_put_rot.json()["beneficios"]

            # Simulador considera a rotação preferencial cadastrada para o terreno
            app.dependency_overrides[simulacao_api.get_crop_simulator] = CropSimulator
            app.dependency_overrides[simulacao_api.get_rotation_explainer] = lambda: None
            resp_sim = client.post(
                "/api/v1/simular-rotacao",
                json={"terreno_id": terreno_id},
            )
            assert resp_sim.status_code == 200
            body_sim = resp_sim.json()
            estrategias = [item["strategy"] for item in body_sim["rotacoes_sugeridas"]]
            assert len(estrategias) == 3
            assert "Feijão Macáçar -> Crotalária" in estrategias

            # Remoção da rotação customizada
            assert client.delete(f"/api/v1/rotacoes/{rot['id']}").status_code == 204
            assert client.get(f"/api/v1/rotacoes/{rot['id']}").status_code == 404
    finally:
        simulacao_api._SERVICE_CACHE.clear()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_b3_migracao_alembic_cria_tabelas_e_colunas(tmp_path, monkeypatch):
    db_file = tmp_path / "alembic_test.db"
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")

    engine = create_engine(db_url)
    try:
        insp = inspect(engine)
        tabelas = set(insp.get_table_names())
        assert {
            "usuarios",
            "terrenos",
            "culturas",
            "atividades_calendario",
            "alertas_climaticos",
            "rotacoes_produtor",
            "metricas_historicas_terreno",
        } <= tabelas
        cols_cultura = {c["name"] for c in insp.get_columns("culturas")}
        assert {"is_seed", "customizada", "usuario_id"} <= cols_cultura
    finally:
        engine.dispose()

    # Cenário incremental: tabela culturas preexistente sem as colunas novas de B1
    db_legacy = tmp_path / "alembic_legacy.db"
    legacy_url = f"sqlite:///{db_legacy}"
    monkeypatch.setenv("DATABASE_URL", legacy_url)
    legacy_engine = create_engine(legacy_url)
    with legacy_engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nome VARCHAR, email VARCHAR, hashed_password VARCHAR)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE culturas (id INTEGER PRIMARY KEY, nome VARCHAR, consumo_agua_mm FLOAT, tempo_colheita_dias INTEGER, resistencia_pragas VARCHAR)"
            )
        )
    legacy_engine.dispose()

    cfg_legacy = Config("alembic.ini")
    cfg_legacy.set_main_option("sqlalchemy.url", legacy_url)
    command.upgrade(cfg_legacy, "head")

    legacy_check = create_engine(legacy_url)
    try:
        insp_leg = inspect(legacy_check)
        assert "metricas_historicas_terreno" in insp_leg.get_table_names()
        assert {"is_seed", "customizada", "usuario_id"} <= {
            c["name"] for c in insp_leg.get_columns("culturas")
        }
    finally:
        legacy_check.dispose()


def test_b3_e_b2_historico_metricas_e_relatorio_m6(monkeypatch):
    engine, TestingSessionLocal = _criar_ambiente_teste(monkeypatch)
    simulacao_api._SERVICE_CACHE.clear()
    try:
        hoje = date.today()
        d1 = (hoje - timedelta(days=3)).isoformat()
        d2 = (hoje - timedelta(days=2)).isoformat()
        d3 = (hoje - timedelta(days=1)).isoformat()

        fake_geo_mod = ModuleType("backend.services.geospatial")
        fake_provider = MagicMock()
        fake_provider.extract_field_metrics.return_value = {
            "data_quality": "clip",
            "avg_soil_moisture_smap": 0.14,
            "avg_surface_temp_ecostress": 34.0,
            "avg_precipitation_gpm": 1.2,
            "is_bare_field_period": False,
            "time_series": [
                {
                    "data": d1,
                    "soil_moisture": 0.18,
                    "surface_temp_c": 32.5,
                    "precipitation_mm": 2.0,
                },
                {
                    "data": d2,
                    "soil_moisture": 0.14,
                    "surface_temp_c": 34.0,
                    "precipitation_mm": 1.0,
                },
                {
                    "data": d3,
                    "soil_moisture": 0.10,
                    "surface_temp_c": 35.5,
                    "precipitation_mm": 0.5,
                },
            ],
        }
        fake_geo_mod.MockNASADataProvider = MagicMock(return_value=fake_provider)
        monkeypatch.setitem(sys.modules, "backend.services.geospatial", fake_geo_mod)

        with TestClient(app) as client:
            terreno_id = _criar_terreno_exemplo(client)

            # Cria atividade que será adaptada por alerta no período
            resp_ativ = client.post(
                "/api/v1/calendario/atividades",
                json={
                    "terreno_id": terreno_id,
                    "titulo": "Irrigação preventiva",
                    "tipo_atividade": "irrigacao",
                    "data_programada": hoje.isoformat(),
                    "prioridade": "media",
                },
            )
            assert resp_ativ.status_code == 201

            # Dispara alerta climático no período (gera adaptação ajustada_por_alerta=True)
            resp_alerta = client.post(
                "/api/v1/alertas/gatilho",
                json={
                    "terreno_id": terreno_id,
                    "tipo_evento": "onda_de_calor",
                    "severidade": "alta",
                    "data_evento": hoje.isoformat(),
                },
            )
            assert resp_alerta.status_code == 202

            # Primeiro GET relatório sem métricas gravadas ainda: extrai field_metrics sob demanda e persiste
            resp_rel_sob_demanda = client.get(
                f"/api/v1/relatorios/terreno/{terreno_id}",
                params={"data_inicio": d1, "data_fim": hoje.isoformat()},
            )
            assert resp_rel_sob_demanda.status_code == 200
            rel1 = resp_rel_sob_demanda.json()
            assert rel1["terreno_id"] == terreno_id
            assert rel1["origem_dados"] == "field_metrics_sob_demanda"
            assert rel1["resumo_climatico"]["total_medicoes"] == 3
            assert rel1["resumo_climatico"]["dias_solo_exposto"] == 1
            assert 0.0 <= rel1["vigor"]["indice"] <= 1.0
            assert rel1["vigor"]["tendencia"] == "queda"
            assert rel1["vulnerabilidade"]["nivel"] in {"media", "alta", "critica"}
            assert rel1["vulnerabilidade"]["total_alertas_periodo"] == 1
            assert rel1["adaptacoes"]["total_ajustadas_por_alerta"] >= 1
            assert rel1["adaptacoes"]["atividades_ajustadas"]

            # Segunda chamada no mesmo período usa o histórico persistido no banco
            resp_rel_persistido = client.get(
                "/api/v1/relatorios/",
                params={"terreno_id": terreno_id, "data_inicio": d1, "data_fim": hoje.isoformat()},
            )
            assert resp_rel_persistido.status_code == 200
            assert resp_rel_persistido.json()["origem_dados"] == "historico_persistido"

            # Upsert manual de métrica na data de hoje e consulta da série
            resp_post_m = client.post(
                f"/api/v1/relatorios/terreno/{terreno_id}/metricas",
                json={
                    "data_medicao": hoje.isoformat(),
                    "soil_moisture": 0.31,
                    "surface_temp_c": 26.5,
                    "precipitation_mm": 12.0,
                },
            )
            assert resp_post_m.status_code == 201

            resp_metricas = client.get(
                f"/api/v1/relatorios/terreno/{terreno_id}/metricas",
                params={"data_inicio": d1, "data_fim": hoje.isoformat()},
            )
            assert resp_metricas.status_code == 200
            assert len(resp_metricas.json()) == 4

            # Simulação também atualiza métricas históricas via upsert sem duplicar datas
            resp_sim = client.post(
                "/api/v1/simular-rotacao",
                json={"terreno_id": terreno_id, "nome_cultura": "Milho"},
            )
            assert resp_sim.status_code == 200
            resp_metricas_pos_sim = client.get(
                f"/api/v1/relatorios/terreno/{terreno_id}/metricas",
                params={"data_inicio": d1, "data_fim": hoje.isoformat()},
            )
            assert len(resp_metricas_pos_sim.json()) == 4

            # Ciclo de monitoramento [M5] também persiste métricas históricas por terreno
            fake_ml_mod = ModuleType("backend.services.ml_models")
            fake_detector = MagicMock()
            fake_detector.detect_extremes.return_value = {
                "anomaly_detected": False,
                "tipo_evento": "nenhum",
                "severidade": "baixa",
            }
            fake_ml_mod.ClimateAnomalyDetector = MagicMock(return_value=fake_detector)
            monkeypatch.setitem(sys.modules, "backend.services.ml_models", fake_ml_mod)
            fake_provider.extract_field_metrics.return_value = {
                "data_quality": "clip",
                "avg_soil_moisture_smap": 0.29,
                "avg_surface_temp_ecostress": 27.0,
                "avg_precipitation_gpm": 4.0,
                "time_series": [
                    {
                        "data": (hoje + timedelta(days=1)).isoformat(),
                        "soil_moisture": 0.29,
                        "surface_temp_c": 27.0,
                        "precipitation_mm": 4.0,
                    }
                ],
            }
            alert_tasks.executar_ciclo_monitoramento_alertas(
                terreno_id=terreno_id, session_factory=TestingSessionLocal
            )
            resp_metricas_pos_mon = client.get(
                f"/api/v1/relatorios/terreno/{terreno_id}/metricas",
                params={"data_inicio": d1, "data_fim": (hoje + timedelta(days=1)).isoformat()},
            )
            assert len(resp_metricas_pos_mon.json()) == 5

            # Validação de período invertido e terreno inexistente
            assert (
                client.get(
                    f"/api/v1/relatorios/terreno/{terreno_id}",
                    params={"data_inicio": hoje.isoformat(), "data_fim": d1},
                ).status_code
                == 400
            )
            assert client.get("/api/v1/relatorios/terreno/999").status_code == 404
    finally:
        simulacao_api._SERVICE_CACHE.clear()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

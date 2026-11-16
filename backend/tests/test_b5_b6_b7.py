from datetime import date, timedelta
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.main as main_mod
from backend.api import simulacao as simulacao_api
from backend.db import models
from backend.db.database import Base, get_db
from backend.main import app, seed_culturas, seed_usuario_padrao
from backend.services import alert_tasks
from backend.services.llm_agent import DISCLAIMER


def _criar_banco_sqlite(monkeypatch=None):
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
    if monkeypatch is not None:
        monkeypatch.setattr(main_mod, "engine", engine)
        monkeypatch.setattr(main_mod, "SessionLocal", TestingSessionLocal)
        monkeypatch.setattr(alert_tasks, "SessionLocal", TestingSessionLocal)
    return engine, TestingSessionLocal


def test_b5_cors_e_seed_usuario_padrao(monkeypatch):
    engine, TestingSessionLocal = _criar_banco_sqlite(monkeypatch)
    try:
        seed_culturas()
        # Chamada repetida não duplica o usuário nem as culturas seed
        seed_usuario_padrao()

        with TestingSessionLocal() as db:
            usuarios = db.query(models.Usuario).all()
            assert len(usuarios) == 1
            assert usuarios[0].email == "produtor@kultiva.agro"

        with TestClient(app) as client:
            resp_preflight = client.options(
                "/api/v1/terrenos/",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "POST",
                },
            )
            assert resp_preflight.status_code in (200, 204)
            assert (
                resp_preflight.headers.get("access-control-allow-origin")
                == "http://localhost:5173"
            )

            resp_get = client.get(
                "/health",
                headers={"Origin": "http://localhost:5173"},
            )
            assert resp_get.status_code == 200
            assert (
                resp_get.headers.get("access-control-allow-origin")
                == "http://localhost:5173"
            )
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_b5_crud_terrenos_com_calculo_automatico_de_geometria(monkeypatch):
    engine, TestingSessionLocal = _criar_banco_sqlite(monkeypatch)
    try:
        with TestingSessionLocal() as db:
            usuario = seed_usuario_padrao(db)
            usuario_id = usuario.id

        with TestClient(app) as client:
            poligono_inicial = [
                {"lat": -7.230, "lng": -35.880},
                {"lat": -7.235, "lng": -35.880},
                {"lat": -7.235, "lng": -35.875},
                {"lat": -7.230, "lng": -35.875},
            ]
            resp_create = client.post(
                "/api/v1/terrenos/",
                json={
                    "nome_propriedade": "Sítio Geometria Automática",
                    "usuario_id": usuario_id,
                    "coordenadas_poligono": poligono_inicial,
                    "prioridades": {"agua": "escassa"},
                },
            )
            assert resp_create.status_code == 200
            terreno = resp_create.json()
            terreno_id = terreno["id"]
            area_inicial = terreno["area_hectares"]
            centro_inicial = terreno["localizacao_central"]
            assert area_inicial is not None and area_inicial > 0
            assert centro_inicial is not None
            assert round(centro_inicial["lat"], 3) in (-7.232, -7.233)

            # Atualização parcial sem alterar polígono preserva área e centroide
            resp_parcial = client.put(
                f"/api/v1/terrenos/{terreno_id}",
                json={"prioridades": {"agua": "escassa", "foco_mercado": "organico"}},
            )
            assert resp_parcial.status_code == 200
            assert resp_parcial.json()["area_hectares"] == area_inicial
            assert resp_parcial.json()["prioridades"]["foco_mercado"] == "organico"

            # Rejeita usuario_id inexistente no PUT
            assert (
                client.put(
                    f"/api/v1/terrenos/{terreno_id}",
                    json={"usuario_id": 9999},
                ).status_code
                == 404
            )

            # Atualiza polígono dobrado em largura/altura sem enviar área/centroide: recalcula automaticamente
            poligono_maior = [
                {"lat": -7.230, "lng": -35.880},
                {"lat": -7.240, "lng": -35.880},
                {"lat": -7.240, "lng": -35.870},
                {"lat": -7.230, "lng": -35.870},
            ]
            resp_put = client.put(
                f"/api/v1/terrenos/{terreno_id}",
                json={
                    "nome_propriedade": "Sítio Expandido",
                    "coordenadas_poligono": poligono_maior,
                },
            )
            assert resp_put.status_code == 200
            atualizado = resp_put.json()
            assert atualizado["nome_propriedade"] == "Sítio Expandido"
            assert atualizado["area_hectares"] > area_inicial * 3
            assert atualizado["localizacao_central"] != centro_inicial

            # Vincula dados dependentes para garantir limpeza limpa no DELETE
            assert (
                client.post(
                    f"/api/v1/relatorios/terreno/{terreno_id}/metricas",
                    json={
                        "data_medicao": date.today().isoformat(),
                        "soil_moisture": 0.25,
                        "surface_temp_c": 28.0,
                        "precipitation_mm": 5.0,
                    },
                ).status_code
                == 201
            )
            assert (
                client.post(
                    "/api/v1/calendario/atividades",
                    json={
                        "terreno_id": terreno_id,
                        "titulo": "Preparo do solo",
                        "tipo_atividade": "manejo",
                        "data_programada": date.today().isoformat(),
                    },
                ).status_code
                == 201
            )

            resp_del = client.delete(f"/api/v1/terrenos/{terreno_id}")
            assert resp_del.status_code == 204
            assert client.get(f"/api/v1/terrenos/{terreno_id}").status_code == 404
            assert (
                client.put(
                    f"/api/v1/terrenos/{terreno_id}",
                    json={"nome_propriedade": "Inexistente"},
                ).status_code
                == 404
            )
            assert client.delete(f"/api/v1/terrenos/{terreno_id}").status_code == 404
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_b6_relatorio_com_comparativo_e_resumo_ia_e_fallback(monkeypatch):
    engine, TestingSessionLocal = _criar_banco_sqlite(monkeypatch)
    simulacao_api._SERVICE_CACHE.clear()
    try:
        with TestingSessionLocal() as db:
            usuario = seed_usuario_padrao(db)
            t_melhora = models.Terreno(
                nome_propriedade="Sítio Recuperação",
                usuario_id=usuario.id,
                coordenadas_poligono=[
                    {"lat": -7.23, "lng": -35.88},
                    {"lat": -7.24, "lng": -35.88},
                    {"lat": -7.24, "lng": -35.87},
                ],
                area_hectares=10.0,
                prioridades={"agua": "moderada"},
            )
            t_queda = models.Terreno(
                nome_propriedade="Sítio Estiagem",
                usuario_id=usuario.id,
                coordenadas_poligono=[
                    {"lat": -7.30, "lng": -35.90},
                    {"lat": -7.31, "lng": -35.90},
                    {"lat": -7.31, "lng": -35.89},
                ],
                area_hectares=10.0,
                prioridades={"agua": "escassa"},
            )
            db.add_all([t_melhora, t_queda])
            db.commit()
            db.refresh(t_melhora)
            db.refresh(t_queda)

            hoje = date.today()
            d_ini = hoje - timedelta(days=4)
            db.add_all(
                [
                    models.MetricaHistoricaTerreno(
                        terreno_id=t_melhora.id,
                        data_medicao=d_ini,
                        soil_moisture=0.14,
                        surface_temp_c=33.0,
                        precipitation_mm=1.0,
                    ),
                    models.MetricaHistoricaTerreno(
                        terreno_id=t_melhora.id,
                        data_medicao=hoje,
                        soil_moisture=0.28,
                        surface_temp_c=27.5,
                        precipitation_mm=18.0,
                    ),
                    models.MetricaHistoricaTerreno(
                        terreno_id=t_queda.id,
                        data_medicao=d_ini,
                        soil_moisture=0.30,
                        surface_temp_c=27.0,
                        precipitation_mm=10.0,
                    ),
                    models.MetricaHistoricaTerreno(
                        terreno_id=t_queda.id,
                        data_medicao=hoje,
                        soil_moisture=0.12,
                        surface_temp_c=35.5,
                        precipitation_mm=0.0,
                    ),
                ]
            )
            db.commit()
            id_melhora = t_melhora.id
            id_queda = t_queda.id

        with TestClient(app) as client:
            resp_melhora = client.get(
                f"/api/v1/relatorios/terreno/{id_melhora}",
                params={"data_inicio": d_ini.isoformat(), "data_fim": hoje.isoformat()},
            )
            assert resp_melhora.status_code == 200
            body_m = resp_melhora.json()
            assert body_m["comparativo_periodo"]["tendencia_geral"] == "melhora"
            assert body_m["comparativo_periodo"]["variacao_umidade"] > 0
            assert "decisão final" in body_m["resumo_ia"].lower()
            assert body_m["resumo_ia"] == body_m["explicacao_ia"]

            # Também garante consistência na rota de atalho por query string
            resp_query = client.get(
                "/api/v1/relatorios/",
                params={
                    "terreno_id": id_melhora,
                    "data_inicio": d_ini.isoformat(),
                    "data_fim": hoje.isoformat(),
                },
            )
            assert resp_query.status_code == 200
            assert resp_query.json()["comparativo_periodo"]["tendencia_geral"] == "melhora"

            # Testa fallback determinístico quando explain_report levanta exceção
            broken_agent = MagicMock()
            broken_agent.explain_report.side_effect = RuntimeError("LLM offline")
            app.dependency_overrides[simulacao_api.get_rotation_explainer] = (
                lambda: broken_agent
            )

            resp_queda = client.get(
                f"/api/v1/relatorios/terreno/{id_queda}",
                params={"data_inicio": d_ini.isoformat(), "data_fim": hoje.isoformat()},
            )
            assert resp_queda.status_code == 200
            body_q = resp_queda.json()
            assert body_q["comparativo_periodo"]["tendencia_geral"] == "queda"
            assert body_q["comparativo_periodo"]["variacao_umidade"] < 0
            assert DISCLAIMER in body_q["resumo_ia"]
            assert "Sítio Estiagem" in body_q["resumo_ia"]
            broken_agent.explain_report.assert_called_once()
    finally:
        simulacao_api._SERVICE_CACHE.clear()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_b7_demo_seed_idempotente_reset_e_integracao_relatorio(monkeypatch):
    engine, _TestingSessionLocal = _criar_banco_sqlite(monkeypatch)
    simulacao_api._SERVICE_CACHE.clear()
    try:
        with TestClient(app) as client:
            resp1 = client.post("/api/v1/demo/seed")
            assert resp1.status_code == 200
            body1 = resp1.json()
            assert body1["status"] == "ok"
            assert body1["reset_executado"] is False
            assert body1["idempotente"] is True
            assert len(body1["terrenos_ids"]) == 2
            assert body1["culturas_total"] >= 4
            assert body1["rotacoes_total"] >= 5
            assert body1["metricas_total"] == 10
            assert body1["atividades_total"] == 6
            assert body1["alertas_total"] == 2

            # Segunda chamada sem reset mantém exatamente os mesmos IDs e quantidades
            resp2 = client.post("/api/v1/demo/seed")
            assert resp2.status_code == 200
            body2 = resp2.json()
            assert body2["terrenos_ids"] == body1["terrenos_ids"]
            assert body2["metricas_total"] == body1["metricas_total"]
            assert body2["atividades_total"] == body1["atividades_total"]
            assert body2["alertas_total"] == body1["alertas_total"]

            # Terreno 1 (perfil A9 'seca') e Terreno 2 (perfil A9 'chuva_extrema')
            # respondem imediatamente no relatório [M6] com contrastes reais dos NetCDFs
            resp_rel_seca = client.get(
                f"/api/v1/relatorios/terreno/{body1['terrenos_ids'][0]}"
            )
            resp_rel_chuva = client.get(
                f"/api/v1/relatorios/terreno/{body1['terrenos_ids'][1]}"
            )
            assert resp_rel_seca.status_code == 200
            assert resp_rel_chuva.status_code == 200

            rel_seca = resp_rel_seca.json()
            rel_chuva = resp_rel_chuva.json()
            assert rel_seca["origem_dados"] == "historico_persistido"
            assert rel_seca["resumo_climatico"]["total_medicoes"] == 5
            assert rel_seca["resumo_climatico"]["umidade_media_solo"] < 0.12
            assert rel_seca["resumo_climatico"]["temperatura_media_c"] >= 33.0
            assert rel_seca["resumo_climatico"]["dias_solo_exposto"] >= 1
            assert rel_seca["adaptacoes"]["total_ajustadas_por_alerta"] >= 1
            assert rel_seca["comparativo_periodo"]["tendencia_geral"] in {
                "melhora",
                "queda",
                "estavel",
            }
            assert "decisão final" in rel_seca["resumo_ia"].lower()

            assert rel_chuva["resumo_climatico"]["total_medicoes"] == 5
            assert rel_chuva["resumo_climatico"]["umidade_media_solo"] > 0.30
            assert rel_chuva["resumo_climatico"]["precipitacao_total_mm"] > 250.0

            # Reset recria dados limpos mantendo consistência de quantidades
            resp_reset = client.post("/api/v1/demo/seed", params={"reset": "true"})
            assert resp_reset.status_code == 200
            body_reset = resp_reset.json()
            assert body_reset["reset_executado"] is True
            assert body_reset["idempotente"] is False
            assert body_reset["terrenos_ids"] == body1["terrenos_ids"]
            assert body_reset["metricas_total"] == 10
            assert body_reset["atividades_total"] == 6
            assert body_reset["alertas_total"] == 2
    finally:
        simulacao_api._SERVICE_CACHE.clear()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_sessao_dispositivo_isola_terrenos_e_api_health(monkeypatch):
    engine, _ = _criar_banco_sqlite(monkeypatch)
    try:
        with TestClient(app) as client:
            resp_health = client.get("/api/v1/health")
            assert resp_health.status_code == 200
            assert resp_health.json()["status"] == "ok"

            s1 = client.post(
                "/api/v1/usuarios/sessao",
                json={"device_id": "device-alpha-123456"},
            )
            s1_again = client.post(
                "/api/v1/usuarios/sessao",
                json={"device_id": "DEVICE-ALPHA-123456"},
            )
            s2 = client.post(
                "/api/v1/usuarios/sessao",
                json={"device_id": "device-beta-987654"},
            )
            assert s1.status_code == 200
            assert s1_again.status_code == 200
            assert s2.status_code == 200
            u1 = s1.json()["id"]
            u2 = s2.json()["id"]
            assert s1_again.json()["id"] == u1
            assert u1 != u2

            poligono = [
                {"lat": -7.23, "lng": -35.88},
                {"lat": -7.24, "lng": -35.88},
                {"lat": -7.24, "lng": -35.87},
            ]
            t1 = client.post(
                "/api/v1/terrenos/",
                json={
                    "nome_propriedade": "Roçado Alpha",
                    "usuario_id": u1,
                    "coordenadas_poligono": poligono,
                },
            )
            t2 = client.post(
                "/api/v1/terrenos/",
                json={
                    "nome_propriedade": "Roçado Beta",
                    "usuario_id": u2,
                    "coordenadas_poligono": poligono,
                },
            )
            assert t1.status_code == 200
            assert t2.status_code == 200

            lista_u1 = client.get("/api/v1/terrenos/", params={"usuario_id": u1}).json()
            lista_u2 = client.get("/api/v1/terrenos/", params={"usuario_id": u2}).json()
            assert [item["nome_propriedade"] for item in lista_u1] == ["Roçado Alpha"]
            assert [item["nome_propriedade"] for item in lista_u2] == ["Roçado Beta"]
            assert (
                client.get(
                    f"/api/v1/terrenos/{t2.json()['id']}",
                    params={"usuario_id": u1},
                ).status_code
                == 404
            )
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

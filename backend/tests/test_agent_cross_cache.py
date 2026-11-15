from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from langchain_core.language_models.fake import FakeListLLM
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.api import simulacao as simulacao_api
from backend.db.database import Base, get_db
from backend.main import app
from backend.services.llm_agent import (
    AlertExplanationStructured,
    DISCLAIMER,
    RotationExplainerAgent,
    StrategyExplanationItem,
    StrategyExplanationsBatch,
    build_simulation_evidence,
    build_strategy_evidence,
    synthesize_cross_insights,
)


def _sample_field_metrics() -> dict:
    return {
        "avg_soil_moisture_smap": 0.19,
        "avg_surface_temp_ecostress": 35.5,
        "avg_precipitation_gpm": 12.0,
        "is_bare_field_period": True,
        "z_scores": {
            "surface_temp_c": 1.85,
            "soil_moisture": -1.75,
            "precipitation_mm": 1.9,
        },
        "gaez": {
            "data_quality": "gaez_v5_cog",
            "input_level": "LRLM",
            "soil": {
                "soil_group": "Arenosols - AR (Neossolos Quartzarênicos)",
                "limiting_factor": "Disponibilidade/retenção natural de nutrientes (SQ2)",
                "slope_range_pct": "12 - 16%",
                "erosion_risk": "alto",
            },
        },
        "ecocrop": {
            "data_quality": "ecocrop_csv",
            "crops": {
                "Milho": {
                    "scientific_name": "Zea mays",
                    "topmin": 18.0,
                    "topmax": 32.0,
                    "tmin": 10.0,
                    "tmax": 40.0,
                    "ropmin": 600.0,
                    "ropmax": 1200.0,
                },
                "Sorgo": {
                    "scientific_name": "Sorghum bicolor",
                    "topmin": 22.0,
                    "topmax": 36.0,
                    "tmin": 12.0,
                    "tmax": 42.0,
                    "ropmin": 400.0,
                    "ropmax": 900.0,
                },
            },
        },
    }


def test_synthesize_cross_insights_cruza_hwsd_ecocrop_cmip6_zscore_agrofit():
    fm = _sample_field_metrics()
    strategy = {
        "strategy": "Milho -> Feijão-caupi",
        "viability": 0.78,
        "water_risk": "medium",
        "benefits": "Quebra ciclo e fixa nitrogênio",
        "score_breakdown": {
            "soil_benefit": 0.85,
            "cmip6_suitability_delta": -0.06,
            "agrofit_pests_count": 4,
            "phytosanitary_triggers": ["heat_stress"],
            "same_family_as_history": False,
        },
    }

    cross = synthesize_cross_insights(strategy=strategy, field_metrics=fm)
    texto_unido = " ".join(
        cross["pontos_positivos"] + cross["alertas_manejo"] + cross["acoes_praticas"]
    ).lower()

    assert "lixiviação" in texto_unido or "parcel" in texto_unido
    assert "erosão" in texto_unido
    assert "ecocrop" in texto_unido
    assert "cmip6" in texto_unido
    assert "agrofit" in texto_unido or "vistoria" in texto_unido
    assert "cobrir rápido" in texto_unido

    ev = build_strategy_evidence(strategy, fm)
    assert "insights_cruzados" in ev
    assert ev["insights_cruzados"]["alertas_manejo"]

    sim_ev = build_simulation_evidence(fm, [strategy])
    assert "insights_cruzados" in sim_ev


def test_structured_output_and_cache_economiza_chamadas(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    structured_batch = StrategyExplanationsBatch(
        estrategias=[
            StrategyExplanationItem(
                estrategia="Sorgo -> Feijão-caupi",
                resumo="Sorgo -> Feijão-caupi aguenta bem o calor atual do terreno.",
                acao_pratica="Mantenha palhada na entrelinha para segurar umidade.",
            ),
            StrategyExplanationItem(
                estrategia="Milho -> Soja (Atual)",
                resumo="Milho -> Soja (Atual) sofre mais se faltar chuva nesta janela.",
                acao_pratica="Observe a previsão antes de adubar em cobertura.",
            ),
        ]
    )
    structured_alert = AlertExplanationStructured(
        diagnostico_simples="Chuva intensa prevista sobre área inclinada.",
        acoes_imediatas=["Limpe as valas de drenagem", "Adie adubação de cobertura"],
    )

    strat_runnable = MagicMock()
    strat_runnable.invoke.return_value = structured_batch
    alert_runnable = MagicMock()
    alert_runnable.invoke.return_value = structured_alert

    class _FakeStructuredLLM:
        def __call__(self, *_args, **_kwargs):
            return ""

        def with_structured_output(self, schema):
            if schema is StrategyExplanationsBatch:
                return lambda _inp: strat_runnable.invoke(_inp)
            if schema is AlertExplanationStructured:
                return lambda _inp: alert_runnable.invoke(_inp)
            raise ValueError("Schema inesperado")

    agent = RotationExplainerAgent(llm=_FakeStructuredLLM())
    strategies = [
        {"strategy": "Sorgo -> Feijão-caupi", "viability": 0.84, "water_risk": "low"},
        {"strategy": "Milho -> Soja (Atual)", "viability": 0.52, "water_risk": "high"},
    ]
    fm = _sample_field_metrics()

    out1 = agent.explain_strategies(strategies, field_metrics=fm)
    out2 = agent.explain_strategies(strategies, field_metrics=fm)

    assert len(out1) == 2
    assert "Na prática: Mantenha palhada" in out1[0]
    assert out1[0].endswith(DISCLAIMER)
    assert out1 == out2
    assert strat_runnable.invoke.call_count == 1  # segunda chamada veio do cache!

    a1 = agent.explain_alert(
        "chuva_intensa", severidade="alta", detalhes_clima={"max_precipitation_mm": 65.0}
    )
    a2 = agent.explain_alert(
        "chuva_intensa", severidade="alta", detalhes_clima={"max_precipitation_mm": 65.0}
    )
    assert "Limpe as valas de drenagem" in a1
    assert a1.endswith(DISCLAIMER)
    assert a1 == a2
    assert alert_runnable.invoke.call_count == 1

    # Limpar cache força nova chamada ao modelo
    agent.clear_cache()
    agent.explain_strategies(strategies, field_metrics=fm)
    assert strat_runnable.invoke.call_count == 2


def test_structured_output_fallback_gracioso_para_chain_padrao():
    class _BrokenStructuredLLM(FakeListLLM):
        def with_structured_output(self, _schema):
            def _boom(_inp):
                raise RuntimeError("Schema indisponível")

            return _boom

    llm = _BrokenStructuredLLM(
        responses=[
            "Explicação 1 para Sorgo -> Feijão-caupi.\n---ESTRATEGIA---\nExplicação 2 para Milho -> Soja."
        ]
    )
    agent = RotationExplainerAgent(llm=llm)
    out = agent.explain_strategies(
        [
            {"strategy": "Sorgo -> Feijão-caupi", "viability": 0.8, "water_risk": "low"},
            {"strategy": "Milho -> Soja", "viability": 0.5, "water_risk": "high"},
        ]
    )
    assert len(out) == 2
    assert "Explicação 1" in out[0]
    assert out[0].endswith(DISCLAIMER)


def test_explain_report_cache_e_simulacao_api_inclui_insights_cruzados():
    fake_llm = FakeListLLM(responses=["Resumo enxuto do relatório de campo."])
    agent = RotationExplainerAgent(llm=fake_llm)

    payload = {
        "resumo_climatico": {"umidade_media_solo": 0.25, "temperatura_media_c": 29.0},
        "vigor": {"classificacao": "bom", "tendencia": "estavel"},
        "vulnerabilidade": {"nivel": "baixo", "total_alertas_periodo": 0},
        "adaptacoes": {"total_atividades_periodo": 2, "total_ajustadas_por_alerta": 0},
        "nome_propriedade": "Sítio Cache",
    }
    r1 = agent.explain_report(**payload)
    r2 = agent.explain_report(**payload)
    assert r1 == r2
    assert r1.endswith(DISCLAIMER)

    # Verifica que rota /api/v1/simular-rotacao funciona ponta a ponta com insights cruzados
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

    class _MockGAEZ:
        def extract_gaez_metrics(self, _coords, prioridades=None):
            return {
                "data_quality": "gaez_v5_cog",
                "origem": "fao_gaez_v5",
                "input_level": "LRLM",
                "soil": {
                    "soil_group": "Arenosols - AR (Neossolos Quartzarênicos)",
                    "limiting_factor": "Disponibilidade/retenção natural de nutrientes (SQ2)",
                    "slope_range_pct": "12 - 16%",
                    "erosion_risk": "alto",
                    "soil_quality_index": 0.58,
                },
                "crops": {
                    "SRG": {
                        "crop_code": "SRG",
                        "nome": "Sorgo",
                        "gaez_caption": "Sorghum",
                        "scientific_name": "Sorghum bicolor",
                        "group": "graminea",
                        "fixes_nitrogen": False,
                        "suitability_index": 0.86,
                        "attainable_yield_kg_ha": 3100.0,
                        "cmip6_suitability_delta": -0.05,
                        "consumo_agua_mm": 320.0,
                        "tempo_colheita_dias": 90,
                        "market": 0.68,
                        "soil_benefit": 0.65,
                        "heat_tolerance": 0.90,
                        "water_demand": 0.36,
                    },
                    "COW": {
                        "crop_code": "COW",
                        "nome": "Feijão-caupi",
                        "gaez_caption": "Cowpea",
                        "scientific_name": "Vigna unguiculata",
                        "group": "leguminosa",
                        "fixes_nitrogen": True,
                        "suitability_index": 0.88,
                        "attainable_yield_kg_ha": 1450.0,
                        "cmip6_suitability_delta": -0.04,
                        "consumo_agua_mm": 300.0,
                        "tempo_colheita_dias": 70,
                        "market": 0.75,
                        "soil_benefit": 0.88,
                        "heat_tolerance": 0.90,
                        "water_demand": 0.35,
                    },
                },
            }

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[simulacao_api.get_gaez_provider] = lambda: _MockGAEZ()
    try:
        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/simular-rotacao",
                json={
                    "nome_propriedade": "Sítio Cruzamento",
                    "coordenadas_poligono": [
                        {"lat": -12.0, "lng": -45.0},
                        {"lat": -12.0, "lng": -44.99},
                        {"lat": -12.01, "lng": -44.99},
                        {"lat": -12.01, "lng": -45.0},
                    ],
                    "prioridades": {"agua": "escassa"},
                    "perfil_climatico": "seca",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["evidencias_estruturadas"] is not None
        assert body["rotacoes_sugeridas"][0]["evidencias_numericas"] is not None
        all_notes = " ".join(body["beneficios_esperados"] + body["riscos_identificados"]).lower()
        assert "cmip6" in all_notes or "arenosols" in all_notes or "solo" in all_notes
    finally:
        app.dependency_overrides.clear()
        simulacao_api._SERVICE_CACHE.clear()
        Base.metadata.drop_all(bind=engine)

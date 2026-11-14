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
        db.add(models.Usuario(nome="Produtor C6", email="c6@kultiva.local"))
        db.add(models.Cultura(nome="Milho", consumo_agua_mm=500.0, tempo_colheita_dias=90))
        db.commit()
    return engine


def test_c6_expoe_score_breakdown_e_explicacao_por_estrategia():
    engine = _setup_sqlite()
    try:
        mock_sim = MagicMock()
        mock_sim.simulate_rotation_strategies.return_value = [
            {
                "strategy": "Milho -> Soja (Atual)",
                "viability": 0.55,
                "water_risk": "high",
                "benefits": "Mercado consolidado",
                "score_breakdown": {"water_fit": 0.4, "heat_fit": 0.6, "soil_benefit": 0.45, "market": 0.95},
            },
            {
                "strategy": "Sorgo -> Feijão-caupi",
                "viability": 0.90,
                "water_risk": "low",
                "benefits": "Tolera seca",
                "score_breakdown": {"water_fit": 0.95, "heat_fit": 0.9, "soil_benefit": 0.8, "market": 0.6},
            },
            {
                "strategy": "Milheto -> Amendoim",
                "viability": 0.80,
                "water_risk": "medium",
                "benefits": "Cobertura do solo",
                "score_breakdown": {"water_fit": 0.75, "heat_fit": 0.8, "soil_benefit": 0.85, "market": 0.7},
            },
        ]
        mock_sim.predict_rotation_viability.return_value = {
            "viability_score": 0.90,
            "water_risk": "low",
        }

        mock_llm = MagicMock()
        mock_llm.generate_explanation.return_value = (
            "Resumo geral. A decisão final é sempre sua."
        )
        mock_llm.explain_strategies.return_value = [
            "Milho -> Soja (Atual) sofre com falta de água.",
            "Sorgo -> Feijão-caupi é a mais segura para seca.",
            "Milheto -> Amendoim protege bem o solo.",
        ]

        app.dependency_overrides[simulacao.get_nasa_processor] = lambda: None
        app.dependency_overrides[simulacao.get_crop_simulator] = lambda: mock_sim
        app.dependency_overrides[simulacao.get_rotation_explainer] = lambda: mock_llm

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/simulacoes/",
                json={"nome_propriedade": "Sítio C6", "nome_cultura": "Milho"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert len(body["rotacoes_sugeridas"]) == 3
            for item in body["rotacoes_sugeridas"]:
                assert isinstance(item["score_breakdown"], dict)
                assert "water_fit" in item["score_breakdown"]
                assert "decisão final" in item["explicacao"].lower()
            assert body["explicacao_ia"] == body["explicacao_textual"]
            mock_llm.explain_strategies.assert_called_once()
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_c6_fallback_dinamico_varia_com_clima_e_prioridades():
    engine = _setup_sqlite()
    try:
        app.dependency_overrides[simulacao.get_nasa_processor] = lambda: None
        app.dependency_overrides[simulacao.get_crop_simulator] = lambda: None
        app.dependency_overrides[simulacao.get_rotation_explainer] = lambda: None

        with TestClient(app) as client:
            resp_seco = client.post(
                "/api/v1/simulacoes/",
                json={
                    "nome_propriedade": "Área Seca",
                    "nome_cultura": "Milho",
                    "prioridades": {"agua": "escassa"},
                    "dados_climaticos": {
                        "umidade_solo": 0.10,
                        "precipitacao_mm": 250.0,
                        "temperatura_media_c": 37.0,
                    },
                },
            )
            resp_umido = client.post(
                "/api/v1/simulacoes/",
                json={
                    "nome_propriedade": "Área Úmida",
                    "nome_cultura": "Milho",
                    "prioridades": {"agua": "abundante"},
                    "dados_climaticos": {
                        "umidade_solo": 0.35,
                        "precipitacao_mm": 1200.0,
                        "temperatura_media_c": 24.0,
                    },
                },
            )
            assert resp_seco.status_code == 200
            assert resp_umido.status_code == 200

            body_seco = resp_seco.json()
            body_umido = resp_umido.json()
            assert body_seco["fallback_usado"] is True
            assert body_seco["viability_score"] < body_umido["viability_score"]
            for item in body_seco["rotacoes_sugeridas"]:
                assert isinstance(item["score_breakdown"], dict)
                assert "decisão final" in item["explicacao"].lower()
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

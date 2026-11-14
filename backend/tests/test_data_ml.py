import sys

import numpy as np
import pytest

from backend.services.ml_models import ClimateAnomalyDetector, CropSimulator
from backend.services.mock_nasa_data import generate_synthetic_netcdf

POLIGONO_SP = [
    {"lat": -23.5505, "lng": -46.6333},
    {"lat": -23.5515, "lng": -46.6343},
    {"lat": -23.5525, "lng": -46.6323},
]
POLIGONO_AMAZONIA = [
    {"lat": -2.50, "lng": -60.00},
    {"lat": -2.50, "lng": -59.00},
    {"lat": -1.50, "lng": -59.50},
]


@pytest.fixture(scope="module")
def provider(tmp_path_factory):
    # Import tardio + limpeza no teardown: outros testes substituem
    # `backend.services.geospatial` via sys.modules e `from backend.services import
    # geospatial` priorizaria o atributo do pacote se o módulo real ficasse importado.
    from backend.services.geospatial import MockNASADataProvider

    d = tmp_path_factory.mktemp("nasa")
    generate_synthetic_netcdf(str(d), force=True)
    yield MockNASADataProvider(data_path=str(d))

    import backend.services as services_pkg

    sys.modules.pop("backend.services.geospatial", None)
    if hasattr(services_pkg, "geospatial"):
        delattr(services_pkg, "geospatial")


# ---- A1: provider / mock --------------------------------------------------


def test_metricas_contrato_completo(provider):
    m = provider.extract_field_metrics(POLIGONO_SP)
    for key in (
        "avg_soil_moisture_smap",
        "avg_surface_temp_ecostress",
        "avg_precipitation_gpm",
        "is_bare_field_period",
        "data_quality",
        "time_series",
    ):
        assert key in m
    assert m["data_quality"] in {"clip", "nearest_cell"}
    assert m["avg_precipitation_gpm"] > 0
    assert len(m["time_series"]) == 5
    assert {"data", "soil_moisture", "surface_temp_c", "precipitation_mm"} <= set(
        m["time_series"][0]
    )
    assert isinstance(m["is_bare_field_period"], bool)


def test_poligono_pequeno_usa_celula_mais_proxima(provider):
    m = provider.extract_field_metrics(POLIGONO_SP)
    assert m["avg_soil_moisture_smap"] > 0.0
    assert m["avg_surface_temp_ecostress"] > 0.0


def test_mock_deterministico_e_espacialmente_distinto(provider):
    a1 = provider.extract_field_metrics(POLIGONO_SP)
    a2 = provider.extract_field_metrics(POLIGONO_SP)
    am = provider.extract_field_metrics(POLIGONO_AMAZONIA)
    assert a1["avg_precipitation_gpm"] == a2["avg_precipitation_gpm"]
    assert am["avg_precipitation_gpm"] > a1["avg_precipitation_gpm"]


# ---- A2: CropSimulator ----------------------------------------------------

SECO = {
    "avg_soil_moisture_smap": 0.10,
    "avg_surface_temp_ecostress": 36.0,
    "avg_precipitation_gpm": 1.0,
    "data_quality": "clip",
}
UMIDO = {
    "avg_soil_moisture_smap": 0.40,
    "avg_surface_temp_ecostress": 27.0,
    "avg_precipitation_gpm": 5.0,
    "data_quality": "clip",
}


def test_simulador_retorna_3_estrategias_com_atual():
    est = CropSimulator().simulate_rotation_strategies(SECO, {})
    assert len(est) == 3
    assert sum("(Atual)" in e["strategy"] for e in est) == 1
    for e in est:
        assert 0.0 <= e["viability"] <= 1.0
        assert e["water_risk"] in {"low", "medium", "high"}
        assert e["benefits"]


def test_simulador_reage_ao_clima():
    sim = CropSimulator()
    seco = {e["strategy"]: e for e in sim.simulate_rotation_strategies(SECO, {})}
    umido = {e["strategy"]: e for e in sim.simulate_rotation_strategies(UMIDO, {})}
    atual_seco = next(e for k, e in seco.items() if "(Atual)" in k)
    atual_umido = next(e for k, e in umido.items() if "(Atual)" in k)
    assert atual_seco["water_risk"] == "high"
    assert atual_umido["viability"] > atual_seco["viability"]


def test_prioridade_hidrica_reduz_viabilidade_de_cultura_sedenta():
    sim = CropSimulator()
    sem = sim.simulate_rotation_strategies(SECO, {})
    com = sim.simulate_rotation_strategies(SECO, {"agua": "escassa"})
    v = lambda lst: next(e["viability"] for e in lst if "(Atual)" in e["strategy"])  # noqa: E731
    assert v(com) < v(sem)


def test_predict_usa_requisitos_da_cultura():
    sim = CropSimulator()
    sedenta = sim.predict_rotation_viability(
        {}, SECO, {"consumo_agua_mm": 650.0, "tempo_colheita_dias": 120}
    )
    rustica = sim.predict_rotation_viability(
        {}, SECO, {"consumo_agua_mm": 250.0, "tempo_colheita_dias": 60}
    )
    assert rustica["viability_score"] > sedenta["viability_score"]
    assert sedenta["water_risk"] == "high"


def test_simulador_aceita_metricas_de_fallback_da_api():
    fallback = {"precipitacao_estimada_mm": 520.0, "temperatura_media_c": 25.5, "umidade_solo_estimada": 0.42}
    assert len(CropSimulator().simulate_rotation_strategies(fallback, {})) == 3


# ---- A3: ClimateAnomalyDetector ------------------------------------------


def _serie_normal(n=30, seed=0):
    rng = np.random.default_rng(seed)
    return [
        {
            "data": f"2026-02-{i + 1:02d}",
            "precipitation_mm": float(rng.normal(8, 1)),
            "surface_temp_c": float(rng.normal(28, 0.5)),
            "soil_moisture": float(rng.normal(0.30, 0.01)),
        }
        for i in range(n)
    ]


def test_serie_normal_nao_dispara():
    r = ClimateAnomalyDetector().detect_extremes(_serie_normal())
    assert r["anomaly_detected"] is False
    assert r["tipo_evento"] == "nenhum"


def test_limiares_absolutos():
    d = ClimateAnomalyDetector()
    assert d.detect_extremes({"precipitation_mm": 90.0})["tipo_evento"] == "chuva_intensa"
    assert d.detect_extremes({"surface_temp_c": 41.0})["severidade"] == "critica"
    assert d.detect_extremes({"soil_moisture": 0.10})["tipo_evento"] == "seca"


def test_outlier_estatistico_sem_estourar_limiar():
    serie = _serie_normal()
    serie[20]["precipitation_mm"] = 40.0  # abaixo de 60 mm, mas outlier claro
    r = ClimateAnomalyDetector().detect_extremes(serie)
    assert r["anomaly_detected"] is True
    assert r["tipo_evento"] == "chuva_intensa"
    assert r["detalhes"]["metodo"] == "isolation_forest"
    assert 20 in r["detalhes"]["indices_outliers"]


def test_contrato_de_saida_e_serie_vazia():
    r = ClimateAnomalyDetector().detect_extremes([])
    assert set(r) == {"anomaly_detected", "tipo_evento", "severidade", "detalhes"}
    assert r["anomaly_detected"] is False

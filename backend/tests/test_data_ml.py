import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from langchain_core.language_models.fake import FakeListLLM

from backend.schemas.simulacao import EstrategiaRotacaoSugerida
from backend.services.llm_agent import (
    DISCLAIMER,
    STRATEGY_SEPARATOR,
    RotationExplainerAgent,
)
from backend.services.ml_models import (
    ClimateAnomalyDetector,
    CropSimulator,
    get_fallback_rotation_strategies,
)
from backend.services.mock_nasa_data import (
    CLIMATE_PROFILES,
    ECOSTRESS_FILE,
    GPM_FILE,
    SMAP_FILE,
    generate_synthetic_netcdf,
    normalize_climate_profile,
)

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


def test_detector_serie_curta_constante_e_outlier_benigno():
    d = ClimateAnomalyDetector()

    # Série curta (< 10 pontos) sem estourar limiar não aciona IsolationForest
    curta = _serie_normal(n=9)
    curta[5]["precipitation_mm"] = 40.0
    assert d.detect_extremes(curta)["anomaly_detected"] is False

    # Série constante (MAD == 0) não divide por zero nem gera falso positivo
    constante = [
        {"precipitation_mm": 5.0, "surface_temp_c": 26.0, "soil_moisture": 0.30}
        for _ in range(15)
    ]
    res_const = d.detect_extremes(constante)
    assert res_const["anomaly_detected"] is False
    assert res_const["tipo_evento"] == "nenhum"

    # Outlier no sentido benigno (menos chuva / dia mais frio) não gera alerta
    benigno = _serie_normal(n=30)
    benigno[10]["precipitation_mm"] = 0.0
    benigno[12]["surface_temp_c"] = 17.0
    benigno[15]["soil_moisture"] = 0.45
    assert d.detect_extremes(benigno)["anomaly_detected"] is False

    # Aliases em português aceitos pelo detector
    assert d.detect_extremes({"precipitacao_mm": 75.0})["tipo_evento"] == "chuva_intensa"
    assert d.detect_extremes({"temperatura_media_c": 37.0})["tipo_evento"] == "onda_de_calor"
    assert d.detect_extremes({"umidade_solo": 0.12})["tipo_evento"] == "seca"


# ---- A1 / A2: casos extremos adicionais -----------------------------------


def test_normalizacao_poligono_invalido_invertido_e_poucos_vertices(provider):
    from backend.services.geospatial import (
        _DEFAULT_BRAZIL_POLYGON,
        _build_polygon_geometry,
        _normalize_polygon_coords,
    )

    assert _normalize_polygon_coords([]) == _DEFAULT_BRAZIL_POLYGON
    assert _normalize_polygon_coords(None) == _DEFAULT_BRAZIL_POLYGON

    # Pares (lat, lon) invertidos são corrigidos para (lon, lat)
    corrigido = _normalize_polygon_coords(
        [(-15.0, -47.0), (-15.5, -47.5), (-16.0, -46.5)]
    )
    assert corrigido == [(-47.0, -15.0), (-47.5, -15.5), (-46.5, -16.0)]

    # Polígonos com 1 ou 2 pontos geram geometria válida com área > 0
    geom_1 = _build_polygon_geometry([(-47.0, -15.0)])
    geom_2 = _build_polygon_geometry([(-47.0, -15.0), (-47.1, -15.1)])
    assert geom_1.is_valid and geom_1.area > 0
    assert geom_2.is_valid and geom_2.area > 0

    # Polígono amplo cobre células da grade e usa clip espacial
    poligono_amplo = [
        {"lat": -16.0, "lng": -48.0},
        {"lat": -16.0, "lng": -47.0},
        {"lat": -15.0, "lng": -47.0},
        {"lat": -15.0, "lng": -48.0},
    ]
    m = provider.extract_field_metrics(poligono_amplo)
    assert m["data_quality"] == "clip"
    assert m["avg_precipitation_gpm"] > 0


def test_generate_synthetic_netcdf_idempotente_e_regera_faltante(tmp_path):
    msg1 = generate_synthetic_netcdf(str(tmp_path), force=False)
    assert "sucesso" in msg1
    for fname in (SMAP_FILE, ECOSTRESS_FILE, GPM_FILE):
        assert (tmp_path / fname).exists()

    smap_mtime_before = (tmp_path / SMAP_FILE).stat().st_mtime_ns
    msg2 = generate_synthetic_netcdf(str(tmp_path), force=False)
    assert "já existentes" in msg2
    assert (tmp_path / SMAP_FILE).stat().st_mtime_ns == smap_mtime_before

    # Se um dos arquivos estiver faltando, regera o conjunto completo
    (tmp_path / GPM_FILE).unlink()
    msg3 = generate_synthetic_netcdf(str(tmp_path), force=False)
    assert "sucesso" in msg3
    assert (tmp_path / GPM_FILE).exists()


def test_simulador_pratica_atual_customizada_e_normalizacao_seta():
    sim = CropSimulator()
    est_custom = sim.simulate_rotation_strategies(
        SECO, {"pratica_atual": "Algodão -> Girassol"}
    )
    assert len(est_custom) == 3
    atuais = [e for e in est_custom if "(Atual)" in e["strategy"]]
    assert len(atuais) == 1
    assert atuais[0]["strategy"] == "Algodão -> Girassol (Atual)"

    # Seta unicode "→" deve casar com item do catálogo sem duplicar
    est_seta = sim.simulate_rotation_strategies(
        UMIDO, {"pratica_atual": "Sorgo → Feijão-caupi"}
    )
    assert len(est_seta) == 3
    sorgo_items = [e for e in est_seta if "sorgo" in e["strategy"].lower()]
    assert len(sorgo_items) == 1
    assert "(Atual)" in sorgo_items[0]["strategy"]


def test_simulador_no_data_e_predict_sem_requisitos():
    sim = CropSimulator()

    # Quando data_quality == "no_data", ignora zeros do provider e usa fallback
    no_data_com_fallback = {
        "data_quality": "no_data",
        "avg_soil_moisture_smap": 0.0,
        "avg_surface_temp_ecostress": 0.0,
        "avg_precipitation_gpm": 0.0,
        "umidade_solo_estimada": 0.40,
        "temperatura_media_c": 26.0,
        "precipitacao_estimada_mm": 1200.0,
    }
    no_data_sem_fallback = {
        "data_quality": "no_data",
        "avg_soil_moisture_smap": 0.0,
        "avg_surface_temp_ecostress": 0.0,
        "avg_precipitation_gpm": 0.0,
    }
    m_fb = sim._read_metrics(no_data_com_fallback)
    m_def = sim._read_metrics(no_data_sem_fallback)
    assert m_fb["moisture"] == pytest.approx(0.40)
    assert m_def["moisture"] == pytest.approx(0.25)

    # predict_rotation_viability com 2 argumentos delega para simulate_rotation_strategies
    res_lista = sim.predict_rotation_viability(UMIDO, {"agua": "escassa"})
    assert isinstance(res_lista, list)
    assert len(res_lista) == 3


# ---- A4: RotationExplainerAgent ------------------------------------------


def test_llm_generate_explanation_garante_disclaimer_sem_duplicar():
    fake_llm = FakeListLLM(
        responses=[
            "Essa rotação ajuda a segurar a umidade no solo.",
            f"Essa rotação ajuda no manejo.\n\n{DISCLAIMER}",
        ]
    )
    agent = RotationExplainerAgent(llm=fake_llm)

    sem_aviso = agent.generate_explanation(
        crop="Sorgo -> Feijão-caupi",
        benefits="Segura mais água",
        risks="Risco baixo",
    )
    assert "decisão final" in sem_aviso.lower()
    assert sem_aviso.endswith(DISCLAIMER)

    com_aviso = agent.generate_explanation(
        crop="Milho -> Soja",
        benefits="Mercado fácil",
        risks="Pede mais água",
    )
    assert com_aviso.lower().count("decisão final") == 1


def test_llm_explain_strategies_uma_chamada_tres_explicacoes_com_disclaimer(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    estrategias = CropSimulator().simulate_rotation_strategies(SECO, {"agua": "escassa"})
    agent = RotationExplainerAgent()

    with patch.object(agent.llm, "_call", wraps=agent.llm._call) as spy_call:
        explicacoes = agent.explain_strategies(
            estrategias,
            field_metrics=SECO,
            farmer_priorities={"agua": "escassa"},
        )

    assert spy_call.call_count == 1
    assert len(explicacoes) == 3
    assert len(set(explicacoes)) == 3
    for estrategia, texto in zip(estrategias, explicacoes):
        assert estrategia["strategy"] in texto
        assert "decisão final" in texto.lower()
        assert texto.endswith(DISCLAIMER)


def test_llm_explain_strategies_parseia_blocos_estruturados_e_lista_vazia():
    estrategias = CropSimulator().simulate_rotation_strategies(UMIDO, {})
    resposta_llm = (
        f"A estratégia {estrategias[0]['strategy']} aproveita bem a chuva do terreno.\n"
        f"{STRATEGY_SEPARATOR}\n"
        "Segunda explicação simples sem repetir o título.\n"
        f"{STRATEGY_SEPARATOR}\n"
        f"Na opção {estrategias[2]['strategy']}, observe o manejo do solo. "
        "A decisão final é sempre sua."
    )
    fake_llm = FakeListLLM(responses=[resposta_llm])
    agent = RotationExplainerAgent(llm=fake_llm)

    with patch.object(agent.llm, "_call", wraps=agent.llm._call) as spy_call:
        assert agent.explain_strategies([]) == []
        assert spy_call.call_count == 0

        explicacoes = agent.explain_strategies(estrategias)

    assert spy_call.call_count == 1
    assert len(explicacoes) == 3
    assert "aproveita bem a chuva" in explicacoes[0]
    assert explicacoes[0].endswith(DISCLAIMER)
    assert estrategias[1]["strategy"] in explicacoes[1]
    assert "Segunda explicação simples" in explicacoes[1]
    assert explicacoes[1].endswith(DISCLAIMER)
    assert estrategias[2]["strategy"] in explicacoes[2]
    assert explicacoes[2].lower().count("decisão final") == 1

    # Também aceita modelos Pydantic (EstrategiaRotacaoSugerida)
    modelos = [
        EstrategiaRotacaoSugerida(
            strategy=e["strategy"],
            viability=e["viability"],
            water_risk=e["water_risk"],
            benefits=e["benefits"],
        )
        for e in estrategias
    ]
    explicacoes_modelos = agent.explain_strategies(modelos)
    assert len(explicacoes_modelos) == 3
    assert all("decisão final" in t.lower() for t in explicacoes_modelos)


# ---- A5: RealNASADataProvider e NASA_PROVIDER ----------------------------


@pytest.fixture()
def geospatial_mod():
    import backend.services as services_pkg
    import backend.services.geospatial as geo_mod

    yield geo_mod

    sys.modules.pop("backend.services.geospatial", None)
    if hasattr(services_pkg, "geospatial"):
        delattr(services_pkg, "geospatial")


def test_factory_nasa_provider_seleciona_mock_por_padrao_e_real_por_env(
    monkeypatch, geospatial_mod
):
    monkeypatch.delenv("NASA_PROVIDER", raising=False)
    assert isinstance(
        geospatial_mod.get_nasa_data_provider(), geospatial_mod.MockNASADataProvider
    )

    monkeypatch.setenv("NASA_PROVIDER", "mock")
    assert isinstance(
        geospatial_mod.get_nasa_data_provider(), geospatial_mod.MockNASADataProvider
    )

    monkeypatch.setenv("NASA_PROVIDER", "real")
    real = geospatial_mod.get_nasa_data_provider()
    assert isinstance(real, geospatial_mod.RealNASADataProvider)


def test_real_nasa_provider_earthaccess_e_open_mfdataset_com_kelvin_e_ndvi(
    monkeypatch, tmp_path, geospatial_mod
):
    lats = np.array([-16.0, -15.5, -15.0])
    lons = np.array([-48.0, -47.5, -47.0])
    d1 = pd.date_range("2026-11-10", periods=1)
    d2 = pd.date_range("2026-11-11", periods=1)
    d_both = pd.date_range("2026-11-10", periods=2)

    smap_1 = tmp_path / "smap_1.nc"
    smap_2 = tmp_path / "smap_2.nc"
    eco_file = tmp_path / "eco.nc"
    gpm_file = tmp_path / "gpm.nc"
    ndvi_file = tmp_path / "ndvi.nc"

    xr.Dataset(
        {"soil_moisture": (["time", "lat", "lon"], np.full((1, 3, 3), 0.32))},
        coords={"time": d1, "lat": lats, "lon": lons},
    ).to_netcdf(smap_1)
    xr.Dataset(
        {"soil_moisture": (["time", "lat", "lon"], np.full((1, 3, 3), 0.32))},
        coords={"time": d2, "lat": lats, "lon": lons},
    ).to_netcdf(smap_2)
    xr.Dataset(
        {"LST": (["time", "latitude", "longitude"], np.full((2, 3, 3), 308.15))},
        coords={"time": d_both, "latitude": lats, "longitude": lons},
    ).to_netcdf(eco_file)
    xr.Dataset(
        {"precipitation": (["time", "lat", "lon"], np.full((2, 3, 3), 4.5))},
        coords={"time": d_both, "lat": lats, "lon": lons},
    ).to_netcdf(gpm_file)
    xr.Dataset(
        {"NDVI": (["time", "lat", "lon"], np.full((2, 3, 3), 1800.0))},
        coords={"time": d_both, "lat": lats, "lon": lons},
    ).to_netcdf(ndvi_file)

    files_by_collection = {
        "SPL3SMP_E": [str(smap_1), str(smap_2)],
        "ECO2LSTE": [str(eco_file)],
        "GPM_3IMERGDF": [str(gpm_file)],
        "MOD13Q1": [str(ndvi_file)],
    }

    fake_ea = ModuleType("earthaccess")
    fake_ea.login = MagicMock(return_value=MagicMock(authenticated=True))
    fake_ea.search_data = MagicMock(
        side_effect=lambda short_name, **kwargs: [{"short_name": short_name}]
    )
    fake_ea.open = MagicMock(
        side_effect=lambda granules: files_by_collection[granules[0]["short_name"]]
    )
    monkeypatch.setitem(sys.modules, "earthaccess", fake_ea)

    poligono_amplo = [
        {"lat": -16.0, "lng": -48.0},
        {"lat": -16.0, "lng": -47.0},
        {"lat": -15.0, "lng": -47.0},
        {"lat": -15.0, "lng": -48.0},
    ]

    real_provider = geospatial_mod.RealNASADataProvider(
        credentials={"username": "nasa_user", "password": "secret"}
    )
    with patch.object(xr, "open_mfdataset", wraps=xr.open_mfdataset) as spy_mf:
        metricas = real_provider.extract_field_metrics(poligono_amplo)

    fake_ea.login.assert_called_once()
    assert fake_ea.search_data.call_count == 4
    assert spy_mf.call_count == 4
    assert metricas["data_quality"] == "clip"
    assert metricas["avg_soil_moisture_smap"] == pytest.approx(0.32, abs=1e-4)
    assert metricas["avg_surface_temp_ecostress"] == pytest.approx(35.0, abs=1e-2)
    assert metricas["avg_precipitation_gpm"] == pytest.approx(4.5, abs=1e-4)
    # Umidade está alta (0.32), mas NDVI=0.18 (< 0.25) indica solo exposto
    assert metricas["is_bare_field_period"] is True
    assert len(metricas["time_series"]) == 2
    assert {"data", "soil_moisture", "surface_temp_c", "precipitation_mm"} <= set(
        metricas["time_series"][0]
    )


def test_real_nasa_provider_sem_earthaccess_retorna_no_data(
    monkeypatch, geospatial_mod
):
    monkeypatch.setenv("GAEZ_ENABLED", "false")
    monkeypatch.setitem(sys.modules, "earthaccess", None)
    real_provider = geospatial_mod.RealNASADataProvider()
    metricas = real_provider.extract_field_metrics(POLIGONO_SP)

    assert metricas["data_quality"] == "no_data"
    assert metricas["time_series"] == []
    assert metricas["is_bare_field_period"] is False
    assert metricas["coordinates"] == POLIGONO_SP
    assert set(metricas) == {
        "coordinates",
        "avg_soil_moisture_smap",
        "avg_surface_temp_ecostress",
        "avg_precipitation_gpm",
        "is_bare_field_period",
        "data_quality",
        "time_series",
    }


# ---- A7: Geometria do terreno, histórico de cultivos e fallback -----------


def test_calcular_geometria_terreno_poligono_valido_e_casos_borda(geospatial_mod):
    # Polígono ~1 km x 1 km próximo ao DF (~100 ha)
    poligono_100ha = [
        {"lat": -15.500, "lng": -47.500},
        {"lat": -15.500, "lng": -47.49068},
        {"lat": -15.509, "lng": -47.49068},
        {"lat": -15.509, "lng": -47.500},
    ]
    geo = geospatial_mod.calcular_geometria_terreno(poligono_100ha)
    assert 85.0 <= geo["area_hectares"] <= 115.0
    assert geo["total_vertices"] == 4
    assert geo["localizacao_central"]["lat"] == pytest.approx(-15.5045, abs=1e-4)
    assert geo["localizacao_central"]["lng"] == pytest.approx(-47.49534, abs=1e-4)

    # Método na interface INASADataProvider delega para a função geoespacial
    assert geospatial_mod.MockNASADataProvider().calculate_field_geometry(
        poligono_100ha
    ) == geo

    # Casos de borda: lista vazia e menos de 3 vértices
    vazio = geospatial_mod.calcular_geometria_terreno([])
    assert vazio == {
        "area_hectares": 0.0,
        "localizacao_central": {"lat": 0.0, "lng": 0.0},
        "total_vertices": 0,
    }

    dois_pontos = geospatial_mod.calcular_geometria_terreno(
        [{"lat": -15.0, "lng": -47.0}, {"lat": -15.2, "lng": -47.4}]
    )
    assert dois_pontos["area_hectares"] == 0.0
    assert dois_pontos["total_vertices"] == 2
    assert dois_pontos["localizacao_central"] == {"lat": -15.1, "lng": -47.2}


def test_crop_simulator_historico_penaliza_monocultura_e_premia_rotacao():
    sim = CropSimulator()
    sem_historico = sim.simulate_rotation_strategies(UMIDO, {})

    historico_monocultura = {
        "ultimoCultivo": {"id": "milho", "officialName": "Milho"},
        "cultivoAnterior": {"id": "milho", "officialName": "Milho"},
        "naoLembro": False,
    }
    com_historico = sim.simulate_rotation_strategies(
        UMIDO,
        {"historico_cultivos": historico_monocultura},
    )

    sem_map = {e["strategy"]: e for e in sem_historico}
    com_map = {e["strategy"]: e for e in com_historico}

    atual_sem = next(v for k, v in sem_map.items() if "(Atual)" in k)
    atual_com = next(v for k, v in com_map.items() if "(Atual)" in k)
    assert atual_com["score_breakdown"]["history_adjustment"] < 0
    assert atual_com["viability"] < atual_sem["viability"]

    leguminosa = next(
        e for e in com_historico if "Feijão" in e["strategy"] and "(Atual)" not in e["strategy"]
    )
    assert leguminosa["score_breakdown"]["history_adjustment"] > 0
    # Ranking alterado: rotação com leguminosa supera a monocultura repetida
    assert com_historico[0]["strategy"] == leguminosa["strategy"]
    assert "(Atual)" not in com_historico[0]["strategy"]

    # Quando `naoLembro=True`, não altera os scores
    nao_lembro = sim.simulate_rotation_strategies(
        UMIDO,
        {},
        historico_cultivos={"ultimoCultivo": "Milho", "cultivoAnterior": "Milho", "naoLembro": True},
    )
    assert nao_lembro[0]["score_breakdown"]["history_adjustment"] == 0.0
    assert [e["viability"] for e in nao_lembro] == [e["viability"] for e in sem_historico]

    # Também aceita lista simples de strings
    lista_hist = sim.simulate_rotation_strategies(UMIDO, {}, historico_cultivos=["Sorgo", "Milho"])
    atual_lista = next(e for e in lista_hist if "(Atual)" in e["strategy"])
    assert atual_lista["score_breakdown"]["history_adjustment"] < 0


def test_crop_simulator_fallback_strategies_dinamico():
    sim = CropSimulator()
    fb_seco = sim.fallback_strategies(
        {"agua": "escassa"},
        {"umidade_solo_estimada": 0.11, "precipitacao_estimada_mm": 380.0},
    )
    fb_padrao = get_fallback_rotation_strategies()

    assert len(fb_seco) == 3
    assert len(fb_padrao) == 3
    for item in fb_seco:
        assert "score_breakdown" in item
        assert "water_fit" in item["score_breakdown"]
        assert item["benefits"]

    atual_seco = next(e for e in fb_seco if "(Atual)" in e["strategy"])
    atual_padrao = next(e for e in fb_padrao if "(Atual)" in e["strategy"])
    assert atual_seco["viability"] < atual_padrao["viability"]
    assert atual_seco["water_risk"] == "high"


# ---- A8: RotationExplainerAgent (alertas [M5] e relatórios [M6]) --------


def test_explainer_explain_alert_e_report_com_disclaimer(monkeypatch):
    from backend.schemas.relatorio import (
        AdaptacoesTerrenoResumo,
        ResumoClimaticoRelatorio,
        VigorTerrenoResumo,
        VulnerabilidadeTerrenoResumo,
    )

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    agent = RotationExplainerAgent()

    explicacao_chuva = agent.explain_alert(
        tipo_evento="chuva_intensa",
        severidade="alta",
        cultura="Milho",
        resumo_adaptacao="Adiar adubação em 2 dias",
        detalhes_clima={"max_precipitation_mm": 88.5},
    )
    assert "chuva intensa" in explicacao_chuva.lower()
    assert "milho" in explicacao_chuva.lower()
    assert "adub" in explicacao_chuva.lower()
    assert "Adiar adubação em 2 dias" in explicacao_chuva
    assert explicacao_chuva.endswith(DISCLAIMER)

    explicacao_calor = agent.explain_alert(
        tipo_evento="onda_de_calor",
        severidade="critica",
        detalhes_clima={"max_surface_temp_c": 41.2},
    )
    assert "onda de calor" in explicacao_calor.lower()
    assert "palhada" in explicacao_calor.lower()
    assert explicacao_calor.endswith(DISCLAIMER)

    resumo_rel = agent.explain_report(
        resumo_climatico=ResumoClimaticoRelatorio(
            umidade_media_solo=0.29,
            umidade_min_solo=0.18,
            umidade_max_solo=0.38,
            temperatura_media_c=29.4,
            temperatura_max_c=34.0,
            precipitacao_total_mm=142.0,
            precipitacao_media_mm=4.7,
            dias_solo_exposto=1,
            total_medicoes=30,
        ),
        vigor=VigorTerrenoResumo(
            indice=0.76,
            classificacao="bom",
            tendencia="subindo",
            descricao="Cobertura vegetal evoluindo bem",
        ),
        vulnerabilidade=VulnerabilidadeTerrenoResumo(
            indice=0.28,
            nivel="baixa",
            total_alertas_periodo=1,
            eventos_criticos=[],
            fatores_risco=[],
        ),
        adaptacoes=AdaptacoesTerrenoResumo(
            total_atividades_periodo=5,
            total_ajustadas_por_alerta=1,
            taxa_adaptacao=0.2,
            atividades_ajustadas=[],
        ),
        nome_propriedade="Sítio Esperança",
    )
    assert "Sítio Esperança" in resumo_rel
    assert "29%" in resumo_rel
    assert "bom" in resumo_rel
    assert "subindo" in resumo_rel
    assert "1 de 5 atividade(s)" in resumo_rel
    assert resumo_rel.endswith(DISCLAIMER)

    # Também funciona com LLM customizado mantendo texto e adicionando disclaimer
    custom_agent = RotationExplainerAgent(
        llm=FakeListLLM(
            responses=[
                "Verifique os canais de drenagem antes da chuva.",
                "O solo manteve boa umidade durante todo o mês.",
            ]
        )
    )
    r1 = custom_agent.explain_alert("chuva_intensa")
    r2 = custom_agent.explain_report({"umidade_media_solo": 0.30})
    assert "Verifique os canais de drenagem" in r1
    assert r1.endswith(DISCLAIMER)
    assert "O solo manteve boa umidade" in r2
    assert r2.endswith(DISCLAIMER)


# ---- A9: Perfis climáticos simuláveis -------------------------------------


def test_perfis_climaticos_mock_geram_cenarios_distintos_e_acionam_detector(
    tmp_path, geospatial_mod
):
    detector = ClimateAnomalyDetector()
    sim = CropSimulator()
    resultados: dict[str, dict] = {}

    for perfil in CLIMATE_PROFILES:
        pasta_perfil = tmp_path / perfil
        msg = generate_synthetic_netcdf(str(pasta_perfil), force=True, profile=perfil)
        assert perfil in msg

        prov = geospatial_mod.get_nasa_data_provider(
            data_path=str(pasta_perfil), profile=perfil
        )
        metricas = prov.extract_field_metrics(POLIGONO_SP)
        resultados[perfil] = metricas

    # Seca: solo exposto, umidade crítica e disparo de evento "seca"
    seca = resultados["seca"]
    assert seca["is_bare_field_period"] is True
    assert seca["avg_soil_moisture_smap"] < resultados["normal"]["avg_soil_moisture_smap"]
    det_seca = detector.detect_extremes(seca["time_series"])
    assert det_seca["anomaly_detected"] is True
    assert det_seca["tipo_evento"] == "seca"

    # Seca reduz viabilidade da prática atual sedenta ("Milho -> Soja") frente ao normal
    viab_seca = next(
        e["viability"]
        for e in sim.simulate_rotation_strategies(seca, {"agua": "escassa"})
        if "(Atual)" in e["strategy"]
    )
    viab_normal = next(
        e["viability"]
        for e in sim.simulate_rotation_strategies(resultados["normal"], {})
        if "(Atual)" in e["strategy"]
    )
    assert viab_seca < viab_normal

    # Chuva extrema: precipitação >= 60 mm/dia e evento "chuva_intensa"
    chuva = resultados["chuva_extrema"]
    assert chuva["avg_precipitation_gpm"] >= detector.HEAVY_RAIN_MM
    assert chuva["avg_soil_moisture_smap"] > seca["avg_soil_moisture_smap"]
    det_chuva = detector.detect_extremes(chuva["time_series"])
    assert det_chuva["anomaly_detected"] is True
    assert det_chuva["tipo_evento"] == "chuva_intensa"

    # Onda de calor: temperatura >= 35 °C e evento "onda_de_calor"
    calor = resultados["onda_de_calor"]
    assert calor["avg_surface_temp_ecostress"] >= detector.HEAT_C
    det_calor = detector.detect_extremes(calor["time_series"])
    assert det_calor["anomaly_detected"] is True
    assert det_calor["tipo_evento"] == "onda_de_calor"


def test_perfil_climatico_aliases_env_e_erro_perfil_invalido(
    monkeypatch, tmp_path, geospatial_mod
):
    assert normalize_climate_profile("chuva_intensa") == "chuva_extrema"
    assert normalize_climate_profile("estiagem") == "seca"
    assert normalize_climate_profile("calor") == "onda_de_calor"
    assert normalize_climate_profile("padrao") == "normal"

    with pytest.raises(ValueError, match="Perfil climático inválido"):
        normalize_climate_profile("nevasca_polar")

    # Via variável de ambiente NASA_MOCK_PROFILE
    monkeypatch.setenv("NASA_MOCK_PROFILE", "chuva_intensa")
    assert normalize_climate_profile() == "chuva_extrema"

    prov = geospatial_mod.MockNASADataProvider(data_path=str(tmp_path))
    m_chuva = prov.extract_field_metrics(POLIGONO_SP)
    assert m_chuva["avg_precipitation_gpm"] >= 60.0

    # Alternar perfil na mesma pasta sem force=True regenera automaticamente
    monkeypatch.setenv("NASA_MOCK_PROFILE", "seca")
    m_seca = prov.extract_field_metrics(POLIGONO_SP)
    assert m_seca["avg_soil_moisture_smap"] <= 0.10
    assert m_seca["is_bare_field_period"] is True


# ---- A10: Perfil climático em runtime e area_hectares na simulação ------


def test_a10_extract_field_metrics_aceita_profile_em_runtime(tmp_path, geospatial_mod):
    prov = geospatial_mod.MockNASADataProvider(data_path=str(tmp_path))

    m_seca = prov.extract_field_metrics(POLIGONO_SP, profile="seca")
    assert m_seca["avg_soil_moisture_smap"] <= 0.10
    assert m_seca["is_bare_field_period"] is True

    m_chuva = prov.extract_field_metrics(POLIGONO_SP, profile="chuva_extrema")
    assert m_chuva["avg_precipitation_gpm"] >= 60.0

    m_calor = prov.extract_field_metrics(POLIGONO_SP, profile="onda_de_calor")
    assert m_calor["avg_surface_temp_ecostress"] >= 35.0

    # Ao omitir `profile`, volta ao padrão ("normal") sem manter extremos anteriores
    m_normal = prov.extract_field_metrics(POLIGONO_SP)
    assert m_normal["avg_precipitation_gpm"] < 60.0
    assert m_normal["avg_soil_moisture_smap"] > m_seca["avg_soil_moisture_smap"]


def test_a10_simulacao_endpoint_com_perfil_climatico_e_area_hectares(
    tmp_path, geospatial_mod
):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from backend.api import simulacao
    from backend.db import models
    from backend.db.database import Base, get_db
    from backend.main import app

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

    with TestingSessionLocal() as db:
        db.add(models.Usuario(nome="Produtor A10", email="a10@kultiva.local"))
        db.add(models.Cultura(nome="Milho", consumo_agua_mm=500.0, tempo_colheita_dias=90))
        db.commit()

    poligono_100ha = [
        {"lat": -15.500, "lng": -47.500},
        {"lat": -15.500, "lng": -47.49068},
        {"lat": -15.509, "lng": -47.49068},
        {"lat": -15.509, "lng": -47.500},
    ]

    prov = geospatial_mod.MockNASADataProvider(data_path=str(tmp_path))
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[simulacao.get_nasa_processor] = lambda: prov
    app.dependency_overrides[simulacao.get_crop_simulator] = lambda: CropSimulator()
    app.dependency_overrides[simulacao.get_rotation_explainer] = (
        lambda: RotationExplainerAgent()
    )

    try:
        with TestClient(app) as client:
            resp_seca = client.post(
                "/api/v1/simular-rotacao",
                json={
                    "nome_propriedade": "Sítio A10",
                    "coordenadas_poligono": poligono_100ha,
                    "nome_cultura": "Milho",
                    "perfil_climatico": "seca",
                    "historico_cultivos": {
                        "ultimoCultivo": {"id": "milho", "officialName": "Milho"},
                        "cultivoAnterior": {"id": "milho", "officialName": "Milho"},
                        "naoLembro": False,
                    },
                },
            )
            assert resp_seca.status_code == 200
            body_seca = resp_seca.json()
            assert 85.0 <= body_seca["metricas_geoespaciais"]["area_hectares"] <= 115.0
            assert body_seca["metricas_geoespaciais"]["perfil_climatico"] == "seca"
            assert body_seca["metricas_geoespaciais"]["avg_soil_moisture_smap"] <= 0.10

            resp_chuva = client.post(
                "/api/v1/simular-rotacao",
                json={
                    "nome_propriedade": "Sítio A10",
                    "coordenadas_poligono": poligono_100ha,
                    "nome_cultura": "Milho",
                    "perfil_climatico": "chuva_extrema",
                },
            )
            assert resp_chuva.status_code == 200
            body_chuva = resp_chuva.json()
            assert (
                body_chuva["metricas_geoespaciais"]["perfil_climatico"]
                == "chuva_extrema"
            )
            assert body_chuva["metricas_geoespaciais"]["avg_precipitation_gpm"] >= 60.0
            assert (
                body_seca["metricas_geoespaciais"]["avg_soil_moisture_smap"]
                < body_chuva["metricas_geoespaciais"]["avg_soil_moisture_smap"]
            )
            assert body_seca["viability_score"] < body_chuva["viability_score"]

            # Mesmo em fallback de provedor, area_hectares permanece calculada
            app.dependency_overrides[simulacao.get_nasa_processor] = lambda: None
            resp_fb = client.post(
                "/api/v1/simular-rotacao",
                json={
                    "nome_propriedade": "Sítio A10 Fallback",
                    "coordenadas_poligono": poligono_100ha,
                    "nome_cultura": "Milho",
                },
            )
            assert resp_fb.status_code == 200
            assert 85.0 <= resp_fb.json()["metricas_geoespaciais"]["area_hectares"] <= 115.0

            resp_invalido = client.post(
                "/api/v1/simular-rotacao",
                json={
                    "nome_propriedade": "Sítio Inválido",
                    "perfil_climatico": "nevasca_polar",
                },
            )
            assert resp_invalido.status_code == 422
    finally:
        simulacao._SERVICE_CACHE.clear()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


# ---- A11 / A12: Ingestão Real Multi-Fonte, NASA POWER e ML Avançado -------


def test_a11_real_nasa_provider_descobre_local_transpoe_e_limpa_fillvalues(
    monkeypatch, tmp_path, geospatial_mod
):
    monkeypatch.setenv("GAEZ_ENABLED", "false")
    monkeypatch.setitem(sys.modules, "earthaccess", None)
    real_dir = tmp_path / "real"
    real_dir.mkdir(parents=True, exist_ok=True)

    times = pd.date_range("2026-11-10", periods=3)
    lats_desc = np.array([-15.0, -15.5, -16.0])  # ordem decrescente
    lons_360 = np.array([312.0, 312.5, 313.0])  # equivalente a -48.0..-47.0
    lons_180 = np.array([-48.0, -47.5, -47.0])

    # GPM IMERG real: dimensão transposta (time, lon, lat) + sentinela -9999.0
    precip_data = np.full((3, 3, 3), 8.0, dtype=float)
    precip_data[0, 0, 0] = -9999.0
    xr.Dataset(
        {"precipitationCal": (["time", "lon", "lat"], precip_data)},
        coords={"time": times, "lon": lons_180, "lat": lats_desc},
    ).to_netcdf(real_dir / "gpm_imerg_2026.nc")

    # SMAP real com longitudes 0..360
    xr.Dataset(
        {
            "Soil_Moisture_Retrieval_Data_AM_soil_moisture": (
                ["time", "lat", "lon"],
                np.full((3, 3, 3), 0.28),
            )
        },
        coords={"time": times, "lat": np.array([-16.0, -15.5, -15.0]), "lon": lons_360},
    ).to_netcdf(real_dir / "spl3smp_smap.nc")

    # ECOSTRESS real com variável SDS_LST em Kelvin
    xr.Dataset(
        {"SDS_LST": (["time", "lat", "lon"], np.full((3, 3, 3), 305.15))},
        coords={
            "time": times,
            "lat": np.array([-16.0, -15.5, -15.0]),
            "lon": lons_180,
        },
    ).to_netcdf(real_dir / "eco2lste_temp.nc")

    poligono_amplo = [
        {"lat": -16.0, "lng": -48.0},
        {"lat": -16.0, "lng": -47.0},
        {"lat": -15.0, "lng": -47.0},
        {"lat": -15.0, "lng": -48.0},
    ]

    prov = geospatial_mod.RealNASADataProvider(data_path=str(tmp_path))
    metricas = prov.extract_field_metrics(poligono_amplo)

    assert metricas["data_quality"] == "clip"
    assert metricas["avg_precipitation_gpm"] == pytest.approx(8.0, abs=1e-4)
    assert metricas["avg_soil_moisture_smap"] == pytest.approx(0.28, abs=1e-4)
    assert metricas["avg_surface_temp_ecostress"] == pytest.approx(32.0, abs=1e-2)
    assert len(metricas["time_series"]) == 3


def test_a11_real_nasa_provider_nasa_power_fallback_e_cache(
    monkeypatch, tmp_path, geospatial_mod
):
    monkeypatch.setenv("GAEZ_ENABLED", "false")
    monkeypatch.setitem(sys.modules, "earthaccess", None)

    power_payload = {
        "properties": {
            "parameter": {
                "GWETTOP": {
                    "20261108": 0.56,
                    "20261109": 0.60,
                    "20261110": 0.64,
                    "20261111": -999.0,  # dia ainda em latência na NASA
                },
                "TS": {
                    "20261108": 28.5,
                    "20261109": 29.0,
                    "20261110": 27.5,
                    "20261111": -999.0,
                },
                "PRECTOTCORR": {
                    "20261108": 2.4,
                    "20261109": 5.1,
                    "20261110": 3.0,
                    "20261111": -999.0,
                },
            }
        }
    }
    fake_resp = MagicMock()
    fake_resp.json.return_value = power_payload
    fake_resp.raise_for_status = MagicMock()

    with patch.object(geospatial_mod.httpx, "get", return_value=fake_resp) as spy_get:
        prov = geospatial_mod.RealNASADataProvider(
            data_path=str(tmp_path),
            days_back=2,
            enable_nasa_power=True,
        )
        m1 = prov.extract_field_metrics(POLIGONO_SP)
        m2 = prov.extract_field_metrics(POLIGONO_SP)

    assert spy_get.call_count == 1  # segunda chamada reutiliza cache em disco
    _, call_kwargs = spy_get.call_args
    assert call_kwargs["params"]["community"] == "AG"
    assert call_kwargs["params"]["parameters"] == "GWETTOP,TS,PRECTOTCORR"

    assert m1["data_quality"] == "nearest_cell"
    assert len(m1["time_series"]) == 2
    assert m1["time_series"][0]["data"] == "2026-11-09"
    assert m1["time_series"][1]["data"] == "2026-11-10"
    assert m1["avg_soil_moisture_smap"] == pytest.approx((0.30 + 0.32) / 2, abs=1e-4)
    assert m1["avg_surface_temp_ecostress"] == pytest.approx(28.25, abs=1e-2)
    assert m1["avg_precipitation_gpm"] == pytest.approx(4.05, abs=1e-2)
    assert m2["time_series"] == m1["time_series"]


def test_a11_ml_features_temporais_random_forest_e_diagnostico_anomalias():
    sim = CropSimulator()
    serie_estavel = {
        "avg_soil_moisture_smap": 0.28,
        "avg_surface_temp_ecostress": 28.0,
        "avg_precipitation_gpm": 4.0,
        "data_quality": "clip",
        "is_bare_field_period": False,
        "time_series": [
            {"data": f"2026-11-0{i+1}", "soil_moisture": 0.27 + 0.005 * i, "surface_temp_c": 28.0, "precipitation_mm": 4.0}
            for i in range(5)
        ],
    }
    serie_instavel_secando = {
        "avg_soil_moisture_smap": 0.28,
        "avg_surface_temp_ecostress": 28.0,
        "avg_precipitation_gpm": 4.0,
        "data_quality": "clip",
        "is_bare_field_period": True,
        "time_series": [
            {"data": "2026-11-01", "soil_moisture": 0.38, "surface_temp_c": 24.0, "precipitation_mm": 20.0},
            {"data": "2026-11-02", "soil_moisture": 0.33, "surface_temp_c": 26.0, "precipitation_mm": 0.0},
            {"data": "2026-11-03", "soil_moisture": 0.28, "surface_temp_c": 28.0, "precipitation_mm": 0.0},
            {"data": "2026-11-04", "soil_moisture": 0.23, "surface_temp_c": 34.0, "precipitation_mm": 0.0},
            {"data": "2026-11-05", "soil_moisture": 0.18, "surface_temp_c": 35.0, "precipitation_mm": 0.0},
        ],
    }

    res_estavel = sim.simulate_rotation_strategies(serie_estavel, {})
    res_instavel = sim.simulate_rotation_strategies(serie_instavel_secando, {})

    bd_est = res_estavel[0]["score_breakdown"]
    bd_inst = res_instavel[0]["score_breakdown"]
    for key in (
        "ml_model_score",
        "temporal_stability",
        "moisture_trend",
        "dry_spell_max",
        "bare_soil_bonus",
    ):
        assert key in bd_est
        assert key in bd_inst

    assert 0.0 <= bd_est["ml_model_score"] <= 1.0
    assert bd_inst["temporal_stability"] < bd_est["temporal_stability"]
    assert bd_inst["moisture_trend"] < 0
    assert bd_inst["dry_spell_max"] == 4
    # Solo exposto premia estratégias com cobertura/solo (soil_benefit >= 0.75)
    assert any(e["score_breakdown"]["bare_soil_bonus"] > 0 for e in res_instavel)

    # ClimateAnomalyDetector expõe métricas diagnósticas extras em `detalhes`
    serie_normal = _serie_normal(n=15)
    det_normal = ClimateAnomalyDetector().detect_extremes(serie_normal)
    assert det_normal["detalhes"]["anomaly_score_min"] is not None
    assert det_normal["detalhes"]["moisture_trend_per_day"] is not None
    assert 0.0 <= det_normal["detalhes"]["heat_stress_index"] <= 1.0


def test_a12_simulacao_endpoint_com_perfil_real_e_nasa_power(
    monkeypatch, tmp_path, geospatial_mod
):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from backend.api import simulacao
    from backend.db import models
    from backend.db.database import Base, get_db
    from backend.main import app

    assert normalize_climate_profile("real", allow_real=True) == "real"
    with pytest.raises(ValueError):
        normalize_climate_profile("real", allow_real=False)

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

    with TestingSessionLocal() as db:
        db.add(models.Usuario(nome="Produtor A12", email="a12@kultiva.local"))
        db.add(models.Cultura(nome="Milho", consumo_agua_mm=500.0, tempo_colheita_dias=90))
        db.commit()

    monkeypatch.setenv("GAEZ_ENABLED", "false")
    monkeypatch.setitem(sys.modules, "earthaccess", None)
    power_payload = {
        "properties": {
            "parameter": {
                "GWETTOP": {"20261109": 0.44, "20261110": 0.48},
                "TS": {"20261109": 30.0, "20261110": 31.0},
                "PRECTOTCORR": {"20261109": 1.5, "20261110": 2.0},
            }
        }
    }
    fake_resp = MagicMock()
    fake_resp.json.return_value = power_payload
    fake_resp.raise_for_status = MagicMock()

    simulacao._SERVICE_CACHE.clear()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[simulacao.get_crop_simulator] = lambda: CropSimulator()
    app.dependency_overrides[simulacao.get_rotation_explainer] = (
        lambda: RotationExplainerAgent()
    )

    real_prov = geospatial_mod.get_nasa_data_provider(
        data_path=str(tmp_path), profile="real"
    )
    assert isinstance(real_prov, geospatial_mod.RealNASADataProvider)
    assert real_prov.enable_nasa_power is True

    try:
        with patch.object(geospatial_mod.httpx, "get", return_value=fake_resp):
            app.dependency_overrides[simulacao.get_nasa_processor] = lambda: real_prov
            with TestClient(app) as client:
                resp = client.post(
                    "/api/v1/simular-rotacao",
                    json={
                        "nome_propriedade": "Sítio Real A12",
                        "coordenadas_poligono": [
                            {"lat": -7.230, "lng": -35.880},
                            {"lat": -7.236, "lng": -35.880},
                            {"lat": -7.236, "lng": -35.874},
                            {"lat": -7.230, "lng": -35.874},
                        ],
                        "nome_cultura": "Milho",
                        "perfil_climatico": "real",
                    },
                )
                assert resp.status_code == 200
                body = resp.json()
                assert body["fallback_usado"] is False
                assert body["metricas_geoespaciais"]["perfil_climatico"] == "real"
                assert body["metricas_geoespaciais"]["avg_precipitation_gpm"] == pytest.approx(1.75)
                assert body["metricas_geoespaciais"]["area_hectares"] > 0
                assert "ml_model_score" in body["rotacoes_sugeridas"][0]["score_breakdown"]
    finally:
        simulacao._SERVICE_CACHE.clear()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


# ---- A13 / A14: FAO GAEZ v5 (Suitability & Attainable Yield, HWSD, CMIP6) --


def _write_single_pixel_geotiff(path, value: float, nodata: float | None = -9.0) -> None:
    import rasterio
    from rasterio.transform import from_origin

    path.parent.mkdir(parents=True, exist_ok=True)
    transform = from_origin(-50.0, -10.0, 5.0, 5.0)
    dtype = "uint16" if nodata == 65535.0 else "float32"
    with rasterio.open(
        str(path),
        "w",
        driver="GTiff",
        height=2,
        width=2,
        count=1,
        dtype=dtype,
        crs="EPSG:4326",
        transform=transform,
        nodata=nodata,
    ) as dst:
        dst.write(np.full((2, 2), value, dtype=dtype), 1)


def _build_local_gaez_cog_tree(root_dir) -> None:
    # Camadas de solo e relevo
    _write_single_pixel_geotiff(
        root_dir / "MAP" / "GAEZ-V5.HWSDV201.tif", 11, nodata=65535.0
    )
    _write_single_pixel_geotiff(
        root_dir / "MAPSET" / "SQ-IDX" / "GAEZ-V5.SQ-IDX.LIM.tif", 2, nodata=0.0
    )
    _write_single_pixel_geotiff(
        root_dir / "MAPSET" / "SQX" / "GAEZ-V5.SQX.SQ0.LIM.tif", 6, nodata=0.0
    )
    _write_single_pixel_geotiff(
        root_dir / "MAP" / "GAEZ-V5.SLOPE-MED.tif", 3, nodata=0.0
    )

    # Culturas RES05 ("Suitability and Attainable Yield" - HIST LRLM/HRLM + FP2140 SSP370 HRLM)
    crops_values = {
        "MZE": (7778.0, 971.0, 7200.0, 880.0),
        "COW": (8100.0, 410.0, 8600.0, 460.0),
        "CSV": (9500.0, 1850.0, 9600.0, 1900.0),
        "SRG": (7000.0, 540.0, 7500.0, 610.0),
    }
    for code, (sux_lrlm, ylx_lrlm, sux_fut, ylx_fut) in crops_values.items():
        _write_single_pixel_geotiff(
            root_dir
            / "MAPSET"
            / "RES05-SUX"
            / f"GAEZ-V5.RES05-SUX.HP0120.AGERA5.HIST.{code}.LRLM.tif",
            sux_lrlm,
        )
        _write_single_pixel_geotiff(
            root_dir
            / "MAPSET"
            / "RES05-YLX"
            / f"GAEZ-V5.RES05-YLX.HP0120.AGERA5.HIST.{code}.LRLM.tif",
            ylx_lrlm,
        )
        _write_single_pixel_geotiff(
            root_dir
            / "MAPSET"
            / "RES05-SUX"
            / f"GAEZ-V5.RES05-SUX.HP0120.AGERA5.HIST.{code}.HRLM.tif",
            sux_lrlm,
        )
        _write_single_pixel_geotiff(
            root_dir
            / "MAPSET"
            / "RES05-SUX"
            / f"GAEZ-V5.RES05-SUX.FP2140.ENSEMBLE.SSP370.{code}.HRLM.tif",
            sux_fut,
        )
        _write_single_pixel_geotiff(
            root_dir
            / "MAPSET"
            / "RES05-YLX"
            / f"GAEZ-V5.RES05-YLX.FP2140.ENSEMBLE.SSP370.{code}.HRLM.tif",
            ylx_fut,
        )


def test_a13_gaez_provider_suitability_attainable_yield_hwsd_e_cache(
    monkeypatch, tmp_path, geospatial_mod
):
    from backend.services import gaez_service

    assert gaez_service.resolve_gaez_input_level(
        {"agua": "chuva", "equipamento": "manual"}
    )["input_level"] == "LRLM"
    assert gaez_service.resolve_gaez_input_level(
        {"metodo_irrigacao": "gotejamento", "equipamento": "manual"}
    )["input_level"] == "LILM"
    assert gaez_service.resolve_gaez_input_level(
        {"agua": "chuva", "nivel_insumo": "alto"}
    )["input_level"] == "HRLM"
    assert gaez_service.resolve_gaez_input_level(
        {"metodo_irrigacao": "aspersao", "nivel_insumo": "alto"}
    )["input_level"] == "HILM"

    assert gaez_service.resolve_crop_code("Milho") == "MZE"
    assert gaez_service.resolve_crop_code("Macaxeira") == "CSV"
    assert gaez_service.resolve_crop_code("Feijão-de-corda") == "COW"
    assert gaez_service.resolve_crop_code("Feijão carioquinha") == "PHB"
    assert gaez_service.resolve_crop_code("Cultura Desconhecida") is None

    cog_root = tmp_path / "fao_cogs"
    _build_local_gaez_cog_tree(cog_root)
    monkeypatch.setattr(gaez_service, "GAEZ_BASE_URL", str(cog_root))
    monkeypatch.setenv("GAEZ_ENABLED", "true")

    cache_root = tmp_path / "data_cache"
    prov = gaez_service.GAEZDataProvider(data_path=str(cache_root), max_workers=4)
    poligono_df = [
        {"lat": -12.0, "lng": -48.0},
        {"lat": -12.1, "lng": -48.0},
        {"lat": -12.1, "lng": -47.9},
    ]

    metrics = prov.extract_gaez_metrics(
        poligono_df,
        prioridades={"agua": "chuva", "equipamento": "manual"},
        crop_codes=["MZE", "COW", "CSV", "SRG"],
    )
    assert metrics["data_quality"] == "gaez_v5_cog"
    assert metrics["origem"] == "fao_gaez_v5"
    assert metrics["input_level"] == "LRLM"
    assert metrics["soil"]["hwsd_code"] == 11
    assert "Latossolos" in metrics["soil"]["soil_group"]
    assert metrics["soil"]["limiting_factor_code"] == 2
    assert metrics["soil"]["soil_quality_index"] == pytest.approx(0.55)
    assert metrics["soil"]["slope_range_pct"] == "2 - 5%"
    assert metrics["soil"]["erosion_risk"] == "baixo"

    assert metrics["crops"]["MZE"]["suitability_score_100"] == pytest.approx(77.78)
    assert metrics["crops"]["MZE"]["attainable_yield_kg_ha"] == pytest.approx(971.0)
    assert metrics["crops"]["MZE"]["cmip6_suitability_delta"] < 0
    assert metrics["crops"]["MZE"]["climate_resilience"] == "perda_moderada"
    assert metrics["crops"]["COW"]["cmip6_suitability_delta"] > 0
    assert metrics["crops"]["COW"]["climate_resilience"] == "ganho"

    # Segunda chamada na mesma célula usa o cache em disco mesmo sem os COGs originais
    for tif in cog_root.rglob("*.tif"):
        tif.unlink()
    cached_metrics = prov.extract_gaez_metrics(
        poligono_df,
        prioridades={"agua": "chuva", "equipamento": "manual"},
        crop_codes=["MZE", "COW", "CSV", "SRG"],
    )
    assert cached_metrics == metrics

    # Em um ponto fora do cache e sem COGs disponíveis, retorna no_data (sem fallback inventado)
    no_data_metrics = prov.extract_gaez_metrics(
        {"lat": -3.5, "lng": -39.0},
        prioridades={"agua": "chuva"},
        crop_codes=["MZE"],
    )
    assert no_data_metrics["data_quality"] == "no_data"
    assert no_data_metrics["crops"] == {}
    assert no_data_metrics["soil"] == {}


def test_a14_crop_simulator_e_explainer_com_gaez_suitability_e_yield(
    monkeypatch, geospatial_mod
):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    gaez_payload = {
        "data_quality": "gaez_v5_cog",
        "origem": "fao_gaez_v5",
        "input_level": "LRLM",
        "ssp_scenario": "SSP370",
        "centroid": {"lat": -12.06, "lng": -47.96},
        "soil": {
            "hwsd_code": 11,
            "soil_group": "Ferralsols - FR (Latossolos)",
            "limiting_factor_code": 2,
            "limiting_factor": "Disponibilidade/retenção natural de nutrientes (SQ2)",
            "soil_quality_class": 6,
            "soil_quality_index": 0.55,
            "slope_class": 3,
            "slope_range_pct": "2 - 5%",
            "erosion_risk": "baixo",
        },
        "crops": {
            "MZE": {
                "crop_code": "MZE",
                "gaez_caption": "Maize",
                "nome": "Milho",
                "group": "graminea",
                "fixes_nitrogen": False,
                "suitability_index": 0.65,
                "suitability_score_100": 65.0,
                "suitability_class": "good",
                "attainable_yield_kg_ha": 971.0,
                "cmip6_suitability_delta": -0.05,
                "consumo_agua_mm": 500.0,
                "tempo_colheita_dias": 95,
                "water_demand": 0.72,
                "heat_tolerance": 0.55,
                "soil_benefit": 0.45,
                "market": 0.95,
            },
            "SOY": {
                "crop_code": "SOY",
                "gaez_caption": "Soybean",
                "nome": "Soja",
                "group": "leguminosa",
                "fixes_nitrogen": True,
                "suitability_index": 0.60,
                "suitability_score_100": 60.0,
                "suitability_class": "good",
                "attainable_yield_kg_ha": 310.0,
                "cmip6_suitability_delta": -0.04,
                "consumo_agua_mm": 550.0,
                "tempo_colheita_dias": 115,
                "water_demand": 0.82,
                "heat_tolerance": 0.60,
                "soil_benefit": 0.75,
                "market": 0.96,
            },
            "CSV": {
                "crop_code": "CSV",
                "gaez_caption": "Cassava",
                "nome": "Mandioca",
                "group": "tuberculo",
                "fixes_nitrogen": False,
                "suitability_index": 0.98,
                "suitability_score_100": 98.0,
                "suitability_class": "very_high",
                "attainable_yield_kg_ha": 1850.0,
                "cmip6_suitability_delta": 0.02,
                "consumo_agua_mm": 400.0,
                "tempo_colheita_dias": 270,
                "water_demand": 0.45,
                "heat_tolerance": 0.85,
                "soil_benefit": 0.55,
                "market": 0.75,
            },
            "COW": {
                "crop_code": "COW",
                "gaez_caption": "Cowpea",
                "nome": "Feijão-caupi",
                "group": "leguminosa",
                "fixes_nitrogen": True,
                "suitability_index": 0.90,
                "suitability_score_100": 90.0,
                "suitability_class": "very_high",
                "attainable_yield_kg_ha": 430.0,
                "cmip6_suitability_delta": 0.05,
                "consumo_agua_mm": 300.0,
                "tempo_colheita_dias": 70,
                "water_demand": 0.35,
                "heat_tolerance": 0.90,
                "soil_benefit": 0.88,
                "market": 0.75,
            },
        },
    }
    metricas_com_gaez = {**SECO, "gaez": gaez_payload}

    sim = CropSimulator()
    estrategias = sim.simulate_rotation_strategies(metricas_com_gaez, {"agua": "escassa"})
    assert len(estrategias) == 3
    assert any("(Atual)" in e["strategy"] for e in estrategias)
    assert any("Mandioca" in e["strategy"] and "Feijão-caupi" in e["strategy"] for e in estrategias)

    top_bd = estrategias[0]["score_breakdown"]
    assert "gaez_suitability" in top_bd
    assert top_bd["attainable_yield_kg_ha"] > 0
    assert top_bd["soil_quality_index"] == pytest.approx(0.55)
    assert top_bd["gaez_input_level"] == "LRLM"

    pred = sim.predict_rotation_viability(
        {}, metricas_com_gaez, {"cultura": "Mandioca", "consumo_agua_mm": 400.0, "tempo_colheita_dias": 270}
    )
    assert pred["gaez_suitability"] == pytest.approx(0.98)
    assert pred["attainable_yield_kg_ha"] == pytest.approx(1850.0)

    captured_prompts: list[str] = []
    agent = RotationExplainerAgent()
    orig_chain = agent.strategies_chain

    class _SpyChain:
        def invoke(self, inputs):
            captured_prompts.append(inputs["context"] + "\n" + inputs["strategies"])
            return orig_chain.invoke(inputs)

    agent.strategies_chain = _SpyChain()
    explicacoes = agent.explain_strategies(
        estrategias,
        field_metrics=metricas_com_gaez,
        farmer_priorities={"agua": "escassa"},
    )

    assert len(explicacoes) == 3
    assert "Latossolos" in captured_prompts[0]
    assert "aptidão FAO GAEZ" in captured_prompts[0]
    assert "kg/ha" in explicacoes[0]
    assert explicacoes[0].endswith(DISCLAIMER)


def test_a14_endpoints_aptidao_gaez_e_simular_rotacao_integrados(
    monkeypatch, tmp_path, geospatial_mod
):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from backend.api import cultura as cultura_api
    from backend.api import simulacao
    from backend.db import models
    from backend.db.database import Base, get_db
    from backend.main import app
    from backend.services import gaez_service

    cog_root = tmp_path / "fao_cogs"
    _build_local_gaez_cog_tree(cog_root)
    monkeypatch.setattr(gaez_service, "GAEZ_BASE_URL", str(cog_root))
    monkeypatch.setenv("GAEZ_ENABLED", "true")

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

    with TestingSessionLocal() as db:
        u = models.Usuario(nome="Produtor A14", email="a14@kultiva.local")
        db.add(u)
        db.flush()
        db.add(
            models.Terreno(
                nome_propriedade="Sítio GAEZ",
                usuario_id=u.id,
                coordenadas_poligono=[
                    {"lat": -12.0, "lng": -48.0},
                    {"lat": -12.1, "lng": -48.0},
                    {"lat": -12.1, "lng": -47.9},
                ],
                prioridades={"agua": "chuva", "equipamento": "manual"},
            )
        )
        db.add(
            models.Cultura(
                nome="Milho",
                consumo_agua_mm=500.0,
                tempo_colheita_dias=90,
                is_seed=True,
                customizada=False,
            )
        )
        db.commit()

    local_gaez = gaez_service.GAEZDataProvider(data_path=str(tmp_path / "cache"))
    mock_nasa = geospatial_mod.MockNASADataProvider(data_path=str(tmp_path / "nasa"))
    simulacao._SERVICE_CACHE.clear()
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[cultura_api.get_gaez_provider] = lambda: local_gaez
    app.dependency_overrides[simulacao.get_gaez_provider] = lambda: local_gaez
    app.dependency_overrides[simulacao.get_nasa_processor] = lambda: mock_nasa
    app.dependency_overrides[simulacao.get_crop_simulator] = lambda: CropSimulator()
    app.dependency_overrides[simulacao.get_rotation_explainer] = (
        lambda: RotationExplainerAgent()
    )

    try:
        with patch.object(
            local_gaez,
            "extract_gaez_metrics",
            wraps=lambda coords, prioridades=None, crop_codes=None: gaez_service.GAEZDataProvider.extract_gaez_metrics(
                local_gaez,
                coords,
                prioridades=prioridades,
                crop_codes=crop_codes or ["MZE", "COW", "CSV", "SRG"],
            ),
        ):
            with TestClient(app) as client:
                # Rota /culturas/{id} continua funcionando sem conflito com /aptidao-gaez
                assert client.get("/api/v1/culturas/1").status_code == 200

                resp_gaez = client.get(
                    "/api/v1/culturas/aptidao-gaez",
                    params={"terreno_id": 1, "sincronizar_catalogo": True},
                )
                assert resp_gaez.status_code == 200
                body_gaez = resp_gaez.json()
                assert body_gaez["origem"] == "fao_gaez_v5"
                assert body_gaez["input_level"] == "LRLM"
                assert "Latossolos" in body_gaez["soil"]["soil_group"]
                assert body_gaez["culturas_avaliadas"][0]["crop_code"] == "CSV"
                assert body_gaez["culturas_avaliadas"][0]["attainable_yield_kg_ha"] == pytest.approx(1850.0)
                sincronizadas = {c["nome"] for c in body_gaez["culturas_sincronizadas"]}
                assert {"Mandioca", "Feijão-caupi", "Sorgo"} <= sincronizadas
                assert "Milho" not in sincronizadas  # seed protegido contra sobrescrita

                resp_list = client.get("/api/v1/culturas/")
                assert resp_list.status_code == 200
                assert any(c["nome"] == "Feijão-caupi" and c["customizada"] for c in resp_list.json())

                resp_sim = client.post(
                    "/api/v1/simular-rotacao",
                    json={"terreno_id": 1, "nome_cultura": "Milho"},
                )
                assert resp_sim.status_code == 200
                body_sim = resp_sim.json()
                assert body_sim["metricas_geoespaciais"]["gaez"]["data_quality"] == "gaez_v5_cog"
                assert "attainable_yield_kg_ha" in body_sim["rotacoes_sugeridas"][0]["score_breakdown"]
                assert "kg/ha" in body_sim["rotacoes_sugeridas"][0]["explicacao"]

                # Quando GAEZ não responde dados (sem rede), /aptidao-gaez retorna 503 sem fallback falso
                with patch.object(
                    local_gaez,
                    "extract_gaez_metrics",
                    return_value={"data_quality": "no_data", "crops": {}, "soil": {}},
                ):
                    resp_503 = client.get(
                        "/api/v1/culturas/aptidao-gaez",
                        params={"lat": -12.0, "lng": -48.0},
                    )
                    assert resp_503.status_code == 503
    finally:
        simulacao._SERVICE_CACHE.clear()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)

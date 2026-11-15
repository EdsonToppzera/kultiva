import importlib
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.database import get_db
from backend.schemas.simulacao import (
    EstrategiaRotacaoSugerida,
    EtapaRotacaoSimulada,
    SimulacaoRequest,
    SimulacaoResponse,
)
from backend.services.geospatial import calcular_geometria_terreno
from backend.services.metrics_service import persistir_metricas_terreno
from backend.services.mock_nasa_data import normalize_climate_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulacoes", tags=["Simulador (M3)"])
simular_rotacao_router = APIRouter(tags=["Simulador (M3)"])

_DISCLAIMER_PADRAO = (
    "Lembre-se: esta ferramenta serve para apoiar a decisão e identificar possibilidades, "
    "mas não substitui a sua experiência local. A decisão final é sempre sua."
)

_ROTACOES_BASE_FALLBACK = [
    {
        "strategy": "Milho -> Soja (Atual)",
        "water_demand": 0.90,
        "heat_tolerance": 0.45,
        "soil_benefit": 0.45,
        "market": 0.95,
        "benefits": "Mercado estabelecido e cadeia de comercialização consolidada",
    },
    {
        "strategy": "Sorgo -> Feijão-caupi",
        "water_demand": 0.35,
        "heat_tolerance": 0.90,
        "soil_benefit": 0.80,
        "market": 0.60,
        "benefits": "Alta tolerância à seca, fixa nitrogênio",
    },
    {
        "strategy": "Milheto -> Amendoim",
        "water_demand": 0.55,
        "heat_tolerance": 0.75,
        "soil_benefit": 0.85,
        "market": 0.70,
        "benefits": "Melhora a estrutura do solo",
    },
]


def _clamp01(valor: float) -> float:
    return round(max(0.0, min(1.0, valor)), 2)


def _extrair_sinais_climaticos(
    metricas: Dict[str, Any], prioridades: Optional[Dict[str, Any]] = None
) -> Tuple[float, float, bool]:
    """Calcula oferta hídrica normalizada (0–1), estresse térmico (0–1) e prioridade de água."""
    umidade = metricas.get("avg_soil_moisture_smap")
    if umidade is None:
        umidade = metricas.get("umidade_solo_estimada", 0.30)
    temp = metricas.get("avg_surface_temp_ecostress")
    if temp is None:
        temp = metricas.get("temperatura_media_c", 26.0)
    chuva_dia = metricas.get("avg_precipitation_gpm")
    if chuva_dia is not None:
        chuva_anual = float(chuva_dia) * 365.0
    else:
        chuva_anual = float(metricas.get("precipitacao_estimada_mm", 900.0))

    oferta_hidrica = 0.6 * min(1.0, max(0.0, float(umidade) / 0.35)) + 0.4 * min(
        1.0, max(0.0, chuva_anual / 1200.0)
    )
    estresse_termico = min(1.0, max(0.0, (float(temp) - 28.0) / 12.0))
    prio = prioridades or {}
    agua_escassa = str(prio.get("agua", "")).strip().lower() in {
        "escassa",
        "baixa",
        "limitada",
    } or bool(prio.get("water_conservation") or prio.get("conservacao_agua"))
    return oferta_hidrica, estresse_termico, agua_escassa


def _calcular_rotacoes_fallback_dinamico(
    metricas_geoespaciais: Dict[str, Any],
    prioridades: Dict[str, Any],
) -> List[EstrategiaRotacaoSugerida]:
    """Gera estratégias e score_breakdown dinâmicos quando o CropSimulator falha."""
    oferta_hidrica, estresse_termico, agua_escassa = _extrair_sinais_climaticos(
        metricas_geoespaciais, prioridades
    )
    pesos = (
        {"water": 0.60, "heat": 0.20, "soil": 0.15, "market": 0.05}
        if agua_escassa
        else {"water": 0.45, "heat": 0.25, "soil": 0.20, "market": 0.10}
    )

    resultados: List[EstrategiaRotacaoSugerida] = []
    historico = [
        str(c).strip().lower()
        for c in (prioridades.get("historico_cultivos") or [])
        if str(c).strip()
    ]
    ultima_cultura = historico[-1] if historico else None

    for item in _ROTACOES_BASE_FALLBACK:
        gap = item["water_demand"] - oferta_hidrica
        water_fit = _clamp01(1.0 - max(gap, 0.0) * 1.8)
        heat_fit = _clamp01(1.0 - estresse_termico * (1.0 - item["heat_tolerance"]))
        soil_fit = _clamp01(item["soil_benefit"])
        market_fit = _clamp01(item["market"])
        viability = _clamp01(
            pesos["water"] * water_fit
            + pesos["heat"] * heat_fit
            + pesos["soil"] * soil_fit
            + pesos["market"] * market_fit
        )
        if ultima_cultura:
            primeira_etapa = item["strategy"].split("->")[0].replace("(Atual)", "").strip().lower()
            if ultima_cultura in primeira_etapa:
                viability = _clamp01(viability - 0.12)
            else:
                viability = _clamp01(viability + 0.05)
        water_risk = "high" if gap > 0.15 else ("medium" if gap > -0.10 else "low")
        resultados.append(
            EstrategiaRotacaoSugerida(
                strategy=item["strategy"],
                viability=viability,
                water_risk=water_risk,
                benefits=item["benefits"],
                score_breakdown={
                    "water_fit": water_fit,
                    "heat_fit": heat_fit,
                    "soil_benefit": soil_fit,
                    "market": market_fit,
                },
            )
        )
    return resultados


_SERVICE_CACHE: Dict[str, Tuple[Any, Any]] = {}


def _get_cached_service(
    cache_key: str,
    module_name: str,
    factory: Callable[[Any], Any],
) -> Optional[Any]:
    """Instancia o serviço uma única vez por objeto de módulo (respeita troca via sys.modules)."""
    try:
        mod = importlib.import_module(module_name)
        cached = _SERVICE_CACHE.get(cache_key)
        if cached is not None and cached[0] is mod:
            return cached[1]
        instance = factory(mod)
        _SERVICE_CACHE[cache_key] = (mod, instance)
        return instance
    except Exception:
        return None


def get_nasa_processor(profile: Optional[str] = None) -> Optional[Any]:
    """Provedor de dependência para INASADataProvider (mock ou real via NASA_PROVIDER/profile)."""
    provider_mode = os.getenv("NASA_PROVIDER", "mock").strip().lower() or "mock"
    active_profile = profile if profile is not None else (os.getenv("NASA_MOCK_PROFILE") or None)

    def _build(geo_module: Any) -> Any:
        factory = getattr(geo_module, "get_nasa_data_provider", None)
        if callable(factory):
            if active_profile is not None:
                try:
                    return factory(
                        data_path="data",
                        provider_type=provider_mode,
                        profile=active_profile,
                    )
                except TypeError:
                    return factory(data_path="data", provider_type=provider_mode)
            return factory(data_path="data", provider_type=provider_mode)
        provider_cls = getattr(geo_module, "MockNASADataProvider", None) or getattr(
            geo_module, "NasaDataProcessor"
        )
        if active_profile is not None and active_profile != "real":
            try:
                return provider_cls(data_path="data", profile=active_profile)
            except TypeError:
                return provider_cls(data_path="data")
        return provider_cls(data_path="data")

    cache_key = f"nasa:{provider_mode}:{active_profile or 'default'}"
    return _get_cached_service(cache_key, "backend.services.geospatial", _build)


def get_crop_simulator() -> Optional[Any]:
    """Provedor de dependência para CropSimulator."""
    return _get_cached_service(
        "simulator", "backend.services.ml_models", lambda mod: mod.CropSimulator()
    )


def get_rotation_explainer() -> Optional[Any]:
    """Provedor de dependência para RotationExplainerAgent."""
    return _get_cached_service(
        "explainer",
        "backend.services.llm_agent",
        lambda mod: mod.RotationExplainerAgent(),
    )


def get_gaez_provider() -> Optional[Any]:
    """Provedor de dependência para GAEZDataProvider (FAO GAEZ v5 COG)."""
    return _get_cached_service(
        "gaez",
        "backend.services.gaez_service",
        lambda mod: mod.GAEZDataProvider(data_path="data"),
    )


def _deve_consultar_gaez(
    gaez_provider: Optional[Any],
    perfil_climatico: Optional[str],
    geo_input: Any,
) -> bool:
    if gaez_provider is None or not geo_input:
        return False
    gaez_raw = os.getenv("GAEZ_ENABLED", "").strip().lower()
    if gaez_raw in {"0", "false", "no", "nao", "não", "off"}:
        return False
    if gaez_raw in {"1", "true", "yes", "sim", "on"}:
        return True
    try:
        gaez_mod = importlib.import_module("backend.services.gaez_service")
        real_cls = getattr(gaez_mod, "GAEZDataProvider", None)
        is_custom_cls = real_cls is not None and not isinstance(gaez_provider, real_cls)
        if is_custom_cls or str(getattr(gaez_provider, "data_path", "data")) != "data":
            return True
    except Exception:
        pass
    nasa_real = os.getenv("NASA_PROVIDER", "").strip().lower() == "real"
    return bool(nasa_real or perfil_climatico == "real")


def _extrair_metricas_gaez(
    geo_input: Any,
    prioridades: Dict[str, Any],
    gaez_provider: Optional[Any],
    perfil_climatico: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not _deve_consultar_gaez(gaez_provider, perfil_climatico, geo_input):
        return None
    try:
        res = gaez_provider.extract_gaez_metrics(geo_input, prioridades=prioridades)
        if isinstance(res, dict) and res.get("data_quality") == "gaez_v5_cog":
            return res
    except Exception:
        logger.exception("Falha ao consultar FAO GAEZ v5 na simulação; seguindo sem GAEZ.")
    return None


def _calcular_metricas_fallback(
    coordenadas_poligono: Any, dados_climaticos: Dict[str, Any]
) -> Dict[str, Any]:
    """Calcula resumo geoespacial determinístico a partir do polígono do terreno."""
    coords = coordenadas_poligono if isinstance(coordenadas_poligono, list) else []
    geometria = calcular_geometria_terreno(coords)
    total_vertices = int(geometria["total_vertices"])
    centroide = geometria["localizacao_central"] if total_vertices > 0 else None

    return {
        "origem": "fallback_geoespacial",
        "total_vertices_poligono": total_vertices,
        "area_hectares": float(geometria["area_hectares"]),
        "centroide": centroide,
        "precipitacao_estimada_mm": dados_climaticos.get("precipitacao_mm", 520.0),
        "temperatura_media_c": dados_climaticos.get("temperatura_media_c", 25.5),
        "umidade_solo_estimada": dados_climaticos.get("umidade_solo", 0.42),
    }


def _extrair_metricas_geoespaciais(
    coordenadas_poligono: Any,
    dados_climaticos: Dict[str, Any],
    nasa_processor: Optional[Any],
    perfil_climatico: Optional[str] = None,
) -> Tuple[Dict[str, Any], bool]:
    """Consulta o serviço geoespacial da NASA injetado com fallback seguro."""
    fallback = _calcular_metricas_fallback(coordenadas_poligono, dados_climaticos)
    if perfil_climatico is not None:
        fallback["perfil_climatico"] = perfil_climatico

    if nasa_processor is not None:
        try:
            if perfil_climatico is not None:
                try:
                    metricas = nasa_processor.extract_field_metrics(
                        coordenadas_poligono,
                        dataset=None,
                        profile=perfil_climatico,
                    )
                except TypeError:
                    metricas = nasa_processor.extract_field_metrics(
                        coordenadas_poligono, dataset=None
                    )
            else:
                metricas = nasa_processor.extract_field_metrics(
                    coordenadas_poligono, dataset=None
                )
            if isinstance(metricas, dict) and metricas:
                resultado = {
                    **fallback,
                    **{k: v for k, v in metricas.items() if v is not None},
                    "origem": "nasa_geospatial_service",
                }
                if perfil_climatico is not None:
                    resultado["perfil_climatico"] = perfil_climatico
                return resultado, False
        except Exception:
            logger.exception("Falha em servico externo da simulacao; usando fallback")

    return fallback, True


def _simular_estrategias_rotacao(
    metricas_geoespaciais: Dict[str, Any],
    prioridades: Dict[str, Any],
    crop_simulator: Optional[Any],
) -> Tuple[List[EstrategiaRotacaoSugerida], bool]:
    """Obtém as estratégias de rotação sugeridas via CropSimulator."""
    if crop_simulator is not None:
        try:
            estrategias = crop_simulator.simulate_rotation_strategies(
                metricas_geoespaciais, prioridades
            )
            if isinstance(estrategias, list) and estrategias and all(
                isinstance(item, dict) and "strategy" in item for item in estrategias
            ):
                return (
                    [
                        EstrategiaRotacaoSugerida(
                            strategy=str(item["strategy"]),
                            viability=float(item.get("viability", 0.85)),
                            water_risk=str(item.get("water_risk", "low")),
                            benefits=(
                                str(item["benefits"])
                                if item.get("benefits") is not None
                                else None
                            ),
                            score_breakdown=(
                                item.get("score_breakdown")
                                if isinstance(item.get("score_breakdown"), dict)
                                else None
                            ),
                        )
                        for item in estrategias
                    ],
                    False,
                )
        except Exception:
            logger.exception("Falha em servico externo da simulacao; usando fallback")

    return _calcular_rotacoes_fallback_dinamico(metricas_geoespaciais, prioridades), True


def _simular_viabilidade_ml(
    soil_data: Dict[str, Any],
    climate_data: Dict[str, Any],
    crop_requirements: Dict[str, Any],
    crop_simulator: Optional[Any],
) -> Tuple[float, str, bool]:
    """Executa predição de viabilidade no CropSimulator injetado com fallback dinâmico."""
    if crop_simulator is not None:
        try:
            resultado = crop_simulator.predict_rotation_viability(
                soil_data, climate_data, crop_requirements
            )
            if isinstance(resultado, dict):
                score = float(resultado.get("viability_score", 0.85))
                risk = str(resultado.get("water_risk", "low"))
                return score, risk, False
        except Exception:
            logger.exception("Falha em servico externo da simulacao; usando fallback")

    prioridades = (
        soil_data.get("prioridades_terreno")
        if isinstance(soil_data, dict)
        else None
    )
    oferta_hidrica, estresse_termico, agua_escassa = _extrair_sinais_climaticos(
        climate_data, prioridades if isinstance(prioridades, dict) else None
    )
    consumo = float(crop_requirements.get("consumo_agua_mm", 450.0))
    demanda_agua = min(1.0, max(0.0, consumo / 700.0))
    gap = demanda_agua - oferta_hidrica
    water_fit = _clamp01(1.0 - max(gap, 0.0) * 1.8)
    heat_fit = _clamp01(1.0 - estresse_termico * 0.4)
    peso_agua = 0.60 if agua_escassa else 0.45
    score = _clamp01(peso_agua * water_fit + (1.0 - peso_agua) * heat_fit)
    risk = "high" if gap > 0.15 else ("medium" if gap > -0.10 else "low")
    return score, risk, True


def _resolver_cultura_principal(
    payload: SimulacaoRequest,
    db: Session,
    rotacoes_sugeridas: List[EstrategiaRotacaoSugerida],
) -> Tuple[str, float, int]:
    """Resolve nome, consumo de água (mm) e ciclo (dias) da cultura/estratégia principal."""
    if payload.cultura_id is not None:
        cultura = (
            db.query(models.Cultura)
            .filter(models.Cultura.id == payload.cultura_id)
            .first()
        )
        if not cultura:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cultura não encontrada",
            )
        return (
            cultura.nome,
            float(cultura.consumo_agua_mm),
            int(cultura.tempo_colheita_dias),
        )

    if payload.nome_cultura and payload.nome_cultura.strip():
        nome_limpo = payload.nome_cultura.strip()
        cultura = (
            db.query(models.Cultura)
            .filter(func.lower(models.Cultura.nome) == nome_limpo.lower())
            .first()
        )
        if cultura:
            return (
                cultura.nome,
                float(cultura.consumo_agua_mm),
                int(cultura.tempo_colheita_dias),
            )
        return nome_limpo, 450.0, 90

    melhor_estrategia = max(rotacoes_sugeridas, key=lambda item: item.viability)
    return melhor_estrategia.strategy, 420.0, 95


def _montar_beneficios_e_riscos(
    nome_cultura: str,
    consumo_agua_mm: float,
    water_risk: str,
    prioridades: Dict[str, Any],
    culturas_rotacao: List[str],
) -> Tuple[List[str], List[str]]:
    """Contextualiza benefícios e riscos agronômicos da simulação."""
    beneficios = [
        f"Adequação do ciclo de {nome_cultura} ao planejamento da propriedade",
        "Aproveitamento dos dados ambientais para manejo preventivo de recursos",
    ]
    if culturas_rotacao:
        beneficios.append(
            f"Diversificação produtiva com rotação envolvendo {', '.join(culturas_rotacao)}"
        )

    riscos: List[str] = []
    agua_prioridade = str(prioridades.get("agua", "")).lower()
    if agua_prioridade in {"escassa", "baixa", "limitada"} and consumo_agua_mm >= 400:
        riscos.append(
            f"Terreno com prioridade hídrica '{agua_prioridade}' frente ao consumo estimado de {consumo_agua_mm:.0f} mm"
        )
    if water_risk.lower() in {"medium", "high", "alto", "medio", "critico"}:
        riscos.append(
            f"Risco hídrico classificado como '{water_risk}' para o cenário climático analisado"
        )
    if not riscos:
        riscos.append(
            "Variações climáticas inesperadas podem exigir ajustes dinâmicos no calendário de manejo"
        )

    return beneficios, riscos


def _gerar_explicacao_ia(
    nome_cultura: str,
    beneficios: List[str],
    riscos: List[str],
    viability_score: float,
    water_risk: str,
    rotation_explainer: Optional[Any],
) -> Tuple[str, bool]:
    """Chama RotationExplainerAgent injetado com fallback determinístico em português."""
    beneficios_txt = "; ".join(beneficios)
    riscos_txt = "; ".join(riscos)

    if rotation_explainer is not None:
        try:
            resposta = rotation_explainer.generate_explanation(
                crop=nome_cultura,
                benefits=beneficios_txt,
                risks=riscos_txt,
            )
            conteudo = (
                resposta.content if hasattr(resposta, "content") else str(resposta)
            )
            if conteudo and conteudo.strip():
                return conteudo.strip(), False
        except Exception:
            logger.exception("Falha em servico externo da simulacao; usando fallback")

    return (
        f"A simulação para a cultura {nome_cultura} apresentou índice de viabilidade de "
        f"{viability_score:.0%} e risco hídrico '{water_risk}'. "
        f"Principais benefícios observados: {beneficios_txt}. "
        f"Pontos de atenção e riscos: {riscos_txt}. "
        f"{_DISCLAIMER_PADRAO}",
        True,
    )


def _garantir_disclaimer(texto: str) -> str:
    limpo = str(texto or "").strip()
    if not limpo:
        return _DISCLAIMER_PADRAO
    if "decisão final" not in limpo.lower():
        return f"{limpo}\n\n{_DISCLAIMER_PADRAO}"
    return limpo


def _gerar_explicacoes_estrategias(
    rotacoes_sugeridas: List[EstrategiaRotacaoSugerida],
    metricas_geoespaciais: Dict[str, Any],
    prioridades: Dict[str, Any],
    rotation_explainer: Optional[Any],
) -> Tuple[List[EstrategiaRotacaoSugerida], bool]:
    """Popula `explicacao` individual para cada estratégia via explain_strategies (A4) com fallback."""
    if not rotacoes_sugeridas:
        return rotacoes_sugeridas, False

    if rotation_explainer is not None and hasattr(rotation_explainer, "explain_strategies"):
        try:
            res = rotation_explainer.explain_strategies(
                strategies=rotacoes_sugeridas,
                field_metrics=metricas_geoespaciais,
                farmer_priorities=prioridades,
            )
            if (
                isinstance(res, list)
                and len(res) == len(rotacoes_sugeridas)
                and all(isinstance(item, str) and item.strip() for item in res)
            ):
                for estrategia, texto in zip(rotacoes_sugeridas, res):
                    estrategia.explicacao = _garantir_disclaimer(texto)
                return rotacoes_sugeridas, False
        except Exception:
            logger.exception("Falha em explain_strategies; usando fallback por estratégia")

    risco_pt = {"low": "baixo", "medium": "médio", "high": "alto"}
    for estrategia in rotacoes_sugeridas:
        risco = risco_pt.get(estrategia.water_risk.lower(), estrategia.water_risk)
        beneficio = estrategia.benefits or "manutenção produtiva da área"
        texto = (
            f"A opção {estrategia.strategy} teve viabilidade estimada de "
            f"{round(estrategia.viability * 100)}% e risco de falta de água {risco}. "
            f"Benefício prático: {beneficio}."
        )
        estrategia.explicacao = _garantir_disclaimer(texto)
    return rotacoes_sugeridas, True


def _buscar_rotacoes_preferenciais(
    db: Session,
    terreno_id: Optional[int],
    usuario_id: Optional[int],
) -> List[Dict[str, Any]]:
    """Busca rotações preferenciais customizadas aplicáveis ao terreno/produtor."""
    query = db.query(models.RotacaoProdutor).filter(
        models.RotacaoProdutor.preferencial.is_(True),
        models.RotacaoProdutor.is_seed.is_(False),
    )
    if terreno_id is not None:
        filtros = [models.RotacaoProdutor.terreno_id == terreno_id]
        if usuario_id is not None:
            filtros.append(
                (models.RotacaoProdutor.terreno_id.is_(None))
                & (models.RotacaoProdutor.usuario_id == usuario_id)
            )
        filtros.append(
            (models.RotacaoProdutor.terreno_id.is_(None))
            & (models.RotacaoProdutor.usuario_id.is_(None))
        )
        query = query.filter(or_(*filtros))
    else:
        query = query.filter(
            models.RotacaoProdutor.terreno_id.is_(None),
            models.RotacaoProdutor.usuario_id.is_(None),
        )

    rotacoes = query.order_by(models.RotacaoProdutor.id.desc()).all()
    if not rotacoes:
        return []

    culturas_db = db.query(models.Cultura).all()
    por_nome = {c.nome.strip().lower(): c for c in culturas_db if c.nome}

    preferenciais: List[Dict[str, Any]] = []
    for rotacao in rotacoes:
        lista_culturas = rotacao.culturas if isinstance(rotacao.culturas, list) else []
        consumos: List[float] = []
        ciclos: List[int] = []
        for nome_cult in lista_culturas:
            c_obj = por_nome.get(str(nome_cult).strip().lower())
            if c_obj is not None:
                consumos.append(float(c_obj.consumo_agua_mm))
                ciclos.append(int(c_obj.tempo_colheita_dias))

        media_consumo = sum(consumos) / len(consumos) if consumos else 385.0
        media_ciclo = sum(ciclos) / len(ciclos) if ciclos else 90.0
        preferenciais.append(
            {
                "strategy": rotacao.nome,
                "culturas": lista_culturas,
                "water_demand": round(max(0.1, min(1.0, media_consumo / 700.0)), 3),
                "heat_tolerance": round(max(0.2, min(0.95, 0.8 - (media_ciclo / 365.0) * 0.3)), 3),
                "soil_benefit": 0.75,
                "market": 0.70,
                "benefits": rotacao.beneficios or "Rotação preferencial cadastrada pelo produtor",
            }
        )

    return preferenciais


def _processar_simulacao(
    payload: SimulacaoRequest,
    db: Session,
    nasa_processor: Optional[Any],
    crop_simulator: Optional[Any],
    rotation_explainer: Optional[Any],
    gaez_provider: Optional[Any] = None,
) -> SimulacaoResponse:
    terreno_id_resp: Optional[int] = None
    usuario_id_terreno: Optional[int] = None
    nome_propriedade = payload.nome_propriedade or "Terreno Simulado"
    coordenadas_poligono: Any = payload.coordenadas_poligono or []
    localizacao_terreno: Any = None
    prioridades_terreno: Dict[str, Any] = {}

    if payload.terreno_id is not None:
        terreno = (
            db.query(models.Terreno)
            .filter(models.Terreno.id == payload.terreno_id)
            .first()
        )
        if not terreno:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Terreno não encontrado",
            )
        terreno_id_resp = terreno.id
        usuario_id_terreno = terreno.usuario_id
        nome_propriedade = payload.nome_propriedade or terreno.nome_propriedade
        localizacao_terreno = terreno.localizacao_central
        if payload.coordenadas_poligono is None:
            coordenadas_poligono = terreno.coordenadas_poligono
        if isinstance(terreno.prioridades, dict):
            prioridades_terreno = terreno.prioridades

    dados_climaticos_req = payload.dados_climaticos or {}
    prioridades_finais = {**prioridades_terreno, **(payload.prioridades or {})}
    if "rotacoes_preferenciais" not in prioridades_finais:
        rotacoes_pref = _buscar_rotacoes_preferenciais(
            db, terreno_id=terreno_id_resp, usuario_id=usuario_id_terreno
        )
        if rotacoes_pref:
            prioridades_finais["rotacoes_preferenciais"] = rotacoes_pref

    dados_solo = {
        "prioridades_terreno": prioridades_finais,
        **(payload.dados_solo or {}),
    }

    perfil_raw = (
        payload.perfil_climatico
        if payload.perfil_climatico is not None
        else dados_climaticos_req.get("perfil_climatico")
        or prioridades_finais.get("perfil_climatico")
    )
    perfil_climatico: Optional[str] = None
    if perfil_raw is not None:
        try:
            perfil_climatico = normalize_climate_profile(str(perfil_raw), allow_real=True)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc

    active_nasa_processor = nasa_processor
    if perfil_climatico == "real" and nasa_processor is not None:
        try:
            geo_mod = importlib.import_module("backend.services.geospatial")
            mock_cls = getattr(geo_mod, "MockNASADataProvider", None)
            if mock_cls is not None and isinstance(nasa_processor, mock_cls):
                active_nasa_processor = get_nasa_processor(profile="real")
        except Exception:
            pass

    metricas_geoespaciais, geo_fallback = _extrair_metricas_geoespaciais(
        coordenadas_poligono,
        dados_climaticos_req,
        active_nasa_processor,
        perfil_climatico=perfil_climatico,
    )
    geo_input_gaez = (
        coordenadas_poligono
        or metricas_geoespaciais.get("centroide")
        or localizacao_terreno
    )
    gaez_metrics = _extrair_metricas_gaez(
        geo_input_gaez,
        prioridades=prioridades_finais,
        gaez_provider=gaez_provider,
        perfil_climatico=perfil_climatico,
    )
    if gaez_metrics is not None:
        metricas_geoespaciais["gaez"] = gaez_metrics

    tipo_solo = (payload.dados_solo or {}).get("tipo_solo") or prioridades_finais.get("tipo_solo")
    if tipo_solo:
        metricas_geoespaciais["tipo_solo"] = tipo_solo

    if terreno_id_resp is not None:
        persistir_metricas_terreno(
            db=db,
            terreno_id=terreno_id_resp,
            field_metrics=metricas_geoespaciais,
            origem=str(metricas_geoespaciais.get("origem") or "nasa_geospatial_service"),
        )
    prioridades_efetivas = dict(prioridades_finais)
    if payload.historico_cultivos:
        prioridades_efetivas["historico_cultivos"] = payload.historico_cultivos

    rotacoes_sugeridas, estrategias_fallback = _simular_estrategias_rotacao(
        metricas_geoespaciais, prioridades_efetivas, crop_simulator
    )

    nome_cultura, consumo_agua_mm, tempo_colheita_dias = _resolver_cultura_principal(
        payload, db, rotacoes_sugeridas
    )

    climate_data = {**metricas_geoespaciais, **dados_climaticos_req}
    crop_requirements = {
        "cultura": nome_cultura,
        "consumo_agua_mm": consumo_agua_mm,
        "tempo_colheita_dias": tempo_colheita_dias,
    }
    viability_score, water_risk, viabilidade_fallback = _simular_viabilidade_ml(
        dados_solo, climate_data, crop_requirements, crop_simulator
    )

    culturas_rotacao = [
        c.strip() for c in (payload.culturas_rotacao or []) if c and c.strip()
    ]
    beneficios, riscos = _montar_beneficios_e_riscos(
        nome_cultura=nome_cultura,
        consumo_agua_mm=consumo_agua_mm,
        water_risk=water_risk,
        prioridades=prioridades_finais,
        culturas_rotacao=culturas_rotacao,
    )
    explicacao, ia_fallback = _gerar_explicacao_ia(
        nome_cultura=nome_cultura,
        beneficios=beneficios,
        riscos=riscos,
        viability_score=viability_score,
        water_risk=water_risk,
        rotation_explainer=rotation_explainer,
    )
    rotacoes_sugeridas, estrategias_ia_fallback = _gerar_explicacoes_estrategias(
        rotacoes_sugeridas=rotacoes_sugeridas,
        metricas_geoespaciais=metricas_geoespaciais,
        prioridades=prioridades_finais,
        rotation_explainer=rotation_explainer,
    )

    plano_rotacao = [
        EtapaRotacaoSimulada(
            ordem=1,
            cultura=nome_cultura,
            duracao_dias=tempo_colheita_dias,
            consumo_agua_estimado_mm=consumo_agua_mm,
            viabilidade_score=viability_score,
            risco_hidrico=water_risk,
        )
    ]

    etapas_fallback = False
    for idx, cultura_nome in enumerate(culturas_rotacao, start=2):
        cultura_db = (
            db.query(models.Cultura)
            .filter(func.lower(models.Cultura.nome) == cultura_nome.lower())
            .first()
        )
        etapa_consumo = float(cultura_db.consumo_agua_mm) if cultura_db else 380.0
        etapa_duracao = int(cultura_db.tempo_colheita_dias) if cultura_db else 75
        etapa_score, etapa_risco, etapa_fb = _simular_viabilidade_ml(
            dados_solo,
            climate_data,
            {
                "cultura": cultura_nome,
                "consumo_agua_mm": etapa_consumo,
                "tempo_colheita_dias": etapa_duracao,
            },
            crop_simulator,
        )
        etapas_fallback = etapas_fallback or etapa_fb
        plano_rotacao.append(
            EtapaRotacaoSimulada(
                ordem=idx,
                cultura=cultura_db.nome if cultura_db else cultura_nome,
                duracao_dias=etapa_duracao,
                consumo_agua_estimado_mm=etapa_consumo,
                viabilidade_score=etapa_score,
                risco_hidrico=etapa_risco,
            )
        )

    flags_fallback = [
        geo_fallback,
        estrategias_fallback,
        viabilidade_fallback,
        ia_fallback,
        estrategias_ia_fallback,
    ]
    fallback_usado = any(flags_fallback) or etapas_fallback
    if not fallback_usado:
        origem = "servicos_ia_nasa"
    elif all(flags_fallback):
        origem = "fallback"
    else:
        origem = "misto_com_fallback"

    return SimulacaoResponse(
        terreno_id=terreno_id_resp,
        nome_propriedade=nome_propriedade,
        cultura_principal=nome_cultura,
        viability_score=viability_score,
        water_risk=water_risk,
        tempo_colheita_dias=tempo_colheita_dias,
        consumo_agua_mm=consumo_agua_mm,
        metricas_geoespaciais=metricas_geoespaciais,
        beneficios_esperados=beneficios,
        riscos_identificados=riscos,
        explicacao_ia=explicacao,
        explicacao_textual=explicacao,
        origem=origem,
        fallback_usado=fallback_usado,
        rotacoes_sugeridas=rotacoes_sugeridas,
        plano_rotacao=plano_rotacao,
    )


@router.post("/", response_model=SimulacaoResponse)
@router.post("/simular-rotacao", response_model=SimulacaoResponse)
def executar_simulacao(
    payload: SimulacaoRequest,
    db: Session = Depends(get_db),
    nasa_processor: Optional[Any] = Depends(get_nasa_processor),
    crop_simulator: Optional[Any] = Depends(get_crop_simulator),
    rotation_explainer: Optional[Any] = Depends(get_rotation_explainer),
    gaez_provider: Optional[Any] = Depends(get_gaez_provider),
) -> SimulacaoResponse:
    """Recebe parâmetros do frontend, integra serviços geoespaciais/ML/LLM e retorna a simulação."""
    return _processar_simulacao(
        payload=payload,
        db=db,
        nasa_processor=nasa_processor,
        crop_simulator=crop_simulator,
        rotation_explainer=rotation_explainer,
        gaez_provider=gaez_provider,
    )


@simular_rotacao_router.post("/simular-rotacao", response_model=SimulacaoResponse)
def simular_rotacao(
    payload: SimulacaoRequest,
    db: Session = Depends(get_db),
    nasa_processor: Optional[Any] = Depends(get_nasa_processor),
    crop_simulator: Optional[Any] = Depends(get_crop_simulator),
    rotation_explainer: Optional[Any] = Depends(get_rotation_explainer),
    gaez_provider: Optional[Any] = Depends(get_gaez_provider),
) -> SimulacaoResponse:
    """Endpoint direto /api/v1/simular-rotacao para orquestração de simulação e explicação IA."""
    return _processar_simulacao(
        payload=payload,
        db=db,
        nasa_processor=nasa_processor,
        crop_simulator=crop_simulator,
        rotation_explainer=rotation_explainer,
        gaez_provider=gaez_provider,
    )

from typing import Any, Dict, List, Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.database import get_db
from backend.schemas.simulacao import (
    EtapaRotacaoSimulada,
    SimulacaoRequest,
    SimulacaoResponse,
)

router = APIRouter(prefix="/simulacoes", tags=["Simulador (M3)"])


def _resolver_cultura_principal(
    payload: SimulacaoRequest, db: Session
) -> Tuple[str, float, int]:
    """Resolve nome, consumo de água (mm) e ciclo (dias) da cultura principal."""
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
        return cultura.nome, float(cultura.consumo_agua_mm), int(cultura.tempo_colheita_dias)

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

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Informe cultura_id ou nome_cultura para a simulação",
    )


def _calcular_metricas_fallback(
    coordenadas_poligono: Any, dados_climaticos: Dict[str, Any]
) -> Dict[str, Any]:
    """Calcula resumo geoespacial determinístico a partir do polígono do terreno."""
    coords = coordenadas_poligono if isinstance(coordenadas_poligono, list) else []
    latitudes = [
        float(c["lat"]) for c in coords if isinstance(c, dict) and "lat" in c
    ]
    longitudes = [
        float(c["lng"]) for c in coords if isinstance(c, dict) and "lng" in c
    ]
    centroide = None
    if latitudes and longitudes:
        centroide = {
            "lat": round(sum(latitudes) / len(latitudes), 6),
            "lng": round(sum(longitudes) / len(longitudes), 6),
        }

    return {
        "origem": "fallback_geoespacial",
        "total_vertices_poligono": len(coords),
        "centroide": centroide,
        "precipitacao_estimada_mm": dados_climaticos.get("precipitacao_mm", 520.0),
        "temperatura_media_c": dados_climaticos.get("temperatura_media_c", 25.5),
        "umidade_solo_estimada": dados_climaticos.get("umidade_solo", 0.42),
    }


def _extrair_metricas_geoespaciais(
    coordenadas_poligono: Any, dados_climaticos: Dict[str, Any]
) -> Dict[str, Any]:
    """Consulta o serviço geoespacial da NASA com fallback seguro."""
    try:
        from backend.services.geospatial import NasaDataProcessor

        processor = NasaDataProcessor(data_path="data/nasa")
        metricas = processor.extract_field_metrics(coordenadas_poligono, dataset=None)
        if isinstance(metricas, dict) and metricas:
            return {
                "origem": "nasa_geospatial_service",
                **metricas,
            }
    except Exception:
        pass

    return _calcular_metricas_fallback(coordenadas_poligono, dados_climaticos)


def _simular_viabilidade_ml(
    soil_data: Dict[str, Any],
    climate_data: Dict[str, Any],
    crop_requirements: Dict[str, Any],
) -> Tuple[float, str]:
    """Executa predição de viabilidade no CropSimulator com fallback seguro."""
    try:
        from backend.services.ml_models import CropSimulator

        simulator = CropSimulator()
        resultado = simulator.predict_rotation_viability(
            soil_data, climate_data, crop_requirements
        )
        if isinstance(resultado, dict):
            score = float(resultado.get("viability_score", 0.85))
            risk = str(resultado.get("water_risk", "low"))
            return score, risk
    except Exception:
        pass

    return 0.85, "low"


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
) -> str:
    """Chama RotationExplainerAgent com fallback determinístico em português."""
    beneficios_txt = "; ".join(beneficios)
    riscos_txt = "; ".join(riscos)

    try:
        from backend.services.llm_agent import RotationExplainerAgent

        agent = RotationExplainerAgent()
        resposta = agent.generate_explanation(
            crop=nome_cultura,
            benefits=beneficios_txt,
            risks=riscos_txt,
        )
        conteudo = resposta.content if hasattr(resposta, "content") else str(resposta)
        if conteudo and conteudo.strip():
            return conteudo.strip()
    except Exception:
        pass

    return (
        f"A simulação para a cultura {nome_cultura} apresentou índice de viabilidade de "
        f"{viability_score:.0%} e risco hídrico '{water_risk}'. "
        f"Principais benefícios observados: {beneficios_txt}. "
        f"Pontos de atenção e riscos: {riscos_txt}. "
        "Estes indicadores servem como apoio técnico baseado em dados, mas a decisão final "
        "sobre o plantio e o manejo da lavoura é sempre sua."
    )


@router.post("/", response_model=SimulacaoResponse)
def executar_simulacao(
    payload: SimulacaoRequest, db: Session = Depends(get_db)
) -> SimulacaoResponse:
    """Recebe parâmetros do frontend, integra serviços geoespaciais/ML/LLM e retorna a simulação."""
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

    nome_cultura, consumo_agua_mm, tempo_colheita_dias = _resolver_cultura_principal(
        payload, db
    )

    dados_climaticos_req = payload.dados_climaticos or {}
    prioridades_terreno = (
        terreno.prioridades if isinstance(terreno.prioridades, dict) else {}
    )
    dados_solo = payload.dados_solo or {"prioridades_terreno": prioridades_terreno}

    metricas_geoespaciais = _extrair_metricas_geoespaciais(
        terreno.coordenadas_poligono, dados_climaticos_req
    )

    climate_data = {**metricas_geoespaciais, **dados_climaticos_req}
    crop_requirements = {
        "cultura": nome_cultura,
        "consumo_agua_mm": consumo_agua_mm,
        "tempo_colheita_dias": tempo_colheita_dias,
    }
    viability_score, water_risk = _simular_viabilidade_ml(
        dados_solo, climate_data, crop_requirements
    )

    culturas_rotacao = [
        c.strip() for c in (payload.culturas_rotacao or []) if c and c.strip()
    ]
    beneficios, riscos = _montar_beneficios_e_riscos(
        nome_cultura=nome_cultura,
        consumo_agua_mm=consumo_agua_mm,
        water_risk=water_risk,
        prioridades=prioridades_terreno,
        culturas_rotacao=culturas_rotacao,
    )
    explicacao_ia = _gerar_explicacao_ia(
        nome_cultura=nome_cultura,
        beneficios=beneficios,
        riscos=riscos,
        viability_score=viability_score,
        water_risk=water_risk,
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

    for idx, cultura_nome in enumerate(culturas_rotacao, start=2):
        cultura_db = (
            db.query(models.Cultura)
            .filter(func.lower(models.Cultura.nome) == cultura_nome.lower())
            .first()
        )
        etapa_consumo = float(cultura_db.consumo_agua_mm) if cultura_db else 380.0
        etapa_duracao = int(cultura_db.tempo_colheita_dias) if cultura_db else 75
        etapa_score, etapa_risco = _simular_viabilidade_ml(
            dados_solo,
            climate_data,
            {
                "cultura": cultura_nome,
                "consumo_agua_mm": etapa_consumo,
                "tempo_colheita_dias": etapa_duracao,
            },
        )
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

    return SimulacaoResponse(
        terreno_id=terreno.id,
        nome_propriedade=terreno.nome_propriedade,
        cultura_principal=nome_cultura,
        viability_score=viability_score,
        water_risk=water_risk,
        tempo_colheita_dias=tempo_colheita_dias,
        consumo_agua_mm=consumo_agua_mm,
        metricas_geoespaciais=metricas_geoespaciais,
        beneficios_esperados=beneficios,
        riscos_identificados=riscos,
        explicacao_ia=explicacao_ia,
        plano_rotacao=plano_rotacao,
    )

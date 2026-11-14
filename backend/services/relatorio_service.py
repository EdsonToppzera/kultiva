from datetime import date, timedelta
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.db import models
from backend.schemas.relatorio import (
    AdaptacaoAtividadeItem,
    AdaptacoesTerrenoResumo,
    AlertaResumoRelatorio,
    MetricaHistoricaResponse,
    RelatorioAdaptacaoResponse,
    ResumoClimaticoRelatorio,
    VigorTerrenoResumo,
    VulnerabilidadeTerrenoResumo,
)
from backend.services.metrics_service import (
    consultar_serie_historica_terreno,
    persistir_metricas_terreno,
)

logger = logging.getLogger(__name__)


def resolver_periodo_relatorio(
    data_inicio: Optional[date],
    data_fim: Optional[date],
) -> Tuple[date, date]:
    fim = data_fim or date.today()
    inicio = data_inicio or (fim - timedelta(days=30))
    if inicio > fim:
        raise ValueError("A data_inicio deve ser menor ou igual à data_fim.")
    return inicio, fim


def _extrair_field_metrics_seguro(
    terreno: models.Terreno,
    nasa_processor: Optional[Any],
) -> Dict[str, Any]:
    if nasa_processor is not None:
        try:
            metricas = nasa_processor.extract_field_metrics(
                terreno.coordenadas_poligono, dataset=None
            )
            if isinstance(metricas, dict) and metricas:
                return {**metricas, "origem": metricas.get("origem") or "nasa_geospatial_service"}
        except Exception as exc:
            logger.warning(
                "Falha ao extrair field_metrics sob demanda para terreno %s: %s",
                terreno.id,
                exc,
            )

    return {
        "origem": "fallback_geoespacial",
        "data_quality": "fallback",
        "avg_soil_moisture_smap": 0.28,
        "avg_surface_temp_ecostress": 27.5,
        "avg_precipitation_gpm": 3.2,
        "is_bare_field_period": False,
        "time_series": [],
    }


def _calcular_vigor(
    umidade_media: float,
    temp_media: float,
    precip_media: float,
    dias_solo_exposto: int,
    total_medicoes: int,
    alertas_graves: int,
    serie: List[models.MetricaHistoricaTerreno],
) -> VigorTerrenoResumo:
    ind_hidrico = max(0.0, min(1.0, umidade_media / 0.35))
    ind_termico = 1.0 - max(0.0, min(1.0, (temp_media - 28.0) / 14.0))
    fator_chuva = 1.0 if precip_media >= 1.5 else (0.7 if precip_media >= 0.5 else 0.45)
    penalidade_solo_exposto = 0.25 * (dias_solo_exposto / max(1, total_medicoes))
    penalidade_alertas = min(0.20, 0.05 * alertas_graves)

    indice = 0.50 * ind_hidrico + 0.35 * ind_termico + 0.15 * fator_chuva
    indice = round(max(0.0, min(1.0, indice - penalidade_solo_exposto - penalidade_alertas)), 2)

    if indice >= 0.70:
        classificacao = "alto"
        descricao = "Condições favoráveis de umidade e temperatura para o desenvolvimento da lavoura."
    elif indice >= 0.45:
        classificacao = "moderado"
        descricao = "Vigor intermediário; recomenda-se atenção à reposição hídrica e cobertura do solo."
    else:
        classificacao = "baixo"
        descricao = "Estresse hídrico ou térmico elevado no período; priorize proteção do solo e irrigação."

    tendencia = "estavel"
    if len(serie) >= 2:
        delta_umidade = serie[-1].soil_moisture - serie[0].soil_moisture
        if delta_umidade > 0.03:
            tendencia = "melhora"
        elif delta_umidade < -0.03:
            tendencia = "queda"

    return VigorTerrenoResumo(
        indice=indice,
        classificacao=classificacao,
        tendencia=tendencia,
        descricao=descricao,
    )


def _calcular_vulnerabilidade(
    umidade_media: float,
    temp_media: float,
    dias_solo_exposto: int,
    total_medicoes: int,
    alertas_periodo: List[models.AlertaClimatico],
    prioridades: Dict[str, Any],
) -> VulnerabilidadeTerrenoResumo:
    deficit_hidrico = max(0.0, min(1.0, (0.28 - umidade_media) / 0.28))
    excesso_termico = max(0.0, min(1.0, (temp_media - 30.0) / 15.0))
    peso_alertas = min(1.0, len(alertas_periodo) * 0.25)
    fator_bare = dias_solo_exposto / max(1, total_medicoes)

    agua_escassa = str((prioridades or {}).get("agua", "")).strip().lower() in {
        "escassa",
        "baixa",
        "limitada",
    }
    adicional_hidrico = 0.08 if agua_escassa and umidade_media < 0.25 else 0.0

    indice = (
        0.35 * deficit_hidrico
        + 0.25 * excesso_termico
        + 0.25 * peso_alertas
        + 0.15 * fator_bare
        + adicional_hidrico
    )
    indice = round(max(0.0, min(1.0, indice)), 2)

    if indice >= 0.75:
        nivel = "critica"
    elif indice >= 0.50:
        nivel = "alta"
    elif indice >= 0.25:
        nivel = "media"
    else:
        nivel = "baixa"

    fatores: List[str] = []
    if umidade_media < 0.20:
        fatores.append(f"Umidade média do solo baixa ({umidade_media:.3f} m³/m³)")
    if temp_media >= 32.0:
        fatores.append(f"Temperatura média de superfície elevada ({temp_media:.1f} °C)")
    if dias_solo_exposto > 0:
        fatores.append(f"{dias_solo_exposto} medição(ões) com solo exposto detectado")
    if alertas_periodo:
        fatores.append(f"{len(alertas_periodo)} alerta(s) climático(s) registrado(s) no período")
    if agua_escassa:
        fatores.append("Propriedade sinalizada com prioridade hídrica escassa")
    if not fatores:
        fatores.append("Sem fatores críticos relevantes no período analisado")

    eventos_criticos = sorted(
        {
            a.tipo_evento
            for a in alertas_periodo
            if str(a.severidade).lower() in {"alta", "critica"}
        }
    )

    return VulnerabilidadeTerrenoResumo(
        indice=indice,
        nivel=nivel,
        total_alertas_periodo=len(alertas_periodo),
        eventos_criticos=eventos_criticos,
        fatores_risco=fatores,
    )


def gerar_relatorio_terreno(
    db: Session,
    terreno: models.Terreno,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
    nasa_processor: Optional[Any] = None,
) -> RelatorioAdaptacaoResponse:
    periodo_inicio, periodo_fim = resolver_periodo_relatorio(data_inicio, data_fim)

    serie = consultar_serie_historica_terreno(
        db=db,
        terreno_id=terreno.id,
        data_inicio=periodo_inicio,
        data_fim=periodo_fim,
    )
    origem_dados = "historico_persistido"

    if not serie:
        field_metrics = _extrair_field_metrics_seguro(terreno, nasa_processor)
        persistir_metricas_terreno(
            db=db,
            terreno_id=terreno.id,
            field_metrics=field_metrics,
            origem=str(field_metrics.get("origem") or "nasa_geospatial_service"),
            data_referencia=periodo_fim,
        )
        serie = consultar_serie_historica_terreno(
            db=db,
            terreno_id=terreno.id,
            data_inicio=periodo_inicio,
            data_fim=periodo_fim,
        )
        # Caso o time_series do provider mockado esteja fora do intervalo pedido,
        # grava também um snapshot de referência em `periodo_fim` com as médias extraídas.
        if not serie:
            resumo_snapshot = {k: v for k, v in field_metrics.items() if k != "time_series"}
            persistir_metricas_terreno(
                db=db,
                terreno_id=terreno.id,
                field_metrics=resumo_snapshot,
                origem=str(field_metrics.get("origem") or "nasa_geospatial_service"),
                data_referencia=periodo_fim,
            )
            serie = consultar_serie_historica_terreno(
                db=db,
                terreno_id=terreno.id,
                data_inicio=periodo_inicio,
                data_fim=periodo_fim,
            )
        origem_dados = "field_metrics_sob_demanda"

    total_medicoes = len(serie)
    umidades = [m.soil_moisture for m in serie]
    temps = [m.surface_temp_c for m in serie]
    precips = [m.precipitation_mm for m in serie]
    dias_solo_exposto = sum(1 for m in serie if m.is_bare_field_period)

    umidade_media = round(sum(umidades) / total_medicoes, 4) if total_medicoes else 0.0
    umidade_min = round(min(umidades), 4) if total_medicoes else 0.0
    umidade_max = round(max(umidades), 4) if total_medicoes else 0.0
    temp_media = round(sum(temps) / total_medicoes, 2) if total_medicoes else 0.0
    temp_max = round(max(temps), 2) if total_medicoes else 0.0
    precip_total = round(sum(precips), 2) if total_medicoes else 0.0
    precip_media = round(precip_total / total_medicoes, 2) if total_medicoes else 0.0

    alertas_periodo = (
        db.query(models.AlertaClimatico)
        .filter(
            models.AlertaClimatico.terreno_id == terreno.id,
            models.AlertaClimatico.data_evento >= periodo_inicio,
            models.AlertaClimatico.data_evento <= periodo_fim,
        )
        .order_by(models.AlertaClimatico.data_evento.desc(), models.AlertaClimatico.id.desc())
        .all()
    )

    atividades_periodo = (
        db.query(models.Activity)
        .filter(
            models.Activity.terreno_id == terreno.id,
            models.Activity.data_programada >= periodo_inicio,
            models.Activity.data_programada <= periodo_fim,
        )
        .order_by(models.Activity.data_programada.asc(), models.Activity.id.asc())
        .all()
    )
    ajustadas = [a for a in atividades_periodo if a.ajustada_por_alerta]

    alertas_graves = sum(
        1 for a in alertas_periodo if str(a.severidade).lower() in {"alta", "critica"}
    )

    vigor = _calcular_vigor(
        umidade_media=umidade_media,
        temp_media=temp_media,
        precip_media=precip_media,
        dias_solo_exposto=dias_solo_exposto,
        total_medicoes=total_medicoes,
        alertas_graves=alertas_graves,
        serie=serie,
    )
    vulnerabilidade = _calcular_vulnerabilidade(
        umidade_media=umidade_media,
        temp_media=temp_media,
        dias_solo_exposto=dias_solo_exposto,
        total_medicoes=total_medicoes,
        alertas_periodo=alertas_periodo,
        prioridades=terreno.prioridades if isinstance(terreno.prioridades, dict) else {},
    )

    total_ativ = len(atividades_periodo)
    total_ajust = len(ajustadas)
    taxa_adaptacao = round(total_ajust / total_ativ, 2) if total_ativ else 0.0

    recomendacoes: List[str] = []
    if vigor.classificacao == "baixo":
        recomendacoes.append(
            "Priorizar cobertura morta e culturas rústicas resistentes à seca/calor."
        )
    if vulnerabilidade.nivel in {"alta", "critica"}:
        recomendacoes.append(
            "Acompanhar alertas diários e reforçar irrigação suplementar em horários amenos."
        )
    if total_ajust > 0:
        recomendacoes.append(
            f"O calendário adaptou automaticamente {total_ajust} atividade(s) frente a eventos climáticos no período."
        )
    if not recomendacoes:
        recomendacoes.append(
            "Manter o planejamento de rotação atual com monitoramento semanal do calendário."
        )

    return RelatorioAdaptacaoResponse(
        terreno_id=terreno.id,
        nome_propriedade=terreno.nome_propriedade,
        periodo_inicio=periodo_inicio,
        periodo_fim=periodo_fim,
        origem_dados=origem_dados,
        resumo_climatico=ResumoClimaticoRelatorio(
            umidade_media_solo=umidade_media,
            umidade_min_solo=umidade_min,
            umidade_max_solo=umidade_max,
            temperatura_media_c=temp_media,
            temperatura_max_c=temp_max,
            precipitacao_total_mm=precip_total,
            precipitacao_media_mm=precip_media,
            dias_solo_exposto=dias_solo_exposto,
            total_medicoes=total_medicoes,
        ),
        vigor=vigor,
        vulnerabilidade=vulnerabilidade,
        adaptacoes=AdaptacoesTerrenoResumo(
            total_atividades_periodo=total_ativ,
            total_ajustadas_por_alerta=total_ajust,
            taxa_adaptacao=taxa_adaptacao,
            atividades_ajustadas=[
                AdaptacaoAtividadeItem(
                    atividade_id=a.id,
                    titulo=a.titulo,
                    tipo_atividade=a.tipo_atividade,
                    data_programada=a.data_programada,
                    prioridade=a.prioridade,
                    status=a.status,
                    motivo_ajuste=a.motivo_ajuste,
                )
                for a in ajustadas
            ],
        ),
        alertas_periodo=[
            AlertaResumoRelatorio(
                id=al.id,
                tipo_evento=al.tipo_evento,
                severidade=al.severidade,
                titulo=al.titulo,
                data_evento=al.data_evento,
                processado_background=al.processado_background,
                resumo_adaptacao=al.resumo_adaptacao,
            )
            for al in alertas_periodo
        ],
        serie_historica=[
            MetricaHistoricaResponse.model_validate(item) for item in serie
        ],
        recomendacoes_manejo=recomendacoes,
    )

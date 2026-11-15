from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.db import models

BARE_MOISTURE_MAX = 0.12
BARE_TEMP_MIN_C = 33.0


def _coerce_float(valor: Any, default: float) -> float:
    if isinstance(valor, bool) or valor is None:
        return default
    try:
        return float(valor)
    except (TypeError, ValueError):
        return default


def _parse_data_medicao(bruto: Any, fallback: date) -> date:
    if isinstance(bruto, date) and not isinstance(bruto, datetime):
        return bruto
    if isinstance(bruto, datetime):
        return bruto.date()
    if isinstance(bruto, str):
        texto = bruto.strip()
        if texto:
            try:
                return date.fromisoformat(texto[:10])
            except ValueError:
                pass
    return fallback


def _upsert_ponto_metrica(
    db: Session,
    terreno_id: int,
    data_medicao: date,
    soil_moisture: float,
    surface_temp_c: float,
    precipitation_mm: float,
    is_bare_field_period: bool,
    data_quality: str,
    origem: str,
) -> models.MetricaHistoricaTerreno:
    existente = (
        db.query(models.MetricaHistoricaTerreno)
        .filter(
            models.MetricaHistoricaTerreno.terreno_id == terreno_id,
            models.MetricaHistoricaTerreno.data_medicao == data_medicao,
        )
        .first()
    )
    if existente is not None:
        existente.soil_moisture = soil_moisture
        existente.surface_temp_c = surface_temp_c
        existente.precipitation_mm = precipitation_mm
        existente.is_bare_field_period = is_bare_field_period
        existente.data_quality = data_quality
        existente.origem = origem
        return existente

    registro = models.MetricaHistoricaTerreno(
        terreno_id=terreno_id,
        data_medicao=data_medicao,
        soil_moisture=soil_moisture,
        surface_temp_c=surface_temp_c,
        precipitation_mm=precipitation_mm,
        is_bare_field_period=is_bare_field_period,
        data_quality=data_quality,
        origem=origem,
    )
    db.add(registro)
    return registro


def persistir_metricas_terreno(
    db: Session,
    terreno_id: int,
    field_metrics: Dict[str, Any],
    origem: str = "nasa_geospatial_service",
    data_referencia: Optional[date] = None,
    commit: bool = True,
) -> List[models.MetricaHistoricaTerreno]:
    """
    Persiste snapshots diários (a partir de `time_series` ou resumo agregado)
    na tabela `metricas_historicas_terreno` com upsert por (terreno_id, data_medicao).
    """
    if not isinstance(field_metrics, dict):
        return []

    ref_date = data_referencia or date.today()
    data_quality = str(field_metrics.get("data_quality") or "clip")
    origem_efetiva = str(field_metrics.get("origem") or origem)

    default_moisture = _coerce_float(
        field_metrics.get("avg_soil_moisture_smap")
        if field_metrics.get("avg_soil_moisture_smap") is not None
        else (
            field_metrics.get("soil_moisture")
            if field_metrics.get("soil_moisture") is not None
            else field_metrics.get("umidade_solo_estimada")
        ),
        0.25,
    )
    default_temp = _coerce_float(
        field_metrics.get("avg_surface_temp_ecostress")
        if field_metrics.get("avg_surface_temp_ecostress") is not None
        else (
            field_metrics.get("surface_temp_c")
            if field_metrics.get("surface_temp_c") is not None
            else field_metrics.get("temperatura_media_c")
        ),
        27.0,
    )
    default_precip = _coerce_float(
        field_metrics.get("avg_precipitation_gpm")
        if field_metrics.get("avg_precipitation_gpm") is not None
        else (
            field_metrics.get("precipitation_mm")
            if field_metrics.get("precipitation_mm") is not None
            else field_metrics.get("precipitacao_estimada_mm")
        ),
        0.0,
    )

    serie = field_metrics.get("time_series")
    registros: List[models.MetricaHistoricaTerreno] = []

    if isinstance(serie, list) and serie:
        for ponto in serie:
            if not isinstance(ponto, dict):
                continue
            dt = _parse_data_medicao(ponto.get("data"), ref_date)
            umidade = _coerce_float(ponto.get("soil_moisture"), default_moisture)
            temp = _coerce_float(ponto.get("surface_temp_c"), default_temp)
            precip = _coerce_float(ponto.get("precipitation_mm"), default_precip)
            bare_flag = bool(
                ponto.get(
                    "is_bare_field_period",
                    data_quality != "no_data"
                    and umidade < BARE_MOISTURE_MAX
                    and temp >= BARE_TEMP_MIN_C,
                )
            )
            registros.append(
                _upsert_ponto_metrica(
                    db=db,
                    terreno_id=terreno_id,
                    data_medicao=dt,
                    soil_moisture=round(umidade, 4),
                    surface_temp_c=round(temp, 2),
                    precipitation_mm=round(precip, 2),
                    is_bare_field_period=bare_flag,
                    data_quality=data_quality,
                    origem=origem_efetiva,
                )
            )
    else:
        bare_flag = bool(
            field_metrics.get(
                "is_bare_field_period",
                data_quality != "no_data"
                and default_moisture < BARE_MOISTURE_MAX
                and default_temp >= BARE_TEMP_MIN_C,
            )
        )
        registros.append(
            _upsert_ponto_metrica(
                db=db,
                terreno_id=terreno_id,
                data_medicao=ref_date,
                soil_moisture=round(default_moisture, 4),
                surface_temp_c=round(default_temp, 2),
                precipitation_mm=round(default_precip, 2),
                is_bare_field_period=bare_flag,
                data_quality=data_quality,
                origem=origem_efetiva,
            )
        )

    if commit:
        db.commit()
        for reg in registros:
            db.refresh(reg)
    else:
        db.flush()

    return registros


def consultar_serie_historica_terreno(
    db: Session,
    terreno_id: int,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
) -> List[models.MetricaHistoricaTerreno]:
    """Consulta a série temporal histórica persistida de um terreno ordenada por data."""
    query = db.query(models.MetricaHistoricaTerreno).filter(
        models.MetricaHistoricaTerreno.terreno_id == terreno_id
    )
    if data_inicio is not None:
        query = query.filter(models.MetricaHistoricaTerreno.data_medicao >= data_inicio)
    if data_fim is not None:
        query = query.filter(models.MetricaHistoricaTerreno.data_medicao <= data_fim)
    return query.order_by(
        models.MetricaHistoricaTerreno.data_medicao.asc(),
        models.MetricaHistoricaTerreno.id.asc(),
    ).all()

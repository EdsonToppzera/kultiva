from datetime import date
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.api.simulacao import get_nasa_processor
from backend.db import models
from backend.db.database import get_db
from backend.schemas.relatorio import (
    MetricaHistoricaCreate,
    MetricaHistoricaResponse,
    RelatorioAdaptacaoResponse,
)
from backend.services.metrics_service import (
    consultar_serie_historica_terreno,
    persistir_metricas_terreno,
)
from backend.services.relatorio_service import (
    gerar_relatorio_terreno,
    resolver_periodo_relatorio,
)

router = APIRouter(prefix="/relatorios", tags=["Relatórios de Adaptação (M6)"])


def _obter_terreno_ou_404(terreno_id: int, db: Session) -> models.Terreno:
    terreno = (
        db.query(models.Terreno).filter(models.Terreno.id == terreno_id).first()
    )
    if not terreno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terreno não encontrado",
        )
    return terreno


@router.get("/terreno/{terreno_id}", response_model=RelatorioAdaptacaoResponse)
def obter_relatorio_terreno(
    terreno_id: int,
    data_inicio: Optional[date] = Query(default=None),
    data_fim: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    nasa_processor: Optional[Any] = Depends(get_nasa_processor),
):
    """Gera relatório periódico [M6] de umidade, temperatura, vigor, vulnerabilidade e adaptações."""
    terreno = _obter_terreno_ou_404(terreno_id, db)
    try:
        resolver_periodo_relatorio(data_inicio, data_fim)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return gerar_relatorio_terreno(
        db=db,
        terreno=terreno,
        data_inicio=data_inicio,
        data_fim=data_fim,
        nasa_processor=nasa_processor,
    )


@router.get("/", response_model=RelatorioAdaptacaoResponse)
def obter_relatorio_por_query(
    terreno_id: int = Query(..., gt=0),
    data_inicio: Optional[date] = Query(default=None),
    data_fim: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
    nasa_processor: Optional[Any] = Depends(get_nasa_processor),
):
    """Atalho GET /api/v1/relatorios/?terreno_id=... para consulta de relatório por período."""
    return obter_relatorio_terreno(
        terreno_id=terreno_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
        db=db,
        nasa_processor=nasa_processor,
    )


@router.get(
    "/terreno/{terreno_id}/metricas",
    response_model=List[MetricaHistoricaResponse],
)
def listar_metricas_historicas_terreno(
    terreno_id: int,
    data_inicio: Optional[date] = Query(default=None),
    data_fim: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Lista a série histórica de métricas climáticas persistida para o terreno."""
    _obter_terreno_ou_404(terreno_id, db)
    if data_inicio is not None and data_fim is not None and data_inicio > data_fim:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A data_inicio deve ser menor ou igual à data_fim.",
        )
    return consultar_serie_historica_terreno(
        db=db,
        terreno_id=terreno_id,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


@router.post(
    "/terreno/{terreno_id}/metricas",
    response_model=List[MetricaHistoricaResponse],
    status_code=status.HTTP_201_CREATED,
)
def registrar_metricas_historicas_terreno(
    terreno_id: int,
    payload: Optional[MetricaHistoricaCreate] = None,
    db: Session = Depends(get_db),
    nasa_processor: Optional[Any] = Depends(get_nasa_processor),
):
    """Registra snapshot climático manual ou extrai/persiste a série via INASADataProvider."""
    terreno = _obter_terreno_ou_404(terreno_id, db)
    if payload is not None:
        dados = (
            payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
        )
        ponto = {
            "data": dados["data_medicao"].isoformat(),
            "soil_moisture": dados["soil_moisture"],
            "surface_temp_c": dados["surface_temp_c"],
            "precipitation_mm": dados["precipitation_mm"],
        }
        if dados.get("is_bare_field_period") is not None:
            ponto["is_bare_field_period"] = dados["is_bare_field_period"]
        return persistir_metricas_terreno(
            db=db,
            terreno_id=terreno.id,
            field_metrics={
                "data_quality": dados.get("data_quality", "manual"),
                "origem": dados.get("origem", "api_ingestao"),
                "time_series": [ponto],
            },
            origem=dados.get("origem", "api_ingestao"),
            data_referencia=dados["data_medicao"],
        )

    if nasa_processor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Provedor geoespacial NASA indisponível para coleta automática.",
        )

    field_metrics = nasa_processor.extract_field_metrics(
        terreno.coordenadas_poligono, dataset=None
    )
    return persistir_metricas_terreno(
        db=db,
        terreno_id=terreno.id,
        field_metrics=field_metrics,
        origem=str((field_metrics or {}).get("origem") or "nasa_geospatial_service"),
    )

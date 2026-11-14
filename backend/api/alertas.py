from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.database import get_db
from backend.schemas.alerta import (
    AlertaClimaticoResponse,
    AlertaDisparoResponse,
    AlertaGatilhoRequest,
)
from backend.services.alert_tasks import processar_alerta_e_adaptar_calendario

router = APIRouter(prefix="/alertas", tags=["Alertas Climáticos (M5)"])


def _executar_detector_anomalias(
    serie_temporal: Optional[List[Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    """Integra com ClimateAnomalyDetector quando uma série temporal é enviada."""
    if not serie_temporal:
        return None

    resultado_ml: Any = None
    origem = "fallback_serie_recebida"
    try:
        from backend.services.ml_models import ClimateAnomalyDetector

        detector = ClimateAnomalyDetector()
        resultado_ml = detector.detect_extremes(serie_temporal)
        origem = "climate_anomaly_detector"
    except Exception as exc:
        resultado_ml = {"erro_detector": str(exc)}

    return {
        "origem_detector": origem,
        "total_pontos_analisados": len(serie_temporal),
        "resultado_ml": resultado_ml,
    }


@router.post(
    "/gatilho",
    response_model=AlertaDisparoResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def disparar_alerta_climatico(
    payload: AlertaGatilhoRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Recebe gatilho de anomalia climática (ML/NASA), registra o alerta e agenda
    a adaptação dinâmica do calendário [M4] em segundo plano.
    """
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

    dados_gatilho = _executar_detector_anomalias(payload.serie_temporal_clima)
    titulo = payload.titulo or f"Alerta climático: {payload.tipo_evento.replace('_', ' ')}"
    mensagem = payload.mensagem or (
        f"Detectado evento '{payload.tipo_evento}' com severidade '{payload.severidade}' "
        f"previsto para {payload.data_evento.isoformat()}. "
        "O calendário de atividades será ajustado automaticamente."
    )

    db_alerta = models.AlertaClimatico(
        terreno_id=payload.terreno_id,
        tipo_evento=payload.tipo_evento,
        severidade=payload.severidade,
        titulo=titulo,
        mensagem=mensagem,
        data_evento=payload.data_evento,
        origem_gatilho=payload.origem_gatilho,
        dados_gatilho=dados_gatilho,
        processado_background=False,
    )
    db.add(db_alerta)
    db.commit()
    db.refresh(db_alerta)

    background_tasks.add_task(
        processar_alerta_e_adaptar_calendario,
        db_alerta.id,
        payload.dias_adiamento,
    )

    return AlertaDisparoResponse(
        status="accepted",
        mensagem="Alerta registrado e rotina de adaptação do calendário agendada em segundo plano.",
        alerta=db_alerta,
    )


@router.get("/", response_model=List[AlertaClimaticoResponse])
def listar_alertas(
    terreno_id: Optional[int] = Query(default=None),
    lido: Optional[bool] = Query(default=None),
    severidade: Optional[str] = Query(default=None),
    tipo_evento: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Lista os alertas climáticos registrados com filtros opcionais."""
    query = db.query(models.AlertaClimatico)

    if terreno_id is not None:
        query = query.filter(models.AlertaClimatico.terreno_id == terreno_id)
    if lido is not None:
        query = query.filter(models.AlertaClimatico.lido == lido)
    if severidade is not None:
        query = query.filter(models.AlertaClimatico.severidade == severidade)
    if tipo_evento is not None:
        query = query.filter(models.AlertaClimatico.tipo_evento == tipo_evento)

    return query.order_by(
        models.AlertaClimatico.data_evento.desc(),
        models.AlertaClimatico.id.desc(),
    ).all()


@router.get("/{alerta_id}", response_model=AlertaClimaticoResponse)
def obter_alerta(alerta_id: int, db: Session = Depends(get_db)):
    """Retorna os detalhes de um alerta climático e o resumo da adaptação no calendário."""
    alerta = (
        db.query(models.AlertaClimatico)
        .filter(models.AlertaClimatico.id == alerta_id)
        .first()
    )
    if not alerta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerta climático não encontrado",
        )
    return alerta


@router.patch("/{alerta_id}/ler", response_model=AlertaClimaticoResponse)
def marcar_alerta_como_lido(alerta_id: int, db: Session = Depends(get_db)):
    """Marca um alerta climático como lido pelo agricultor."""
    alerta = (
        db.query(models.AlertaClimatico)
        .filter(models.AlertaClimatico.id == alerta_id)
        .first()
    )
    if not alerta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerta climático não encontrado",
        )
    alerta.lido = True
    db.commit()
    db.refresh(alerta)
    return alerta

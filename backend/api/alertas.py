from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.database import get_db
from backend.schemas.alerta import (
    AlertaClimaticoResponse,
    AlertaDisparoResponse,
    AlertaGatilhoRequest,
    MonitoramentoClimaRequest,
    MonitoramentoClimaResponse,
    ResumoAlertasNaoLidosResponse,
    ResumoAlertasTerrenoItem,
)
from backend.services.alert_tasks import (
    buscar_alerta_duplicado,
    executar_ciclo_monitoramento_alertas,
    gerar_orientacao_alerta,
    obter_intervalo_monitoramento_horas,
    processar_alerta_e_adaptar_calendario,
)

router = APIRouter(prefix="/alertas", tags=["Alertas Climáticos (M5)"])


def _serializar_alerta(alerta: models.AlertaClimatico) -> AlertaClimaticoResponse:
    """Converte AlertaClimatico garantindo orientacao_pratica acessível."""
    dados = alerta.dados_gatilho if isinstance(alerta.dados_gatilho, dict) else {}
    orientacao = dados.get("orientacao_pratica")
    if not orientacao:
        orientacao = gerar_orientacao_alerta(
            tipo_evento=alerta.tipo_evento,
            severidade=alerta.severidade,
            resumo_adaptacao=alerta.resumo_adaptacao,
            detalhes_clima=dados.get("dados_climaticos")
            if isinstance(dados.get("dados_climaticos"), dict)
            else None,
        )
    return AlertaClimaticoResponse(
        id=alerta.id,
        terreno_id=alerta.terreno_id,
        tipo_evento=alerta.tipo_evento,
        severidade=alerta.severidade,
        titulo=alerta.titulo,
        mensagem=alerta.mensagem,
        data_evento=alerta.data_evento,
        origem_gatilho=alerta.origem_gatilho,
        dados_gatilho=alerta.dados_gatilho,
        processado_background=alerta.processado_background,
        resumo_adaptacao=alerta.resumo_adaptacao,
        orientacao_pratica=orientacao,
        lido=alerta.lido,
        criado_em=alerta.criado_em,
    )


def _executar_detector_anomalias(
    serie_temporal: Optional[List[Dict[str, Any]]],
    baseline_climatology: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Integra com ClimateAnomalyDetector quando uma série temporal é enviada."""
    if not serie_temporal:
        return None

    resultado_ml: Any = None
    origem = "fallback_serie_recebida"
    z_scores: Optional[Dict[str, Any]] = None
    try:
        from backend.services.ml_models import ClimateAnomalyDetector

        detector = ClimateAnomalyDetector()
        resultado_ml = detector.detect_extremes(
            serie_temporal, baseline=baseline_climatology
        )
        origem = "climate_anomaly_detector"
        if isinstance(resultado_ml, dict):
            detalhes = resultado_ml.get("detalhes")
            if isinstance(detalhes, dict) and isinstance(detalhes.get("z_scores"), dict):
                z_scores = detalhes["z_scores"]
    except Exception as exc:
        resultado_ml = {"erro_detector": str(exc)}

    payload: Dict[str, Any] = {
        "origem_detector": origem,
        "total_pontos_analisados": len(serie_temporal),
        "resultado_ml": resultado_ml,
    }
    if z_scores is not None:
        payload["z_scores"] = z_scores
    return payload


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

    alerta_existente = buscar_alerta_duplicado(
        db=db,
        terreno_id=payload.terreno_id,
        tipo_evento=payload.tipo_evento,
        data_evento=payload.data_evento,
    )
    if alerta_existente is not None:
        return AlertaDisparoResponse(
            status="deduplicated",
            mensagem="Alerta equivalente já registrado para este terreno/evento (deduplicado).",
            alerta=_serializar_alerta(alerta_existente),
        )

    idioma = (
        "en"
        if str(getattr(payload, "idioma", "pt") or "pt").strip().lower().startswith("en")
        else "pt"
    )
    dados_gatilho = _executar_detector_anomalias(payload.serie_temporal_clima) or {}
    dados_gatilho["idioma"] = idioma
    dados_gatilho["orientacao_pratica"] = gerar_orientacao_alerta(
        tipo_evento=payload.tipo_evento,
        severidade=payload.severidade,
        idioma=idioma,
    )
    if idioma == "en":
        titulo = payload.titulo or f"Weather alert: {payload.tipo_evento.replace('_', ' ')}"
        mensagem = payload.mensagem or (
            f"Detected '{payload.tipo_evento}' event with '{payload.severidade}' severity "
            f"expected for {payload.data_evento.isoformat()}. "
            "The activity schedule will be adjusted automatically."
        )
    else:
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
        alerta=_serializar_alerta(db_alerta),
    )


@router.post(
    "/monitorar",
    response_model=MonitoramentoClimaResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@router.post(
    "/monitorar-clima",
    response_model=MonitoramentoClimaResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def iniciar_monitoramento_clima(
    payload: MonitoramentoClimaRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Agenda em segundo plano a verificação climática via gerador sintético e
    ClimateAnomalyDetector, persistindo novos alertas em banco se anomalias forem detectadas.
    """
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

    intervalo_efetivo = (
        payload.intervalo_horas
        if payload.intervalo_horas is not None
        else obter_intervalo_monitoramento_horas()
    )

    background_tasks.add_task(
        executar_ciclo_monitoramento_alertas,
        payload.terreno_id,
        intervalo_efetivo,
        "data",
        None,
        None,
        payload.perfil_climatico,
    )

    return MonitoramentoClimaResponse(
        status="accepted",
        mensagem=(
            "Monitoramento climático em segundo plano agendado "
            f"(janela configurada de {intervalo_efetivo}h"
            + (f", perfil '{payload.perfil_climatico}'" if payload.perfil_climatico else "")
            + ")."
        ),
        intervalo_horas=intervalo_efetivo,
        terreno_id=payload.terreno_id,
        perfil_climatico=payload.perfil_climatico,
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

    alertas = query.order_by(
        models.AlertaClimatico.data_evento.desc(),
        models.AlertaClimatico.id.desc(),
    ).all()
    return [_serializar_alerta(a) for a in alertas]


@router.get("/resumo-nao-lidos", response_model=ResumoAlertasNaoLidosResponse)
def resumo_alertas_nao_lidos(
    terreno_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Retorna a contagem de alertas não lidos por terreno para o painel do produtor."""
    query = db.query(models.AlertaClimatico).filter(
        models.AlertaClimatico.lido.is_(False)
    )
    if terreno_id is not None:
        query = query.filter(models.AlertaClimatico.terreno_id == terreno_id)

    nao_lidos = query.order_by(
        models.AlertaClimatico.data_evento.desc(),
        models.AlertaClimatico.id.desc(),
    ).all()

    terrenos_map = {
        t.id: t.nome_propriedade for t in db.query(models.Terreno).all()
    }
    agrupado: Dict[int, Dict[str, Any]] = {}
    for alerta in nao_lidos:
        item = agrupado.setdefault(
            alerta.terreno_id,
            {
                "terreno_id": alerta.terreno_id,
                "nome_propriedade": terrenos_map.get(alerta.terreno_id),
                "nao_lidos": 0,
                "criticos_nao_lidos": 0,
                "ultimo_evento": alerta.tipo_evento,
                "ultima_data_evento": alerta.data_evento,
            },
        )
        item["nao_lidos"] += 1
        if (alerta.severidade or "").strip().lower() == "critica":
            item["criticos_nao_lidos"] += 1

    por_terreno = [ResumoAlertasTerrenoItem(**dados) for dados in agrupado.values()]
    return ResumoAlertasNaoLidosResponse(
        total_nao_lidos=len(nao_lidos),
        por_terreno=por_terreno,
    )


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
    return _serializar_alerta(alerta)


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
    return _serializar_alerta(alerta)

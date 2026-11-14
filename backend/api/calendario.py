from datetime import date, datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.database import get_db
from backend.schemas.calendario import (
    AtividadeCalendarioCreate,
    AtividadeCalendarioResponse,
    AtividadeCalendarioUpdate,
    AtividadeStatusPatch,
    GerarCronogramaRequest,
)

router = APIRouter(prefix="/calendario", tags=["Calendário de Cultivo (M4)"])


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


def _obter_atividade_ou_404(
    atividade_id: int, db: Session
) -> models.AtividadeCalendario:
    atividade = (
        db.query(models.AtividadeCalendario)
        .filter(models.AtividadeCalendario.id == atividade_id)
        .first()
    )
    if not atividade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atividade do calendário não encontrada",
        )
    return atividade


@router.post(
    "/atividades",
    response_model=AtividadeCalendarioResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_atividade(
    payload: AtividadeCalendarioCreate, db: Session = Depends(get_db)
):
    """Cria uma nova atividade diária programada para o terreno."""
    _obter_terreno_ou_404(payload.terreno_id, db)

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

    dados = (
        payload.model_dump()
        if hasattr(payload, "model_dump")
        else payload.dict()
    )
    db_atividade = models.AtividadeCalendario(**dados)
    db.add(db_atividade)
    db.commit()
    db.refresh(db_atividade)
    return db_atividade


@router.post(
    "/gerar-cronograma",
    response_model=List[AtividadeCalendarioResponse],
    status_code=status.HTTP_201_CREATED,
)
def gerar_cronograma_inicial(
    payload: GerarCronogramaRequest, db: Session = Depends(get_db)
):
    """Gera automaticamente as atividades essenciais do ciclo de cultivo."""
    _obter_terreno_ou_404(payload.terreno_id, db)

    nome_cultura = payload.nome_cultura or "Cultura Principal"
    duracao_dias = payload.tempo_colheita_dias

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
        nome_cultura = cultura.nome
        if payload.tempo_colheita_dias == 90 and cultura.tempo_colheita_dias:
            duracao_dias = cultura.tempo_colheita_dias

    dia_inspecao = max(5, min(duracao_dias - 2, duracao_dias // 6))
    dia_adubacao = max(10, min(duracao_dias - 1, duracao_dias // 3))

    etapas = [
        (
            f"Plantio de {nome_cultura}",
            f"Preparo do canteiro e semeadura/plantio de {nome_cultura}.",
            "plantio",
            payload.data_inicio,
            "alta",
        ),
        (
            f"Irrigação inicial — {nome_cultura}",
            "Rega de estabelecimento para garantir germinação uniforme.",
            "irrigacao",
            payload.data_inicio + timedelta(days=2),
            "alta",
        ),
        (
            f"Inspeção fitossanitária — {nome_cultura}",
            "Verificação preventiva de pragas, doenças e umidade do solo.",
            "inspecao",
            payload.data_inicio + timedelta(days=dia_inspecao),
            "media",
        ),
        (
            f"Adubação de cobertura — {nome_cultura}",
            "Reforço nutricional conforme desenvolvimento vegetativo.",
            "adubacao",
            payload.data_inicio + timedelta(days=dia_adubacao),
            "media",
        ),
        (
            f"Colheita de {nome_cultura}",
            "Avaliação do ponto ideal e realização da colheita.",
            "colheita",
            payload.data_inicio + timedelta(days=duracao_dias),
            "alta",
        ),
    ]

    atividades = [
        models.AtividadeCalendario(
            terreno_id=payload.terreno_id,
            cultura_id=payload.cultura_id,
            titulo=titulo,
            descricao=descricao,
            tipo_atividade=tipo,
            data_programada=data_prevista,
            prioridade=prioridade,
        )
        for titulo, descricao, tipo, data_prevista, prioridade in etapas
    ]

    db.add_all(atividades)
    db.commit()
    for atividade in atividades:
        db.refresh(atividade)

    return atividades


@router.get("/atividades", response_model=List[AtividadeCalendarioResponse])
def listar_atividades(
    terreno_id: Optional[int] = Query(default=None),
    concluida: Optional[bool] = Query(default=None),
    tipo_atividade: Optional[str] = Query(default=None),
    data_inicio: Optional[date] = Query(default=None),
    data_fim: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Lista atividades do calendário com filtros opcionais."""
    query = db.query(models.AtividadeCalendario)

    if terreno_id is not None:
        query = query.filter(models.AtividadeCalendario.terreno_id == terreno_id)
    if concluida is not None:
        query = query.filter(models.AtividadeCalendario.concluida == concluida)
    if tipo_atividade is not None:
        query = query.filter(
            models.AtividadeCalendario.tipo_atividade == tipo_atividade
        )
    if data_inicio is not None:
        query = query.filter(
            models.AtividadeCalendario.data_programada >= data_inicio
        )
    if data_fim is not None:
        query = query.filter(
            models.AtividadeCalendario.data_programada <= data_fim
        )

    return query.order_by(
        models.AtividadeCalendario.data_programada.asc(),
        models.AtividadeCalendario.id.asc(),
    ).all()


@router.get(
    "/atividades/{atividade_id}", response_model=AtividadeCalendarioResponse
)
def obter_atividade(atividade_id: int, db: Session = Depends(get_db)):
    """Busca uma atividade específica pelo ID."""
    return _obter_atividade_ou_404(atividade_id, db)


@router.patch(
    "/atividades/{atividade_id}/concluir",
    response_model=AtividadeCalendarioResponse,
)
def atualizar_status_conclusao(
    atividade_id: int,
    payload: AtividadeStatusPatch,
    db: Session = Depends(get_db),
):
    """Permite ao agricultor marcar ou desmarcar uma atividade como concluída."""
    atividade = _obter_atividade_ou_404(atividade_id, db)
    atividade.concluida = payload.concluida
    atividade.data_conclusao = datetime.utcnow() if payload.concluida else None
    db.commit()
    db.refresh(atividade)
    return atividade


@router.put(
    "/atividades/{atividade_id}", response_model=AtividadeCalendarioResponse
)
def atualizar_atividade(
    atividade_id: int,
    payload: AtividadeCalendarioUpdate,
    db: Session = Depends(get_db),
):
    """Atualiza os dados de uma atividade programada."""
    atividade = _obter_atividade_ou_404(atividade_id, db)
    atualizacoes = (
        payload.model_dump(exclude_unset=True)
        if hasattr(payload, "model_dump")
        else payload.dict(exclude_unset=True)
    )

    for campo, valor in atualizacoes.items():
        setattr(atividade, campo, valor)

    if "concluida" in atualizacoes:
        atividade.data_conclusao = (
            datetime.utcnow() if atualizacoes["concluida"] else None
        )

    db.commit()
    db.refresh(atividade)
    return atividade


@router.delete("/atividades/{atividade_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_atividade(atividade_id: int, db: Session = Depends(get_db)):
    """Remove uma atividade do calendário."""
    atividade = _obter_atividade_ou_404(atividade_id, db)
    db.delete(atividade)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

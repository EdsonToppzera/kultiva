from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple
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


def _normalizar_status(valor: str) -> Tuple[str, bool]:
    """Normaliza status textual ('pendente' / 'concluida') para (status, concluida)."""
    normalizado = valor.strip().lower()
    if normalizado in {"concluida", "concluída"}:
        return "concluida", True
    if normalizado == "pendente":
        return "pendente", False
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Status inválido. Utilize 'pendente' ou 'concluida'.",
    )


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


def _obter_usuario_ou_404(usuario_id: int, db: Session) -> models.Usuario:
    usuario = (
        db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    )
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )
    return usuario


def _obter_atividade_ou_404(atividade_id: int, db: Session) -> models.Activity:
    atividade = (
        db.query(models.Activity)
        .filter(models.Activity.id == atividade_id)
        .first()
    )
    if not atividade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atividade do calendário não encontrada",
        )
    return atividade


def _aplicar_status(
    atividade: models.Activity,
    novo_status: Optional[str],
    nova_conclusao: Optional[bool],
) -> None:
    if novo_status is not None:
        status_norm, flag = _normalizar_status(novo_status)
        atividade.status = status_norm
        atividade.concluida = flag
    elif nova_conclusao is not None:
        atividade.concluida = nova_conclusao
        atividade.status = "concluida" if nova_conclusao else "pendente"

    atividade.data_conclusao = datetime.utcnow() if atividade.concluida else None


@router.post(
    "/atividades",
    response_model=AtividadeCalendarioResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_atividade(
    payload: AtividadeCalendarioCreate, db: Session = Depends(get_db)
):
    """Cria uma nova atividade diária programada vinculada a um Terreno ou Usuário."""
    if payload.terreno_id is None and payload.usuario_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe terreno_id ou usuario_id para criar a atividade.",
        )

    if payload.terreno_id is not None:
        _obter_terreno_ou_404(payload.terreno_id, db)

    if payload.usuario_id is not None:
        _obter_usuario_ou_404(payload.usuario_id, db)

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
    status_norm, flag_concluida = _normalizar_status(dados.pop("status", "pendente"))

    db_atividade = models.Activity(
        **dados,
        status=status_norm,
        concluida=flag_concluida,
        data_conclusao=datetime.utcnow() if flag_concluida else None,
    )
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
    terreno = _obter_terreno_ou_404(payload.terreno_id, db)

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
        models.Activity(
            terreno_id=payload.terreno_id,
            usuario_id=terreno.usuario_id,
            cultura_id=payload.cultura_id,
            titulo=titulo,
            descricao=descricao,
            tipo_atividade=tipo,
            data_programada=data_prevista,
            prioridade=prioridade,
            status="pendente",
            concluida=False,
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
    usuario_id: Optional[int] = Query(default=None),
    status_atividade: Optional[str] = Query(default=None, alias="status"),
    concluida: Optional[bool] = Query(default=None),
    tipo_atividade: Optional[str] = Query(default=None),
    data_inicio: Optional[date] = Query(default=None),
    data_fim: Optional[date] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Lista atividades do calendário com filtros por período, terreno, usuário e status."""
    query = db.query(models.Activity)

    if terreno_id is not None:
        query = query.filter(models.Activity.terreno_id == terreno_id)
    if usuario_id is not None:
        query = query.filter(models.Activity.usuario_id == usuario_id)
    if status_atividade is not None:
        status_norm, _ = _normalizar_status(status_atividade)
        query = query.filter(models.Activity.status == status_norm)
    if concluida is not None:
        query = query.filter(models.Activity.concluida == concluida)
    if tipo_atividade is not None:
        query = query.filter(models.Activity.tipo_atividade == tipo_atividade)
    if data_inicio is not None:
        query = query.filter(models.Activity.data_programada >= data_inicio)
    if data_fim is not None:
        query = query.filter(models.Activity.data_programada <= data_fim)

    return query.order_by(
        models.Activity.data_programada.asc(),
        models.Activity.id.asc(),
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
    nova_conclusao = payload.concluida if payload.concluida is not None else True
    _aplicar_status(atividade, payload.status, nova_conclusao)
    db.commit()
    db.refresh(atividade)
    return atividade


@router.patch(
    "/atividades/{atividade_id}/status",
    response_model=AtividadeCalendarioResponse,
)
def atualizar_status_atividade(
    atividade_id: int,
    payload: AtividadeStatusPatch,
    db: Session = Depends(get_db),
):
    """Atualiza o status ('pendente' ou 'concluida') de uma atividade programada."""
    if payload.status is None and payload.concluida is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe 'status' ('pendente'/'concluida') ou 'concluida' (bool).",
        )
    atividade = _obter_atividade_ou_404(atividade_id, db)
    _aplicar_status(atividade, payload.status, payload.concluida)
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

    novo_status = atualizacoes.pop("status", None)
    nova_conclusao = atualizacoes.pop("concluida", None)

    for campo, valor in atualizacoes.items():
        setattr(atividade, campo, valor)

    if novo_status is not None or nova_conclusao is not None:
        _aplicar_status(atividade, novo_status, nova_conclusao)

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

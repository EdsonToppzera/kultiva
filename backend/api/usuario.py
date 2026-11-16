import re
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.db import models
from backend.db.database import get_db

router = APIRouter(prefix="/usuarios", tags=["Usuários"])

_DEVICE_ID_SANITY_RE = re.compile(r"[^a-z0-9_-]+")


class SessaoDispositivoRequest(BaseModel):
    device_id: str = Field(..., min_length=8, max_length=128)


class SessaoDispositivoResponse(BaseModel):
    id: int
    nome: str
    device_id: str
    model_config = ConfigDict(from_attributes=True)


def _normalizar_device_id(raw_id: str) -> str:
    cleaned = _DEVICE_ID_SANITY_RE.sub("", raw_id.strip().lower())
    if len(cleaned) < 8 or len(cleaned) > 128:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Identificador de dispositivo inválido.",
        )
    return cleaned


def _email_para_dispositivo(device_id: str) -> str:
    return f"device-{device_id}@local.kultiva"


@router.post("/sessao", response_model=SessaoDispositivoResponse)
def obter_ou_criar_sessao_dispositivo(
    payload: SessaoDispositivoRequest,
    db: Session = Depends(get_db),
):
    """Resolve de forma idempotente o usuário anônimo associado ao dispositivo."""
    safe_device_id = _normalizar_device_id(payload.device_id)
    email_dispositivo = _email_para_dispositivo(safe_device_id)

    usuario = (
        db.query(models.Usuario)
        .filter(models.Usuario.email == email_dispositivo)
        .first()
    )
    if usuario is not None:
        return SessaoDispositivoResponse(
            id=usuario.id,
            nome=usuario.nome,
            device_id=safe_device_id,
        )

    novo_usuario = models.Usuario(
        nome="Produtor Rural",
        email=email_dispositivo,
    )
    db.add(novo_usuario)
    try:
        db.commit()
        db.refresh(novo_usuario)
        usuario = novo_usuario
    except IntegrityError:
        db.rollback()
        usuario = (
            db.query(models.Usuario)
            .filter(models.Usuario.email == email_dispositivo)
            .first()
        )
        if usuario is None:
            raise

    return SessaoDispositivoResponse(
        id=usuario.id,
        nome=usuario.nome,
        device_id=safe_device_id,
    )

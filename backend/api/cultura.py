from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.db.database import get_db
from backend.db import models
from backend.schemas.rotacao import CulturaCreate, CulturaResponse

router = APIRouter(prefix="/culturas", tags=["Culturas (Catálogo M2)"])


@router.get("/", response_model=List[CulturaResponse])
def listar_culturas(
    skip: int = 0, limit: int = 100, db: Session = Depends(get_db)
):
    return db.query(models.Cultura).offset(skip).limit(limit).all()


@router.get("/{cultura_id}", response_model=CulturaResponse)
def buscar_cultura(cultura_id: int, db: Session = Depends(get_db)):
    cultura = (
        db.query(models.Cultura).filter(models.Cultura.id == cultura_id).first()
    )
    if not cultura:
        raise HTTPException(status_code=404, detail="Cultura não encontrada")
    return cultura


@router.post("/", response_model=CulturaResponse)
def criar_cultura(cultura: CulturaCreate, db: Session = Depends(get_db)):
    nome_limpo = cultura.nome.strip()
    db_cultura = (
        db.query(models.Cultura)
        .filter(func.lower(models.Cultura.nome) == nome_limpo.lower())
        .first()
    )
    if db_cultura:
        raise HTTPException(status_code=400, detail="Cultura já cadastrada")

    payload = (
        cultura.model_dump() if hasattr(cultura, "model_dump") else cultura.dict()
    )
    payload["nome"] = nome_limpo
    nova_cultura = models.Cultura(**payload)
    db.add(nova_cultura)
    db.commit()
    db.refresh(nova_cultura)
    return nova_cultura

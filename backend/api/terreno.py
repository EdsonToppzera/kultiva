from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.db.database import get_db
from backend.db import models
from backend.schemas.terreno import TerrenoCreate, TerrenoResponse

router = APIRouter(prefix="/terrenos", tags=["Terrenos (M1)"])


@router.post("/", response_model=TerrenoResponse)
def criar_terreno(terreno: TerrenoCreate, db: Session = Depends(get_db)):
    usuario_existe = (
        db.query(models.Usuario)
        .filter(models.Usuario.id == terreno.usuario_id)
        .first()
    )
    if not usuario_existe:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    localizacao = None
    if terreno.localizacao_central is not None:
        localizacao = (
            terreno.localizacao_central.model_dump()
            if hasattr(terreno.localizacao_central, "model_dump")
            else terreno.localizacao_central.dict()
        )

    db_terreno = models.Terreno(
        nome_propriedade=terreno.nome_propriedade,
        usuario_id=terreno.usuario_id,
        coordenadas_poligono=[
            c.model_dump() if hasattr(c, "model_dump") else c.dict()
            for c in terreno.coordenadas_poligono
        ],
        area_hectares=terreno.area_hectares,
        localizacao_central=localizacao,
        prioridades=terreno.prioridades,
    )
    db.add(db_terreno)
    db.commit()
    db.refresh(db_terreno)
    return db_terreno


@router.get("/", response_model=List[TerrenoResponse])
def listar_terrenos(
    usuario_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(models.Terreno)
    if usuario_id is not None:
        query = query.filter(models.Terreno.usuario_id == usuario_id)
    return query.offset(skip).limit(limit).all()


@router.get("/{terreno_id}", response_model=TerrenoResponse)
def buscar_terreno(terreno_id: int, db: Session = Depends(get_db)):
    terreno = (
        db.query(models.Terreno).filter(models.Terreno.id == terreno_id).first()
    )
    if not terreno:
        raise HTTPException(status_code=404, detail="Terreno não encontrado")
    return terreno

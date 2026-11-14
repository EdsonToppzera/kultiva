from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.db.database import get_db
from backend.db import models
from backend.schemas.terreno import TerrenoCreate, TerrenoResponse

router = APIRouter(prefix="/terrenos", tags=["Terrenos (M1)"])

@router.post("/", response_model=TerrenoResponse)
def criar_terreno(terreno: TerrenoCreate, db: Session = Depends(get_db)):
    db_terreno = models.Terreno(
        nome_propriedade=terreno.nome_propriedade,
        usuario_id=terreno.usuario_id,
        coordenadas_poligono=[c.model_dump() if hasattr(c, 'model_dump') else c.dict() for c in terreno.coordenadas_poligono],
        prioridades=terreno.prioridades
    )
    db.add(db_terreno)
    db.commit()
    db.refresh(db_terreno)
    return db_terreno

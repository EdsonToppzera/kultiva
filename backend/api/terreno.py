from typing import Any, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session
from backend.db.database import get_db
from backend.db import models
from backend.schemas.terreno import TerrenoCreate, TerrenoResponse, TerrenoUpdate
from backend.services.geospatial import calcular_geometria_terreno

router = APIRouter(prefix="/terrenos", tags=["Terrenos (M1)"])


def _coordenada_para_dict(coordenada: Any) -> Optional[dict]:
    if coordenada is None:
        return None
    if isinstance(coordenada, dict):
        return coordenada
    return (
        coordenada.model_dump()
        if hasattr(coordenada, "model_dump")
        else coordenada.dict()
    )


def _validar_usuario_ou_404(usuario_id: int, db: Session) -> models.Usuario:
    usuario = (
        db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    )
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )
    return usuario


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


def _resolver_geometria_terreno(
    coords_list: list[dict],
    area_hectares: Optional[float],
    localizacao_central: Optional[dict],
) -> Tuple[float, dict]:
    """Calcula área em hectares e centroide do polígono quando omitidos pelo cliente."""
    geo = calcular_geometria_terreno(coords_list)

    if area_hectares is None:
        raw_area = geo.get("area_hectares")
        area_resolvida = (
            float(raw_area) if raw_area is not None and float(raw_area) > 0 else 0.01
        )
    else:
        area_resolvida = float(area_hectares)

    centro_resolvido = (
        localizacao_central
        if localizacao_central is not None
        else geo.get("localizacao_central")
    )
    return area_resolvida, centro_resolvido


@router.post("/", response_model=TerrenoResponse)
def criar_terreno(terreno: TerrenoCreate, db: Session = Depends(get_db)):
    _validar_usuario_ou_404(terreno.usuario_id, db)

    coords_list = [_coordenada_para_dict(c) for c in terreno.coordenadas_poligono]
    localizacao_informada = _coordenada_para_dict(terreno.localizacao_central)
    area_resolvida, centro_resolvido = _resolver_geometria_terreno(
        coords_list,
        terreno.area_hectares,
        localizacao_informada,
    )

    db_terreno = models.Terreno(
        nome_propriedade=terreno.nome_propriedade,
        usuario_id=terreno.usuario_id,
        coordenadas_poligono=coords_list,
        area_hectares=area_resolvida,
        localizacao_central=centro_resolvido,
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
    return _obter_terreno_ou_404(terreno_id, db)


@router.put("/{terreno_id}", response_model=TerrenoResponse)
def atualizar_terreno(
    terreno_id: int,
    payload: TerrenoUpdate,
    db: Session = Depends(get_db),
):
    db_terreno = _obter_terreno_ou_404(terreno_id, db)

    if payload.usuario_id is not None:
        _validar_usuario_ou_404(payload.usuario_id, db)
        db_terreno.usuario_id = payload.usuario_id

    if payload.nome_propriedade is not None:
        db_terreno.nome_propriedade = payload.nome_propriedade

    if payload.prioridades is not None:
        db_terreno.prioridades = payload.prioridades

    localizacao_payload = _coordenada_para_dict(payload.localizacao_central)

    if payload.coordenadas_poligono is not None:
        coords_list = [_coordenada_para_dict(c) for c in payload.coordenadas_poligono]
        db_terreno.coordenadas_poligono = coords_list
        area_resolvida, centro_resolvido = _resolver_geometria_terreno(
            coords_list,
            payload.area_hectares,
            localizacao_payload,
        )
        db_terreno.area_hectares = area_resolvida
        db_terreno.localizacao_central = centro_resolvido
    else:
        if payload.area_hectares is not None:
            db_terreno.area_hectares = payload.area_hectares
        if localizacao_payload is not None:
            db_terreno.localizacao_central = localizacao_payload
        if db_terreno.area_hectares is None or db_terreno.localizacao_central is None:
            area_calc, centro_calc = _resolver_geometria_terreno(
                db_terreno.coordenadas_poligono or [],
                db_terreno.area_hectares,
                db_terreno.localizacao_central,
            )
            if db_terreno.area_hectares is None:
                db_terreno.area_hectares = area_calc
            if db_terreno.localizacao_central is None:
                db_terreno.localizacao_central = centro_calc

    db.commit()
    db.refresh(db_terreno)
    return db_terreno


def limpar_dependencias_terreno(db: Session, terreno_id: int) -> None:
    """Remove registros dependentes vinculados a um terreno para remoção ou reset."""
    db.query(models.MetricaHistoricaTerreno).filter(
        models.MetricaHistoricaTerreno.terreno_id == terreno_id
    ).delete(synchronize_session=False)
    db.query(models.AlertaClimatico).filter(
        models.AlertaClimatico.terreno_id == terreno_id
    ).delete(synchronize_session=False)
    db.query(models.Activity).filter(
        models.Activity.terreno_id == terreno_id
    ).delete(synchronize_session=False)
    db.query(models.RotacaoProdutor).filter(
        models.RotacaoProdutor.terreno_id == terreno_id,
        models.RotacaoProdutor.is_seed.is_(False),
    ).delete(synchronize_session=False)
    db.query(models.RotacaoProdutor).filter(
        models.RotacaoProdutor.terreno_id == terreno_id,
        models.RotacaoProdutor.is_seed.is_(True),
    ).update({"terreno_id": None}, synchronize_session=False)


@router.delete("/{terreno_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_terreno(terreno_id: int, db: Session = Depends(get_db)):
    db_terreno = _obter_terreno_ou_404(terreno_id, db)
    limpar_dependencias_terreno(db, terreno_id)
    db.delete(db_terreno)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

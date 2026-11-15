from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.database import get_db
from backend.schemas.rotacao import (
    CulturaCreate,
    CulturaResponse,
    CulturaUpdate,
    GAEZAptidaoResponse,
    RotacaoCreate,
    RotacaoResponse,
    RotacaoUpdate,
)
from backend.services.gaez_service import GAEZDataProvider

router = APIRouter(prefix="/culturas", tags=["Culturas (Catálogo M2)"])
rotacao_router = APIRouter(
    prefix="/rotacoes", tags=["Rotações do Produtor (Catálogo M2)"]
)


def _obter_cultura_ou_404(cultura_id: int, db: Session) -> models.Cultura:
    cultura = (
        db.query(models.Cultura).filter(models.Cultura.id == cultura_id).first()
    )
    if not cultura:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cultura não encontrada",
        )
    return cultura


def _obter_rotacao_ou_404(rotacao_id: int, db: Session) -> models.RotacaoProdutor:
    rotacao = (
        db.query(models.RotacaoProdutor)
        .filter(models.RotacaoProdutor.id == rotacao_id)
        .first()
    )
    if not rotacao:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rotação não encontrada",
        )
    return rotacao


def _validar_usuario_opcional(usuario_id: Optional[int], db: Session) -> None:
    if usuario_id is None:
        return
    usuario = (
        db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    )
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado",
        )


def _validar_terreno_opcional(terreno_id: Optional[int], db: Session) -> None:
    if terreno_id is None:
        return
    terreno = (
        db.query(models.Terreno).filter(models.Terreno.id == terreno_id).first()
    )
    if not terreno:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Terreno não encontrado",
        )


def get_gaez_provider() -> GAEZDataProvider:
    """Provedor de dependência para o cliente direto do FAO GAEZ v5."""
    return GAEZDataProvider(data_path="data")


@router.get("/aptidao-gaez", response_model=GAEZAptidaoResponse)
def consultar_aptidao_gaez(
    lat: Optional[float] = Query(default=None),
    lng: Optional[float] = Query(default=None),
    terreno_id: Optional[int] = Query(default=None, gt=0),
    agua: Optional[str] = Query(default=None),
    metodo_irrigacao: Optional[str] = Query(default=None),
    nivel_insumo: Optional[str] = Query(default=None),
    sincronizar_catalogo: bool = Query(default=False),
    db: Session = Depends(get_db),
    gaez_provider: Any = Depends(get_gaez_provider),
):
    """
    Consulta diretamente os dados de 'Suitability and Attainable Yield' (RES05-SUX/YLX)
    e solo (HWSD v2.01 / SQ-IDX / SLOPE-MED) no FAO GAEZ v5, com sincronização opcional
    no catálogo [M2].
    """
    prioridades: Dict[str, Any] = {}
    coords: Any

    if terreno_id is not None:
        terreno = (
            db.query(models.Terreno).filter(models.Terreno.id == terreno_id).first()
        )
        if not terreno:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Terreno não encontrado",
            )
        coords = terreno.coordenadas_poligono
        if not coords and isinstance(terreno.localizacao_central, dict):
            coords = terreno.localizacao_central
        if isinstance(terreno.prioridades, dict):
            prioridades.update(terreno.prioridades)
    else:
        if lat is None or lng is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Informe lat e lng ou um terreno_id válido.",
            )
        coords = {"lat": float(lat), "lng": float(lng)}

    if agua is not None:
        prioridades["agua"] = agua
    if metodo_irrigacao is not None:
        prioridades["metodo_irrigacao"] = metodo_irrigacao
    if nivel_insumo is not None:
        prioridades["nivel_insumo"] = nivel_insumo

    gaez_res = gaez_provider.extract_gaez_metrics(coords, prioridades=prioridades)
    if not isinstance(gaez_res, dict) or gaez_res.get("data_quality") == "no_data":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível obter os dados de Suitability and Attainable Yield da API FAO GAEZ v5.",
        )

    crops_dict = gaez_res.get("crops") or {}
    culturas_ordenadas = sorted(
        crops_dict.values(),
        key=lambda c: (
            float(c.get("suitability_index", 0.0)),
            float(c.get("attainable_yield_kg_ha", 0.0)),
        ),
        reverse=True,
    )

    culturas_sincronizadas: List[models.Cultura] = []
    if sincronizar_catalogo:
        existentes = {
            c.nome.strip().lower(): c
            for c in db.query(models.Cultura).all()
            if c.nome
        }
        for item in culturas_ordenadas:
            if float(item.get("suitability_index", 0.0)) <= 0.0:
                continue
            nome = str(item["nome"]).strip()
            resumo_gaez = (
                f"GAEZ v5 ({gaez_res.get('input_level', 'LRLM')}): "
                f"aptidão {item['suitability_score_100']:.0f}% ({item['suitability_class']}), "
                f"produtividade atingível ~{item['attainable_yield_kg_ha']:.0f} kg/ha"
            )
            existente = existentes.get(nome.lower())
            if existente is not None:
                if existente.is_seed:
                    continue
                existente.consumo_agua_mm = float(item["consumo_agua_mm"])
                existente.tempo_colheita_dias = int(item["tempo_colheita_dias"])
                existente.resistencia_pragas = resumo_gaez
                culturas_sincronizadas.append(existente)
            else:
                nova = models.Cultura(
                    nome=nome,
                    consumo_agua_mm=float(item["consumo_agua_mm"]),
                    tempo_colheita_dias=int(item["tempo_colheita_dias"]),
                    resistencia_pragas=resumo_gaez,
                    is_seed=False,
                    customizada=True,
                )
                db.add(nova)
                existentes[nome.lower()] = nova
                culturas_sincronizadas.append(nova)

        if culturas_sincronizadas:
            db.commit()
            for obj in culturas_sincronizadas:
                db.refresh(obj)

    return {
        "origem": gaez_res.get("origem", "fao_gaez_v5"),
        "data_quality": gaez_res.get("data_quality", "gaez_v5_cog"),
        "input_level": gaez_res.get("input_level", "LRLM"),
        "ssp_scenario": gaez_res.get("ssp_scenario", "SSP370"),
        "centroid": gaez_res.get("centroid") or {},
        "soil": gaez_res.get("soil") or {},
        "culturas_avaliadas": culturas_ordenadas,
        "culturas_sincronizadas": culturas_sincronizadas,
    }


@router.get("/", response_model=List[CulturaResponse])
def listar_culturas(
    is_seed: Optional[bool] = Query(default=None),
    customizada: Optional[bool] = Query(default=None),
    usuario_id: Optional[int] = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(models.Cultura)
    if is_seed is not None:
        query = query.filter(models.Cultura.is_seed == is_seed)
    if customizada is not None:
        query = query.filter(models.Cultura.customizada == customizada)
    if usuario_id is not None:
        query = query.filter(models.Cultura.usuario_id == usuario_id)
    return query.order_by(models.Cultura.id.asc()).offset(skip).limit(limit).all()


@router.get("/{cultura_id}", response_model=CulturaResponse)
def buscar_cultura(cultura_id: int, db: Session = Depends(get_db)):
    return _obter_cultura_ou_404(cultura_id, db)


@router.post("/", response_model=CulturaResponse)
def criar_cultura(cultura: CulturaCreate, db: Session = Depends(get_db)):
    nome_limpo = cultura.nome.strip()
    db_cultura = (
        db.query(models.Cultura)
        .filter(func.lower(models.Cultura.nome) == nome_limpo.lower())
        .first()
    )
    if db_cultura:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cultura já cadastrada",
        )

    _validar_usuario_opcional(cultura.usuario_id, db)

    payload = (
        cultura.model_dump() if hasattr(cultura, "model_dump") else cultura.dict()
    )
    payload["nome"] = nome_limpo
    nova_cultura = models.Cultura(
        **payload,
        is_seed=False,
        customizada=True,
    )
    db.add(nova_cultura)
    db.commit()
    db.refresh(nova_cultura)
    return nova_cultura


@router.put("/{cultura_id}", response_model=CulturaResponse)
def atualizar_cultura(
    cultura_id: int,
    payload: CulturaUpdate,
    db: Session = Depends(get_db),
):
    cultura = _obter_cultura_ou_404(cultura_id, db)
    if cultura.is_seed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Culturas iniciais (seed) do sistema não podem ser editadas.",
        )

    atualizacoes = (
        payload.model_dump(exclude_unset=True)
        if hasattr(payload, "model_dump")
        else payload.dict(exclude_unset=True)
    )
    if "nome" in atualizacoes and atualizacoes["nome"] is not None:
        nome_limpo = atualizacoes["nome"].strip()
        conflito = (
            db.query(models.Cultura)
            .filter(
                func.lower(models.Cultura.nome) == nome_limpo.lower(),
                models.Cultura.id != cultura_id,
            )
            .first()
        )
        if conflito:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Já existe outra cultura cadastrada com este nome.",
            )
        atualizacoes["nome"] = nome_limpo

    for campo, valor in atualizacoes.items():
        setattr(cultura, campo, valor)

    db.commit()
    db.refresh(cultura)
    return cultura


@router.delete("/{cultura_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_cultura(cultura_id: int, db: Session = Depends(get_db)):
    cultura = _obter_cultura_ou_404(cultura_id, db)
    if cultura.is_seed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Culturas iniciais (seed) do sistema não podem ser removidas.",
        )

    # Desvincula atividades do calendário antes da remoção para manter integridade referencial
    db.query(models.Activity).filter(models.Activity.cultura_id == cultura_id).update(
        {"cultura_id": None}
    )
    db.delete(cultura)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@rotacao_router.get("/", response_model=List[RotacaoResponse])
def listar_rotacoes(
    usuario_id: Optional[int] = Query(default=None),
    terreno_id: Optional[int] = Query(default=None),
    preferencial: Optional[bool] = Query(default=None),
    is_seed: Optional[bool] = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(models.RotacaoProdutor)
    if usuario_id is not None:
        query = query.filter(models.RotacaoProdutor.usuario_id == usuario_id)
    if terreno_id is not None:
        query = query.filter(models.RotacaoProdutor.terreno_id == terreno_id)
    if preferencial is not None:
        query = query.filter(models.RotacaoProdutor.preferencial == preferencial)
    if is_seed is not None:
        query = query.filter(models.RotacaoProdutor.is_seed == is_seed)
    return query.order_by(models.RotacaoProdutor.id.asc()).offset(skip).limit(limit).all()


@rotacao_router.get("/{rotacao_id}", response_model=RotacaoResponse)
def buscar_rotacao(rotacao_id: int, db: Session = Depends(get_db)):
    return _obter_rotacao_ou_404(rotacao_id, db)


@rotacao_router.post(
    "/",
    response_model=RotacaoResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_rotacao(payload: RotacaoCreate, db: Session = Depends(get_db)):
    _validar_usuario_opcional(payload.usuario_id, db)
    _validar_terreno_opcional(payload.terreno_id, db)

    nome_rotacao = payload.nome or " -> ".join(payload.culturas)
    duplicada_query = db.query(models.RotacaoProdutor).filter(
        func.lower(models.RotacaoProdutor.nome) == nome_rotacao.lower(),
        models.RotacaoProdutor.usuario_id == payload.usuario_id,
        models.RotacaoProdutor.terreno_id == payload.terreno_id,
    )
    if duplicada_query.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rotação já cadastrada para este escopo.",
        )

    nova_rotacao = models.RotacaoProdutor(
        nome=nome_rotacao,
        culturas=payload.culturas,
        usuario_id=payload.usuario_id,
        terreno_id=payload.terreno_id,
        preferencial=payload.preferencial,
        is_seed=False,
        beneficios=payload.beneficios,
    )
    db.add(nova_rotacao)
    db.commit()
    db.refresh(nova_rotacao)
    return nova_rotacao


@rotacao_router.put("/{rotacao_id}", response_model=RotacaoResponse)
def atualizar_rotacao(
    rotacao_id: int,
    payload: RotacaoUpdate,
    db: Session = Depends(get_db),
):
    rotacao = _obter_rotacao_ou_404(rotacao_id, db)
    if rotacao.is_seed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rotações iniciais (seed) do sistema não podem ser editadas.",
        )

    atualizacoes = (
        payload.model_dump(exclude_unset=True)
        if hasattr(payload, "model_dump")
        else payload.dict(exclude_unset=True)
    )
    if "terreno_id" in atualizacoes:
        _validar_terreno_opcional(atualizacoes["terreno_id"], db)

    if "culturas" in atualizacoes and "nome" not in atualizacoes:
        atualizacoes["nome"] = " -> ".join(atualizacoes["culturas"])

    novo_nome = atualizacoes.get("nome")
    if novo_nome is not None:
        conflito = (
            db.query(models.RotacaoProdutor)
            .filter(
                func.lower(models.RotacaoProdutor.nome) == novo_nome.lower(),
                models.RotacaoProdutor.usuario_id == rotacao.usuario_id,
                models.RotacaoProdutor.terreno_id == atualizacoes.get("terreno_id", rotacao.terreno_id),
                models.RotacaoProdutor.id != rotacao_id,
            )
            .first()
        )
        if conflito:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Já existe outra rotação cadastrada com este nome.",
            )

    for campo, valor in atualizacoes.items():
        setattr(rotacao, campo, valor)

    db.commit()
    db.refresh(rotacao)
    return rotacao


@rotacao_router.delete("/{rotacao_id}", status_code=status.HTTP_204_NO_CONTENT)
def remover_rotacao(rotacao_id: int, db: Session = Depends(get_db)):
    rotacao = _obter_rotacao_ou_404(rotacao_id, db)
    if rotacao.is_seed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rotações iniciais (seed) do sistema não podem ser removidas.",
        )

    db.delete(rotacao)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

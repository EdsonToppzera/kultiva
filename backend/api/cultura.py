import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.database import get_db
from backend.schemas.rotacao import (
    CulturaCatalogoItem,
    CulturaCreate,
    CulturaResponse,
    CulturaUpdate,
    EcoCropLookupResponse,
    GAEZAptidaoResponse,
    PragaCatalogoItem,
    RotacaoCreate,
    RotacaoResponse,
    RotacaoUpdate,
)
from backend.services.ecocrop_seed import seed_agrofit, seed_ecocrop
from backend.services.ecocrop_service import EcoCropDataProvider
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


def get_ecocrop_provider() -> EcoCropDataProvider:
    """Provedor de dependência para o cliente direto da base FAO ECOCROP."""
    return EcoCropDataProvider(data_path="data")


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


@router.get("/ecocrop", response_model=EcoCropLookupResponse)
def consultar_ecocrop(
    q: Optional[str] = Query(default=None, description="Nome popular, científico ou código GAEZ/EcoPort"),
    nome: Optional[str] = Query(default=None),
    scientific_name: Optional[str] = Query(default=None),
    crop_code: Optional[str] = Query(default=None),
    ecoport_code: Optional[str] = Query(default=None),
    cultura_id: Optional[int] = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    ecocrop_provider: Any = Depends(get_ecocrop_provider),
):
    """
    Consulta diretamente a zona de conforto climático (TMIN/TMAX, TOPMIN/TOPMAX,
    RMIN/RMAX, GMIN/GMAX) e taxonomia (Scientific Name e Family) na base FAO ECOCROP.
    """
    termo = ecoport_code or scientific_name or crop_code or nome or q
    if not termo and cultura_id is not None:
        cultura_db = _obter_cultura_ou_404(cultura_id, db)
        termo = cultura_db.nome

    if not termo or not str(termo).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Informe 'q', 'scientific_name', 'crop_code', 'ecoport_code', 'nome' ou 'cultura_id'.",
        )

    res = ecocrop_provider.lookup_crop(str(termo).strip())
    if not isinstance(res, dict) or res.get("data_quality") == "no_data":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Não foi possível consultar os dados da base ECOCROP.",
        )

    if not res.get("found") or res.get("crop") is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cultura '{termo}' não encontrada na base ECOCROP.",
        )

    return res


_PEST_SUFFIX_RE = re.compile(r"\s*\(\d+\)\s*$")


@lru_cache(maxsize=1)
def _load_agrofit_weeds() -> Set[str]:
    weeds_path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "processed"
        / "agrofit_weeds.txt"
    )
    if not weeds_path.exists():
        return set()
    return {
        line.strip().lower()
        for line in weeds_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _garantir_catalogo_ecocrop_agrofit(db: Session) -> None:
    if db.query(models.CulturaLimite).count() == 0:
        seed_ecocrop(db=db)
    if db.query(models.CulturaPraga).count() == 0 or (
        db.query(models.CulturaPraga)
        .filter(models.CulturaPraga.praga_nome_cientifico == "Cenchrus echinatus")
        .first()
        is None
    ):
        seed_agrofit(db=db, replace=True)


def _limpar_nomes_populares_praga(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    result: List[str] = []
    seen: set[str] = set()
    for part in raw.split(";"):
        cleaned = _PEST_SUFFIX_RE.sub("", part.strip()).strip()
        if not cleaned or cleaned in {"-", "--", "---"}:
            continue
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


@router.get("/catalogo/buscar", response_model=List[CulturaCatalogoItem])
def buscar_culturas_catalogo(
    q: str = Query(default="", description="Termo de busca (nome científico ou popular)."),
    lang: str = Query(default="pt", pattern="^(pt|en)$", description="Idioma dos nomes populares (pt em uso; en reservado para expansão)."),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Busca culturas na base integrada EcoCrop + AGROFIT por qualquer nome popular ou científico."""
    _garantir_catalogo_ecocrop_agrofit(db)

    syn_model = (
        models.CulturaSinonimoPt if lang == "pt" else models.CulturaSinonimoEn
    )

    termo = q.strip()
    if termo:
        pattern = f"%{termo}%"
        syn_sci_subq = (
            db.query(syn_model.scientific_name)
            .filter(syn_model.synonym.ilike(pattern))
        )
        filters = [
            models.CulturaLimite.scientific_name.ilike(pattern),
            models.CulturaLimite.scientific_name.in_(syn_sci_subq),
        ]
        if lang == "pt":
            praga_sci_subq = (
                db.query(models.CulturaPraga.scientific_name)
                .filter(models.CulturaPraga.cultura_agrofit.ilike(pattern))
            )
            filters.append(models.CulturaLimite.scientific_name.in_(praga_sci_subq))

        matched_rows = (
            db.query(models.CulturaLimite)
            .filter(or_(*filters))
            .order_by(models.CulturaLimite.scientific_name.asc())
            .limit(limit * 3)
            .all()
        )
    else:
        agrofit_scis = [
            r[0]
            for r in db.query(models.CulturaPraga.scientific_name)
            .distinct()
            .limit(limit)
            .all()
        ]
        if agrofit_scis:
            matched_rows = (
                db.query(models.CulturaLimite)
                .filter(models.CulturaLimite.scientific_name.in_(agrofit_scis))
                .all()
            )
        else:
            matched_rows = (
                db.query(models.CulturaLimite)
                .order_by(models.CulturaLimite.scientific_name.asc())
                .limit(limit)
                .all()
            )

    if not matched_rows:
        return []

    sci_names = [row.scientific_name for row in matched_rows]

    agrofit_names_map: Dict[str, List[str]] = {}
    if lang == "pt":
        for sci, agro_name in (
            db.query(
                models.CulturaPraga.scientific_name,
                models.CulturaPraga.cultura_agrofit,
            )
            .filter(models.CulturaPraga.scientific_name.in_(sci_names))
            .distinct()
            .all()
        ):
            if agro_name:
                agrofit_names_map.setdefault(sci, []).append(agro_name.strip())

    synonyms_map: Dict[str, List[str]] = {}
    for sci, syn in (
        db.query(syn_model.scientific_name, syn_model.synonym)
        .filter(syn_model.scientific_name.in_(sci_names))
        .all()
    ):
        if syn:
            synonyms_map.setdefault(sci, []).append(syn.strip())

    items: List[CulturaCatalogoItem] = []
    for row in matched_rows:
        sci = row.scientific_name
        pt_names = sorted(agrofit_names_map.get(sci, []), key=len)
        lang_syns = synonyms_map.get(sci, [])

        merged_popular: List[str] = []
        seen_pop: set[str] = set()
        for candidate in [*pt_names, *lang_syns]:
            key = candidate.lower()
            if candidate and key not in seen_pop:
                seen_pop.add(key)
                merged_popular.append(candidate)

        official_name = (
            pt_names[0]
            if pt_names
            else (merged_popular[0] if merged_popular else sci)
        )

        items.append(
            CulturaCatalogoItem(
                id=sci,
                scientific_name=sci,
                official_name=official_name,
                popular_names=merged_popular or [sci],
                family=row.family,
                cat=row.cat,
                gmin=row.gmin,
                gmax=row.gmax,
                image_url=None,
            )
        )

    # Prioriza culturas com nome oficial no idioma ativo
    items.sort(
        key=lambda item: (
            0 if item.scientific_name in agrofit_names_map else 1,
            item.official_name.lower(),
        )
    )
    return items[:limit]


_PEST_EN_BY_SCI_PREFIX: List[tuple[str, str, List[str]]] = [
    ("bemisia tabaci", "Whitefly", ["Whitefly", "Silverleaf whitefly"]),
    ("spodoptera frugiperda", "Fall armyworm", ["Fall armyworm", "Corn leafworm"]),
    ("colletotrichum", "Anthracnose", ["Anthracnose", "Black spot"]),
    ("tetranychus urticae", "Two-spotted spider mite", ["Two-spotted spider mite", "Red spider mite"]),
    ("diabrotica speciosa", "Cucumber beetle", ["Cucumber beetle", "Rootworm"]),
    ("alternaria solani", "Early blight", ["Early blight", "Alternaria leaf spot"]),
    ("sclerotinia sclerotiorum", "White mold", ["White mold", "Sclerotinia stem rot"]),
    ("helicoverpa armigera", "Cotton bollworm", ["Cotton bollworm", "Corn earworm"]),
    ("myzus persicae", "Green peach aphid", ["Green peach aphid", "Aphid"]),
    ("aphis gossypii", "Cotton aphid", ["Cotton aphid", "Melon aphid"]),
    ("frankliniella", "Thrips", ["Thrips", "Western flower thrips"]),
    ("phytophthora infestans", "Late blight", ["Late blight", "Potato blight"]),
    ("pseudoperonospora cubensis", "Downy mildew", ["Downy mildew", "Cucurbit downy mildew"]),
    ("polyphagotarsonemus latus", "Broad mite", ["Broad mite", "Tropical mite"]),
    ("anticarsia gemmatalis", "Velvetbean caterpillar", ["Velvetbean caterpillar", "Soybean caterpillar"]),
    ("phaeoisariopsis griseola", "Angular leaf spot", ["Angular leaf spot"]),
    ("botrytis cinerea", "Gray mold", ["Gray mold", "Botrytis blight"]),
    ("sphaerotheca fuliginea", "Powdery mildew", ["Powdery mildew"]),
    ("meloidogyne", "Root-knot nematode", ["Root-knot nematode", "Nematodes"]),
    ("atta", "Leafcutter ant", ["Leafcutter ant", "Saúva ant"]),
    ("acromyrmex", "Leafcutter ant", ["Leafcutter ant", "Quenquém ant"]),
    ("dalbulus maidis", "Corn leafhopper", ["Corn leafhopper", "Corn stunt"]),
    ("ralstonia solanacearum", "Bacterial wilt", ["Bacterial wilt", "Brown rot"]),
    ("neoleucinodes elegantalis", "Tomato fruit borer", ["Tomato fruit borer"]),
    ("tuta absoluta", "Tomato leafminer", ["Tomato leafminer", "South American tomato pinworm"]),
    ("thrips tabaci", "Onion thrips", ["Onion thrips", "Thrips"]),
    ("anastrepha", "Fruit fly", ["Fruit fly", "South American fruit fly"]),
    ("ceratitis capitata", "Mediterranean fruit fly", ["Mediterranean fruit fly", "Medfly"]),
    ("euschistus heros", "Neotropical brown stink bug", ["Brown stink bug", "Stink bug"]),
    ("nezara viridula", "Southern green stink bug", ["Green stink bug", "Stink bug"]),
    ("fusarium", "Fusarium wilt", ["Fusarium wilt", "Root rot"]),
    ("rhizoctonia solani", "Root rot", ["Root rot", "Damping off"]),
    ("puccinia", "Rust", ["Rust", "Leaf rust"]),
    ("cercospora", "Cercospora leaf spot", ["Cercospora leaf spot", "Leaf spot"]),
    ("xanthomonas", "Bacterial spot", ["Bacterial spot", "Bacterial blight"]),
    ("cenchrus echinatus", "Southern sandbur", ["Southern sandbur", "Sandbur grass"]),
    ("digitaria horizontalis", "Jamaican crabgrass", ["Jamaican crabgrass", "Crabgrass"]),
    ("digitaria insularis", "Sourgrass", ["Sourgrass"]),
    ("euphorbia heterophylla", "Wild poinsettia", ["Wild poinsettia", "Mexican fireplant"]),
    ("brachiaria", "Signalgrass", ["Signalgrass"]),
    ("eleusine indica", "Goosegrass", ["Goosegrass", "Crowfootgrass"]),
    ("zea mays", "Volunteer corn", ["Volunteer corn", "Corn"]),
    ("oryza sativa", "Volunteer rice", ["Volunteer rice", "Red rice"]),
    ("amaranthus", "Pigweed", ["Pigweed", "Amaranth"]),
    ("cynodon dactylon", "Bermudagrass", ["Bermudagrass"]),
    ("galinsoga parviflora", "Gallant soldier", ["Gallant soldier", "Quickweed"]),
    ("portulaca oleracea", "Common purslane", ["Common purslane", "Purslane"]),
    ("panicum maximum", "Guinea grass", ["Guinea grass"]),
    ("echinochloa", "Barnyardgrass", ["Barnyardgrass"]),
    ("bidens pilosa", "Beggarticks", ["Beggarticks", "Blackjack"]),
    ("sorghum halepense", "Johnsongrass", ["Johnsongrass"]),
    ("commelina benghalensis", "Tropical spiderwort", ["Tropical spiderwort", "Dayflower"]),
    ("cyperus", "Nutsedge", ["Nutsedge"]),
]

_PEST_EN_BY_PT_KEYWORD: List[tuple[str, str]] = [
    ("mosca-branca", "Whitefly"),
    ("mosca branca", "Whitefly"),
    ("lagarta-do-cartucho", "Fall armyworm"),
    ("lagarta-militar", "Fall armyworm"),
    ("lagarta", "Caterpillar"),
    ("antracnose", "Anthracnose"),
    ("ácaro-rajado", "Two-spotted spider mite"),
    ("acaro-rajado", "Two-spotted spider mite"),
    ("ácaro", "Mite"),
    ("acaro", "Mite"),
    ("pulgão", "Aphid"),
    ("pulgao", "Aphid"),
    ("tripes", "Thrips"),
    ("mofo branco", "White mold"),
    ("mofo-branco", "White mold"),
    ("mofo-cinzento", "Gray mold"),
    ("míldio", "Downy mildew"),
    ("oídio", "Powdery mildew"),
    ("ferrugem", "Rust"),
    ("nematoide", "Nematodes"),
    ("formiga", "Leafcutter ant"),
    ("cigarrinha", "Leafhopper"),
    ("percevejo", "Stink bug"),
    ("vaquinha", "Cucumber beetle"),
    ("podridão", "Root rot"),
    ("murcha", "Wilt"),
    ("cochonilha", "Scale insect"),
    ("broca", "Borer"),
    ("mancha", "Leaf spot"),
    ("requeima", "Late blight"),
    ("pinta-preta", "Early blight"),
]


def _traduzir_praga_para_en(
    sci_name: Optional[str],
    popular_names: List[str],
    official_pt: str,
) -> tuple[str, List[str]]:
    sci_low = (sci_name or "").strip().lower()
    for prefix, en_official, en_pops in _PEST_EN_BY_SCI_PREFIX:
        if sci_low.startswith(prefix):
            return en_official, en_pops
    joined_pt = " ".join([official_pt, *popular_names]).lower()
    for kw, en_name in _PEST_EN_BY_PT_KEYWORD:
        if kw in joined_pt:
            return en_name, [en_name]
    return official_pt, popular_names


@router.get("/pragas/buscar", response_model=List[PragaCatalogoItem])
def buscar_pragas_catalogo(
    q: str = Query(default="", description="Termo de busca (nome popular ou científico da praga)."),
    lang: str = Query(default="pt", pattern="^(pt|en)$", description="Idioma dos nomes populares (pt ou en)."),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Busca pragas e doenças na base AGROFIT exibindo os nomes populares."""
    _garantir_catalogo_ecocrop_agrofit(db)

    query = db.query(
        models.CulturaPraga.praga_nome_cientifico,
        models.CulturaPraga.praga_nome_comum,
    )
    termo = q.strip()
    if termo and lang == "pt":
        pattern = f"%{termo}%"
        query = query.filter(
            or_(
                models.CulturaPraga.praga_nome_comum.ilike(pattern),
                models.CulturaPraga.praga_nome_cientifico.ilike(pattern),
            )
        )

    rows = query.limit(2000).all()

    grouped: Dict[str, Dict[str, Any]] = {}
    for sci, comum_raw in rows:
        sci_clean = (sci or "").strip()
        pop_list = _limpar_nomes_populares_praga(comum_raw)
        key = sci_clean or (pop_list[0] if pop_list else "")
        if not key:
            continue

        entry = grouped.setdefault(
            key,
            {
                "scientific_name": sci_clean or None,
                "popular_names": [],
                "seen": set(),
                "count": 0,
            },
        )
        entry["count"] += 1
        for pop in pop_list:
            low = pop.lower()
            if low not in entry["seen"]:
                entry["seen"].add(low)
                entry["popular_names"].append(pop)

    termo_low = termo.lower()
    weed_set = _load_agrofit_weeds()
    items: List[tuple[int, PragaCatalogoItem]] = []
    for key, data in grouped.items():
        popular_names: List[str] = data["popular_names"]
        sci_name: Optional[str] = data["scientific_name"]
        official_name = popular_names[0] if popular_names else (sci_name or key)
        display_pops = popular_names if popular_names else [official_name]
        is_weed = bool(sci_name and sci_name.lower() in weed_set)
        category = (
            ("Weed" if lang == "en" else "Erva daninha")
            if is_weed
            else ("Pest / Disease" if lang == "en" else "Praga / Doença")
        )

        if lang == "en":
            official_name, display_pops = _traduzir_praga_para_en(
                sci_name, display_pops, official_name
            )
            if termo_low:
                haystack = " ".join(
                    [official_name, sci_name or "", *display_pops]
                ).lower()
                if termo_low not in haystack:
                    continue

        items.append(
            (
                data["count"],
                PragaCatalogoItem(
                    id=key.lower().replace(" ", "-"),
                    official_name=official_name,
                    popular_names=display_pops,
                    scientific_name=sci_name,
                    category=category,
                ),
            )
        )

    items.sort(key=lambda pair: (-pair[0], pair[1].official_name.lower()))
    return [item for _, item in items[:limit]]


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

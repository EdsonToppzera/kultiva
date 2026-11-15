from datetime import date, datetime, timedelta, timezone
import logging
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.api.simulacao import get_rotation_explainer
from backend.api.terreno import limpar_dependencias_terreno
from backend.db import models
from backend.db.database import get_db
from backend.schemas.demo import DemoSeedResponse
from backend.services.geospatial import MockNASADataProvider, calcular_geometria_terreno
from backend.services.llm_agent import DISCLAIMER
from backend.services.metrics_service import persistir_metricas_terreno

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo", tags=["Demonstração (Demo)"])

_DEMO_USER_EMAIL = "produtor@kultiva.agro"
_DEMO_USER_NAME = "Produtor Rural Kultiva"

_DEMO_TERRENOS = [
    {
        "nome_propriedade": "Sítio Boa Esperança (Demo Seca)",
        "coordenadas_poligono": [
            {"lat": -7.230, "lng": -35.880},
            {"lat": -7.236, "lng": -35.880},
            {"lat": -7.236, "lng": -35.874},
            {"lat": -7.230, "lng": -35.874},
        ],
        "prioridades": {
            "agua": "escassa",
            "foco_mercado": "local",
            "tolerancia_seca": True,
        },
        "perfil": "seca",
        "rotacao_custom": {
            "nome": "Feijão Macáçar -> Mandioca -> Crotalária",
            "culturas": ["Feijão Macáçar", "Mandioca", "Crotalária"],
            "beneficios": "Alta tolerância à seca com cobertura contínua do solo.",
        },
        "alerta": {
            "tipo_evento": "seca",
            "severidade": "alta",
            "cultura": "Feijão Macáçar",
            "titulo": "Alerta de déficit hídrico e solo seco no Cariri",
            "mensagem": (
                "Umidade do solo caiu abaixo de 12% nos últimos dias com temperaturas "
                "superiores a 35 °C. Recomenda-se reforçar cobertura morta e priorizar irrigação."
            ),
            "resumo_adaptacao": (
                "Irrigação preventiva antecipada para horário ameno e aplicação de cobertura morta."
            ),
            "dados_gatilho": {
                "min_soil_moisture": 0.10,
                "max_surface_temp_c": 36.2,
                "max_precipitation_mm": 0.0,
            },
        },
    },
    {
        "nome_propriedade": "Fazenda Vale Verde (Demo Irrigado)",
        "coordenadas_poligono": [
            {"lat": -8.050, "lng": -35.950},
            {"lat": -8.057, "lng": -35.950},
            {"lat": -8.057, "lng": -35.943},
            {"lat": -8.050, "lng": -35.943},
        ],
        "prioridades": {
            "agua": "moderada",
            "foco_mercado": "regional",
            "conservacao_solo": True,
        },
        "perfil": "chuva_extrema",
        "rotacao_custom": None,
        "alerta": {
            "tipo_evento": "chuva_intensa",
            "severidade": "media",
            "cultura": "Milho",
            "titulo": "Alerta de chuva intensa na zona de cultivo",
            "mensagem": (
                "Precipitação acumulada acima do esperado pode causar lixiviação de "
                "nutrientes. Adubação em cobertura reagendada."
            ),
            "resumo_adaptacao": (
                "Adubação em cobertura adiada em 2 dias para evitar perda por enxurrada."
            ),
            "dados_gatilho": {
                "min_soil_moisture": 0.35,
                "max_surface_temp_c": 27.5,
                "max_precipitation_mm": 85.0,
            },
        },
    },
]


def _garantir_usuario_demo(db: Session) -> models.Usuario:
    usuario = (
        db.query(models.Usuario)
        .filter(models.Usuario.email == _DEMO_USER_EMAIL)
        .first()
    )
    if usuario is None:
        usuario = models.Usuario(
            nome=_DEMO_USER_NAME,
            email=_DEMO_USER_EMAIL,
        )
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
    return usuario


def _extrair_field_metrics_perfil_demo(
    perfil: str,
    coordenadas_poligono: List[Dict[str, float]],
    hoje: date,
) -> Dict[str, Any]:
    """Extrai métricas reais dos NetCDFs A9 em diretório temporário e alinha datas até hoje."""
    with tempfile.TemporaryDirectory(prefix="kultiva_demo_") as tmp_dir:
        provider = MockNASADataProvider(data_path=tmp_dir, profile=perfil)
        extraido = provider.extract_field_metrics(coordenadas_poligono)

    serie_bruta = extraido.get("time_series") or []
    total_dias = len(serie_bruta)
    serie_ajustada: List[Dict[str, Any]] = []

    for idx, ponto in enumerate(serie_bruta):
        dt = hoje - timedelta(days=total_dias - 1 - idx)
        umidade = round(float(ponto["soil_moisture"]), 4)
        temp = round(float(ponto["surface_temp_c"]), 2)
        precip = round(float(ponto["precipitation_mm"]), 2)
        bare = (
            umidade < provider.BARE_MOISTURE_MAX
            and temp >= provider.BARE_TEMP_MIN_C
        )
        serie_ajustada.append(
            {
                "data": dt.isoformat(),
                "soil_moisture": umidade,
                "surface_temp_c": temp,
                "precipitation_mm": precip,
                "is_bare_field_period": bare,
            }
        )

    return {
        **extraido,
        "origem": f"demo_seed:{perfil}",
        "time_series": serie_ajustada,
    }


def _gerar_explicacao_alerta_demo(
    alerta_spec: Dict[str, Any],
    explainer_agent: Optional[Any],
) -> str:
    resumo_base = alerta_spec["resumo_adaptacao"]
    if explainer_agent is not None and hasattr(explainer_agent, "explain_alert"):
        try:
            texto = explainer_agent.explain_alert(
                tipo_evento=alerta_spec["tipo_evento"],
                severidade=alerta_spec["severidade"],
                cultura=alerta_spec.get("cultura"),
                resumo_adaptacao=resumo_base,
                detalhes_clima=alerta_spec.get("dados_gatilho"),
            )
            if isinstance(texto, str) and texto.strip():
                return texto.strip()
        except Exception as exc:
            logger.warning("Fallback de explicação de alerta na demo: %s", exc)
    return f"{resumo_base} {DISCLAIMER}".strip()


def _garantir_terreno_demo(
    db: Session,
    usuario_id: int,
    spec: Dict[str, Any],
    reset: bool,
) -> models.Terreno:
    terreno = (
        db.query(models.Terreno)
        .filter(
            models.Terreno.usuario_id == usuario_id,
            models.Terreno.nome_propriedade == spec["nome_propriedade"],
        )
        .first()
    )
    geo = calcular_geometria_terreno(spec["coordenadas_poligono"])
    area = float(geo.get("area_hectares") or 0.0) or 1.0
    centro = geo.get("localizacao_central")

    if terreno is None:
        terreno = models.Terreno(
            nome_propriedade=spec["nome_propriedade"],
            usuario_id=usuario_id,
            coordenadas_poligono=spec["coordenadas_poligono"],
            area_hectares=area,
            localizacao_central=centro,
            prioridades=spec["prioridades"],
        )
        db.add(terreno)
        db.commit()
        db.refresh(terreno)
    elif reset:
        limpar_dependencias_terreno(db, terreno.id)
        db.flush()
        terreno.coordenadas_poligono = spec["coordenadas_poligono"]
        terreno.area_hectares = area
        terreno.localizacao_central = centro
        terreno.prioridades = spec["prioridades"]
        db.commit()
        db.refresh(terreno)
    return terreno


def _popular_terreno_demo(
    db: Session,
    usuario: models.Usuario,
    terreno: models.Terreno,
    spec: Dict[str, Any],
    culturas_por_nome: Dict[str, models.Cultura],
    hoje: date,
    explainer_agent: Optional[Any],
) -> None:
    rot_spec = spec.get("rotacao_custom")
    if rot_spec:
        existe_rot = (
            db.query(models.RotacaoProdutor)
            .filter(
                models.RotacaoProdutor.terreno_id == terreno.id,
                models.RotacaoProdutor.nome == rot_spec["nome"],
            )
            .first()
        )
        if existe_rot is None:
            db.add(
                models.RotacaoProdutor(
                    nome=rot_spec["nome"],
                    culturas=rot_spec["culturas"],
                    usuario_id=usuario.id,
                    terreno_id=terreno.id,
                    preferencial=True,
                    is_seed=False,
                    beneficios=rot_spec["beneficios"],
                )
            )

    if (
        db.query(models.MetricaHistoricaTerreno)
        .filter(models.MetricaHistoricaTerreno.terreno_id == terreno.id)
        .count()
        == 0
    ):
        field_metrics = _extrair_field_metrics_perfil_demo(
            spec["perfil"],
            spec["coordenadas_poligono"],
            hoje,
        )
        persistir_metricas_terreno(
            db=db,
            terreno_id=terreno.id,
            field_metrics=field_metrics,
            origem=str(field_metrics.get("origem") or f"demo_seed:{spec['perfil']}"),
            data_referencia=hoje,
            commit=False,
        )

    if (
        db.query(models.Activity)
        .filter(models.Activity.terreno_id == terreno.id)
        .count()
        == 0
    ):
        cultura_nome = spec["alerta"].get("cultura")
        cultura_obj = culturas_por_nome.get(cultura_nome)
        cultura_id = cultura_obj.id if cultura_obj else None
        agora = datetime.now(timezone.utc)

        if spec["perfil"] == "seca":
            atividades = [
                models.Activity(
                    terreno_id=terreno.id,
                    usuario_id=usuario.id,
                    cultura_id=cultura_id,
                    titulo="Preparo conservacionista do solo",
                    descricao="Gradagem mínima mantendo palhada de cobertura.",
                    tipo_atividade="manejo",
                    data_programada=hoje - timedelta(days=5),
                    prioridade="media",
                    status="concluida",
                    concluida=True,
                    data_conclusao=agora - timedelta(days=5),
                ),
                models.Activity(
                    terreno_id=terreno.id,
                    usuario_id=usuario.id,
                    cultura_id=cultura_id,
                    titulo="Irrigação suplementar prioritária",
                    descricao="Aplicação em gotejamento ao amanhecer.",
                    tipo_atividade="irrigacao",
                    data_programada=hoje,
                    prioridade="critica",
                    status="pendente",
                    concluida=False,
                    ajustada_por_alerta=True,
                    motivo_ajuste="Prioridade elevada pelo alerta de seca severa.",
                ),
                models.Activity(
                    terreno_id=terreno.id,
                    usuario_id=usuario.id,
                    cultura_id=cultura_id,
                    titulo="Inspeção de umidade radicular",
                    descricao="Verificar retenção hídrica após cobertura morta.",
                    tipo_atividade="inspecao",
                    data_programada=hoje + timedelta(days=3),
                    prioridade="alta",
                    status="pendente",
                    concluida=False,
                ),
            ]
        else:
            atividades = [
                models.Activity(
                    terreno_id=terreno.id,
                    usuario_id=usuario.id,
                    cultura_id=cultura_id,
                    titulo="Plantio em contorno de Milho",
                    descricao="Semeadura seguindo curvas de nível.",
                    tipo_atividade="plantio",
                    data_programada=hoje - timedelta(days=6),
                    prioridade="media",
                    status="concluida",
                    concluida=True,
                    data_conclusao=agora - timedelta(days=6),
                ),
                models.Activity(
                    terreno_id=terreno.id,
                    usuario_id=usuario.id,
                    cultura_id=cultura_id,
                    titulo="Adubação nitrogenada em cobertura",
                    descricao="Reagendada para janela sem enxurrada.",
                    tipo_atividade="adubacao",
                    data_programada=hoje + timedelta(days=2),
                    prioridade="alta",
                    status="pendente",
                    concluida=False,
                    ajustada_por_alerta=True,
                    motivo_ajuste="Adiada em 2 dias após alerta de chuva intensa.",
                ),
                models.Activity(
                    terreno_id=terreno.id,
                    usuario_id=usuario.id,
                    cultura_id=cultura_id,
                    titulo="Vistoria de drenagem superficial",
                    descricao="Checar sulcos de escoamento e palhada.",
                    tipo_atividade="inspecao",
                    data_programada=hoje + timedelta(days=4),
                    prioridade="media",
                    status="pendente",
                    concluida=False,
                ),
            ]
        db.add_all(atividades)

    if (
        db.query(models.AlertaClimatico)
        .filter(models.AlertaClimatico.terreno_id == terreno.id)
        .count()
        == 0
    ):
        al = spec["alerta"]
        explicacao = _gerar_explicacao_alerta_demo(al, explainer_agent)
        db.add(
            models.AlertaClimatico(
                terreno_id=terreno.id,
                tipo_evento=al["tipo_evento"],
                severidade=al["severidade"],
                titulo=al["titulo"],
                mensagem=f"{al['mensagem']}\n\n{explicacao}",
                data_evento=hoje - timedelta(days=1),
                origem_gatilho="demo_seed",
                dados_gatilho=al["dados_gatilho"],
                processado_background=True,
                resumo_adaptacao=explicacao,
                lido=False,
            )
        )

    db.commit()


@router.post("/seed", response_model=DemoSeedResponse)
def popular_cenario_demo(
    reset: bool = Query(
        default=False,
        description="Quando true, remove e recria os dados de demonstração do zero.",
    ),
    db: Session = Depends(get_db),
    explainer_agent: Optional[Any] = Depends(get_rotation_explainer),
):
    """Popula usuário, terrenos, métricas históricas, atividades e alertas para demonstração."""
    from backend.main import seed_culturas
    from backend.services.ecocrop_seed import seed_ecocrop

    seed_culturas(db=db)
    seed_ecocrop(db=db, reset=reset)
    usuario = _garantir_usuario_demo(db)
    culturas = db.query(models.Cultura).all()
    culturas_por_nome = {c.nome: c for c in culturas}

    hoje = date.today()
    terrenos_ids: List[int] = []

    for spec in _DEMO_TERRENOS:
        terreno = _garantir_terreno_demo(
            db=db,
            usuario_id=usuario.id,
            spec=spec,
            reset=reset,
        )
        _popular_terreno_demo(
            db=db,
            usuario=usuario,
            terreno=terreno,
            spec=spec,
            culturas_por_nome=culturas_por_nome,
            hoje=hoje,
            explainer_agent=explainer_agent,
        )
        terrenos_ids.append(terreno.id)

    culturas_total = db.query(models.Cultura).count()
    rotacoes_total = db.query(models.RotacaoProdutor).count()
    metricas_total = (
        db.query(models.MetricaHistoricaTerreno)
        .filter(models.MetricaHistoricaTerreno.terreno_id.in_(terrenos_ids))
        .count()
    )
    atividades_total = (
        db.query(models.Activity)
        .filter(models.Activity.terreno_id.in_(terrenos_ids))
        .count()
    )
    alertas_total = (
        db.query(models.AlertaClimatico)
        .filter(models.AlertaClimatico.terreno_id.in_(terrenos_ids))
        .count()
    )

    acao = "recriados" if reset else "garantidos de forma idempotente"
    return DemoSeedResponse(
        status="ok",
        reset_executado=reset,
        idempotente=not reset,
        usuario_id=usuario.id,
        terrenos_ids=terrenos_ids,
        culturas_total=culturas_total,
        rotacoes_total=rotacoes_total,
        metricas_total=metricas_total,
        atividades_total=atividades_total,
        alertas_total=alertas_total,
        resumo=(
            f"Dados de demonstração {acao}: {len(terrenos_ids)} terreno(s), "
            f"{metricas_total} métricas, {atividades_total} atividades e {alertas_total} alertas."
        ),
    )

import asyncio
from contextlib import asynccontextmanager, contextmanager
import importlib
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db import models
from backend.db.database import SessionLocal, get_db
from backend.services.metrics_service import persistir_metricas_terreno

_DEFAULT_SESSION_LOCAL = SessionLocal

logger = logging.getLogger(__name__)

TIPOS_CHUVA = {"chuva_intensa", "tempestade", "heavy_rain"}
TIPOS_CALOR_SECA = {"onda_de_calor", "seca", "heatwave", "drought"}
TIPOS_PRAGA = {"praga", "manejo_fitossanitario", "ocorrencia_praga", "encontrei_praga"}

_DISCLAIMER_ALERTA = (
    "Lembre-se: esta ferramenta serve para apoiar a decisão e identificar possibilidades, "
    "mas não substitui a sua experiência local. A decisão final é sempre sua."
)


def gerar_orientacao_alerta(
    tipo_evento: str,
    severidade: str = "alta",
    resumo_adaptacao: Optional[str] = None,
    detalhes_clima: Optional[Dict[str, Any]] = None,
) -> str:
    """Gera orientação prática acessível para alertas [M5] via explain_alert (A8) com fallback."""
    try:
        llm_mod = importlib.import_module("backend.services.llm_agent")
        agent_cls = getattr(llm_mod, "RotationExplainerAgent", None)
        if agent_cls is not None:
            agent = agent_cls()
            if hasattr(agent, "explain_alert"):
                texto = agent.explain_alert(
                    tipo_evento=tipo_evento,
                    severidade=severidade,
                    resumo_adaptacao=resumo_adaptacao,
                    detalhes_clima=detalhes_clima,
                )
                if isinstance(texto, str) and texto.strip():
                    if "decisão final" not in texto.lower():
                        return f"{texto.strip()}\n\n{_DISCLAIMER_ALERTA}"
                    return texto.strip()
    except Exception as exc:
        logger.warning("Falha em explain_alert; usando orientação determinística: %s", exc)

    ev = str(tipo_evento or "").strip().lower()
    if ev in TIPOS_CHUVA:
        base = (
            "Há previsão de chuva forte. Evite adubar ou aplicar insumos antes da chuva, "
            "verifique valas de drenagem e proteja áreas com solo exposto."
        )
    elif ev in TIPOS_CALOR_SECA:
        base = (
            "Há sinal de calor forte ou tempo seco. Priorize a irrigação nos horários mais frescos "
            "(início da manhã ou fim da tarde) e reforce a cobertura morta para segurar a umidade do solo."
        )
    elif ev in TIPOS_PRAGA:
        base = (
            "Ocorrência de praga registrada na área. Faça uma vistoria nas folhas novas e na base das plantas, "
            "remova focos iniciais manualmente quando possível e priorize controle biológico ou manejo integrado "
            "antes de aplicar defensivos."
        )
    else:
        base = (
            f"Atenção ao alerta de {tipo_evento.replace('_', ' ')} (severidade {severidade}). "
            "Observe a lavoura de perto e ajuste o manejo preventivo conforme a condição do talhão."
        )
    if resumo_adaptacao:
        base = f"{base} {resumo_adaptacao}"
    return f"{base}\n\n{_DISCLAIMER_ALERTA}"


def obter_intervalo_monitoramento_horas(default: int = 6) -> int:
    """Lê ALERT_MONITOR_INTERVAL_HOURS do ambiente com fallback seguro."""
    bruto = os.getenv("ALERT_MONITOR_INTERVAL_HOURS", str(default))
    try:
        return max(1, int(bruto))
    except (TypeError, ValueError):
        return default


def obter_cooldown_alerta_horas(default: int = 24) -> int:
    """Lê ALERT_COOLDOWN_HOURS do ambiente (0 desativa janela de cooldown)."""
    bruto = os.getenv("ALERT_COOLDOWN_HOURS", str(default))
    try:
        return max(0, int(bruto))
    except (TypeError, ValueError):
        return default


def get_nasa_provider(
    data_path: str = "data", profile: Optional[str] = None
) -> Optional[Any]:
    """Instancia o provedor NASA (INASADataProvider) via geospatial.py."""
    try:
        geo_module = importlib.import_module("backend.services.geospatial")
        factory = getattr(geo_module, "get_nasa_data_provider", None)
        if callable(factory):
            if profile is not None:
                try:
                    return factory(data_path=data_path, profile=profile)
                except TypeError:
                    return factory(data_path=data_path)
            return factory(data_path=data_path)
        provider_cls = getattr(geo_module, "MockNASADataProvider", None) or getattr(
            geo_module, "NasaDataProcessor", None
        )
        if provider_cls is None:
            return None
        if profile is not None:
            try:
                return provider_cls(data_path=data_path, profile=profile)
            except TypeError:
                return provider_cls(data_path=data_path)
        return provider_cls(data_path=data_path)
    except Exception:
        return None


def buscar_alerta_duplicado(
    db: Session,
    terreno_id: int,
    tipo_evento: str,
    data_evento: date,
    cooldown_horas: Optional[int] = None,
) -> Optional[models.AlertaClimatico]:
    """
    Verifica se já existe alerta equivalente para evitar duplicidade:
    - mesmo terreno + mesmo tipo_evento + mesma data_evento, ou
    - mesmo terreno + mesmo tipo_evento criado dentro da janela de cooldown.
    """
    tipo_norm = tipo_evento.strip().lower()
    existentes = (
        db.query(models.AlertaClimatico)
        .filter(
            models.AlertaClimatico.terreno_id == terreno_id,
            func.lower(models.AlertaClimatico.tipo_evento) == tipo_norm,
        )
        .order_by(models.AlertaClimatico.id.desc())
        .all()
    )
    if not existentes:
        return None

    horas_cooldown = (
        obter_cooldown_alerta_horas() if cooldown_horas is None else max(0, cooldown_horas)
    )
    agora_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    limite_cooldown = agora_naive - timedelta(hours=horas_cooldown)

    for alerta in existentes:
        if alerta.data_evento == data_evento:
            return alerta
        if horas_cooldown > 0 and alerta.criado_em is not None:
            criado = (
                alerta.criado_em.replace(tzinfo=None)
                if alerta.criado_em.tzinfo is not None
                else alerta.criado_em
            )
            if criado >= limite_cooldown:
                return alerta
    return None


@contextmanager
def _abrir_sessao_background(session_factory=None):
    """
    Abre uma sessão SQLAlchemy respeitando:
    1) `session_factory` explícita;
    2) `alert_tasks.SessionLocal` quando sobrescrita em testes;
    3) override de `get_db` registrado em `backend.main.app.dependency_overrides`, se houver;
    4) fallback para `SessionLocal` padrão.
    """
    if session_factory is not None:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()
        return

    if SessionLocal is not _DEFAULT_SESSION_LOCAL:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
        return

    override_fn = None
    try:
        main_mod = importlib.import_module("backend.main")
        fastapi_app = getattr(main_mod, "app", None)
        if fastapi_app is not None:
            override_fn = fastapi_app.dependency_overrides.get(get_db)
    except Exception:
        override_fn = None

    if override_fn is not None:
        gen = override_fn()
        if hasattr(gen, "__next__"):
            db = next(gen)
            try:
                yield db
            finally:
                try:
                    next(gen)
                except StopIteration:
                    pass
                except Exception:
                    gen.close()
            return
        db = gen
        try:
            yield db
        finally:
            if hasattr(db, "close"):
                db.close()
        return

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def aplicar_regras_ajuste_pos_alerta(
    db: Session,
    alerta: models.AlertaClimatico,
    atividades_pendentes: List[models.Activity],
    dias_adiamento: int = 2,
) -> tuple[int, int]:
    """
    Aplica as regras de ajuste pós-alerta sobre atividades pendentes na janela do evento
    e cria a atividade emergencial correspondente. Retorna (ajustadas, criadas).
    """
    evento = alerta.tipo_evento.strip().lower()
    ajustadas = 0
    criadas = 0

    if evento in TIPOS_CHUVA:
        for atividade in atividades_pendentes:
            if atividade.tipo_atividade.lower() in {
                "irrigacao",
                "adubacao",
                "pulverizacao",
            }:
                atividade.data_programada = (
                    atividade.data_programada + timedelta(days=dias_adiamento)
                )
                atividade.ajustada_por_alerta = True
                atividade.motivo_ajuste = (
                    f"Adiado automaticamente em {dias_adiamento} dia(s) "
                    f"devido a alerta de {alerta.tipo_evento} ({alerta.data_evento.isoformat()})"
                )
                ajustadas += 1

        nova_atividade = models.Activity(
            terreno_id=alerta.terreno_id,
            titulo="Inspeção de drenagem e escoamento pós-chuva",
            descricao=(
                "Verificar acúmulo de água, erosão em canteiros e condição das raízes "
                f"após evento de {alerta.tipo_evento}."
            ),
            tipo_atividade="inspecao",
            data_programada=alerta.data_evento + timedelta(days=1),
            prioridade="alta",
            status="pendente",
            concluida=False,
            ajustada_por_alerta=True,
            motivo_ajuste=f"Criada automaticamente por alerta #{alerta.id}",
        )
        db.add(nova_atividade)
        criadas += 1

    elif evento in TIPOS_CALOR_SECA:
        for atividade in atividades_pendentes:
            if atividade.tipo_atividade.lower() == "irrigacao":
                atividade.prioridade = "critica"
                atividade.ajustada_por_alerta = True
                atividade.motivo_ajuste = (
                    "Prioridade elevada para crítica devido a alerta de "
                    f"{alerta.tipo_evento} ({alerta.data_evento.isoformat()})"
                )
                ajustadas += 1

        nova_atividade = models.Activity(
            terreno_id=alerta.terreno_id,
            titulo="Irrigação suplementar e proteção térmica do solo",
            descricao=(
                "Reforçar cobertura morta e realizar irrigação nos horários mais frescos "
                f"para mitigar {alerta.tipo_evento}."
            ),
            tipo_atividade="irrigacao",
            data_programada=alerta.data_evento,
            prioridade="critica",
            status="pendente",
            concluida=False,
            ajustada_por_alerta=True,
            motivo_ajuste=(
                f"Criada automaticamente por alerta de {alerta.tipo_evento} #{alerta.id}"
            ),
        )
        db.add(nova_atividade)
        criadas += 1

    elif evento in TIPOS_PRAGA:
        nova_atividade = models.Activity(
            terreno_id=alerta.terreno_id,
            titulo="Inspeção fitossanitária e manejo de praga",
            descricao=(
                "Avaliar nível de infestação nas folhas e caules, isolar reboleiras e definir manejo integrado."
            ),
            tipo_atividade="inspecao",
            data_programada=alerta.data_evento,
            prioridade="alta",
            status="pendente",
            concluida=False,
            ajustada_por_alerta=True,
            motivo_ajuste=f"Criada automaticamente por relato de praga (alerta #{alerta.id})",
        )
        db.add(nova_atividade)
        criadas += 1

    else:
        for atividade in atividades_pendentes:
            if atividade.tipo_atividade.lower() in {"plantio", "adubacao"}:
                atividade.data_programada = (
                    atividade.data_programada + timedelta(days=dias_adiamento)
                )
                atividade.ajustada_por_alerta = True
                atividade.motivo_ajuste = (
                    f"Adiado automaticamente em {dias_adiamento} dia(s) "
                    f"devido a alerta de {alerta.tipo_evento} ({alerta.data_evento.isoformat()})"
                )
                ajustadas += 1

        nova_atividade = models.Activity(
            terreno_id=alerta.terreno_id,
            titulo=f"Proteção emergencial da lavoura contra {alerta.tipo_evento}",
            descricao=(
                "Adotar barreiras de proteção ou cobertura temporária antes do pico do evento extremo."
            ),
            tipo_atividade="manejo",
            data_programada=alerta.data_evento,
            prioridade="critica",
            status="pendente",
            concluida=False,
            ajustada_por_alerta=True,
            motivo_ajuste=f"Criada automaticamente por alerta #{alerta.id}",
        )
        db.add(nova_atividade)
        criadas += 1

    return ajustadas, criadas


def processar_alerta_e_adaptar_calendario(
    alerta_id: int,
    dias_adiamento: int = 2,
    session_factory=None,
) -> None:
    """
    Rotina assíncrona executada em segundo plano para adaptar o calendário [M4]
    quando um alerta climático [M5] é disparado pelo modelo de ML ou sensor.
    """
    with _abrir_sessao_background(session_factory) as db:
        try:
            alerta = (
                db.query(models.AlertaClimatico)
                .filter(models.AlertaClimatico.id == alerta_id)
                .first()
            )
            if not alerta:
                return

            janela_inicio = alerta.data_evento
            janela_fim = alerta.data_evento + timedelta(days=3)

            atividades_pendentes: List[models.Activity] = (
                db.query(models.Activity)
                .filter(
                    models.Activity.terreno_id == alerta.terreno_id,
                    models.Activity.concluida.is_(False),
                    models.Activity.data_programada >= janela_inicio,
                    models.Activity.data_programada <= janela_fim,
                )
                .all()
            )

            ajustadas, criadas = aplicar_regras_ajuste_pos_alerta(
                db=db,
                alerta=alerta,
                atividades_pendentes=atividades_pendentes,
                dias_adiamento=dias_adiamento,
            )

            alerta.processado_background = True
            alerta.resumo_adaptacao = (
                f"Calendário adaptado automaticamente na janela de {janela_inicio.isoformat()} "
                f"a {janela_fim.isoformat()}: {ajustadas} atividade(s) ajustada(s)/adiada(s) "
                f"e {criadas} nova(s) atividade(s) criada(s)."
            )
            dados_atualizados = dict(alerta.dados_gatilho or {})
            dados_atualizados["orientacao_pratica"] = gerar_orientacao_alerta(
                tipo_evento=alerta.tipo_evento,
                severidade=alerta.severidade,
                resumo_adaptacao=alerta.resumo_adaptacao,
                detalhes_clima=dados_atualizados.get("dados_climaticos")
                if isinstance(dados_atualizados.get("dados_climaticos"), dict)
                else None,
            )
            alerta.dados_gatilho = dados_atualizados
            db.commit()
        except Exception:
            db.rollback()
            raise


def coletar_dados_climaticos_sinteticos(output_dir: str = "data") -> Dict[str, Any]:
    """
    Gera/consulta dados climáticos sintéticos via mock_nasa_data (NetCDF) com
    fallback determinístico quando bibliotecas científicas não estão disponíveis.
    """
    try:
        import xarray as xr
        from backend.services.mock_nasa_data import generate_synthetic_netcdf

        mensagem_netcdf = generate_synthetic_netcdf(output_dir=output_dir)
        caminho_nc = os.path.join(output_dir, "smap_mock.nc")
        umidade_media = 0.22
        if os.path.exists(caminho_nc):
            with xr.open_dataset(caminho_nc) as ds:
                if "soil_moisture" in ds:
                    umidade_media = float(ds["soil_moisture"].mean().item())

        precip = 82.0 if umidade_media > 0.3 else 12.0
        temp = 24.5 if umidade_media > 0.3 else 36.8
        return {
            "origem": "mock_nasa_data_netcdf",
            "detalhe_geracao": mensagem_netcdf,
            "soil_moisture": round(umidade_media, 4),
            "precipitation_mm": precip,
            "surface_temp_c": temp,
            "anomaly_detected": precip >= 60.0 or temp >= 35.0 or umidade_media <= 0.2,
        }
    except Exception:
        return {
            "origem": "fallback_sintetico",
            "soil_moisture": 0.14,
            "precipitation_mm": 12.0,
            "surface_temp_c": 36.8,
            "anomaly_detected": True,
        }


def coletar_dados_climaticos_terreno(
    terreno: models.Terreno,
    output_dir: str = "data",
    nasa_provider: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Coleta métricas climáticas específicas do polígono do terreno via INASADataProvider,
    com fallback para o gerador sintético caso o provider falhe ou retorne no_data.
    """
    provider = nasa_provider if nasa_provider is not None else get_nasa_provider(output_dir)
    if provider is not None:
        try:
            metricas = provider.extract_field_metrics(
                terreno.coordenadas_poligono, dataset=None
            )
            if isinstance(metricas, dict) and metricas.get("data_quality") != "no_data":
                return {
                    "origem": "nasa_geospatial_provider",
                    "data_quality": metricas.get("data_quality", "clip"),
                    "soil_moisture": metricas.get("avg_soil_moisture_smap"),
                    "surface_temp_c": metricas.get("avg_surface_temp_ecostress"),
                    "precipitation_mm": metricas.get("avg_precipitation_gpm"),
                    "is_bare_field_period": metricas.get("is_bare_field_period"),
                    "time_series": metricas.get("time_series") or [],
                }
        except Exception as exc:
            logger.warning(
                "Falha ao extrair métricas NASA para terreno %s: %s",
                terreno.id,
                exc,
            )

    return coletar_dados_climaticos_sinteticos(output_dir=output_dir)


def _avaliar_anomalia_climatica(dados_climaticos: Dict[str, Any]) -> Dict[str, Any]:
    """Aciona ClimateAnomalyDetector sobre série do terreno (ou ponto) respeitando anomaly_detected."""
    resultado_ml: Any = None
    origem_detector = "limiar_sintetico"
    entrada_detector: Any = (
        dados_climaticos["time_series"]
        if isinstance(dados_climaticos.get("time_series"), list)
        and dados_climaticos["time_series"]
        else dados_climaticos
    )

    try:
        from backend.services.ml_models import ClimateAnomalyDetector

        detector = ClimateAnomalyDetector()
        resultado_ml = detector.detect_extremes(entrada_detector)
        origem_detector = "climate_anomaly_detector"
    except Exception as exc:
        resultado_ml = {"erro_detector": str(exc)}

    if isinstance(resultado_ml, dict) and "anomaly_detected" in resultado_ml:
        anomalia = bool(resultado_ml["anomaly_detected"])
        tipo_evento = str(resultado_ml.get("tipo_evento", "nenhum"))
        severidade = str(resultado_ml.get("severidade", "baixa"))
    else:
        precip = float(dados_climaticos.get("precipitation_mm") or 0.0)
        temp = float(dados_climaticos.get("surface_temp_c") or 25.0)
        umidade_val = dados_climaticos.get("soil_moisture")
        umidade = float(umidade_val) if umidade_val is not None else 0.3

        if precip >= 60.0:
            anomalia = True
            tipo_evento = "chuva_intensa"
            severidade = "alta"
        elif temp >= 35.0:
            anomalia = True
            tipo_evento = "onda_de_calor"
            severidade = "alta"
        elif umidade <= 0.15:
            anomalia = True
            tipo_evento = "seca"
            severidade = "alta"
        else:
            anomalia = False
            tipo_evento = "nenhum"
            severidade = "baixa"

    return {
        "origem_detector": origem_detector,
        "anomaly_detected": anomalia,
        "tipo_evento": tipo_evento,
        "severidade": severidade,
        "resultado_ml": resultado_ml,
    }


def executar_ciclo_monitoramento_alertas(
    terreno_id: Optional[int] = None,
    intervalo_horas: Optional[int] = None,
    output_dir: str = "data",
    session_factory=None,
    cooldown_horas: Optional[int] = None,
    perfil_climatico: Optional[str] = None,
) -> List[int]:
    """
    Executa um ciclo de monitoramento climático em segundo plano por terreno:
    extrai métricas via INASADataProvider, avalia ClimateAnomalyDetector e
    persiste Alertas deduplicados (terreno + tipo + data e cooldown).
    """
    intervalo_efetivo = (
        obter_intervalo_monitoramento_horas()
        if intervalo_horas is None
        else max(1, int(intervalo_horas))
    )
    alertas_gerados: List[int] = []
    with _abrir_sessao_background(session_factory) as db:
        try:
            query_terrenos = db.query(models.Terreno)
            if terreno_id is not None:
                query_terrenos = query_terrenos.filter(models.Terreno.id == terreno_id)
            terrenos = query_terrenos.all()
            if not terrenos:
                return []

            nasa_provider = get_nasa_provider(
                data_path=output_dir, profile=perfil_climatico
            )
            data_prevista = date.today() + timedelta(days=1)

            for terreno in terrenos:
                dados_terreno = coletar_dados_climaticos_terreno(
                    terreno=terreno,
                    output_dir=output_dir,
                    nasa_provider=nasa_provider,
                )
                if perfil_climatico:
                    dados_terreno["perfil_climatico"] = perfil_climatico
                persistir_metricas_terreno(
                    db=db,
                    terreno_id=terreno.id,
                    field_metrics=dados_terreno,
                    origem=str(dados_terreno.get("origem") or "monitoramento_climatico"),
                )
                avaliacao = _avaliar_anomalia_climatica(dados_terreno)
                if not avaliacao["anomaly_detected"]:
                    continue

                tipo_evento = avaliacao["tipo_evento"]
                severidade = avaliacao["severidade"]

                if buscar_alerta_duplicado(
                    db=db,
                    terreno_id=terreno.id,
                    tipo_evento=tipo_evento,
                    data_evento=data_prevista,
                    cooldown_horas=cooldown_horas,
                ):
                    logger.info(
                        "Alerta duplicado/em cooldown ignorado para terreno=%s tipo=%s data=%s",
                        terreno.id,
                        tipo_evento,
                        data_prevista.isoformat(),
                    )
                    continue

                alerta = models.AlertaClimatico(
                    terreno_id=terreno.id,
                    tipo_evento=tipo_evento,
                    severidade=severidade,
                    titulo=f"Monitoramento automático ({intervalo_efetivo}h): {tipo_evento.replace('_', ' ')}",
                    mensagem=(
                        f"Anomalia climática detectada ({tipo_evento}) para o terreno "
                        f"'{terreno.nome_propriedade}' em {data_prevista.isoformat()}."
                    ),
                    data_evento=data_prevista,
                    origem_gatilho="periodic_synthetic_monitor",
                    dados_gatilho={
                        "intervalo_horas": intervalo_efetivo,
                        "dados_climaticos": dados_terreno,
                        "detector": avaliacao,
                    },
                    processado_background=False,
                )
                db.add(alerta)
                db.commit()
                db.refresh(alerta)
                alertas_gerados.append(alerta.id)

                processar_alerta_e_adaptar_calendario(
                    alerta_id=alerta.id,
                    dias_adiamento=2,
                    session_factory=session_factory,
                )

            return alertas_gerados
        except Exception:
            db.rollback()
            raise


async def iniciar_monitoramento_periodico(
    intervalo_horas: Optional[int] = None,
    max_ciclos: Optional[int] = 1,
    terreno_id: Optional[int] = None,
    session_factory=None,
    aguardar_inicio: bool = False,
) -> List[int]:
    """
    Orquestra ciclos periódicos de verificação climática (ex: a cada 6 ou 12 horas).
    """
    intervalo_efetivo = (
        obter_intervalo_monitoramento_horas()
        if intervalo_horas is None
        else max(1, int(intervalo_horas))
    )
    todos_alertas: List[int] = []
    ciclos_executados = 0

    if aguardar_inicio:
        await asyncio.sleep(intervalo_efetivo * 3600)

    while max_ciclos is None or ciclos_executados < max_ciclos:
        try:
            gerados = executar_ciclo_monitoramento_alertas(
                terreno_id=terreno_id,
                intervalo_horas=intervalo_efetivo,
                session_factory=session_factory,
            )
            todos_alertas.extend(gerados)
        except Exception:
            if max_ciclos is not None:
                raise
        ciclos_executados += 1

        if max_ciclos is not None and ciclos_executados >= max_ciclos:
            break

        await asyncio.sleep(intervalo_efetivo * 3600)

    return todos_alertas


@asynccontextmanager
async def lifespan_monitoramento_alertas(app):
    """Inicia a rotina periódica de monitoramento climático no startup do FastAPI."""
    intervalo_horas = obter_intervalo_monitoramento_horas()
    task = asyncio.create_task(
        iniciar_monitoramento_periodico(
            intervalo_horas=intervalo_horas,
            max_ciclos=None,
            aguardar_inicio=True,
        )
    )
    app.state.alert_monitor_task = task
    try:
        yield
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

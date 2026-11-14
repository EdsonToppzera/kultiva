import asyncio
from contextlib import asynccontextmanager
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from backend.db import models
from backend.db.database import SessionLocal

TIPOS_CHUVA = {"chuva_intensa", "tempestade", "heavy_rain"}
TIPOS_CALOR_SECA = {"onda_de_calor", "seca", "heatwave", "drought"}


def processar_alerta_e_adaptar_calendario(
    alerta_id: int,
    dias_adiamento: int = 2,
    session_factory=None,
) -> None:
    """
    Rotina assíncrona executada em segundo plano para adaptar o calendário [M4]
    quando um alerta climático [M5] é disparado pelo modelo de ML ou sensor.
    """
    factory = session_factory or SessionLocal
    db = factory()
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

        alerta.processado_background = True
        alerta.resumo_adaptacao = (
            f"Calendário adaptado automaticamente na janela de {janela_inicio.isoformat()} "
            f"a {janela_fim.isoformat()}: {ajustadas} atividade(s) ajustada(s)/adiada(s) "
            f"e {criadas} nova(s) atividade(s) criada(s)."
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


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


def _avaliar_anomalia_climatica(dados_sinteticos: Dict[str, Any]) -> Dict[str, Any]:
    """Aciona ClimateAnomalyDetector com interpretação determinística de limiares."""
    resultado_ml: Any = None
    origem_detector = "limiar_sintetico"

    try:
        from backend.services.ml_models import ClimateAnomalyDetector

        detector = ClimateAnomalyDetector()
        resultado_ml = detector.detect_extremes(dados_sinteticos)
        origem_detector = "climate_anomaly_detector"
    except Exception as exc:
        resultado_ml = {"erro_detector": str(exc)}

    if isinstance(resultado_ml, dict) and "anomaly_detected" in resultado_ml:
        anomalia = bool(resultado_ml["anomaly_detected"])
        tipo_evento = str(resultado_ml.get("tipo_evento", "onda_de_calor"))
        severidade = str(resultado_ml.get("severidade", "alta"))
    else:
        anomalia = bool(dados_sinteticos.get("anomaly_detected", True))
        precip = float(dados_sinteticos.get("precipitation_mm", 0.0))
        temp = float(dados_sinteticos.get("surface_temp_c", 25.0))
        umidade = float(dados_sinteticos.get("soil_moisture", 0.3))

        if precip >= 60.0:
            tipo_evento = "chuva_intensa"
            severidade = "alta"
        elif temp >= 35.0 or umidade <= 0.2:
            tipo_evento = "onda_de_calor"
            severidade = "alta"
        else:
            tipo_evento = "onda_de_calor"
            severidade = "media"

    return {
        "origem_detector": origem_detector,
        "anomaly_detected": anomalia,
        "tipo_evento": tipo_evento,
        "severidade": severidade,
        "resultado_ml": resultado_ml,
    }


def executar_ciclo_monitoramento_alertas(
    terreno_id: Optional[int] = None,
    intervalo_horas: int = 6,
    output_dir: str = "data",
    session_factory=None,
) -> List[int]:
    """
    Executa um ciclo de monitoramento climático em segundo plano:
    consulta o gerador sintético/ClimateAnomalyDetector e persiste Alertas no banco.
    """
    dados_sinteticos = coletar_dados_climaticos_sinteticos(output_dir=output_dir)
    avaliacao = _avaliar_anomalia_climatica(dados_sinteticos)
    if not avaliacao["anomaly_detected"]:
        return []

    factory = session_factory or SessionLocal
    db = factory()
    alertas_gerados: List[int] = []
    try:
        query_terrenos = db.query(models.Terreno)
        if terreno_id is not None:
            query_terrenos = query_terrenos.filter(models.Terreno.id == terreno_id)
        terrenos = query_terrenos.all()
        if not terrenos:
            return []

        data_prevista = date.today() + timedelta(days=1)
        tipo_evento = avaliacao["tipo_evento"]
        severidade = avaliacao["severidade"]

        for terreno in terrenos:
            alerta = models.AlertaClimatico(
                terreno_id=terreno.id,
                tipo_evento=tipo_evento,
                severidade=severidade,
                titulo=f"Monitoramento automático ({intervalo_horas}h): {tipo_evento.replace('_', ' ')}",
                mensagem=(
                    f"Anomalia climática detectada ({tipo_evento}) para o terreno "
                    f"'{terreno.nome_propriedade}' em {data_prevista.isoformat()}."
                ),
                data_evento=data_prevista,
                origem_gatilho="periodic_synthetic_monitor",
                dados_gatilho={
                    "intervalo_horas": intervalo_horas,
                    "dados_climaticos": dados_sinteticos,
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
                session_factory=factory,
            )

        return alertas_gerados
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def iniciar_monitoramento_periodico(
    intervalo_horas: int = 6,
    max_ciclos: Optional[int] = 1,
    terreno_id: Optional[int] = None,
    session_factory=None,
    aguardar_inicio: bool = False,
) -> List[int]:
    """
    Orquestra ciclos periódicos de verificação climática (ex: a cada 6 ou 12 horas).
    """
    todos_alertas: List[int] = []
    ciclos_executados = 0

    if aguardar_inicio:
        await asyncio.sleep(max(0, intervalo_horas) * 3600)

    while max_ciclos is None or ciclos_executados < max_ciclos:
        try:
            gerados = executar_ciclo_monitoramento_alertas(
                terreno_id=terreno_id,
                intervalo_horas=intervalo_horas,
                session_factory=session_factory,
            )
            todos_alertas.extend(gerados)
        except Exception:
            if max_ciclos is not None:
                raise
        ciclos_executados += 1

        if max_ciclos is not None and ciclos_executados >= max_ciclos:
            break

        await asyncio.sleep(max(0, intervalo_horas) * 3600)

    return todos_alertas


@asynccontextmanager
async def lifespan_monitoramento_alertas(app):
    """Inicia a rotina periódica de monitoramento climático no startup do FastAPI."""
    intervalo_horas = int(os.getenv("ALERT_MONITOR_INTERVAL_HOURS", "6"))
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

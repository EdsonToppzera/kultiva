from datetime import timedelta
from typing import List
from backend.db import models
from backend.db.database import SessionLocal

TIPOS_CHUVA = {"chuva_intensa", "tempestade", "heavy_rain"}
TIPOS_CALOR_SECA = {"onda_de_calor", "seca", "heatwave", "drought"}


def processar_alerta_e_adaptar_calendario(
    alerta_id: int,
    dias_adiamento: int = 2,
    session_factory=SessionLocal,
) -> None:
    """
    Rotina assíncrona executada em segundo plano para adaptar o calendário [M4]
    quando um alerta climático [M5] é disparado pelo modelo de ML ou sensor.
    """
    db = session_factory()
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

        atividades_pendentes: List[models.AtividadeCalendario] = (
            db.query(models.AtividadeCalendario)
            .filter(
                models.AtividadeCalendario.terreno_id == alerta.terreno_id,
                models.AtividadeCalendario.concluida.is_(False),
                models.AtividadeCalendario.data_programada >= janela_inicio,
                models.AtividadeCalendario.data_programada <= janela_fim,
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

            nova_atividade = models.AtividadeCalendario(
                terreno_id=alerta.terreno_id,
                titulo="Inspeção de drenagem e escoamento pós-chuva",
                descricao=(
                    "Verificar acúmulo de água, erosão em canteiros e condição das raízes "
                    f"após evento de {alerta.tipo_evento}."
                ),
                tipo_atividade="inspecao",
                data_programada=alerta.data_evento + timedelta(days=1),
                prioridade="alta",
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

            nova_atividade = models.AtividadeCalendario(
                terreno_id=alerta.terreno_id,
                titulo="Irrigação suplementar e proteção térmica do solo",
                descricao=(
                    "Reforçar cobertura morta e realizar irrigação nos horários mais frescos "
                    f"para mitigar {alerta.tipo_evento}."
                ),
                tipo_atividade="irrigacao",
                data_programada=alerta.data_evento,
                prioridade="critica",
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

            nova_atividade = models.AtividadeCalendario(
                terreno_id=alerta.terreno_id,
                titulo=f"Proteção emergencial da lavoura contra {alerta.tipo_evento}",
                descricao=(
                    "Adotar barreiras de proteção ou cobertura temporária antes do pico do evento extremo."
                ),
                tipo_atividade="manejo",
                data_programada=alerta.data_evento,
                prioridade="critica",
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

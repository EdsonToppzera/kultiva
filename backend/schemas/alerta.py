from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class AlertaGatilhoRequest(BaseModel):
    terreno_id: int
    tipo_evento: str = Field(
        ...,
        description="Tipo de evento climático: chuva_intensa, onda_de_calor, seca, geada, vendaval",
    )
    severidade: str = Field(
        default="alta",
        description="Severidade do alerta: baixa, media, alta, critica",
    )
    data_evento: date
    titulo: Optional[str] = None
    mensagem: Optional[str] = None
    origem_gatilho: str = Field(
        default="ml_anomaly_detector",
        description="Origem do disparo: ml_anomaly_detector, nasa_power, manual",
    )
    serie_temporal_clima: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Série temporal opcional para análise pelo ClimateAnomalyDetector",
    )
    dias_adiamento: int = Field(default=2, ge=1, le=14)
    idioma: Optional[str] = Field(
        default="pt",
        description="Idioma desejado para título, mensagem e orientação prática ('pt' ou 'en')",
    )


class AlertaClimaticoResponse(BaseModel):
    id: int
    terreno_id: int
    tipo_evento: str
    severidade: str
    titulo: str
    mensagem: str
    data_evento: date
    origem_gatilho: str
    dados_gatilho: Optional[Dict[str, Any]] = None
    processado_background: bool
    resumo_adaptacao: Optional[str] = None
    orientacao_pratica: Optional[str] = None
    lido: bool
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class AlertaDisparoResponse(BaseModel):
    status: str
    mensagem: str
    alerta: AlertaClimaticoResponse


class MonitoramentoClimaRequest(BaseModel):
    terreno_id: Optional[int] = Field(
        default=None,
        description="ID do terreno a monitorar (se omitido, monitora todos os terrenos cadastrados)",
    )
    intervalo_horas: Optional[int] = Field(
        default=None,
        ge=1,
        le=24,
        description="Intervalo periódico em horas (se omitido, usa ALERT_MONITOR_INTERVAL_HOURS)",
    )
    perfil_climatico: Optional[
        Literal["normal", "seca", "chuva_extrema", "onda_de_calor"]
    ] = Field(
        default=None,
        description="Perfil climático simulável para disparo sob demanda na demo",
    )


class MonitoramentoClimaResponse(BaseModel):
    status: str
    mensagem: str
    intervalo_horas: int
    terreno_id: Optional[int] = None
    perfil_climatico: Optional[str] = None


class ResumoAlertasTerrenoItem(BaseModel):
    terreno_id: int
    nome_propriedade: Optional[str] = None
    nao_lidos: int
    criticos_nao_lidos: int
    ultimo_evento: Optional[str] = None
    ultima_data_evento: Optional[date] = None


class ResumoAlertasNaoLidosResponse(BaseModel):
    total_nao_lidos: int
    por_terreno: List[ResumoAlertasTerrenoItem]

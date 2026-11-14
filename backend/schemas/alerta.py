from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


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
    lido: bool
    criado_em: datetime

    class Config:
        from_attributes = True


class AlertaDisparoResponse(BaseModel):
    status: str
    mensagem: str
    alerta: AlertaClimaticoResponse

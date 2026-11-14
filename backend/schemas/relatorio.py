from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MetricaHistoricaCreate(BaseModel):
    data_medicao: date
    soil_moisture: float = Field(..., ge=0.0, le=1.0)
    surface_temp_c: float = Field(..., ge=-20.0, le=70.0)
    precipitation_mm: float = Field(default=0.0, ge=0.0)
    is_bare_field_period: Optional[bool] = None
    data_quality: str = "manual"
    origem: str = "api_ingestao"


class MetricaHistoricaResponse(BaseModel):
    id: int
    terreno_id: int
    data_medicao: date
    soil_moisture: float
    surface_temp_c: float
    precipitation_mm: float
    is_bare_field_period: bool
    data_quality: str
    origem: str
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumoClimaticoRelatorio(BaseModel):
    umidade_media_solo: float
    umidade_min_solo: float
    umidade_max_solo: float
    temperatura_media_c: float
    temperatura_max_c: float
    precipitacao_total_mm: float
    precipitacao_media_mm: float
    dias_solo_exposto: int
    total_medicoes: int


class VigorTerrenoResumo(BaseModel):
    indice: float
    classificacao: str
    tendencia: str
    descricao: str


class VulnerabilidadeTerrenoResumo(BaseModel):
    indice: float
    nivel: str
    total_alertas_periodo: int
    eventos_criticos: List[str]
    fatores_risco: List[str]


class AdaptacaoAtividadeItem(BaseModel):
    atividade_id: int
    titulo: str
    tipo_atividade: str
    data_programada: date
    prioridade: str
    status: str
    motivo_ajuste: Optional[str] = None


class AdaptacoesTerrenoResumo(BaseModel):
    total_atividades_periodo: int
    total_ajustadas_por_alerta: int
    taxa_adaptacao: float
    atividades_ajustadas: List[AdaptacaoAtividadeItem]


class AlertaResumoRelatorio(BaseModel):
    id: int
    tipo_evento: str
    severidade: str
    titulo: str
    data_evento: date
    processado_background: bool
    resumo_adaptacao: Optional[str] = None


class RelatorioAdaptacaoResponse(BaseModel):
    terreno_id: int
    nome_propriedade: str
    periodo_inicio: date
    periodo_fim: date
    origem_dados: str
    resumo_climatico: ResumoClimaticoRelatorio
    vigor: VigorTerrenoResumo
    vulnerabilidade: VulnerabilidadeTerrenoResumo
    adaptacoes: AdaptacoesTerrenoResumo
    alertas_periodo: List[AlertaResumoRelatorio]
    serie_historica: List[MetricaHistoricaResponse]
    recomendacoes_manejo: List[str]

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SimulacaoRequest(BaseModel):
    terreno_id: Optional[int] = Field(
        default=None, description="ID opcional do terreno cadastrado no módulo M1"
    )
    nome_propriedade: Optional[str] = Field(
        default=None,
        description="Nome opcional da propriedade para simulação direta sem cadastro prévio",
    )
    coordenadas_poligono: Optional[List[Dict[str, float]]] = Field(
        default=None,
        description="Coordenadas do polígono caso terreno_id não seja informado",
    )
    cultura_id: Optional[int] = Field(
        default=None, description="ID da cultura cadastrada no banco"
    )
    nome_cultura: Optional[str] = Field(
        default=None, description="Nome da cultura caso não seja informado cultura_id"
    )
    culturas_rotacao: Optional[List[str]] = Field(
        default=None,
        description="Lista opcional de culturas subsequentes para simular rotação",
    )
    prioridades: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Prioridades adicionais do produtor (ex: {'water_conservation': True})",
    )
    dados_solo: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parâmetros opcionais de solo (ex: pH, textura, matéria orgânica)",
    )
    dados_climaticos: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parâmetros climáticos opcionais para complementar os dados da NASA",
    )


class EtapaRotacaoSimulada(BaseModel):
    ordem: int
    cultura: str
    duracao_dias: int
    consumo_agua_estimado_mm: float
    viabilidade_score: float
    risco_hidrico: str


class EstrategiaRotacaoSugerida(BaseModel):
    strategy: str
    viability: float
    water_risk: str


class SimulacaoResponse(BaseModel):
    terreno_id: Optional[int] = None
    nome_propriedade: str
    cultura_principal: str
    viability_score: float
    water_risk: str
    tempo_colheita_dias: int
    consumo_agua_mm: float
    metricas_geoespaciais: Dict[str, Any]
    beneficios_esperados: List[str]
    riscos_identificados: List[str]
    explicacao_ia: str
    explicacao_textual: str
    rotacoes_sugeridas: List[EstrategiaRotacaoSugerida]
    plano_rotacao: List[EtapaRotacaoSimulada]

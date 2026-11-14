from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AtividadeCalendarioBase(BaseModel):
    terreno_id: Optional[int] = None
    usuario_id: Optional[int] = None
    cultura_id: Optional[int] = None
    titulo: str = Field(..., min_length=1)
    descricao: Optional[str] = None
    tipo_atividade: str = Field(
        ...,
        description="Tipo da atividade: plantio, irrigacao, adubacao, manejo, colheita, inspecao",
    )
    data_programada: date
    prioridade: str = Field(
        default="media",
        description="Prioridade da atividade: baixa, media, alta, critica",
    )
    status: str = Field(
        default="pendente",
        description="Status da atividade: pendente ou concluida",
    )


class AtividadeCalendarioCreate(AtividadeCalendarioBase):
    pass


class AtividadeCalendarioUpdate(BaseModel):
    terreno_id: Optional[int] = None
    usuario_id: Optional[int] = None
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    tipo_atividade: Optional[str] = None
    data_programada: Optional[date] = None
    prioridade: Optional[str] = None
    status: Optional[str] = None
    concluida: Optional[bool] = None


class AtividadeStatusPatch(BaseModel):
    concluida: Optional[bool] = None
    status: Optional[str] = Field(
        default=None,
        description="Novo status da atividade: pendente ou concluida",
    )


class EtapaCronogramaInput(BaseModel):
    ordem: Optional[int] = None
    cultura: str = Field(..., min_length=1)
    duracao_dias: int = Field(default=90, ge=5, le=730)
    risco_hidrico: Optional[str] = None


class GerarCronogramaRequest(BaseModel):
    terreno_id: int
    cultura_id: Optional[int] = None
    nome_cultura: Optional[str] = "Cultura Principal"
    data_inicio: date
    tempo_colheita_dias: int = Field(default=90, ge=5, le=730)
    estrategia_rotacao: Optional[str] = Field(
        default=None,
        description="Estratégia vinda do M3 (ex: 'Sorgo -> Feijão-caupi')",
    )
    plano_rotacao: Optional[List[EtapaCronogramaInput]] = Field(
        default=None,
        description="Etapas vindas de SimulacaoResponse.plano_rotacao (M3)",
    )


class AtividadeCalendarioResponse(AtividadeCalendarioBase):
    id: int
    concluida: bool
    status: str
    data_conclusao: Optional[datetime] = None
    ajustada_por_alerta: bool
    motivo_ajuste: Optional[str] = None
    criado_em: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Aliases alinhados ao modelo Activity
ActivityCreate = AtividadeCalendarioCreate
ActivityUpdate = AtividadeCalendarioUpdate
ActivityStatusPatch = AtividadeStatusPatch
ActivityResponse = AtividadeCalendarioResponse

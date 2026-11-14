from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class AtividadeCalendarioBase(BaseModel):
    terreno_id: int
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


class AtividadeCalendarioCreate(AtividadeCalendarioBase):
    pass


class AtividadeCalendarioUpdate(BaseModel):
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    tipo_atividade: Optional[str] = None
    data_programada: Optional[date] = None
    prioridade: Optional[str] = None
    concluida: Optional[bool] = None


class AtividadeStatusPatch(BaseModel):
    concluida: bool = True


class GerarCronogramaRequest(BaseModel):
    terreno_id: int
    cultura_id: Optional[int] = None
    nome_cultura: Optional[str] = "Cultura Principal"
    data_inicio: date
    tempo_colheita_dias: int = Field(default=90, ge=5, le=730)


class AtividadeCalendarioResponse(AtividadeCalendarioBase):
    id: int
    concluida: bool
    data_conclusao: Optional[datetime] = None
    ajustada_por_alerta: bool
    motivo_ajuste: Optional[str] = None
    criado_em: Optional[datetime] = None

    class Config:
        from_attributes = True

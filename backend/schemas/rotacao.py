from typing import Optional
from pydantic import BaseModel, ConfigDict


class CulturaBase(BaseModel):
    nome: str
    consumo_agua_mm: float
    tempo_colheita_dias: int
    resistencia_pragas: Optional[str] = None


class CulturaCreate(CulturaBase):
    pass


class CulturaResponse(CulturaBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

from typing import Optional
from pydantic import BaseModel


class CulturaBase(BaseModel):
    nome: str
    consumo_agua_mm: float
    tempo_colheita_dias: int
    resistencia_pragas: Optional[str] = None


class CulturaCreate(CulturaBase):
    pass


class CulturaResponse(CulturaBase):
    id: int

    class Config:
        from_attributes = True

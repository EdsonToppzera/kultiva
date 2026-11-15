from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Optional


class Coordenada(BaseModel):
    lat: float
    lng: float


class TerrenoCreate(BaseModel):
    nome_propriedade: str
    usuario_id: int
    coordenadas_poligono: List[Coordenada] = Field(
        ...,
        min_length=3,
        description="Lista de coordenadas que formam o polígono (mínimo 3 pontos)",
    )
    area_hectares: Optional[float] = Field(default=None, gt=0)
    localizacao_central: Optional[Coordenada] = None
    prioridades: Optional[Dict[str, Any]] = Field(
        default=None,
        json_schema_extra={"example": {"agua": "escassa", "foco_mercado": "local"}},
    )


class TerrenoUpdate(BaseModel):
    nome_propriedade: Optional[str] = Field(default=None, min_length=1)
    usuario_id: Optional[int] = Field(default=None, gt=0)
    coordenadas_poligono: Optional[List[Coordenada]] = Field(
        default=None,
        min_length=3,
        description="Lista de coordenadas que formam o polígono (mínimo 3 pontos)",
    )
    area_hectares: Optional[float] = Field(default=None, gt=0)
    localizacao_central: Optional[Coordenada] = None
    prioridades: Optional[Dict[str, Any]] = None


class TerrenoResponse(TerrenoCreate):
    id: int
    area_hectares: Optional[float] = Field(default=None, ge=0)
    model_config = ConfigDict(from_attributes=True)

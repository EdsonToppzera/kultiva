from pydantic import BaseModel, Field
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
        example={"agua": "escassa", "foco_mercado": "local"}
    )

class TerrenoResponse(TerrenoCreate):
    id: int
    class Config:
        from_attributes = True

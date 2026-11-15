from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validar_nome_nao_vazio(valor: str) -> str:
    limpo = valor.strip()
    if not limpo:
        raise ValueError("O nome não pode ser vazio.")
    return limpo


class CulturaBase(BaseModel):
    nome: str = Field(..., min_length=1, description="Nome da cultura")
    consumo_agua_mm: float = Field(..., gt=0, description="Consumo hídrico em mm")
    tempo_colheita_dias: int = Field(..., gt=0, description="Duração do ciclo em dias")
    resistencia_pragas: Optional[str] = None
    usuario_id: Optional[int] = Field(default=None, gt=0)

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, v: str) -> str:
        return _validar_nome_nao_vazio(v)


class CulturaCreate(CulturaBase):
    pass


class CulturaUpdate(BaseModel):
    nome: Optional[str] = Field(default=None, min_length=1)
    consumo_agua_mm: Optional[float] = Field(default=None, gt=0)
    tempo_colheita_dias: Optional[int] = Field(default=None, gt=0)
    resistencia_pragas: Optional[str] = None

    @field_validator("nome")
    @classmethod
    def validar_nome_opcional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _validar_nome_nao_vazio(v)


class CulturaResponse(CulturaBase):
    id: int
    is_seed: bool = False
    customizada: bool = True

    model_config = ConfigDict(from_attributes=True)


def _normalizar_culturas_rotacao(culturas: List[str]) -> List[str]:
    limpas = [item.strip() for item in culturas if isinstance(item, str) and item.strip()]
    if len(limpas) < 2:
        raise ValueError("Informe pelo menos 2 culturas válidas para a rotação.")
    return limpas


class RotacaoBase(BaseModel):
    nome: Optional[str] = Field(
        default=None,
        description="Nome legível da rotação (ex: 'Sorgo -> Feijão-caupi')",
    )
    culturas: List[str] = Field(
        ...,
        min_length=2,
        description="Sequência ordenada de culturas na rotação",
    )
    usuario_id: Optional[int] = Field(default=None, gt=0)
    terreno_id: Optional[int] = Field(default=None, gt=0)
    preferencial: bool = True
    beneficios: Optional[str] = None

    @field_validator("culturas")
    @classmethod
    def validar_culturas(cls, v: List[str]) -> List[str]:
        return _normalizar_culturas_rotacao(v)

    @field_validator("nome")
    @classmethod
    def validar_nome_rotacao(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        limpo = v.strip()
        return limpo or None


class RotacaoCreate(RotacaoBase):
    pass


class RotacaoUpdate(BaseModel):
    nome: Optional[str] = None
    culturas: Optional[List[str]] = Field(default=None, min_length=2)
    terreno_id: Optional[int] = Field(default=None, gt=0)
    preferencial: Optional[bool] = None
    beneficios: Optional[str] = None

    @field_validator("culturas")
    @classmethod
    def validar_culturas_opcional(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        return _normalizar_culturas_rotacao(v)

    @field_validator("nome")
    @classmethod
    def validar_nome_opcional(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return _validar_nome_nao_vazio(v)


class RotacaoResponse(RotacaoBase):
    id: int
    nome: str
    is_seed: bool = False
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class GAEZSoilResponse(BaseModel):
    hwsd_code: Optional[int] = None
    soil_group: Optional[str] = None
    limiting_factor_code: Optional[int] = None
    limiting_factor: Optional[str] = None
    soil_quality_class: Optional[int] = None
    soil_quality_index: Optional[float] = None
    slope_class: Optional[int] = None
    slope_range_pct: Optional[str] = None
    erosion_risk: Optional[str] = None


class GAEZCropSuitabilityResponse(BaseModel):
    crop_code: str
    gaez_caption: str
    scientific_name: Optional[str] = None
    nome: str
    group: str
    fixes_nitrogen: bool
    suitability_raw: float
    suitability_index: float
    suitability_score_100: float
    suitability_class: str
    attainable_yield_kg_ha: float
    cmip6_future_suitability_index: Optional[float] = None
    cmip6_suitability_delta: float = 0.0
    cmip6_future_yield_kg_ha: Optional[float] = None
    climate_resilience: str = "estavel"
    consumo_agua_mm: float
    tempo_colheita_dias: int


class GAEZAptidaoResponse(BaseModel):
    origem: str = "fao_gaez_v5"
    data_quality: str
    input_level: str
    ssp_scenario: str
    centroid: Dict[str, float]
    soil: GAEZSoilResponse
    culturas_avaliadas: List[GAEZCropSuitabilityResponse]
    culturas_sincronizadas: List[CulturaResponse] = Field(default_factory=list)


class EcoCropProfileResponse(BaseModel):
    ecoport_code: Optional[str] = None
    scientific_name: str
    family: Optional[str] = None
    family_canonical: Optional[str] = None
    family_taxonomy: Optional[str] = None
    common_names: List[str] = Field(default_factory=list)
    tmin: Optional[float] = None
    tmax: Optional[float] = None
    topmin: Optional[float] = None
    topmax: Optional[float] = None
    rmin: Optional[float] = None
    rmax: Optional[float] = None
    ropmin: Optional[float] = None
    ropmax: Optional[float] = None
    gmin: Optional[int] = None
    gmax: Optional[int] = None
    phmin: Optional[float] = None
    phmax: Optional[float] = None
    phopmin: Optional[float] = None
    phopmax: Optional[float] = None
    climate_zones: Optional[str] = None
    synonyms: Optional[str] = None


class EcoCropLookupResponse(BaseModel):
    origem: str = "fao_ecocrop"
    data_quality: str
    query: str
    found: bool
    crop: Optional[EcoCropProfileResponse] = None


class CulturaCatalogoItem(BaseModel):
    id: str
    scientific_name: str
    official_name: str
    popular_names: List[str] = Field(default_factory=list)
    family: Optional[str] = None
    cat: Optional[str] = None
    gmin: Optional[int] = None
    gmax: Optional[int] = None
    image_url: Optional[str] = None


class PragaCatalogoItem(BaseModel):
    id: str
    official_name: str
    popular_names: List[str] = Field(default_factory=list)
    scientific_name: Optional[str] = None
    category: str = "Praga / Doença"

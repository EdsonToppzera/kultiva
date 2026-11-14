from datetime import datetime
from typing import List, Optional
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

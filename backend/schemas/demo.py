from typing import List
from pydantic import BaseModel


class DemoSeedResponse(BaseModel):
    status: str = "ok"
    reset_executado: bool
    idempotente: bool
    usuario_id: int
    terrenos_ids: List[int]
    culturas_total: int
    rotacoes_total: int
    metricas_total: int
    atividades_total: int
    alertas_total: int
    resumo: str

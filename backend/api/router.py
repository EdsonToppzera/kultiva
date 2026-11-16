from fastapi import APIRouter
from backend.api import alertas, calendario, cultura, demo, relatorios, simulacao, terreno, usuario

api_router = APIRouter()
api_router.include_router(usuario.router)
api_router.include_router(terreno.router)
api_router.include_router(cultura.router)
api_router.include_router(cultura.rotacao_router)
api_router.include_router(simulacao.router)
api_router.include_router(simulacao.simular_rotacao_router)
api_router.include_router(calendario.router)
api_router.include_router(alertas.router)
api_router.include_router(relatorios.router)
api_router.include_router(demo.router)


@api_router.get("/health", tags=["Sistema"])
def api_health_check():
    return {"status": "ok", "message": "Kultiva API is running"}


# Importar e adicionar rotas modulares futuras aqui
# ex: api_router.include_router(geospatial_router, prefix="/geo", tags=["Geospatial"])

from fastapi import APIRouter
from backend.api import terreno

api_router = APIRouter()
api_router.include_router(terreno.router)
# Importar e adicionar rotas modulares futuras aqui
# ex: api_router.include_router(geospatial_router, prefix="/geo", tags=["Geospatial"])

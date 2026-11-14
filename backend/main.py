from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError
from backend.api.router import api_router
from backend.db import models
from backend.db.database import SessionLocal, engine

logger = logging.getLogger(__name__)


def seed_culturas():
    """Popula o catálogo inicial de culturas caso a tabela esteja vazia."""
    db = SessionLocal()
    try:
        if db.query(models.Cultura).count() == 0:
            culturas_iniciais = [
                models.Cultura(
                    nome="Milho",
                    consumo_agua_mm=500.0,
                    tempo_colheita_dias=90,
                    resistencia_pragas="Média (Lagarta)",
                ),
                models.Cultura(
                    nome="Feijão Macáçar",
                    consumo_agua_mm=300.0,
                    tempo_colheita_dias=70,
                    resistencia_pragas="Alta (Seca/Pragas)",
                ),
                models.Cultura(
                    nome="Mandioca",
                    consumo_agua_mm=400.0,
                    tempo_colheita_dias=270,
                    resistencia_pragas="Alta",
                ),
                models.Cultura(
                    nome="Crotalária",
                    consumo_agua_mm=250.0,
                    tempo_colheita_dias=60,
                    resistencia_pragas="Alta (Nematoides)",
                ),
            ]
            db.add_all(culturas_iniciais)
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        models.Base.metadata.create_all(bind=engine)
        seed_culturas()
    except SQLAlchemyError as exc:
        logger.warning("Banco indisponível no startup; pulando create_all/seed: %s", exc)
    yield


app = FastAPI(
    title="Kultiva API",
    description="Sistema de apoio à decisão para pequenos produtores rurais.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Kultiva API is running"}

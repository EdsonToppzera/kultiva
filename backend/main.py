from contextlib import asynccontextmanager
import logging
import os
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from backend.api.router import api_router
from backend.db import models
from backend.db.database import SessionLocal, engine
from backend.services.alert_tasks import lifespan_monitoramento_alertas

logger = logging.getLogger(__name__)

_DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
]


def _resolver_origens_cors() -> list[str]:
    """Combina origens padrão locais com CORS_ALLOWED_ORIGINS mantendo ordem única."""
    env_raw = os.getenv("CORS_ALLOWED_ORIGINS", "")
    extras = [item.strip() for item in env_raw.split(",") if item.strip()]
    return list(dict.fromkeys([*extras, *_DEFAULT_CORS_ORIGINS]))


def seed_usuario_padrao(db: Optional[Session] = None) -> models.Usuario:
    """Garante a existência de um usuário padrão no banco para uso inicial/demo."""
    own_session = db is None
    session = SessionLocal() if own_session else db
    try:
        usuario = (
            session.query(models.Usuario)
            .order_by(models.Usuario.id.asc())
            .first()
        )
        if usuario is None:
            usuario = models.Usuario(
                nome="Produtor Rural Kultiva",
                email="produtor@kultiva.agro",
            )
            session.add(usuario)
            session.commit()
            session.refresh(usuario)
        return usuario
    finally:
        if own_session:
            session.close()


def seed_culturas(db: Optional[Session] = None):
    """Popula usuário padrão, catálogo inicial de culturas e rotações base se vazios."""
    own_session = db is None
    session = SessionLocal() if own_session else db
    try:
        seed_usuario_padrao(session)

        if session.query(models.Cultura).count() == 0:
            culturas_iniciais = [
                models.Cultura(
                    nome="Milho",
                    consumo_agua_mm=500.0,
                    tempo_colheita_dias=90,
                    resistencia_pragas="Média (Lagarta)",
                    is_seed=True,
                    customizada=False,
                ),
                models.Cultura(
                    nome="Feijão Macáçar",
                    consumo_agua_mm=300.0,
                    tempo_colheita_dias=70,
                    resistencia_pragas="Alta (Seca/Pragas)",
                    is_seed=True,
                    customizada=False,
                ),
                models.Cultura(
                    nome="Mandioca",
                    consumo_agua_mm=400.0,
                    tempo_colheita_dias=270,
                    resistencia_pragas="Alta",
                    is_seed=True,
                    customizada=False,
                ),
                models.Cultura(
                    nome="Crotalária",
                    consumo_agua_mm=250.0,
                    tempo_colheita_dias=60,
                    resistencia_pragas="Alta (Nematoides)",
                    is_seed=True,
                    customizada=False,
                ),
            ]
            session.add_all(culturas_iniciais)
            session.commit()

        if session.query(models.RotacaoProdutor).count() == 0:
            rotacoes_iniciais = [
                models.RotacaoProdutor(
                    nome="Milho -> Soja",
                    culturas=["Milho", "Soja"],
                    preferencial=False,
                    is_seed=True,
                    beneficios="Mercado estabelecido e cadeia de comercialização consolidada",
                ),
                models.RotacaoProdutor(
                    nome="Sorgo -> Feijão-caupi",
                    culturas=["Sorgo", "Feijão-caupi"],
                    preferencial=False,
                    is_seed=True,
                    beneficios="Alta tolerância à seca, fixa nitrogênio",
                ),
                models.RotacaoProdutor(
                    nome="Milheto -> Amendoim",
                    culturas=["Milheto", "Amendoim"],
                    preferencial=False,
                    is_seed=True,
                    beneficios="Melhora a estrutura do solo",
                ),
                models.RotacaoProdutor(
                    nome="Mandioca -> Crotalária",
                    culturas=["Mandioca", "Crotalária"],
                    preferencial=False,
                    is_seed=True,
                    beneficios="Rústica, cobre o solo e controla nematoides",
                ),
            ]
            session.add_all(rotacoes_iniciais)
            session.commit()
    finally:
        if own_session:
            session.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        models.Base.metadata.create_all(bind=engine)
        seed_culturas()
    except SQLAlchemyError as exc:
        logger.warning("Banco indisponível no startup; pulando create_all/seed: %s", exc)
    async with lifespan_monitoramento_alertas(_app):
        yield


app = FastAPI(
    title="Kultiva API",
    description="Sistema de apoio à decisão para pequenos produtores rurais.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolver_origens_cors(),
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Kultiva API is running"}

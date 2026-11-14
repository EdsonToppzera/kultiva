from fastapi import FastAPI
from backend.api.router import api_router

app = FastAPI(
    title="Kultiva API",
    description="Sistema de apoio à decisão para pequenos produtores rurais.",
    version="0.1.0"
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health_check():
    return {"status": "ok", "message": "Kultiva API is running"}

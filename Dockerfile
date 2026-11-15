FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --prefer-binary --upgrade pip \
    && pip install --no-cache-dir --prefer-binary -r requirements.txt

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PORT=7860

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libexpat1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
COPY backend ./backend
COPY alembic ./alembic
COPY alembic.ini ./
COPY data/processed/ecocrop_culturas_limites.csv \
     data/processed/ecocrop_culturas_sinonimos_en.csv \
     data/processed/ecocrop_culturas_sinonimos_pt.csv \
     data/processed/cultura_pragas_ecocrop_join.csv \
     ./data/processed/

RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data/ecocrop_cache \
    && chown -R appuser:appuser /app/data \
    && chmod -R a+rwX /app/data

USER appuser

EXPOSE 7860 8000

CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers"]

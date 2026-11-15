# System Architecture

This document describes the relational database modeling (PostgreSQL/SQLAlchemy) and orchestration across the **Kultiva** API modules.

## 1. Database Modeling (ERD)

```mermaid
erDiagram
    usuarios ||--o{ terrenos : owns
    usuarios ||--o{ culturas : customizes
    usuarios ||--o{ rotacoes_produtor : defines
    usuarios ||--o{ atividades_calendario : tracks
    terrenos ||--o{ rotacoes_produtor : prefers
    terrenos ||--o{ metricas_historicas_terreno : records
    terrenos ||--o{ atividades_calendario : schedules
    culturas ||--o{ atividades_calendario : references
    terrenos ||--o{ alertas_climaticos : receives

    usuarios {
        int id PK
        string nome
        string email
    }

    terrenos {
        int id PK
        string nome_propriedade
        int usuario_id FK
        json coordenadas_poligono
        json prioridades
    }

    culturas {
        int id PK
        string nome
        float consumo_agua_mm
        int tempo_colheita_dias
        boolean is_seed
        boolean customizada
        int usuario_id FK
    }

    rotacoes_produtor {
        int id PK
        string nome
        json culturas
        int usuario_id FK
        int terreno_id FK
        boolean preferencial
        boolean is_seed
    }

    metricas_historicas_terreno {
        int id PK
        int terreno_id FK
        date data_medicao
        float soil_moisture
        float surface_temp_c
        float precipitation_mm
        boolean is_bare_field_period
        string data_quality
        string origem
    }

    atividades_calendario {
        int id PK
        int terreno_id FK
        int usuario_id FK
        int cultura_id FK
        string titulo
        text descricao
        string tipo_atividade
        date data_programada
        string prioridade
        string status
        boolean concluida
        datetime data_conclusao
        boolean ajustada_por_alerta
        string motivo_ajuste
        datetime criado_em
    }

    alertas_climaticos {
        int id PK
        int terreno_id FK
        string tipo_evento
        string severidade
        string titulo
        text mensagem
        date data_evento
        string origem_gatilho
        json dados_gatilho
        boolean processado_background
        text resumo_adaptacao
        boolean lido
        datetime criado_em
    }
```

> **Modeling note:** The `atividades_calendario` table is mapped by the `Activity` class (`backend/db/models.py`, aliased as `AtividadeCalendario`), allowing direct association with a `Terreno` or `Usuario`, in addition to the textual `status` field (`pendente` / `concluida`) synchronized with `concluida` and `data_conclusao`.

## 2. Two-Layer Geospatial Architecture (Strategic FAO GAEZ v5 + Operational NASA)

To combine long-term structural suitability for Brazilian territory with continuous real-time climate monitoring, the backend separates data collection into two complementary layers:

1. **Strategic Layer (`backend/services/gaez_service.py` — ~10 km / 5 arc-min):**
   - `GAEZDataProvider` **directly** accesses public **FAO GAEZ v5** Cloud-Optimized GeoTIFF (COG) rasters via HTTP Range Requests (`RES05-SUX` / `RES05-YLX` *Suitability and Attainable Yield*, `CMIP6 FP2140 SSP370` projection, `HWSDV201` soil, `SQX.SQ0` quality, `SQ-IDX` limiting factor, and `SLOPE-MED` slope), selecting among the 4 management regimes (`LRLM`, `HRLM`, `LILM`, `HILM`) based on farmer priorities and keeping a local cache in `data/gaez_cache/`.
   - **No fabricated fallbacks policy:** when the GAEZ service is unresponsive, it explicitly returns `data_quality="no_data"` (HTTP `503` in `GET /api/v1/culturas/aptidao-gaez`).
2. **Operational Layer (`backend/services/geospatial.py`):**
   - `INASADataProvider` (`MockNASADataProvider` with simulatable profiles or `RealNASADataProvider` via `data/real/`, Earthdata `SPL3SMP_E`, `ECO2LSTE`, `GPM_3IMERGDF`, `MOD13Q1`, and public **NASA POWER** fallback) provides recent series for soil moisture, surface temperature, precipitation, and bare-field periods.

## 3. Crop & Rotation Simulator Orchestration (M3)

The `backend/api/simulacao.py` controller acts as the synchronous orchestration layer via dependency injection (`Depends`) for the `POST /api/v1/simular-rotacao` endpoint (also exposed at `/api/v1/simulacoes/`):

```mermaid
flowchart LR
    FE["Frontend (PWA)"] -->|"POST /api/v1/simular-rotacao"| M3["M3 Controller (backend/api/simulacao.py)"]
    M3 -->|"Queries Plot and Crop"| DB[("PostgreSQL (SQLAlchemy)")]
    M3 -->|"Operational Layer: extract_field_metrics()"| GEO["INASADataProvider (services/geospatial.py)"]
    M3 -->|"Strategic Layer: extract_gaez_metrics()"| GAEZ["GAEZDataProvider (services/gaez_service.py -> FAO COG)"]
    GEO -->|"Time series + current weather"| ML
    GAEZ -->|"Suitability, Yield kg/ha, HWSD, CMIP6"| ML["CropSimulator (RandomForest + GAEZ in ml_models.py)"]
    ML -->|"3 strategies + score_breakdown"| LLM["RotationExplainerAgent (Gemini / FakeListLLM in llm_agent.py)"]
    M3 -->|"JSON SimulacaoResponse"| FE
```

- **Input Resilience and Flexibility:** The controller accepts either `terreno_id` (fetching from the database) or `coordenadas_poligono` and `prioridades` sent directly in the JSON payload without requiring prior registration. In the NASA operational layer, if NetCDF data or optional packages are unavailable, a safe fallback preserves the JSON contract; the FAO GAEZ v5 layer enriches the simulation only when real COG/cache data is available (`GAEZ_ENABLED=true` or `perfil_climatico="real"`).

## 4. Asynchronous Climate Alerts & Flexible Calendar Flow (M4 & M5)

To keep the containerized environment lean (without requiring an external broker in the current `docker-compose.yml`), `[M5]` alerts use `FastAPI BackgroundTasks` and FastAPI's native `lifespan` in `backend/services/alert_tasks.py` (`lifespan_monitoramento_alertas`), which automatically starts the periodic background scheduler at application startup (configurable via the `ALERT_MONITOR_INTERVAL_HOURS` environment variable, default `6` hours):

```mermaid
flowchart TD
    MON["Periodic Routine (6h / 12h) or POST /api/v1/alertas/monitorar"] -->|"Collects climate data"| MOCK["generate_synthetic_netcdf() (services/mock_nasa_data.py)"]
    MOCK -->|"Series / metrics"| DET["ClimateAnomalyDetector (services/ml_models.py)"]
    ML["ML / NASA / Sensor Trigger"] -->|"POST /api/v1/alertas/gatilho"| API["M5 Alerts Endpoint (backend/api/alertas.py)"]
    API -->|"detect_extremes()"| DET
    DET -->|"Anomaly detected"| PERSIST["Persists AlertaClimatico in PostgreSQL"]
    API -->|"Returns HTTP 202 Accepted"| ML
    PERSIST -->|"Schedules / Runs BackgroundTask"| TASK["processar_alerta_e_adaptar_calendario()"]
    TASK -->|"Opens own session (SessionLocal)"| DB[("PostgreSQL")]
    TASK -->|"Postpones/Adjusts/Creates Activity (M4)"| DB
```

### Dynamic Calendar Adaptation Rules
1. **`chuva_intensa` / `tempestade` / `heavy_rain`:**
   - Postpones pending `irrigacao`, `adubacao`, and `pulverizacao` activities within the event window by `dias_adiamento` days (default `2` days).
   - Creates an `inspecao` activity to check post-rain drainage and runoff.
2. **`onda_de_calor` / `seca` / `heatwave` / `drought`:**
   - Escalates the priority of pending `irrigacao` activities in the window to `critica`.
   - Creates an emergency supplemental `irrigacao` and soil thermal protection activity on the event date.
3. **`geada` / `vendaval` / `frost` / `windstorm` (and other extremes):**
   - Postpones pending `plantio` and `adubacao` activities in the window by `dias_adiamento` days.
   - Creates an emergency `manejo` activity for crop protection.

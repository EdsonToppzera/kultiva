# Technical Specifications (Specs)

API base prefix: `/api/v1`  
Automatic interactive documentation (Swagger UI): `GET /docs`

---

## [M1] Plots and Initial Setup (`backend/api/terreno.py`, `backend/main.py`)

### Startup and CORS Configuration
- `CORSMiddleware` enabled in FastAPI for local frontend origins (`http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000`, `http://localhost:8000`) and additional origins via `CORS_ALLOWED_ORIGINS`.
- Automatic seeding of the default `Usuario` (`seed_usuario_padrao` / `produtor@kultiva.agro`) and base catalog on startup (`lifespan`).

### `POST /api/v1/terrenos/`
Creates a new plot with the geographic polygon and farmer priorities. When `area_hectares` or `localizacao_central` are omitted, they are automatically calculated from `coordenadas_poligono` via `calcular_geometria_terreno`.

**Request Body:**
```json
{
  "nome_propriedade": "Sítio Esperança",
  "usuario_id": 1,
  "coordenadas_poligono": [
    {"lat": -23.5505, "lng": -46.6333},
    {"lat": -23.5515, "lng": -46.6343},
    {"lat": -23.5525, "lng": -46.6323}
  ],
  "prioridades": {
    "agua": "escassa",
    "foco_mercado": "local"
  }
}
```

**Response (`200 OK`):** Returns the created plot data including `"id"`, `"area_hectares"`, and `"localizacao_central"`.

### `GET /api/v1/terrenos/` (`200 OK`) and `GET /api/v1/terrenos/{terreno_id}` (`200 OK`)
Lists plots (with optional `usuario_id` filter) or fetches a specific plot (`404` if not found).

### `PUT /api/v1/terrenos/{terreno_id}` (`200 OK`)
Partially or fully updates a plot. When `coordenadas_poligono` is changed, automatically recalculates `area_hectares` and `localizacao_central` if omitted from the payload.

### `DELETE /api/v1/terrenos/{terreno_id}` (`204 No Content`)
Deletes the plot and cleans up associated dependent records (`metricas_historicas_terreno`, `alertas_climaticos`, `atividades_calendario`, and plot-specific custom rotations).

---

## [M2] Crop and Rotation Catalog (`backend/api/cultura.py`)

### Crops (`/api/v1/culturas`)
- `GET /api/v1/culturas/`: lists crops with optional filters (`is_seed`, `customizada`, `usuario_id`).
- `GET /api/v1/culturas/aptidao-gaez`: **directly** queries **FAO GAEZ v5** COGs (*Suitability and Attainable Yield* `RES05-SUX`/`YLX`, `HWSDV201` soil, `SQ-IDX`, `SQX.SQ0`, `SLOPE-MED` slope, and `CMIP6 FP2140 SSP370` projection) for the coordinate/plot and management profile (`LRLM`, `HRLM`, `LILM`, `HILM`).
  - **Query Params:** `terreno_id` or `lat` & `lng`; optional `agua`, `metodo_irrigacao`, `nivel_insumo`, and `sincronizar_catalogo=true|false` (saves/updates viable crops in the `[M2]` catalog while preserving `is_seed=true`).
  - **Responses:** `200 OK` (`origem`, `data_quality`, `input_level`, `ssp_scenario`, `centroid`, `soil`, `culturas_avaliadas`, `culturas_sincronizadas`) or `503 Service Unavailable` if GAEZ v5 does not respond (`no_data`, no fabricated fallback).
- `GET /api/v1/culturas/ecocrop`: directly queries the **FAO ECOCROP** database (`EcoCrop_DB.csv` with local cache, no fabricated fallback) to return taxonomy (`scientific_name`, `family`, `family_canonical`) and comfort zone (`tmin`/`tmax`, `topmin`/`topmax`, `rmin`/`rmax`, `gmin`/`gmax`).
  - **Query Params:** `q`, `nome`, `scientific_name`, `crop_code`, `ecoport_code`, or `cultura_id`.
  - **Responses:** `200 OK`, `404 Not Found` (crop not found in database), or `503 Service Unavailable` if the ECOCROP CSV is unavailable (`no_data`).
- `GET /api/v1/culturas/{cultura_id}`: retrieves details of a crop.
- `POST /api/v1/culturas/` (`200 OK`): creates a custom crop (`is_seed=false`, `customizada=true`), validating unique name and positive values (`consumo_agua_mm > 0`, `tempo_colheita_dias > 0`).
- `PUT /api/v1/culturas/{cultura_id}` (`200 OK`): edits a custom crop (returns `403 Forbidden` for `is_seed=true` crops).
- `DELETE /api/v1/culturas/{cultura_id}` (`204 No Content`): deletes a custom crop (returns `403 Forbidden` for `is_seed=true`).

### Farmer Rotations (`/api/v1/rotacoes`)
- `GET /api/v1/rotacoes/`: lists rotations with filters (`usuario_id`, `terreno_id`, `preferencial`, `is_seed`).
- `GET /api/v1/rotacoes/{rotacao_id}`: retrieves details of a rotation.
- `POST /api/v1/rotacoes/` (`201 Created`): creates a preferred rotation (`culturas` with at least 2 crops). Rotations with `preferencial=true` are automatically included in the `[M3]` simulator ranking.
- `PUT /api/v1/rotacoes/{rotacao_id}` (`200 OK`): updates a custom rotation (`403` if `is_seed=true`).
- `DELETE /api/v1/rotacoes/{rotacao_id}` (`204 No Content`): deletes a custom rotation (`403` if `is_seed=true`).

---

## [M3] Crop and Rotation Simulator (`backend/api/simulacao.py`)

### `POST /api/v1/simular-rotacao`
*(Also available at `POST /api/v1/simulacoes/` and `POST /api/v1/simulacoes/simular-rotacao`)*

Receives the request from the frontend, accepts either `terreno_id` (loaded from PostgreSQL) or `coordenadas_poligono`, `nome_propriedade`, and `prioridades` sent directly in JSON without requiring prior registration, and injects `INASADataProvider` (`services/geospatial.py`), `GAEZDataProvider` (`services/gaez_service.py` — when `GAEZ_ENABLED=true` or `perfil_climatico="real"`), `CropSimulator` (`services/ml_models.py`), and `RotationExplainerAgent` (`services/llm_agent.py`), returning the suggested rotation strategies (with `score_breakdown` and per-strategy explanation).

**Request Body (with registered `terreno_id` or direct coordinates in JSON):**
```json
{
  "terreno_id": 1,
  "nome_propriedade": "Sítio Esperança",
  "coordenadas_poligono": [
    {"lat": -23.5505, "lng": -46.6333},
    {"lat": -23.5515, "lng": -46.6343},
    {"lat": -23.5525, "lng": -46.6323}
  ],
  "cultura_id": null,
  "nome_cultura": "Feijão Carioca",
  "culturas_rotacao": ["Milho", "Crotalária"],
  "historico_cultivos": ["Milho", "Milho"],
  "perfil_climatico": "normal",
  "prioridades": {
    "water_conservation": true
  },
  "dados_solo": {
    "ph": 6.2,
    "textura": "argilosa"
  },
  "dados_climaticos": {
    "precipitacao_mm": 480.0,
    "temperatura_media_c": 26.0
  }
}
```
> **Note:** `terreno_id` is optional if `coordenadas_poligono`/`prioridades` are sent directly in the payload (in this case `terreno_id` returns `null`). `perfil_climatico` accepts `normal`, `seca`, `chuva_extrema`, `onda_de_calor`, or `real`. If `cultura_id` and `nome_cultura` are omitted, the controller automatically selects the highest-viability strategy returned by `CropSimulator.simulate_rotation_strategies()`.

**Response (`200 OK`):**
```json
{
  "terreno_id": 1,
  "nome_propriedade": "Sítio Esperança",
  "cultura_principal": "Feijão Carioca",
  "viability_score": 0.85,
  "water_risk": "low",
  "tempo_colheita_dias": 90,
  "consumo_agua_mm": 450.0,
  "metricas_geoespaciais": {
    "origem": "nasa_geospatial_service",
    "total_vertices_poligono": 3,
    "area_hectares": 12.4,
    "centroide": {"lat": -23.5515, "lng": -46.6333},
    "precipitacao_estimada_mm": 480.0,
    "temperatura_media_c": 26.0,
    "umidade_solo_estimada": 0.42,
    "gaez": {
      "origem": "fao_gaez_v5",
      "data_quality": "gaez_v5_cog",
      "input_level": "LRLM",
      "soil": {"soil_group": "Ferralsols - FR (Latossolos)", "soil_quality_index": 0.55}
    }
  },
  "beneficios_esperados": [
    "Alignment of Feijão Carioca's cycle with your plot planning",
    "Use of environmental data for preventive resource management"
  ],
  "riscos_identificados": [
    "Plot with limited water availability compared to estimated demand of 450 mm"
  ],
  "explicacao_ia": "...",
  "explicacao_textual": "...",
  "rotacoes_sugeridas": [
    {
      "strategy": "Sorgo -> Feijão-caupi",
      "viability": 0.88,
      "water_risk": "low",
      "score_breakdown": {
        "water_fit": 1.0,
        "heat_fit": 0.94,
        "ml_model_score": 0.86,
        "temporal_stability": 0.82,
        "gaez_suitability": 0.92,
        "attainable_yield_kg_ha": 1150.0,
        "cmip6_suitability_delta": 0.03,
        "soil_quality_index": 0.55,
        "gaez_input_level": "LRLM"
      },
      "explicacao": "..."
    }
  ],
  "plano_rotacao": [
    {
      "ordem": 1,
      "cultura": "Feijão Carioca",
      "duracao_dias": 90,
      "consumo_agua_estimado_mm": 450.0,
      "viabilidade_score": 0.85,
      "risco_hidrico": "low"
    }
  ]
}
```

---

## [M4] Crop Activity Calendar (`backend/api/calendario.py`)

The module uses the `Activity` (`atividades_calendario`) model, which can be linked to a `terreno_id`, a `usuario_id`, or both, keeping `status` (`pendente` / `concluida`) synchronized with `concluida` (`bool`).

### `POST /api/v1/calendario/atividades` (`201 Created`)
Creates a scheduled daily activity in the calendar (requires `terreno_id` or `usuario_id`).

**Request Body:**
```json
{
  "terreno_id": 1,
  "usuario_id": 1,
  "cultura_id": null,
  "titulo": "Morning bed irrigation",
  "descricao": "Apply light water layer before 9 AM",
  "tipo_atividade": "irrigacao",
  "data_programada": "2026-11-20",
  "prioridade": "alta",
  "status": "pendente"
}
```
Supported types: `plantio`, `irrigacao`, `adubacao`, `manejo`, `colheita`, `inspecao`.  
Priorities: `baixa`, `media`, `alta`, `critica`.  
Valid statuses: `pendente`, `concluida`.

### `POST /api/v1/calendario/gerar-cronograma` (`201 Created`)
Automatically generates the initial schedule for a cycle (planting, initial irrigation, phytosanitary inspection, top-dressing fertilization, and harvest).

**Request Body:**
```json
{
  "terreno_id": 1,
  "cultura_id": null,
  "nome_cultura": "Milho",
  "data_inicio": "2026-11-15",
  "tempo_colheita_dias": 110
}
```

### `GET /api/v1/calendario/atividades` (`200 OK`)
Lists activities ordered by `data_programada` and `id`, focusing on date-range queries.  
**Optional Query Params:** `terreno_id`, `usuario_id`, `status` (`pendente` / `concluida`), `concluida`, `tipo_atividade`, `data_inicio`, `data_fim`.

### `GET /api/v1/calendario/atividades/{atividade_id}` (`200 OK`)
Returns details for a specific activity.

### `PATCH /api/v1/calendario/atividades/{atividade_id}/status` (`200 OK`)
*(Also available at `PATCH /api/v1/calendario/atividades/{atividade_id}/concluir`)*

Updates the activity status between `pendente` and `concluida`, automatically updating `concluida` and `data_conclusao`.

**Request Body:**
```json
{
  "status": "concluida"
}
```
*(Alternatively accepts `{"concluida": true}` or `{"concluida": false}`).*

### `PUT /api/v1/calendario/atividades/{atividade_id}` (`200 OK`)
Partially or fully updates a scheduled activity.

### `DELETE /api/v1/calendario/atividades/{atividade_id}` (`204 No Content`)
Removes an activity from the calendar.

---

## [M5] Climate Alerts and Background Tasks (`backend/api/alertas.py`)

### `POST /api/v1/alertas/monitorar` / `POST /api/v1/alertas/monitorar-clima` (`202 Accepted`)
In addition to the periodic scheduler started automatically in FastAPI's `lifespan` (configurable via `ALERT_MONITOR_INTERVAL_HOURS`, default `6` hours), these endpoints allow triggering an on-demand background cycle (`FastAPI BackgroundTasks`) of `executar_ciclo_monitoramento_alertas()` (`backend/services/alert_tasks.py`), which reads climate data (`services/mock_nasa_data.py`), runs `ClimateAnomalyDetector.detect_extremes()`, and, if anomalies are detected, automatically persists an `AlertaClimatico` in the database (with `orientacao_pratica` via `explain_alert`) and adapts the `[M4]` calendar. Optionally accepts `"perfil_climatico"` (`normal`, `seca`, `chuva_extrema`, `onda_de_calor`) for immediate demo scenario triggers.

**Request Body:**
```json
{
  "terreno_id": 1,
  "intervalo_horas": 6,
  "perfil_climatico": "chuva_extrema"
}
```

**Response (`202 Accepted`):**
```json
{
  "status": "accepted",
  "mensagem": "Background climate monitoring scheduled (configured 6h window, profile 'chuva_extrema').",
  "intervalo_horas": 6,
  "terreno_id": 1,
  "perfil_climatico": "chuva_extrema"
}
```

### `POST /api/v1/alertas/gatilho` (`202 Accepted`)
Receives explicit triggers from ML algorithms (or NASA/manual data), optionally runs `ClimateAnomalyDetector.detect_extremes()`, records the alert, and schedules `processar_alerta_e_adaptar_calendario()` in the background to adapt pending tasks in the `[data_evento, data_evento + 3 days]` window.

**Request Body:**
```json
{
  "terreno_id": 1,
  "tipo_evento": "chuva_intensa",
  "severidade": "alta",
  "data_evento": "2026-11-20",
  "titulo": "Heavy rainfall alert",
  "mensagem": "Forecast of rainfall above 70 mm over the next 48 hours.",
  "origem_gatilho": "ml_anomaly_detector",
  "serie_temporal_clima": [
    {"data": "2026-11-19", "precipitacao_mm": 12.0, "temp_max_c": 29.0},
    {"data": "2026-11-20", "precipitacao_mm": 78.5, "temp_max_c": 23.0}
  ],
  "dias_adiamento": 2
}
```

### `GET /api/v1/alertas/` (`200 OK`)
Lists climate alerts ordered by `data_evento` descending.  
**Optional Query Params:** `terreno_id`, `lido`, `severidade`, `tipo_evento`.

### `GET /api/v1/alertas/resumo-nao-lidos` (`200 OK`)
Returns `total_nao_lidos` and `por_terreno` grouping (including unread critical count and latest event) for the farmer dashboard (`terreno_id` optional).

### `GET /api/v1/alertas/{alerta_id}` (`200 OK`)
Retrieves alert details, `orientacao_pratica`, and `resumo_adaptacao`.

### `PATCH /api/v1/alertas/{alerta_id}/ler` (`200 OK`)
Marks the alert as read (`"lido": true`).

---

## [M6] Periodic Reports and Metrics History (`backend/api/relatorios.py`)

### `GET /api/v1/relatorios/terreno/{terreno_id}` (`200 OK`)
*(Also accessible at `GET /api/v1/relatorios/?terreno_id=...`)*

Consolidates the periodic adaptation report for the plot (optional `data_inicio` and `data_fim`, default last 30 days):
- Historical series of soil moisture, temperature, precipitation, and bare-soil indicator (`metricas_historicas_terreno`). If no snapshots are stored in the period, queries `INASADataProvider.extract_field_metrics()` on demand and persists the series.
- Computed **vigor** (`indice`, `classificacao`, `tendencia`) and **vulnerability** (`indice`, `nivel`, `fatores_risco`) indices.
- Accounting of calendar **adaptations** (`ajustada_por_alerta == true`) and climate alerts for the period.
- **Period comparison** (`comparativo_periodo`): changes between the first and last measurements in the historical series (`umidade_inicial`/`umidade_final`, `variacao_umidade`, `variacao_umidade_percentual`, temperature, precipitation, and `tendencia_geral`).
- **AI Interpretive Summary** (`resumo_ia` and `explicacao_ia`): plain-language synthesis generated via `RotationExplainerAgent.explain_report()` (with offline deterministic fallback), always concluded with the legal disclaimer (`DISCLAIMER`).

### `GET /api/v1/relatorios/terreno/{terreno_id}/metricas` (`200 OK`)
Lists persisted daily snapshots for the plot with optional `data_inicio` and `data_fim` filtering.

### `POST /api/v1/relatorios/terreno/{terreno_id}/metricas` (`201 Created`)
Allows manually recording a climate measurement or triggering synchronization via `INASADataProvider` when the JSON body is omitted.

---

## [Demo] Demo Seed (`backend/api/demo.py`)

### `POST /api/v1/demo/seed` (`200 OK`)
*(Optional query param: `reset=false|true`)*

Populates the complete demonstration environment in a single call (default user, seed and custom crops/rotations, two plots with A9 climate profiles — `seca` and `chuva_extrema` — extracted via `MockNASADataProvider`, historical metrics aligned to the recent period, calendar activities with `ajustada_por_alerta=true` records, and climate alerts with practical guidance):
- `reset=false` *(default)*: **idempotent** operation that creates only what does not yet exist, preserving IDs and counts across consecutive calls.
- `reset=true`: deletes and recreates all data associated with the demo plots from scratch.

# Hackathon Tasks — Data/ML/AI, Backend & Demo Integration

**Owners:** **Dev A** = data, ML & AI · **Dev B** = catalog, reports, plots & infra/demo · **Dev C** = simulation, alerts & calendar.

**Legend:** ✅ done (merged into `dev` / ready for PR) · 🔄 in progress · ⬜ pending

## Current Status (Rounds 1, 2 & 3 completed · Round 4 / Biological Evolution & Frontend `F3` planned)

- `backend/tests` suite: **green** (75 tests covering Rounds 1, 2, 3, partial Round 4, NASA Real Data, FAO GAEZ v5, ECOCROP, and AGROFIT: `A1–A16`, `B1–B8`, `C1–C9`).
- **Done (Round 1):** `A1–A6` (Dev A) · `B1–B4` (Dev B) · `C1–C5` (Dev C) · infra baseline.
- **Done (Round 2):** `A7–A9` (Dev A) · `B5–B7` (Dev B) · `C6–C8` (Dev C).
- **Done (Round 3):** `A10–A14` ✅ · `B8` ✅ · `C9` ✅ · `F1–F2` ✅.
- **Round 4 (In progress):** `A15` (ECOCROP) ✅ · `A16` (AGROFIT × NASA × `CropSimulator`) ✅ · **Pending:** `A17` (historical climate Z-score) · `A18` (structured explanation with numerical evidence + SRTM/HLS) · `F3` (complete `frontend/` screens with numerical blocks).

### Summary of Deliverables

- **Dev A (`A1–A14`)**
  - **A1–A6 (Round 1):** Deterministic synthetic NetCDFs (`mock_nasa_data.py`), `MockNASADataProvider` + `RealNASADataProvider` (`geospatial.py`, `NASA_PROVIDER=mock|real`), dynamic `CropSimulator` and `ClimateAnomalyDetector` (`ml_models.py`), `RotationExplainerAgent.explain_strategies` with `DISCLAIMER` (`llm_agent.py`), and unit test suite (`backend/tests/test_data_ml.py`).
  - **A7 — Geometry, crop history & dynamic fallback** (`geospatial.py`, `ml_models.py`): `calcular_geometria_terreno` (area in hectares and polygon centroid); `CropSimulator` factoring in `historico_cultivos` (penalizes monoculture and rewards cycle breaks with legumes) and `fallback_strategies` method.
  - **A8 — Alert `[M5]` and report `[M6]` explanations** (`llm_agent.py`): `explain_alert` with practical management guidance and `explain_report` in plain language, keeping `DISCLAIMER` and offline deterministic fallback.
  - **A9 — Simulatable climate profiles** (`mock_nasa_data.py`, `geospatial.py`, `backend/tests/test_data_ml.py`): `normal`, `seca`, `chuva_extrema`, and `onda_de_calor` profiles (via `profile` parameter or `NASA_MOCK_PROFILE`) generating distinct scenarios that trigger `ClimateAnomalyDetector` and alter `CropSimulator` rankings.
  - **A10 — Runtime climate profile & area in simulation** (`geospatial.py`, `api/simulacao.py`): accepts on-demand `perfil_climatico` and computes `area_hectares` in `metricas_geoespaciais`.
  - **A11–A12 — Multi-source real datasets + NASA POWER + advanced ML (`RandomForestRegressor` + temporal features)** (`geospatial.py`, `ml_models.py`, `mock_nasa_data.py`, `api/simulacao.py`, `docker-compose.yml`, `.env.example`, `backend/requirements.txt`): local discovery in `data/real/`, transposed grid harmonization and `_FillValue`, unauthenticated public NASA POWER API integration/caching, `RandomForestRegressor` + temporal stability in `CropSimulator`, diagnostic metrics in `ClimateAnomalyDetector`, and `perfil_climatico="real"` support.
  - **A13 — Direct FAO GAEZ v5 provider (`Suitability and Attainable Yield`, `HWSD v2.01`, `SQ-IDX`, `SLOPE-MED`, and `CMIP6`)** (`backend/services/gaez_service.py`): parallel direct HTTP Range Requests to official COGs in FAO's public bucket (`RES05-SUX`, `RES05-YLX` for `HP0120` and `FP2140` SSP370, `HWSDV201`, `SQX.SQ0`, `SQ-IDX`, `SLOPE-MED`), mapping of the 4 management regimes (`LRLM`, `HRLM`, `LILM`, `HILM`), 5 arc-min cell caching, and `no_data` return without fabricated deterministic fallbacks.
  - **A14 — Catalog `[M2]`, Simulator `[M3]`, and AI Agent calibrated by FAO GAEZ v5** (`api/cultura.py`, `schemas/rotacao.py`, `ml_models.py`, `llm_agent.py`, `api/simulacao.py`): `GET /api/v1/culturas/aptidao-gaez` endpoint with optional database syncing of viable crops/seeds, rotation generation and scoring in `CropSimulator` using `gaez_suitability`, `attainable_yield_kg_ha` (kg/ha), `soil_quality_index`, and `cmip6_suitability_delta`, plus HWSD soil/yield contextualization in `RotationExplainerAgent`.
  - **A15 — Direct FAO ECOCROP provider** (`backend/services/ecocrop_service.py`, `api/cultura.py`, `schemas/rotacao.py`): disk-cached reading of `EcoCrop_DB.csv` (no fabricated fallback), extraction of `Scientific Name`, `Family`, `TMIN`/`TMAX`, `TOPMIN`/`TOPMAX`, `RMIN`/`RMAX`, `GMIN`/`GMAX`, and `GET /api/v1/culturas/ecocrop` endpoint.
  - **A16 — Direct AGROFIT (Embrapa AgroAPI) × NASA × `CropSimulator` provider** (`backend/services/agrofit_service.py`, `ml_models.py`, `api/simulacao.py`): OAuth2/cached query by `Scientific Name` on Agrofit v1 API (no fabricated fallback) cross-referenced with ECOCROP botanical family, `historico_cultivos`, `praga_alvo`, and NASA climate triggers (SMAP/ECOSTRESS/GPM) to expose `phytosanitary_risk`, `phytosanitary_penalty`, `botanical_families`, `agrofit_pests_count`, and `phytosanitary_warnings` in `score_breakdown`, **without blocking** subsistence crops.
- **Dev B (`B1–B7`)**
  - **B1–B4 (Round 1):** Full `[M2]` catalog CRUD (`api/cultura.py`), seed record protection, `[M6]` report service/endpoints (`services/relatorio_service.py`, `api/relatorios.py`), historical persistence in Postgres/Alembic (`services/metrics_service.py`), and tests/CI (`backend/tests/test_b1_b2_b3.py`, `.github/workflows/ci.yml`).
  - **B5 — CORS, initial seed & full `[M1]` plot CRUD** (`main.py`, `api/terreno.py`, `schemas/terreno.py`): `CORSMiddleware` enabled for `localhost:5173`, automatic default `Usuario` seed on startup, and `PUT`/`DELETE /api/v1/terrenos/{terreno_id}` with automatic area/centroid calculation (A7).
  - **B6 — `[M6]` report with AI and comparison** (`services/relatorio_service.py`, `schemas/relatorio.py`, `api/relatorios.py`): period start/end comparison and interpretive summary via `explain_report` (A8).
  - **B7 — Demo seed and Specs** (`api/demo.py`, `docs/Specs/README.md`, `backend/tests/test_b5_b6_b7.py`): `POST /api/v1/demo/seed` populating user, plots, metrics, activities, and alerts in one call.
- **Dev C (`C1–C8`)**
  - **C1–C5 (Round 1):** `origem`/`fallback_usado` in response and service caching (`api/simulacao.py`), per-plot `[M5]` monitor with deduplication and cooldown (`services/alert_tasks.py`, `api/alertas.py`), `[M4]` calendar generation and post-alert adjustment (`api/calendario.py`, `backend/tests/test_c4_fluxo.py`), timezone-aware datetimes, and Pydantic v2 schemas.
  - **C6 — `score_breakdown`, individual `explicacao`, and dynamic fallback** (`schemas/simulacao.py`, `api/simulacao.py`, `backend/tests/test_c6_simulacao.py`): each strategy in `rotacoes_sugeridas` exposes `score_breakdown` and an accessible `explicacao` with disclaimer.
  - **C7 — History in simulator and schedule directly from strategy** (`schemas/simulacao.py`, `api/simulacao.py`, `api/calendario.py`, `backend/tests/test_c7_c8.py`): `SimulacaoRequest` integrates `historico_cultivos` and `[M4]` calendar generates/updates schedule directly from the chosen strategy.
  - **C8 — Practical guidance in `[M5]` alerts and unread summary** (`api/alertas.py`, `services/alert_tasks.py`, `schemas/alerta.py`, `backend/tests/test_c7_c8.py`): `explain_alert` (A8) integration and unread alerts summary per plot.

### Focus Areas for Closing Round 3 (Frontend `F3` and Evolution)

- The entire backend (`A1–A14`, `B1–B8`, `C1–C9`) and initial frontend flows (`F1–F2`: routing, HTTP client, `PlantationsPage.tsx`, `MapTerrainPage.tsx`, `CropHistoryStep.tsx`, and `WaterDistributionStep.tsx`) are already implemented and tested (70 passing tests in `backend/tests`).
- **Primary active item (`F3`):** build/connect final screens in `frontend/src/pages/` for Simulation `[M3]` (including `score_breakdown`, `attainable_yield_kg_ha`, HWSD soil, and AI explanation), `[M2]` catalog connected to `GET /api/v1/culturas/aptidao-gaez`, Calendar `[M4]`, Alerts `[M5]`, and Reports `[M6]`, followed by end-to-end demo testing.

## Two-Layer Data Architecture, ML Status & Evolution Suggestions

1. **Brazil Adaptation — Two-Layer Architecture (no fabricated GAEZ fallbacks):**
   - **Strategic Layer (~10 km / 5 arc-min — `backend/services/gaez_service.py`):** FAO GAEZ v5 (*Suitability and Attainable Yield* `RES05-SUX`/`RES05-YLX` across the 4 regimes `LRLM`, `HRLM`, `LILM`, `HILM`) + **HWSD v2.01** + `SQ-IDX` / `SQX.SQ0` + `SLOPE-MED` + **CMIP6** (`FP2140` `SSP370`). Direct HTTP Range query to public GCS COGs with per-cell cache (`data/gaez_cache/`); if unavailable, returns `data_quality="no_data"` (HTTP `503` on `/aptidao-gaez`) without fabricating regional fallbacks.
   - **Operational Layer (`backend/services/geospatial.py`):** NASA **SMAP** (`SPL3SMP_E`), **ECOSTRESS** (`ECO2LSTE`), **GPM/IMERG** (`GPM_3IMERGDF`), **MODIS NDVI** (`MOD13Q1`) via `earthaccess`/local NetCDF and public **NASA POWER** API (`GWETTOP`, `TS`, `PRECTOTCORR`) with disk cache and simulatable (`mock`) profiles in dev/demo.
2. **What Has vs. Has Not Been Implemented in Machine Learning and AI:**
   - **Implemented:** `CropSimulator` (9-feature `RandomForestRegressor` + temporal series features + `gaez_suitability`, `attainable_yield_kg_ha`, `soil_quality_index`, `cmip6_suitability_delta` + `historico_cultivos` adjustment), `ClimateAnomalyDetector` (agronomic thresholds + `IsolationForest` + MAD robust z-score + diagnostic metrics), and `RotationExplainerAgent` (Gemini `gemini-2.5-flash` / `FakeListLLM` with HWSD soil, `kg/ha`, and mandatory `DISCLAIMER`).
   - **Planned next tasks (`A15–A18`):**
     - **ECOCROP (`A15`):** extract `Scientific Name`, `Family`, `TMIN`/`TMAX`, `TOPMIN`/`TOPMAX`, `RMIN`/`RMAX`, and `GMIN`/`GMAX` from the public ECOCROP database.
     - **AGROFIT × NASA (`A16`):** cross-reference `Scientific Name` with the Agrofit API (Embrapa AgroAPI) + NASA climate triggers (SMAP/POWER moisture + ECOSTRESS/POWER temperature) to compute phytosanitary risk in `CropSimulator`, **penalizing/warning without blocking subsistence crops** by botanical family.
     - **Historical climate Z-score (`A17`):** compare the current window against the historical baseline for the same period via NASA POWER in `ClimateAnomalyDetector`.
     - **Structured explanation + SRTM 30 m (`A18`):** return structured blocks with real numerical data for frontend cards (`F3`) and incorporate **SRTM 30 m** / **HLS** elevation/slope when available.
   - **Scope decisions (explicitly out of scope):** **do not** implement rigid botanical-family blocking (*hard-filter*) (preserves subsistence farmers), **do not** create regional presets on the map, and **do not** include *What-If* simulation sliders.
   - **Longer-term future evolutions:** offline retraining of `RandomForestRegressor` on real Brazilian historical harvest datasets (CONAB/IBGE/Embrapa), **PyAEZ** library, native **ERA5**, **VIIRS**, and **NASA FIRMS**.
3. **Product & UX Suggestions (inspired by the FAO GAEZ v5 portal):**
   - **WMS Overlay in Leaflet (`MapTerrainPage.tsx`):** display visual suitability/soil layers via FAO's public GeoServer WMS (`https://data.apps.fao.org/geoserver/wms`).
   - **Split View (side-by-side comparison):** compare historical vs. CMIP6 future or rainfed (`LRLM`) vs. irrigated (`HILM`).
   - **Point Feature Information:** on clicking a plot, display `attainable_yield_kg_ha` (kg/ha), HWSD v2.01 class, and dominant limiting factor (`SQ-IDX`).

## Contracts (do not break without notifying others)

1. **`field_metrics`** (output of `INASADataProvider.extract_field_metrics`):
   `avg_soil_moisture_smap`, `avg_surface_temp_ecostress`, `avg_precipitation_gpm` (mm/day), `is_bare_field_period`, `data_quality` (`clip` | `nearest_cell` | `no_data`), `time_series` (daily list with `data`, `soil_moisture`, `surface_temp_c`, `precipitation_mm`), `coordinates`. When GAEZ is active in the simulation, `metricas_geoespaciais["gaez"]` carries the strategic-layer output.
2. **`GAEZDataProvider.extract_gaez_metrics`** (and `GET /api/v1/culturas/aptidao-gaez`):
   Returns `{origem: "fao_gaez_v5", data_quality: "gaez_v5_cog" | "no_data", input_level, ssp_scenario, centroid, soil, crops}` (and on the REST endpoint `culturas_avaliadas` / `culturas_sincronizadas`, or HTTP `503` on `no_data`).
3. **`ClimateAnomalyDetector.detect_extremes(dict | list[dict])`** returns
   `{anomaly_detected: bool, tipo_evento: onda_de_calor|seca|chuva_intensa|nenhum, severidade, detalhes}`; `detalhes` includes `metodo` (`limiar` | `isolation_forest`) and `indices_outliers`.
4. **`CropSimulator.simulate_rotation_strategies`** returns 3 items (including current practice, marked with `(Atual)`) of
   `{strategy, viability (0–1), water_risk (low|medium|high), benefits, score_breakdown}`.
5. **`SimulacaoResponse`** includes `origem` and `fallback_usado`.
6. **LLM Notice:** every explanation ends with the disclaimer (enforced in `llm_agent.py`).

## Dev A — Data, ML & AI

| # | Status | Task | Files | Done When |
|---|---|---|---|---|
| A1 | ✅ | Mock GPM/IMERG with clipping and `avg_precipitation_gpm`; dynamic `is_bare_field_period` | `mock_nasa_data.py`, `geospatial.py` | Provider returns precipitation and flag; unit test |
| A2 | ✅ | Dynamic `CropSimulator` (climate + priorities); `predict_rotation_viability` uses `crop_requirements` | `ml_models.py` | Strategies change with plot/priorities |
| A3 | ✅ | `ClimateAnomalyDetector` with `IsolationForest` + thresholds | `ml_models.py` | Outlier series triggers; normal does not |
| A4 | ✅ | LLM Agent: explain all 3 strategies in one call, plain language (agent cache/singleton came in C1) | `llm_agent.py` | One call → 3 explanations, all with disclaimer |
| A5 | ✅ | `RealNASADataProvider` (`earthaccess` + `xr.open_mfdataset`) via `NASA_PROVIDER=mock\|real` | `geospatial.py` | `get_nasa_data_provider` factory and `RealNASADataProvider` with NDVI/Earthdata tested; mock stays default |
| A6 | ✅ | Unit tests for `MockNASADataProvider`, `CropSimulator`, `ClimateAnomalyDetector`, and `RotationExplainerAgent` | `backend/tests/` | `pytest` green |
| A7 | ✅ | Geospatial area calculation (`area_hectares`) and polygon centroid; `CropSimulator` using `historico_cultivos` (penalizes monoculture, rewards cycle breaks) and dynamic fallback | `geospatial.py`, `ml_models.py` | Area/centroid computed from polygon; history alters simulator ranking |
| A8 | ✅ | Expand `RotationExplainerAgent` with `explain_alert` (practical `[M5]` guidance) and `explain_report` (plain-language `[M6]` summary), keeping `DISCLAIMER` and offline mock | `llm_agent.py` | Alerts and reports produce accessible explanation always with disclaimer |
| A9 | ✅ | Simulatable climate profiles (`normal`, `seca`, `chuva_extrema`, `onda_de_calor`) in `mock_nasa_data.py` for stress/demo tests + `A7–A9` unit tests | `mock_nasa_data.py`, `backend/tests/test_data_ml.py` | Profiles generate distinct scenarios and `pytest` green |
| A10 | ✅ | Expose runtime `perfil_climatico` in extraction/simulation (`get_nasa_processor` / `extract_field_metrics`) and use `calcular_geometria_terreno` inside `_calcular_metricas_fallback` to include `area_hectares` in `metricas_geoespaciais` | `geospatial.py`, `api/simulacao.py`, `schemas/simulacao.py`, `backend/tests/test_data_ml.py` | Simulation accepts on-demand climate profile and always returns polygon-computed `area_hectares` |
| A11 | ✅ | Multi-source real ingestion in `RealNASADataProvider` (`data/real/`, GPM harmonization/transposition, `_FillValue` filtering, partial tolerance, and cached NASA POWER API) + `RandomForestRegressor` and temporal features in `CropSimulator` / diagnostics in `ClimateAnomalyDetector` | `geospatial.py`, `ml_models.py` | Real/POWER data and time series feed ML with `ml_model_score` and `temporal_stability` |
| A12 | ✅ | Earthdata infrastructure (`earthaccess`, `h5netcdf`, `EARTHDATA_TOKEN`, `NASA_POWER_FALLBACK`, `NASA_REAL_DAYS_BACK`), `perfil_climatico="real"` support in simulation, and `A11–A12` tests | `requirements.txt`, `docker-compose.yml`, `.env.example`, `mock_nasa_data.py`, `api/simulacao.py`, `backend/tests/test_data_ml.py` | `POST /api/v1/simular-rotacao` supports real data and `pytest` suite green |
| A13 | ✅ | Direct FAO GAEZ v5 COG provider (`RES05-SUX`/`YLX` Suitability and Attainable Yield, `HWSDV201`, `SQ-IDX`, `SQX.SQ0`, `SLOPE-MED`, and `CMIP6` 2021–2040) with per-cell cache and no fabricated fallbacks | `backend/services/gaez_service.py` | Direct extraction from official COGs across all 4 profiles (`LRLM`, `HRLM`, `LILM`, `HILM`) |
| A14 | ✅ | "Suitability and Attainable Yield" integration in `[M2]` catalog (`/culturas/aptidao-gaez`), `CropSimulator` `[M3]`, and `RotationExplainerAgent` + `A13–A14` tests | `api/cultura.py`, `schemas/rotacao.py`, `ml_models.py`, `llm_agent.py`, `api/simulacao.py`, `backend/tests/test_data_ml.py` | Crops/rotations and AI use GAEZ suitability, `kg/ha` yield, HWSD soil, and `CMIP6` |
| A15 | ✅ | Direct **ECOCROP** provider (no fabricated fallback): extract `Scientific Name`, `Family`, `TMIN`/`TMAX`, `TOPMIN`/`TOPMAX`, `RMIN`/`RMAX`, `GMIN`/`GMAX` | `backend/services/ecocrop_service.py`, `api/cultura.py`, `schemas/rotacao.py` | Plant comfort zone and taxonomy queryable via scientific name/code |
| A16 | ✅ | Direct **AGROFIT (Embrapa AgroAPI)** provider cross-referenced by `Scientific Name` + NASA climate triggers (SMAP/ECOSTRESS/POWER) in `CropSimulator` (pest and botanical-family penalty/warning **without blocking** subsistence) | `backend/services/agrofit_service.py`, `ml_models.py`, `api/simulacao.py` | Phytosanitary risk computed in `score_breakdown` without excluding subsistence crops |
| A17 | ✅ | **Climate anomaly Z-score** calculation against historical baseline for the same period (NASA POWER) in `ClimateAnomalyDetector` and `RealNASADataProvider` | `geospatial.py`, `ml_models.py`, `api/alertas.py` | Rain/moisture/heat Z-score integrated into `[M5]` detection and `[M3]` metrics |
| A18 | ✅ | Structured explanation with numerical evidence (`RotationExplainerAgent` + `[M3]` schema) and **SRTM 30 m** / **HLS** coverage integration | `llm_agent.py`, `schemas/simulacao.py`, `geospatial.py` | Structured blocks with real numbers for frontend cards + SRTM elevation |

## Dev B — Catalog, Reports, Plots & Infra/Demo

| # | Status | Task | Files | Done When |
|---|---|---|---|---|
| B1 | ✅ | **[M2]** Full farmer crops/rotations CRUD (PUT/DELETE, validations); mark custom vs seed and protect seed records; preferred rotations enter simulator | `api/cultura.py`, `db/models.py` | Farmer creates/edits/deletes; seed is non-deletable |
| B2 | ✅ | **[M6]** Report service and endpoints: moisture/temperature history, vigor, vulnerability, adaptations (`ajustada_por_alerta`) | `services/relatorio_service.py`, `api/relatorios.py` | Report `GET` by plot and period; uses `field_metrics` |
| B3 | ✅ | Persist historical metrics (table + Alembic migration) to feed M6 | `services/metrics_service.py`, `alembic/` | Queryable per-plot series |
| B4 | ✅ | API tests for M2/M6 and CI running `pytest` | `backend/tests/test_b1_b2_b3.py`, `.github/workflows/ci.yml` | CI green on PR |
| B5 | ✅ | Configure `CORSMiddleware` for frontend (`localhost:5173`), default `Usuario` seed on startup, and complete `PUT`/`DELETE /api/v1/terrenos/{terreno_id}` with automatic area/centroid calculation (A7) | `main.py`, `api/terreno.py`, `schemas/terreno.py` | Frontend connects without CORS; created/edited/deleted plot computes area when omitted |
| B6 | ✅ | Enrich `[M6]` report with AI interpretive summary (`explain_report` from A8 with deterministic fallback) and period start/end comparison | `services/relatorio_service.py`, `schemas/relatorio.py`, `api/relatorios.py` | `GET /api/v1/relatorios/...` includes accessible summary and period comparison |
| B7 | ✅ | Demo seed endpoint/routine (`POST /api/v1/demo/seed` with user, plots, metrics, activities, and alerts), `docs/Specs/README.md` update, and `B5–B7` tests | `api/`, `docs/Specs/README.md`, `backend/tests/` | Demo populated in 1 call; specs and tests updated and green |
| B8 | ✅ | Align `docker-compose.yml` and `.env.example` with `NASA_MOCK_PROFILE`, integrate `api/demo.py` with `A9` profiles, and update `docs/index.md` removing already delivered roadmap items | `docker-compose.yml`, `.env.example`, `api/demo.py`, `docs/index.md` | Environment starts with configurable profile, demo uses real mock profiles, and docs reflect current state |

## Dev C — Simulation, Alerts & Calendar

| # | Status | Task | Files | Done When |
|---|---|---|---|---|
| C1 | ✅ | `origem`/`fallback_usado` in response; provider/simulator/agent instantiated once | `api/simulacao.py` | Response indicates whether fallback occurred |
| C2 | ✅ | [M5] Monitor: **per-plot** metrics via `INASADataProvider` (polygon); alert only on `anomaly_detected` (A3 ready) | `services/alert_tasks.py` | Different plots → different alerts |
| C3 | ✅ | Deduplicate alerts (same plot + type + date), cooldown; env-configured interval | `alert_tasks.py`, `api/alertas.py` | Two consecutive cycles do not duplicate |
| C4 | ✅ | Calendar generated from chosen M3 strategy (`[M1]→[M3]→[M4]`); testable post-alert adjustment rules | `api/calendario.py` | End-to-end flow covered by test |
| C5 | ✅ | Timezone-aware datetimes and Pydantic schemas in `ConfigDict` | `api/calendario.py`, `schemas/` | `pytest` without project DeprecationWarning |
| C6 | ✅ | Expose `score_breakdown` and individual `explicacao` in `EstrategiaRotacaoSugerida` (using `explain_strategies` from A4, keeping `explicacao_ia`/`explicacao_textual`) and dynamic fallback | `schemas/simulacao.py`, `api/simulacao.py` | Each of the 3 strategies carries `score_breakdown` and `explicacao` with disclaimer |
| C7 | ✅ | Accept `historico_cultivos` in `SimulacaoRequest` (integrating onboarding + A7) and allow generating/updating `[M4]` schedule directly from the chosen simulation strategy | `schemas/simulacao.py`, `api/simulacao.py`, `api/calendario.py` | Simulation uses farmer history and generates calendar directly from chosen strategy |
| C8 | ✅ | Integrate `explain_alert` (A8 with fallback) in `[M5]` alerts, add unread alerts summary per plot for dashboard, and `C6–C8` tests | `api/alertas.py`, `services/alert_tasks.py`, `schemas/alerta.py`, `backend/tests/` | Alerts include accessible practical guidance; unread count and green tests |
| C9 | ✅ | Allow selecting `perfil_climatico` (`seca`, `chuva_extrema`, `onda_de_calor`) in `POST /api/v1/alertas/monitorar-clima` to trigger full `[M5] -> [M4]` cycle on demand in demo + test | `schemas/alerta.py`, `api/alertas.py`, `services/alert_tasks.py`, `backend/tests/` | One demo click generates alert with `explain_alert` and adapts calendar activities |

## Frontend (`frontend/` — End-to-End Integration)

| # | Status | Task | Files | Done When |
|---|---|---|---|---|
| F1 | ✅ | Create application entrypoint and routing (`index.html`, `src/main.tsx`, `src/App.tsx`) + HTTP client for `/api/v1` | `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/services/api.ts` | Vite app starts with `npm run dev` and navigates across all flow steps |
| F2 | ✅ | Connect `PlantationsPage.tsx`, `MapTerrainPage.tsx`, `CropHistoryStep.tsx`, and `WaterDistributionStep.tsx` to `[M1]` (`GET`/`POST`/`PUT`/`DELETE /api/v1/terrenos`), `[M3]` (`POST /api/v1/simular-rotacao`), and demo seed (`POST /api/v1/demo/seed`) endpoints | `frontend/src/pages/`, `frontend/src/features/onboarding/`, `frontend/src/services/api.ts` | Real plots listed/created/deleted in Postgres without static mocks and onboarding connected to API |
| F3 | ⬜ | Implement complete screens for Simulation `[M3]` (3 strategies, structured blocks with real numbers: `score_breakdown`, `kg/ha`, HWSD soil, ECOCROP range, Agrofit risk, Z-score, and AI explanation + disclaimer), Calendar `[M4]` + Alerts `[M5]`, and Report `[M6]` | `frontend/src/pages/` | Complete `[M1] -> [M3] -> [M4]/[M5] -> [M6]` flow tested in browser (no regional presets and no what-if sliders) |

## Order and Dependencies

1. ✅ **Round 1 completed:** `A1–A6` · `B1–B4` · `C1–C5`.
2. ✅ **Round 2 completed:** `A7–A9` · `B5–B7` · `C6–C8`.
3. ✅ **Round 3 completed:** `A10–A14` · `B8` · `C9` · `F1–F2`.
4. **Round 4 — In progress:** `A15` (ECOCROP) ✅ → `A16` (Agrofit × NASA) ✅ · `A17` (Z-score) ✅ · `A18` (Structured explanation + SRTM) ✅ · `F3` (final screens + numerical blocks in frontend).

## Working Rules

- One branch per task from updated `dev` (`feat/A7-geo-crop-history`, `feat/B5-cors-terrenos-crud`, `feat/C6-simulacao-breakdown`...), small PR into `dev`, `pytest backend/tests` green before opening.
- Changed a contract above → notify the other two devs before merging.
- Without `GOOGLE_API_KEY`, the LLM uses mocked responses; do not commit `.env` (use `.env.example`).
- Run locally: `python -m venv venv`, `pip install -r backend/requirements.txt`, `pytest backend/tests`.

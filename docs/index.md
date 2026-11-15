# Kultiva — Technical Documentation and Project Context

**Kultiva** is a decision-support system for smallholder farmers, developed for the NASA Space Apps Challenge. The platform combines NASA satellite geospatial data, Machine Learning models, and generative AI agents (Google Gemini) to plan climate-resilient crop rotations.

The project aims to democratize access to advanced technology by translating complex data into practical, interactive, and easy-to-understand recommendations.

---

## 🎯 Overview and Target Audience

**Kultiva** is a decision-support tool for crop rotation planning. The interface allows farmers to simulate rotations based on their priorities, connecting that information to NASA data and providing adjustment suggestions whenever needed. Once planting is defined, a full-cycle crop calendar is generated with scheduled daily activities to keep the plantation healthy, which can be marked as "completed".

Because NASA datasets are updated periodically, the project maintains continuous alerts and dynamically adjusts the calendar whenever needed based on climate changes captured by those updates.

*   **Target audience:** Smallholder commercial farmers and family farms.
*   **Profile:** Users who typically do not have access to advanced technological tools or deep technical expertise to maintain continuous monitoring and adapt crops to adverse conditions. For this reason, the system's (AI) language is always accessible and transparent.

---

## 🧩 System Modules

The system is divided into 6 core modules, categorized by implementation priority:

| Module | Description | Priority | Specific Business Rules |
| :--- | :--- | :--- | :--- |
| **[M1]** | Plot creation and geographic registration | Mandatory | Collects the property polygon/coordinates and farmer priorities (e.g., water conservation). |
| **[M2]** | Crop and rotation suggestions | Mandatory | Must allow adding farmer-preferred crops/rotations to the catalog. |
| **[M3]** | Crop and rotation simulator | Mandatory* | Compares and returns **at least 3 rotation strategies**, including the farmer's current practice. |
| **[M4]** | Daily activity calendar | Optional | Allows marking tasks as "completed". The calendar has a **flexible** schedule that adapts to weather events. |
| **[M5]** | Climate change alerts | Optional | Background tasks monitor anomalies (heatwaves, heavy rain) to trigger adaptations in `[M4]`. |
| **[M6]** | Periodic adaptation reports | Optional | Long-term monitoring of crop vigor and plot vulnerability. |

---

## 🧠 Two-Layer Data Architecture (100% Brazil Adaptation), ML & AI

The original challenge scope combined NASA Earth observations with US-only agricultural databases. To adapt **Kultiva** fully to Brazilian rural conditions, US-restricted datasets were replaced by **global** alternatives organized into **two complementary layers**, paired with Machine Learning and Generative AI models:

### 1. Mapping Global Datasets for Brazil

| Module | Replaced US Dataset | Global Replacement (Brazil) | Role in Kultiva |
| :--- | :--- | :--- | :--- |
| **[M1]** Plot Mapping | NAIP | **Copernicus Sentinel-2 / Landsat (HLS)** *(planned 10–30 m)* + **SRTM** *(planned 30 m)* / **GAEZ `SLOPE-MED`** *(in production 5 arc-min)* | Plot boundaries (`calcular_geometria_terreno`), slope, and erosion risk. |
| **[M2] / [M3]** Crops & Rotations | SSURGO / WSS / CDL | **FAO GAEZ v5** (*Suitability and Attainable Yield* `RES05-SUX`/`YLX`, **HWSD v2.01**, `SQ-IDX`, `SQX.SQ0`) + **SMAP** (`SPL3SMP_E`) | Suitability by management (`LRLM`, `HRLM`, `LILM`, `HILM`), attainable yield (`kg/ha`), soil limitations, and surface moisture. |
| **[M4] / [M5]** Climate, Calendar & Alerts | PRISM | **NASA POWER** + **GPM & IMERG** (`GPM_3IMERGDF`) + **AgERA5 / CMIP6** (`FP2140` `SSP370`) *(and native ERA5 planned)* | Daily rainfall, water trends, dynamic extreme alerts, and 2021–2040 climate resilience. |
| **[M6]** Reports & Monitoring | OpenET | **ECOSTRESS** (`ECO2LSTE`) + **MODIS NDVI** (`MOD13Q1`) *(and VIIRS / NASA FIRMS planned)* | Surface temperature, heat stress, vegetative vigor, and vulnerability history. |

### 2. Separation Between Strategic Layer and Operational Layer

- **Strategic Layer — FAO GAEZ v5 (`backend/services/gaez_service.py`, ~10 km / 5 arc-min resolution):**
  Answers *"which crops fit this region, this soil (HWSD v2.01), the farmer's water/input level, and future climate?"*.
  - `GAEZDataProvider` **directly** queries official Cloud-Optimized GeoTIFF (COG) rasters via HTTP Range Requests in the public bucket `storage.googleapis.com/fao-gismgr-gaez-v5-data/DATA/GAEZ-V5/` (no login/API key required), caching only real responses on disk (`data/gaez_cache/`).
  - **No fabricated deterministic fallbacks:** if the GAEZ API/COG does not respond, the provider explicitly returns `data_quality="no_data"` (and `GET /api/v1/culturas/aptidao-gaez` returns HTTP `503`).
  - Automatically selects one of the 4 management regimes based on plot priorities: `LRLM` (rainfed + low input), `HRLM` (rainfed + high input), `LILM` (irrigated + low input), or `HILM` (irrigated + high input).
- **Operational Layer — NASA (`backend/services/geospatial.py`):**
  Answers *"what is happening on the plot right now, where is water/heat stress occurring, and which `[M5]` alerts should be triggered in the `[M4]` calendar?"*.
  - Uses the *Adapter/Interface* pattern (`INASADataProvider` + factory `get_nasa_data_provider`).
  - In offline/demo development (`NASA_PROVIDER=mock`), `MockNASADataProvider` generates and clips synthetic NetCDFs (`.nc`) via `xarray`/`rioxarray`/`geopandas` with selectable profiles (`normal`, `seca`, `chuva_extrema`, `onda_de_calor` via `NASA_MOCK_PROFILE` or `perfil_climatico`).
  - In real mode (`NASA_PROVIDER=real` or `perfil_climatico="real"`), `RealNASADataProvider` reads local NetCDF/HDF files in `data/real/`, queries NASA Earthdata collections (`SPL3SMP_E`, `ECO2LSTE`, `GPM_3IMERGDF`, `MOD13Q1` via `earthaccess` with `EARTHDATA_TOKEN`), and falls back to the public **NASA POWER** API (`GWETTOP`, `TS`, `PRECTOTCORR`, no login required, cached in `data/nasa_power_cache/`).

### 3. Machine Learning (`ml_models.py`) and Generative AI (`llm_agent.py`)

- **CropSimulator (Implemented):**
  - Combines agronomic heuristics weighted by water priority, a `RandomForestRegressor` (9 environmental, crop, and temporal-stability features), features extracted from the daily series (`temporal_stability`, linear-regression `moisture_trend`, `dry_spell_max`), bare-soil cover bonus (`is_bare_field_period`), and `historico_cultivos` adjustment.
  - When FAO GAEZ v5 data is present, it generates real rotation candidates from *Suitability and Attainable Yield* (`RES05-SUX`/`RES05-YLX`), discards static pairs without GAEZ backing (while preserving `(Atual)` current practice and registered preferred rotations), and calibrates the final score with `gaez_suitability`, `attainable_yield_kg_ha`, `soil_quality_index` (`SQX.SQ0`), and `cmip6_suitability_delta`.
- **ClimateAnomalyDetector (Implemented):**
  - Two layers: absolute agronomic thresholds (`HEAVY_RAIN_MM >= 60`, `HEAT_C >= 35`, `DROUGHT_MOISTURE <= 0.15`) + `IsolationForest(contamination=0.05)` validated by robust z-score (MAD `>= 3.5`), exposing diagnostics (`anomaly_score_min`, `moisture_trend_per_day`, `heat_stress_index`, `dry_days_count`).
- **RotationExplainerAgent (Implemented):**
  - Google Gemini (`gemini-2.5-flash`, configurable via `GEMINI_MODEL`, or offline `FakeListLLM` when `GOOGLE_API_KEY` is unset) via `langchain-google-genai`, with **structured output (`with_structured_output`)** and **in-memory LRU cache** to save tokens, translating `score_breakdown`, `kg/ha`, HWSD v2.01 soil group, limiting factor (`SQ-IDX`), slope, and alerts/reports.
  - **Pre-LLM deterministic cross-check (`synthesize_cross_insights`):** combines HWSD/`SQ-IDX`/slope soil × GPM rainfall, **ECOCROP** thermal/water ranges × ECOSTRESS, **CMIP6** trend, **Z-score** deviations, and **AGROFIT** phytosanitary risk before generating explanations, offline fallbacks, and simulation `beneficios_esperados`/`riscos_identificados`.
  - **Mandatory Safety Rule:** every explanation ensures the presence of the disclaimer (`DISCLAIMER`) stating that the tool supports decision-making, but the final word is always the farmer's.
- **What is NOT yet implemented / Planned next steps (ML & Data):**
  - **ECOCROP (FAO) + AGROFIT (Embrapa/MAPA):** integrate `EcoCrop_DB` (`Scientific Name`, `Family`, `TMIN`/`TMAX`, `TOPMIN`/`TOPMAX`, `RMIN`/`RMAX`, `GMIN`/`GMAX`) cross-referenced by scientific name with the **Agrofit** API and NASA climate triggers (SMAP/ECOSTRESS/NASA POWER) to compute phytosanitary risk — using botanical family solely as an informational signal / cycle-break penalty in `CropSimulator`, **without blocking** subsistence crops (`A15–A16`).
  - **Historical climate anomaly Z-score:** compare the plot's current window against the historical average for the same period via NASA POWER (`A17`).
  - **Structured explanation with numerical evidence + SRTM 30 m:** structure explanation blocks with exact satellite/soil/ECOCROP/Agrofit numbers for frontend cards and incorporate **SRTM 30 m** elevation/slope and **Sentinel-2 / Landsat (HLS)** (`A18`).
  - **Supervised retraining on real Brazilian harvests:** the current `RandomForestRegressor` is trained in memory on a synthetic grid of 400 agronomic scenarios and calibrated at runtime by real GAEZ v5 rasters; an offline pipeline with real historical yield data (IBGE PAM / CONAB / Embrapa) and versioned model artifacts is still pending.
  - **PyAEZ, native ERA5, VIIRS, and NASA FIRMS:** **PyAEZ** library for local calculation with station microclimate and direct ingestion of active fire hotspots/reanalysis.

---

## 🛠️ Tech Stack

The backend applies the MVC/Service-Layer pattern and isolates AI/Data logic (`backend/services/`) from API routes (`backend/api/`).

- **Language:** Python 3.12 (`python:3.11-slim` base image in `Dockerfile`)
- **API & Web Framework:** FastAPI + Uvicorn + HTTPX
- **Database & ORM:** PostgreSQL 15 + SQLAlchemy (`psycopg2-binary`) + Alembic + Pydantic v2
- **Geospatial Data:** Xarray, NetCDF4, h5netcdf, Rasterio (COG/HTTP Range), Rioxarray, GeoPandas, Shapely, Pandas, `earthaccess`
- **Machine Learning & AI:** Scikit-Learn (`RandomForestRegressor`, `IsolationForest`), LangChain (`langchain-google-genai`, `langchain-core`)
- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS v4 + Leaflet (`frontend/`)
- **Infrastructure:** Docker and Docker Compose (`.env` managed from `.env.example`)

---

## 🚀 Running Locally

Copy `.env.example` to `.env` (adjust `NASA_PROVIDER`, `NASA_MOCK_PROFILE`, `GAEZ_ENABLED`, `EARTHDATA_TOKEN` if using Earthdata, `CORS_ALLOWED_ORIGINS`, or `GOOGLE_API_KEY`) and start the API + PostgreSQL with Docker Compose:

```bash
cp .env.example .env
docker-compose up --build
```

After starting the containers (and the frontend via `cd frontend && npm run dev`):

- **Frontend (Vite):** `http://localhost:5173`
- **API Base:** `http://localhost:8000`
- **Health Check:** `GET http://localhost:8000/health`
- **Swagger UI (OpenAPI):** `http://localhost:8000/docs`
- **Demo Seed:** `POST http://localhost:8000/api/v1/demo/seed` (populates default user, plots with `seca` and `chuva_extrema` profiles, historical metrics, adapted activities, and alerts).
- **FAO GAEZ v5 Suitability:** `GET http://localhost:8000/api/v1/culturas/aptidao-gaez?lat=-15.78&lng=-47.92` (direct query to FAO's public COGs without login).

---

## 📂 Quick Navigation

- [Requirements and Business Rules](Requisitos/README.md) — Functional scope of modules `[M1]` through `[M6]`.
- [System Architecture](Arquitetura/README.md) — Database modeling (ERD), two-layer data architecture, and synchronous/asynchronous flows.
- [Technical Specifications (Specs)](Specs/README.md) — REST contracts, query parameters, and JSON payloads for endpoints (including GAEZ v5).
- [Design & UI/UX](Design/README.md) — Mobile-First, Offline-First (PWA) interface guidelines and geospatial UX suggestions (Split View, WMS, Feature Info).
- [Tasks and Project Progress](Tasks/README.md) — Deliverable checklist (`A1–A14`, `B1–B8`, `C1–C9`, `F1–F3`), ML/Data status, and next steps.

---

## ✅ Delivered Features, Pending Work & Suggestions

### Already Implemented (Backend, Data/ML/AI, Infrastructure, and Partial Frontend)
- **Strategic Layer & Real Data (`[M1]` / `[M2]` / `[M3]`):** `GAEZDataProvider` consuming FAO GAEZ v5 public COGs (*Suitability and Attainable Yield* `RES05-SUX`/`YLX`, `HWSDV201`, `SQ-IDX`, `SQX.SQ0`, `SLOPE-MED`, CMIP6 `FP2140` `SSP370`) across all 4 management regimes, with `GET /api/v1/culturas/aptidao-gaez` and optional viable crop syncing.
- **Operational NASA Layer (`[M1]` / `[M5]` / `[M6]`):** `MockNASADataProvider` (`normal`, `seca`, `chuva_extrema`, `onda_de_calor` profiles), `RealNASADataProvider` (`earthaccess` + `data/real/` files + cached public **NASA POWER** API), and automatic area/centroid calculation (`calcular_geometria_terreno`).
- **Explainable ML & AI (`[M2]` / `[M3]` / `[M5]` / `[M6]`):** `CropSimulator` (`RandomForestRegressor` + temporal features + GAEZ suitability/yield + crop history + `score_breakdown`), `ClimateAnomalyDetector` (`IsolationForest` + MAD + thresholds), and `RotationExplainerAgent` (strategies, alerts, and reports always with `DISCLAIMER`).
- **Full Backend & Infra (`A1–A14`, `B1–B8`, `C1–C9`):** Plot CRUD, crops/rotations (`is_seed` protection), simulation, flexible calendar, alerts with background monitor and on-demand simulatable profile (`monitorar-clima`), reports with period comparison, PostgreSQL + Alembic, 70 automated tests (`pytest backend/tests`), CI, and `POST /api/v1/demo/seed`.
- **Frontend (`F1–F2` completed):** Vite + React Router (`App.tsx`), HTTP client (`services/api.ts`), `PlantationsPage.tsx`, `MapTerrainPage.tsx`, `CropHistoryStep.tsx`, and `WaterDistributionStep.tsx` connected to the backend.

### Remaining Work (`A15–A18`, `F3`, and Finalization)
1. **Data, ML & AI Round 4 (`A15–A18`):**
   - **`A15` (ECOCROP):** direct **ECOCROP** database provider extracting `Scientific Name`, `Family`, `TMIN`/`TMAX`, `TOPMIN`/`TOPMAX`, `RMIN`/`RMAX`, and `GMIN`/`GMAX`.
   - **`A16` (AGROFIT × NASA):** **Agrofit** API (Embrapa AgroAPI) provider cross-referenced by `Scientific Name` with ECOCROP and NASA climate triggers (SMAP/POWER moisture + ECOSTRESS/POWER temperature) for phytosanitary risk in `CropSimulator` (non-blocking penalty/warning to preserve subsistence crops).
   - **`A17` (Climate Z-score):** historical climate Z-score calculation via NASA POWER in `ClimateAnomalyDetector` to qualify current-season deviations.
   - **`A18` (Structured Explanation + SRTM):** improve `RotationExplainerAgent` and API responses to deliver structured blocks with real numbers (for frontend cards) and integrate **SRTM 30 m** / **HLS** terrain data where applicable.
2. **Frontend Task `F3` (`frontend/src/pages/`):**
   - Complete Simulation `[M3]` screen displaying the 3 strategies, structured blocks with key numbers (`score_breakdown`, `gaez_suitability`, `attainable_yield_kg_ha`, HWSD v2.01 soil, ECOCROP ranges, Agrofit phytosanitary risk, Z-score, and AI explanation with disclaimer).
   - Consumption of `GET /api/v1/culturas/aptidao-gaez` in the `[M2]` flow to suggest regionally viable crops/seeds and allow `sincronizar_catalogo`.
   - Integrated Calendar `[M4]`, Climate Alerts `[M5]`, and Reports `[M6]` screens.
   - *Retained scope decisions:* **do not** apply rigid blocking by botanical family (to avoid restricting subsistence farming), **do not** use regional presets on the map, and **do not** add *What-If* simulation sliders.
3. **Final Demo Rehearsal & Deploy:**
   - Validate the complete `[M1] -> [M2] -> [M3] -> [M4]/[M5] -> [M6]` flow in the browser using `POST /api/v1/demo/seed`.

### Evolution Suggestions (Product, UX, and Data Science)
- **Map UX inspired by the FAO GAEZ v5 portal (`MapTerrainPage.tsx`):**
  - *WMS/WMTS Overlay:* render suitability and soil layers directly in Leaflet via FAO's official GeoServer (`https://data.apps.fao.org/geoserver/wms`) without downloading full rasters on the client.
  - *Split View (side-by-side comparison):* slider comparing historical climate vs. CMIP6 future scenario (`2021–2040` SSP370) or rainfed (`LRLM`) vs. irrigated (`HILM`) management.
  - *Point Feature Information:* on clicking a plot on the map, display a quick card with estimated attainable yield (`kg/ha`), HWSD v2.01 soil group, and dominant limiting factor.
- **Data & ML Evolution:**
  - Expand `GAEZ_SUITABILITY_CROPS` by ingesting the **ECOCROP** catalog (72+ crops) and evaluate **PyAEZ** for fine local zoning.
  - Incorporate **Sentinel-2 / Landsat (HLS)** + **SRTM 30 m** into `[M1]` for intra-plot diagnostics (~10–30 m) complementing GAEZ v5's regional scale (~10 km), plus **NASA FIRMS** and **ERA5**.
  - Train and version supervised models on real Brazilian harvest data (CONAB/IBGE) and real farmer feedback from the app.

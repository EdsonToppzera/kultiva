# Kultiva — Documentação Técnica e Contexto do Projeto

**Kultiva** é um sistema de apoio à decisão para pequenos produtores rurais, desenvolvido para o NASA Space Apps Challenge. A plataforma une dados geoespaciais de satélite da NASA, modelos de Machine Learning e agentes de IA generativa (Google Gemini) para planejar rotações de culturas resilientes às mudanças climáticas.

O projeto visa democratizar o acesso à tecnologia avançada, traduzindo dados complexos em recomendações práticas, interativas e de fácil compreensão.

---

## 🎯 Visão Geral e Público-Alvo

O **Kultiva** é uma ferramenta de auxílio na tomada de decisões acerca da rotação de culturas. A interface permite simular rotações com base nas prioridades do agricultor, interligando essas informações aos dados da NASA e fornecendo sugestões de modificação, se necessário. Após definido o plantio, é emitido um calendário de todo o período de cultivo, com atividades diárias programadas para manter o bem-estar da plantação, que podem ser marcadas como "concluídas".

Como as bases da NASA são atualizadas periodicamente, o projeto visa manter alertas constantes e modificação do calendário, se necessário, com base em mudanças climáticas capturadas por essas atualizações.

*   **Público-alvo:** Pequenos agricultores comerciais ou agricultura familiar.
*   **Perfil:** Indivíduos que tendem a não possuir muitas ferramentas tecnológicas ou alto conhecimento técnico para manter o monitoramento constante e a adaptação da plantação a adversidades. Por isso, a linguagem do sistema (IA) é sempre acessível e transparente.

---

## 🧩 Módulos do Sistema

O sistema é dividido em 6 módulos principais, categorizados por prioridade de implementação:

| Módulo | Descrição | Prioridade | Regras de Negócio Específicas |
| :--- | :--- | :--- | :--- |
| **[M1]** | Criação e cadastro geográfico do terreno | Obrigatório | Coleta o polígono/coordenadas da propriedade e as prioridades do agricultor (ex: economia de água). |
| **[M2]** | Sugestões de culturas e rotações | Obrigatório | Deve permitir a inclusão de culturas/rotações da preferência do próprio produtor no catálogo. |
| **[M3]** | Simulador de culturas e rotações | Obrigatório* | Compara e retorna **pelo menos 3 estratégias** de rotação, incluindo a prática atual do agricultor. |
| **[M4]** | Calendário com atividades diárias | Opcional | Permite marcar tarefas como "concluídas". O calendário possui rotina **maleável** a eventos climáticos. |
| **[M5]** | Alertas de mudanças climáticas | Opcional | Background tasks monitoram anomalias (ondas de calor, chuvas) para engatilhar adaptações no [M4]. |
| **[M6]** | Relatórios periódicos de adaptação | Opcional | Monitoramento de longo prazo do vigor das culturas e vulnerabilidade do terreno. |

---

## 🧠 Arquitetura de Dados em 2 Camadas (Adaptação 100% Brasil), ML e IA

O escopo original do desafio combinava observações da Terra da NASA com bases agrícolas locais dos EUA. Para adaptar o **Kultiva** integralmente à realidade rural brasileira, as bases restritas aos Estados Unidos foram substituídas por alternativas **globais** organizadas em **duas camadas complementares**, somadas a modelos de Machine Learning e IA Generativa:

### 1. Mapeamento de Datasets Globais para o Brasil

| Módulo | Base EUA descartada | Substituição Global (Brasil) | Papel no Kultiva |
| :--- | :--- | :--- | :--- |
| **[M1]** Mapeamento de Terreno | NAIP | **Copernicus Sentinel-2 / Landsat (HLS)** *(planejado 10–30 m)* + **SRTM** *(planejado 30 m)* / **GAEZ `SLOPE-MED`** *(em produção 5 arc-min)* | Limites do talhão (`calcular_geometria_terreno`), declividade e risco de erosão. |
| **[M2] / [M3]** Culturas & Rotações | SSURGO / WSS / CDL | **FAO GAEZ v5** (*Suitability and Attainable Yield* `RES05-SUX`/`YLX`, **HWSD v2.01**, `SQ-IDX`, `SQX.SQ0`) + **SMAP** (`SPL3SMP_E`) | Aptidão por manejo (`LRLM`, `HRLM`, `LILM`, `HILM`), produtividade atingível (`kg/ha`), limitações de solo e umidade superficial. |
| **[M4] / [M5]** Clima, Calendário & Alertas | PRISM | **NASA POWER** + **GPM & IMERG** (`GPM_3IMERGDF`) + **AgERA5 / CMIP6** (`FP2140` `SSP370`) *(e ERA5 nativo planejado)* | Chuva diária, tendências hídricas, alertas extremos dinâmicos e resiliência climática 2021–2040. |
| **[M6]** Relatórios & Monitoramento | OpenET | **ECOSTRESS** (`ECO2LSTE`) + **MODIS NDVI** (`MOD13Q1`) *(e VIIRS / NASA FIRMS planejados)* | Temperatura de superfície, estresse térmico, vigor vegetativo e histórico de vulnerabilidade. |

### 2. Separação entre Camada Estratégica e Camada Operacional

- **Camada Estratégica — FAO GAEZ v5 (`backend/services/gaez_service.py`, resolução ~10 km / 5 arc-min):**
  Responde *"quais culturas combinam com esta região, este solo (HWSD v2.01), o nível de água/insumo do produtor e o clima futuro?"*.
  - `GAEZDataProvider` consulta **diretamente** via HTTP Range Requests os rasters Cloud-Optimized GeoTIFF (COG) oficiais no bucket público `storage.googleapis.com/fao-gismgr-gaez-v5-data/DATA/GAEZ-V5/` (sem login/chave de API), armazenando apenas respostas reais em cache de disco (`data/gaez_cache/`).
  - **Sem fallbacks determinísticos inventados:** se a API/COG do GAEZ não responder, o provedor retorna explicitamente `data_quality="no_data"` (e `GET /api/v1/culturas/aptidao-gaez` retorna HTTP `503`).
  - Seleciona automaticamente um dos 4 regimes de manejo conforme as prioridades do terreno: `LRLM` (sequeiro + baixo insumo), `HRLM` (sequeiro + alto insumo), `LILM` (irrigado + baixo insumo) ou `HILM` (irrigado + alto insumo).
- **Camada Operacional — NASA (`backend/services/geospatial.py`):**
  Responde *"o que está acontecendo no terreno agora, onde há estresse hídrico/térmico e quais alertas `[M5]` disparar no calendário `[M4]`?"*.
  - Utiliza o padrão *Adapter/Interface* (`INASADataProvider` + fábrica `get_nasa_data_provider`).
  - Em desenvolvimento offline/demo (`NASA_PROVIDER=mock`), `MockNASADataProvider` gera e recorta NetCDFs sintéticos (`.nc`) via `xarray`/`rioxarray`/`geopandas` com perfis selecionáveis (`normal`, `seca`, `chuva_extrema`, `onda_de_calor` via `NASA_MOCK_PROFILE` ou `perfil_climatico`).
  - Em modo real (`NASA_PROVIDER=real` ou `perfil_climatico="real"`), `RealNASADataProvider` lê arquivos NetCDF/HDF locais em `data/real/`, consulta coleções NASA Earthdata (`SPL3SMP_E`, `ECO2LSTE`, `GPM_3IMERGDF`, `MOD13Q1` via `earthaccess` com `EARTHDATA_TOKEN`) e recorre à API pública **NASA POWER** (`GWETTOP`, `TS`, `PRECTOTCORR`, sem login, com cache em `data/nasa_power_cache/`).

### 3. Machine Learning (`ml_models.py`) e IA Generativa (`llm_agent.py`)

- **CropSimulator (Implementado):**
  - Combina heurística agronômica ponderada por prioridade hídrica, regressor `RandomForestRegressor` (9 features ambientais, da cultura e estabilidade temporal), features extraídas da série diária (`temporal_stability`, `moisture_trend` por regressão linear, `dry_spell_max`), bônus de cobertura sobre solo exposto (`is_bare_field_period`) e ajuste por `historico_cultivos`.
  - Quando os dados do FAO GAEZ v5 estão presentes, gera candidatas reais de rotação a partir de *Suitability and Attainable Yield* (`RES05-SUX`/`RES05-YLX`), descarta pares estáticos sem respaldo do GAEZ (preservando a prática `(Atual)` e rotações preferenciais cadastradas) e calibra o score final com `gaez_suitability`, `attainable_yield_kg_ha`, `soil_quality_index` (`SQX.SQ0`) e `cmip6_suitability_delta`.
- **ClimateAnomalyDetector (Implementado):**
  - Duas camadas: limiares agronômicos absolutos (`HEAVY_RAIN_MM >= 60`, `HEAT_C >= 35`, `DROUGHT_MOISTURE <= 0.15`) + `IsolationForest(contamination=0.05)` validado por z-score robusto (MAD `>= 3.5`), expondo diagnósticos (`anomaly_score_min`, `moisture_trend_per_day`, `heat_stress_index`, `dry_days_count`).
- **RotationExplainerAgent (Implementado):**
  - Google Gemini (`gemini-2.5-flash`, configurável via `GEMINI_MODEL`, ou `FakeListLLM` offline quando `GOOGLE_API_KEY` não estiver definida) via `langchain-google-genai`, traduzindo `score_breakdown`, `kg/ha`, grupo de solo HWSD v2.01, fator limitante (`SQ-IDX`), declividade e alertas/relatórios.
  - **Regra de Segurança Mandatória:** toda explicação garante a presença do aviso (`DISCLAIMER`) de que a ferramenta apoia a decisão, mas a palavra final é sempre do produtor.
- **O que ainda NÃO foi implementado em ML / Dados (Backlog Técnico):**
  - **Retreino supervisionado com safras reais brasileiras:** o `RandomForestRegressor` atual é treinado em memória sobre uma grade sintética de 400 cenários agronômicos e calibrado em runtime pelos rasters reais do GAEZ v5; falta pipeline offline com dados históricos reais de produtividade (IBGE PAM / CONAB / Embrapa) e artefato versionado.
  - **Expansão ECOCROP & PyAEZ:** atualmente há 13 culturas brasileiras mapeadas em `GAEZ_SUITABILITY_CROPS`; ainda não foram integradas a ingestão automática do catálogo completo **ECOCROP** (72+ culturas GAEZ) nem a biblioteca **PyAEZ** para cálculo local com microclima de estação.
  - **Alta resolução espacial (10–30 m) e novos sensores:** falta processar rasters **Sentinel-2 / Landsat (HLS)** e **SRTM 30 m** no módulo `[M1]`, bem como ingestão direta de **ERA5**, **VIIRS** e focos de calor **NASA FIRMS**.

---

## 🛠️ Stack Tecnológica

O backend do sistema aplica o padrão MVC/Service-Layer e isola a lógica de IA/Dados (`backend/services/`) das rotas da API (`backend/api/`).

- **Linguagem:** Python 3.12 (imagem base `python:3.11-slim` no `Dockerfile`)
- **API & Web Framework:** FastAPI + Uvicorn + HTTPX
- **Banco de Dados & ORM:** PostgreSQL 15 + SQLAlchemy (`psycopg2-binary`) + Alembic + Pydantic v2
- **Dados Geoespaciais:** Xarray, NetCDF4, h5netcdf, Rasterio (COG/HTTP Range), Rioxarray, GeoPandas, Shapely, Pandas, `earthaccess`
- **Machine Learning & IA:** Scikit-Learn (`RandomForestRegressor`, `IsolationForest`), LangChain (`langchain-google-genai`, `langchain-core`)
- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS v4 + Leaflet (`frontend/`)
- **Infraestrutura:** Docker e Docker Compose (`.env` gerenciado a partir de `.env.example`)

---

## 🚀 Como Rodar Localmente

Copie o arquivo `.env.example` para `.env` (ajuste `NASA_PROVIDER`, `NASA_MOCK_PROFILE`, `GAEZ_ENABLED`, `EARTHDATA_TOKEN` se usar Earthdata, `CORS_ALLOWED_ORIGINS` ou `GOOGLE_API_KEY`) e suba a API + PostgreSQL com Docker Compose:

```bash
cp .env.example .env
docker-compose up --build
```

Após iniciar os containers (e o frontend via `cd frontend && npm run dev`):

- **Frontend (Vite):** `http://localhost:5173`
- **API Base:** `http://localhost:8000`
- **Health Check:** `GET http://localhost:8000/health`
- **Swagger UI (OpenAPI):** `http://localhost:8000/docs`
- **Seed de Demonstração:** `POST http://localhost:8000/api/v1/demo/seed` (popula usuário padrão, terrenos com perfis `seca` e `chuva_extrema`, métricas históricas, atividades adaptadas e alertas).
- **Aptidão FAO GAEZ v5:** `GET http://localhost:8000/api/v1/culturas/aptidao-gaez?lat=-15.78&lng=-47.92` (consulta direta aos COGs públicos da FAO sem necessidade de login).

---

## 📂 Navegação Rápida

- [Requisitos e Regras de Negócio](Requisitos/README.md) — Escopo funcional dos módulos `[M1]` a `[M6]`.
- [Arquitetura do Sistema](Arquitetura/README.md) — Modelagem do banco de dados (DER), arquitetura de dados em 2 camadas e fluxos síncrono/assíncrono.
- [Especificações Técnicas (Specs)](Specs/README.md) — Contratos REST, parâmetros de consulta e payloads JSON dos endpoints (incluindo GAEZ v5).
- [Design e UI/UX](Design/README.md) — Diretrizes de interface Mobile-First, Offline-First (PWA) e sugestões de UX geoespacial (Split View, WMS, Feature Info).
- [Tasks e Evolução do Projeto](Tasks/README.md) — Checklist das entregas (`A1–A14`, `B1–B8`, `C1–C9`, `F1–F3`), estado de ML/Dados e próximos passos.

---

## ✅ Funcionalidades Entregues, O Que Falta Fazer e Sugestões

### Já implementado (Backend, Dados/ML/IA, Infraestrutura e Frontend Parcial)
- **Camada Estratégica & Dados Reais (`[M1]` / `[M2]` / `[M3]`):** `GAEZDataProvider` consumindo COGs públicos do FAO GAEZ v5 (*Suitability and Attainable Yield* `RES05-SUX`/`YLX`, `HWSDV201`, `SQ-IDX`, `SQX.SQ0`, `SLOPE-MED`, CMIP6 `FP2140` `SSP370`) nos 4 regimes de manejo, com `GET /api/v1/culturas/aptidao-gaez` e sincronização opcional de culturas viáveis.
- **Camada Operacional NASA (`[M1]` / `[M5]` / `[M6]`):** `MockNASADataProvider` (perfis `normal`, `seca`, `chuva_extrema`, `onda_de_calor`), `RealNASADataProvider` (`earthaccess` + arquivos `data/real/` + API pública **NASA POWER** com cache) e cálculo automático de área/centroide (`calcular_geometria_terreno`).
- **ML & IA Explicável (`[M2]` / `[M3]` / `[M5]` / `[M6]`):** `CropSimulator` (`RandomForestRegressor` + features temporais + GAEZ suitability/yield + histórico de cultivos + `score_breakdown`), `ClimateAnomalyDetector` (`IsolationForest` + MAD + limiares) e `RotationExplainerAgent` (estratégias, alertas e relatórios sempre com `DISCLAIMER`).
- **Backend Completo & Infra (`A1–A14`, `B1–B8`, `C1–C9`):** CRUD de terrenos, culturas/rotações (proteção `is_seed`), simulação, calendário maleável, alertas com monitor em background e perfil simulável sob demanda (`monitorar-clima`), relatórios com comparativo, PostgreSQL + Alembic, 70 testes automatizados (`pytest backend/tests`), CI e `POST /api/v1/demo/seed`.
- **Frontend (`F1–F2` concluídos):** Vite + React Router (`App.tsx`), cliente HTTP (`services/api.ts`), `PlantationsPage.tsx`, `MapTerrainPage.tsx`, `CropHistoryStep.tsx` e `WaterDistributionStep.tsx` conectados ao backend.

### O que ainda falta fazer (`F3` e Finalização)
1. **Task `F3` no Frontend (`frontend/src/pages/`):**
   - Tela completa de Simulação `[M3]` exibindo as 3 estratégias, `score_breakdown` (incluindo `gaez_suitability`, `attainable_yield_kg_ha`, `soil_quality_index`, `cmip6_suitability_delta`), dados de solo HWSD v2.01 e explicação IA com disclaimer.
   - Consumo de `GET /api/v1/culturas/aptidao-gaez` no fluxo `[M2]` para sugerir culturas/sementes viáveis na região e permitir `sincronizar_catalogo`.
   - Telas integradas de Calendário `[M4]` (marcação de conclusão e geração via estratégia), Alertas Climáticos `[M5]` (painel de não lidos e disparo demo em 1 clique via `/alertas/monitorar-clima`) e Relatórios `[M6]`.
2. **Ensaio Final da Demo & Deploy:**
   - Validar o fluxo completo `[M1] -> [M2] -> [M3] -> [M4]/[M5] -> [M6]` no navegador usando `POST /api/v1/demo/seed`.

### Sugestões de Evolução (Produto, UX e Ciência de Dados)
- **UX de Mapa inspirada no portal FAO GAEZ v5 (`MapTerrainPage.tsx`):**
  - *Overlay WMS/WMTS:* plotar camadas de aptidão e solo diretamente no Leaflet via GeoServer oficial da FAO (`https://data.apps.fao.org/geoserver/wms`) sem baixar rasters completos no cliente.
  - *Split View (comparação lado a lado):* slider comparando clima histórico vs. cenário futuro CMIP6 (`2021–2040` SSP370) ou manejo sequeiro (`LRLM`) vs. irrigado (`HILM`).
  - *Feature Information pontual:* ao clicar no terreno no mapa, exibir card rápido com a produtividade atingível estimada (`kg/ha`), grupo de solo HWSD v2.01 e fator limitante dominante.
- **Evolução de Dados & ML:**
  - Expandir `GAEZ_SUITABILITY_CROPS` via ingestão do catálogo **ECOCROP** (72+ culturas) e avaliar **PyAEZ** para zoneamento local fino.
  - Incorporar **Sentinel-2 / Landsat (HLS)** + **SRTM 30 m** no `[M1]` para diagnóstico intra-talhão (~10–30 m) complementar à escala regional (~10 km) do GAEZ v5, além de **NASA FIRMS** e **ERA5**.
  - Treinar e versionar modelos supervisionados com dados reais de safra brasileira (CONAB/IBGE) e feedback real dos produtores no app.

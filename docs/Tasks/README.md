# Tasks do Hackathon — Dados/ML/IA, Backend e Integração Demo

**Responsáveis:** **Dev A** = dados, ML e IA · **Dev B** = catálogo, relatórios, terrenos e infra/demo · **Dev C** = simulação, alertas e calendário.

**Legenda:** ✅ feito (mergeado na `dev` / pronto para PR) · 🔄 em andamento · ⬜ pendente

## Estado atual (Rodadas 1, 2 e 3 concluídas · Rodada 4 / Evolução Biológica & Frontend `F3` planejada)

- Suíte `backend/tests`: **verde** (75 testes cobrindo Rodadas 1, 2, 3, 4 parcial, Dados Reais NASA, FAO GAEZ v5, ECOCROP e AGROFIT: `A1–A16`, `B1–B8`, `C1–C9`).
- **Feito (Rodada 1):** `A1–A6` (Dev A) · `B1–B4` (Dev B) · `C1–C5` (Dev C) · base de infra.
- **Feito (Rodada 2):** `A7–A9` (Dev A) · `B5–B7` (Dev B) · `C6–C8` (Dev C).
- **Feito (Rodada 3):** `A10–A14` ✅ · `B8` ✅ · `C9` ✅ · `F1–F2` ✅.
- **Rodada 4 (Em execução):** `A15` (ECOCROP) ✅ · `A16` (AGROFIT × NASA × `CropSimulator`) ✅ · **Pendente:** `A17` (Z-score climático histórico) · `A18` (Explicação estruturada com evidências numéricas + SRTM/HLS) · `F3` (telas completas no `frontend/` com blocos numéricos).

### Resumo do que foi entregue

- **Dev A (`A1–A14`)**
  - **A1–A6 (Rodada 1):** NetCDFs sintéticos determinísticos (`mock_nasa_data.py`), `MockNASADataProvider` + `RealNASADataProvider` (`geospatial.py`, `NASA_PROVIDER=mock|real`), `CropSimulator` dinâmico e `ClimateAnomalyDetector` (`ml_models.py`), `RotationExplainerAgent.explain_strategies` com `DISCLAIMER` (`llm_agent.py`) e suíte unitária (`backend/tests/test_data_ml.py`).
  - **A7 — Geometria, histórico de cultivos e fallback dinâmico** (`geospatial.py`, `ml_models.py`): `calcular_geometria_terreno` (área em hectares e centroide do polígono); `CropSimulator` considerando `historico_cultivos` (penaliza monocultura e bonifica quebra de ciclo com leguminosas) e método `fallback_strategies`.
  - **A8 — Explicações de alertas `[M5]` e relatórios `[M6]`** (`llm_agent.py`): `explain_alert` com orientações práticas de manejo e `explain_report` em linguagem simples, mantendo `DISCLAIMER` e fallback determinístico offline.
  - **A9 — Perfis climáticos simuláveis** (`mock_nasa_data.py`, `geospatial.py`, `backend/tests/test_data_ml.py`): perfis `normal`, `seca`, `chuva_extrema` e `onda_de_calor` (via parâmetro `profile` ou `NASA_MOCK_PROFILE`) gerando cenários distintos que acionam `ClimateAnomalyDetector` e alteram o ranking do `CropSimulator`.
  - **A10 — Perfil climático em runtime e área na simulação** (`geospatial.py`, `api/simulacao.py`): aceita `perfil_climatico` sob demanda e calcula `area_hectares` em `metricas_geoespaciais`.
  - **A11–A12 — Datasets reais multi-fonte + NASA POWER + ML avançado (`RandomForestRegressor` + features temporais)** (`geospatial.py`, `ml_models.py`, `mock_nasa_data.py`, `api/simulacao.py`, `docker-compose.yml`, `.env.example`, `backend/requirements.txt`): descoberta local em `data/real/`, harmonização de grades transpostas e `_FillValue`, integração/cache da API pública NASA POWER sem login, regressor `RandomForestRegressor` + estabilidade temporal no `CropSimulator`, métricas diagnósticas no `ClimateAnomalyDetector` e suporte a `perfil_climatico="real"`.
  - **A13 — Provedor direto FAO GAEZ v5 (`Suitability and Attainable Yield`, `HWSD v2.01`, `SQ-IDX`, `SLOPE-MED` e `CMIP6`)** (`backend/services/gaez_service.py`): leitura paralela direta via HTTP Range Requests nos COGs oficiais do bucket público da FAO (`RES05-SUX`, `RES05-YLX` para `HP0120` e `FP2140` SSP370, `HWSDV201`, `SQX.SQ0`, `SQ-IDX`, `SLOPE-MED`), mapeamento dos 4 regimes de manejo (`LRLM`, `HRLM`, `LILM`, `HILM`), cache por célula de 5 arc-min e retorno `no_data` sem fallbacks determinísticos inventados.
  - **A14 — Catálogo `[M2]`, Simulador `[M3]` e Agente IA calibrados pelo FAO GAEZ v5** (`api/cultura.py`, `schemas/rotacao.py`, `ml_models.py`, `llm_agent.py`, `api/simulacao.py`): endpoint `GET /api/v1/culturas/aptidao-gaez` com sincronização opcional de culturas/sementes viáveis no banco, geração e pontuação de rotações no `CropSimulator` usando `gaez_suitability`, `attainable_yield_kg_ha` (kg/ha), `soil_quality_index` e `cmip6_suitability_delta`, e contextualização de solo HWSD/produtividade no `RotationExplainerAgent`.
  - **A15 — Provedor direto FAO ECOCROP** (`backend/services/ecocrop_service.py`, `api/cultura.py`, `schemas/rotacao.py`): leitura com cache em disco do `EcoCrop_DB.csv` (sem fallback inventado), extração de `Scientific Name`, `Family`, `TMIN`/`TMAX`, `TOPMIN`/`TOPMAX`, `RMIN`/`RMAX`, `GMIN`/`GMAX` e endpoint `GET /api/v1/culturas/ecocrop`.
  - **A16 — Provedor direto AGROFIT (Embrapa AgroAPI) × NASA × `CropSimulator`** (`backend/services/agrofit_service.py`, `ml_models.py`, `api/simulacao.py`): consulta OAuth2/cache por `Scientific Name` na API Agrofit v1 (sem fallback inventado) cruzada com família botânica ECOCROP, `historico_cultivos`, `praga_alvo` e gatilhos climáticos NASA (SMAP/ECOSTRESS/GPM) para expor `phytosanitary_risk`, `phytosanitary_penalty`, `botanical_families`, `agrofit_pests_count` e `phytosanitary_warnings` no `score_breakdown`, **sem bloquear** culturas de subsistência.
- **Dev B (`B1–B7`)**
  - **B1–B4 (Rodada 1):** CRUD completo do catálogo `[M2]` (`api/cultura.py`), proteção de registros seed, serviço/endpoints de relatório `[M6]` (`services/relatorio_service.py`, `api/relatorios.py`), persistência histórica em Postgres/Alembic (`services/metrics_service.py`) e testes/CI (`backend/tests/test_b1_b2_b3.py`, `.github/workflows/ci.yml`).
  - **B5 — CORS, seed inicial e CRUD completo de terrenos `[M1]`** (`main.py`, `api/terreno.py`, `schemas/terreno.py`): `CORSMiddleware` habilitado para `localhost:5173`, seed automático de `Usuario` padrão e `PUT`/`DELETE /api/v1/terrenos/{terreno_id}` com cálculo automático de área/centroide (A7).
  - **B6 — Relatório `[M6]` com IA e comparativo** (`services/relatorio_service.py`, `schemas/relatorio.py`, `api/relatorios.py`): comparativo início/fim do período e resumo interpretativo via `explain_report` (A8).
  - **B7 — Seed de demonstração e Specs** (`api/demo.py`, `docs/Specs/README.md`, `backend/tests/test_b5_b6_b7.py`): `POST /api/v1/demo/seed` populando usuário, terrenos, métricas, atividades e alertas em uma chamada.
- **Dev C (`C1–C8`)**
  - **C1–C5 (Rodada 1):** `origem`/`fallback_usado` e cache de serviços (`api/simulacao.py`), monitor `[M5]` por terreno com deduplicação e cooldown (`services/alert_tasks.py`, `api/alertas.py`), geração de calendário `[M4]` e ajuste pós-alerta (`api/calendario.py`, `backend/tests/test_c4_fluxo.py`), datetimes com timezone e schemas Pydantic v2.
  - **C6 — `score_breakdown`, `explicacao` individual e fallback dinâmico** (`schemas/simulacao.py`, `api/simulacao.py`, `backend/tests/test_c6_simulacao.py`): cada estratégia de `rotacoes_sugeridas` expõe `score_breakdown` e `explicacao` acessível com disclaimer.
  - **C7 — Histórico no simulador e cronograma direto da estratégia** (`schemas/simulacao.py`, `api/simulacao.py`, `api/calendario.py`, `backend/tests/test_c7_c8.py`): `SimulacaoRequest` integra `historico_cultivos` e o calendário `[M4]` gera/atualiza cronograma direto pela estratégia escolhida.
  - **C8 — Explicações práticas nos alertas `[M5]` e resumo de não lidos** (`api/alertas.py`, `services/alert_tasks.py`, `schemas/alerta.py`, `backend/tests/test_c7_c8.py`): integração de `explain_alert` (A8) e resumo de alertas não lidos por terreno.

### Pontos de atenção para o fechamento da Rodada 3 (Frontend `F3` e Evolução)

- Todo o backend (`A1–A14`, `B1–B8`, `C1–C9`) e os fluxos iniciais de frontend (`F1–F2`: roteamento, cliente HTTP, `PlantationsPage.tsx`, `MapTerrainPage.tsx`, `CropHistoryStep.tsx` e `WaterDistributionStep.tsx`) já estão implementados e testados (70 testes verdes em `backend/tests`).
- **Pendência ativa principal (`F3`):** construir/conectar as telas finais no `frontend/src/pages/` para Simulação `[M3]` (incluindo `score_breakdown`, `attainable_yield_kg_ha`, solo HWSD e explicação IA), catálogo `[M2]` conectado a `GET /api/v1/culturas/aptidao-gaez`, Calendário `[M4]`, Alertas `[M5]` e Relatórios `[M6]`, seguidos do ensaio ponta a ponta da demo.

## Arquitetura de Dados em 2 Camadas, Estado do ML e Sugestões de Evolução

1. **Adaptação Brasil — Arquitetura em 2 Camadas (sem fallbacks inventados no GAEZ):**
   - **Camada Estratégica (~10 km / 5 arc-min — `backend/services/gaez_service.py`):** FAO GAEZ v5 (*Suitability and Attainable Yield* `RES05-SUX`/`RES05-YLX` nos 4 regimes `LRLM`, `HRLM`, `LILM`, `HILM`) + **HWSD v2.01** + `SQ-IDX` / `SQX.SQ0` + `SLOPE-MED` + **CMIP6** (`FP2140` `SSP370`). Consulta direta via HTTP Range nos COGs públicos do GCS com cache por célula (`data/gaez_cache/`); se indisponível, retorna `data_quality="no_data"` (HTTP `503` em `/aptidao-gaez`) sem inventar fallback regional.
   - **Camada Operacional (`backend/services/geospatial.py`):** NASA **SMAP** (`SPL3SMP_E`), **ECOSTRESS** (`ECO2LSTE`), **GPM/IMERG** (`GPM_3IMERGDF`), **MODIS NDVI** (`MOD13Q1`) via `earthaccess`/NetCDF local e API pública **NASA POWER** (`GWETTOP`, `TS`, `PRECTOTCORR`) com cache em disco e perfis simuláveis (`mock`) em desenvolvimento/demo.
2. **O que foi vs. não foi implementado de Machine Learning e IA:**
   - **Implementado:** `CropSimulator` (`RandomForestRegressor` de 9 features + features temporais da série + `gaez_suitability`, `attainable_yield_kg_ha`, `soil_quality_index`, `cmip6_suitability_delta` + ajuste por `historico_cultivos`), `ClimateAnomalyDetector` (limiares agronômicos + `IsolationForest` + z-score robusto MAD + métricas diagnósticas) e `RotationExplainerAgent` (Gemini `gemini-2.5-flash` / `FakeListLLM` com solo HWSD, `kg/ha` e `DISCLAIMER` obrigatório).
   - **Próximas tasks planejadas (`A15–A18`):**
     - **ECOCROP (`A15`):** extrair `Scientific Name`, `Family`, `TMIN`/`TMAX`, `TOPMIN`/`TOPMAX`, `RMIN`/`RMAX` e `GMIN`/`GMAX` da base pública ECOCROP.
     - **AGROFIT × NASA (`A16`):** cruzar o `Scientific Name` com a API Agrofit (Embrapa AgroAPI) + gatilhos climáticos da NASA (umidade SMAP/POWER + temperatura ECOSTRESS/POWER) para calcular risco fitossanitário no `CropSimulator`, **penalizando/alertando sem bloquear culturas de subsistência** por família botânica.
     - **Z-score climático histórico (`A17`):** comparar a janela atual contra o histórico do mesmo período via NASA POWER no `ClimateAnomalyDetector`.
     - **Explicação estruturada + SRTM 30 m (`A18`):** retornar blocos estruturados com os dados numéricos reais para cards no frontend (`F3`) e incorporar elevação/declividade **SRTM 30 m** / **HLS** quando disponível.
   - **Decisões de escopo (explicitamente fora):** **não** implementar bloqueio rígido (*hard-filter*) por família botânica (preserva agricultores de subsistência), **não** criar presets regionais no mapa e **não** incluir sliders de simulação *What-If*.
   - **Evoluções futuras de mais longo prazo:** retreino offline do `RandomForestRegressor` sobre bases históricas reais brasileiras (CONAB/IBGE/Embrapa), biblioteca **PyAEZ**, **ERA5** nativo, **VIIRS** e **NASA FIRMS**.
3. **Sugestões de Produto & UX (inspiradas no portal FAO GAEZ v5):**
   - **Overlay WMS no Leaflet (`MapTerrainPage.tsx`):** exibir camadas visuais de aptidão/solo via GeoServer WMS público da FAO (`https://data.apps.fao.org/geoserver/wms`).
   - **Split View (comparação lado a lado):** comparar histórico vs. CMIP6 futuro ou sequeiro (`LRLM`) vs. irrigado (`HILM`).
   - **Feature Information pontual:** ao clicar no terreno, exibir `attainable_yield_kg_ha` (kg/ha), classe HWSD v2.01 e fator limitante dominante (`SQ-IDX`).

## Contratos (não quebrar sem avisar os outros)

1. **`field_metrics`** (saída de `INASADataProvider.extract_field_metrics`):
   `avg_soil_moisture_smap`, `avg_surface_temp_ecostress`, `avg_precipitation_gpm` (mm/dia), `is_bare_field_period`, `data_quality` (`clip` | `nearest_cell` | `no_data`), `time_series` (lista por dia com `data`, `soil_moisture`, `surface_temp_c`, `precipitation_mm`), `coordinates`. Quando GAEZ ativo na simulação, `metricas_geoespaciais["gaez"]` traz a saída da camada estratégica.
2. **`GAEZDataProvider.extract_gaez_metrics`** (e `GET /api/v1/culturas/aptidao-gaez`):
   Retorna `{origem: "fao_gaez_v5", data_quality: "gaez_v5_cog" | "no_data", input_level, ssp_scenario, centroid, soil, crops}` (e no endpoint REST `culturas_avaliadas` / `culturas_sincronizadas`, ou HTTP `503` em `no_data`).
3. **`ClimateAnomalyDetector.detect_extremes(dict | list[dict])`** retorna
   `{anomaly_detected: bool, tipo_evento: onda_de_calor|seca|chuva_intensa|nenhum, severidade, detalhes}`; `detalhes` inclui `metodo` (`limiar` | `isolation_forest`) e `indices_outliers`.
4. **`CropSimulator.simulate_rotation_strategies`** retorna 3 itens (incluindo a prática atual, marcada com `(Atual)`) de
   `{strategy, viability (0–1), water_risk (low|medium|high), benefits, score_breakdown}`.
5. **`SimulacaoResponse`** inclui `origem` e `fallback_usado`.
6. **Aviso do LLM:** toda explicação termina com o disclaimer (garantido em `llm_agent.py`).

## Dev A — Dados, ML e IA

| # | Status | Task | Arquivos | Pronto quando |
|---|---|---|---|---|
| A1 | ✅ | Mock GPM/IMERG com recorte e `avg_precipitation_gpm`; `is_bare_field_period` dinâmico | `mock_nasa_data.py`, `geospatial.py` | Provider devolve precipitação e flag; teste unitário |
| A2 | ✅ | `CropSimulator` dinâmico (clima + prioridades); `predict_rotation_viability` usa `crop_requirements` | `ml_models.py` | Estratégias mudam com terreno/prioridades |
| A3 | ✅ | `ClimateAnomalyDetector` com `IsolationForest` + limiares | `ml_models.py` | Série com outlier dispara; normal não |
| A4 | ✅ | Agente LLM: explicar as 3 estratégias numa chamada, linguagem simples (o cache/singleton do agente já veio na C1) | `llm_agent.py` | Uma chamada → 3 explicações, todas com disclaimer |
| A5 | ✅ | `RealNASADataProvider` (`earthaccess` + `xr.open_mfdataset`) via `NASA_PROVIDER=mock\|real` | `geospatial.py` | Fábrica `get_nasa_data_provider` e `RealNASADataProvider` com NDVI/Earthdata testados; mock segue como padrão |
| A6 | ✅ | Testes unitários de `MockNASADataProvider`, `CropSimulator`, `ClimateAnomalyDetector` e `RotationExplainerAgent` | `backend/tests/` | `pytest` verde |
| A7 | ✅ | Cálculo geoespacial de área (`area_hectares`) e centroide do polígono; `CropSimulator` considerando `historico_cultivos` (penaliza monocultura, bonifica quebra de ciclo) e fallback dinâmico | `geospatial.py`, `ml_models.py` | Área/centroide calculados do polígono; histórico altera ranking do simulador |
| A8 | ✅ | Expandir `RotationExplainerAgent` com `explain_alert` (orientações práticas de manejo para `[M5]`) e `explain_report` (resumo em linguagem simples para `[M6]`), mantendo `DISCLAIMER` e mock offline | `llm_agent.py` | Alertas e relatórios geram explicação acessível sempre com disclaimer |
| A9 | ✅ | Perfis climáticos simuláveis (`normal`, `seca`, `chuva_extrema`, `onda_de_calor`) em `mock_nasa_data.py` para testes de estresse/demo + testes unitários de `A7–A9` | `mock_nasa_data.py`, `backend/tests/test_data_ml.py` | Perfis geram cenários distintos e `pytest` verde |
| A10 | ✅ | Expor `perfil_climatico` em runtime na extração/simulação (`get_nasa_processor` / `extract_field_metrics`) e usar `calcular_geometria_terreno` dentro de `_calcular_metricas_fallback` para incluir `area_hectares` em `metricas_geoespaciais` | `geospatial.py`, `api/simulacao.py`, `schemas/simulacao.py`, `backend/tests/test_data_ml.py` | Simulação aceita perfil climático sob demanda e sempre retorna `area_hectares` calculada do polígono |
| A11 | ✅ | Ingestão real multi-fonte no `RealNASADataProvider` (`data/real/`, harmonização/transposição GPM, filtro `_FillValue`, tolerância parcial e API NASA POWER com cache) + `RandomForestRegressor` e features temporais no `CropSimulator` / diagnósticos no `ClimateAnomalyDetector` | `geospatial.py`, `ml_models.py` | Dados reais/POWER e séries temporais alimentam o ML com `ml_model_score` e `temporal_stability` |
| A12 | ✅ | Infraestrutura Earthdata (`earthaccess`, `h5netcdf`, `EARTHDATA_TOKEN`, `NASA_POWER_FALLBACK`, `NASA_REAL_DAYS_BACK`), suporte a `perfil_climatico="real"` na simulação e testes de `A11–A12` | `requirements.txt`, `docker-compose.yml`, `.env.example`, `mock_nasa_data.py`, `api/simulacao.py`, `backend/tests/test_data_ml.py` | `POST /api/v1/simular-rotacao` suporta dados reais e suíte `pytest` verde |
| A13 | ✅ | Provedor direto FAO GAEZ v5 COG (`RES05-SUX`/`YLX` Suitability and Attainable Yield, `HWSDV201`, `SQ-IDX`, `SQX.SQ0`, `SLOPE-MED` e `CMIP6` 2021–2040) com cache por célula e sem fallbacks inventados | `backend/services/gaez_service.py` | Extração direta dos COGs oficiais nos 4 perfis (`LRLM`, `HRLM`, `LILM`, `HILM`) |
| A14 | ✅ | Integração "Suitability and Attainable Yield" no catálogo `[M2]` (`/culturas/aptidao-gaez`), `CropSimulator` `[M3]` e `RotationExplainerAgent` + testes de `A13–A14` | `api/cultura.py`, `schemas/rotacao.py`, `ml_models.py`, `llm_agent.py`, `api/simulacao.py`, `backend/tests/test_data_ml.py` | Culturas/rotações e IA usam aptidão GAEZ, produtividade `kg/ha`, solo HWSD e `CMIP6` |
| A15 | ✅ | Provedor direto **ECOCROP** (sem fallback inventado): extrair `Scientific Name`, `Family`, `TMIN`/`TMAX`, `TOPMIN`/`TOPMAX`, `RMIN`/`RMAX`, `GMIN`/`GMAX` | `backend/services/ecocrop_service.py`, `api/cultura.py`, `schemas/rotacao.py` | Zona de conforto e taxonomia da planta consultáveis via nome/código científico |
| A16 | ✅ | Provedor direto **AGROFIT (Embrapa AgroAPI)** cruzado por `Scientific Name` + gatilhos climáticos NASA (SMAP/ECOSTRESS/POWER) no `CropSimulator` (penalização/aviso de pragas e família botânica **sem bloquear** subsistência) | `backend/services/agrofit_service.py`, `ml_models.py`, `api/simulacao.py` | Risco fitossanitário calculado no `score_breakdown` sem excluir culturas de subsistência |
| A17 | ✅ | Cálculo de **Z-score de anomalia climática** contra baseline histórica do mesmo período (NASA POWER) no `ClimateAnomalyDetector` e `RealNASADataProvider` | `geospatial.py`, `ml_models.py`, `api/alertas.py` | Z-score de chuva/umidade/calor integrado à detecção `[M5]` e métricas `[M3]` |
| A18 | ✅ | Explicação estruturada com evidências numéricas (`RotationExplainerAgent` + schema `[M3]`) e integração de **SRTM 30 m** / cobertura **HLS** | `llm_agent.py`, `schemas/simulacao.py`, `geospatial.py` | Blocos estruturados com números reais para cards no frontend + elevação SRTM |

## Dev B — Catálogo, relatórios, terrenos e infra/demo

| # | Status | Task | Arquivos | Pronto quando |
|---|---|---|---|---|
| B1 | ✅ | **[M2]** CRUD completo de culturas/rotações do produtor (PUT/DELETE, validações); marcar customizadas vs seed e proteger as de seed; rotações preferenciais entram no simulador | `api/cultura.py`, `db/models.py` | Produtor cadastra/edita/remove; seed não removível |
| B2 | ✅ | **[M6]** Serviço e endpoints de relatório: histórico de umidade/temperatura, vigor, vulnerabilidade, adaptações (`ajustada_por_alerta`) | `services/relatorio_service.py`, `api/relatorios.py` | `GET` de relatório por terreno e período; usa `field_metrics` |
| B3 | ✅ | Persistir métricas históricas (tabela + migração/Alembic) para alimentar o M6 | `services/metrics_service.py`, `alembic/` | Série por terreno consultável |
| B4 | ✅ | Testes de API para M2/M6 e CI rodando `pytest` | `backend/tests/test_b1_b2_b3.py`, `.github/workflows/ci.yml` | CI verde no PR |
| B5 | ✅ | Configurar `CORSMiddleware` para o frontend (`localhost:5173`), seed de `Usuario` padrão no startup e completar `PUT`/`DELETE /api/v1/terrenos/{terreno_id}` com cálculo automático de área/centroide (A7) | `main.py`, `api/terreno.py`, `schemas/terreno.py` | Frontend conecta sem CORS; terreno criado/editado/removido calcula área quando omitida |
| B6 | ✅ | Enriquecer relatório `[M6]` com resumo interpretativo da IA (`explain_report` da A8 com fallback determinístico) e comparação entre início/fim do período | `services/relatorio_service.py`, `schemas/relatorio.py`, `api/relatorios.py` | `GET /api/v1/relatorios/...` inclui resumo acessível e comparativo do período |
| B7 | ✅ | Endpoint/rotina de seed de demonstração (`POST /api/v1/demo/seed` com usuário, terrenos, métricas, atividades e alertas), atualização de `docs/Specs/README.md` e testes de `B5–B7` | `api/`, `docs/Specs/README.md`, `backend/tests/` | Demo populada em 1 chamada; specs e testes atualizados e verdes |
| B8 | ✅ | Alinhar `docker-compose.yml` e `.env.example` com `NASA_MOCK_PROFILE`, integrar `api/demo.py` aos perfis da `A9` e atualizar `docs/index.md` removendo itens já entregues do roadmap | `docker-compose.yml`, `.env.example`, `api/demo.py`, `docs/index.md` | Ambiente sobe com perfil configurável, demo usa perfis reais do mock e docs refletem estado atual |

## Dev C — Simulação, alertas e calendário

| # | Status | Task | Arquivos | Pronto quando |
|---|---|---|---|---|
| C1 | ✅ | `origem`/`fallback_usado` na resposta; provider/simulator/agente instanciados uma vez | `api/simulacao.py` | Resposta indica se houve fallback |
| C2 | ✅ | Monitor [M5]: métricas **por terreno** via `INASADataProvider` (polígono); alerta só com `anomaly_detected` (A3 já pronta) | `services/alert_tasks.py` | Terrenos diferentes → alertas diferentes |
| C3 | ✅ | Deduplicar alertas (mesmo terreno + tipo + data), cooldown; intervalo por env | `alert_tasks.py`, `api/alertas.py` | Dois ciclos seguidos não duplicam |
| C4 | ✅ | Calendário gerado a partir da estratégia escolhida no M3 (`[M1]→[M3]→[M4]`); regras de ajuste pós-alerta testáveis | `api/calendario.py` | Fluxo ponta a ponta coberto por teste |
| C5 | ✅ | Datetimes com timezone e schemas Pydantic em `ConfigDict` | `api/calendario.py`, `schemas/` | `pytest` sem DeprecationWarning do projeto |
| C6 | ✅ | Expor `score_breakdown` e `explicacao` individual em `EstrategiaRotacaoSugerida` (usando `explain_strategies` da A4, mantendo `explicacao_ia`/`explicacao_textual`) e fallback dinâmico | `schemas/simulacao.py`, `api/simulacao.py` | Cada uma das 3 estratégias traz `score_breakdown` e `explicacao` com disclaimer |
| C7 | ✅ | Aceitar `historico_cultivos` no `SimulacaoRequest` (integrando onboarding + A7) e permitir gerar/atualizar cronograma `[M4]` direto pela estratégia escolhida na simulação | `schemas/simulacao.py`, `api/simulacao.py`, `api/calendario.py` | Simulação usa histórico do produtor e gera calendário direto da estratégia escolhida |
| C8 | ✅ | Integrar `explain_alert` (A8 com fallback) nos alertas `[M5]`, adicionar resumo de alertas não lidos por terreno para o painel e testes de `C6–C8` | `api/alertas.py`, `services/alert_tasks.py`, `schemas/alerta.py`, `backend/tests/` | Alertas trazem orientação prática acessível; contagem de não lidos e testes verdes |
| C9 | ✅ | Permitir selecionar `perfil_climatico` (`seca`, `chuva_extrema`, `onda_de_calor`) em `POST /api/v1/alertas/monitorar-clima` para disparar ciclo completo `[M5] -> [M4]` sob demanda na demo + teste | `schemas/alerta.py`, `api/alertas.py`, `services/alert_tasks.py`, `backend/tests/` | Um clique na demo gera alerta com `explain_alert` e adapta atividades do calendário |

## Frontend (`frontend/` — Integração Ponta a Ponta)

| # | Status | Task | Arquivos | Pronto quando |
|---|---|---|---|---|
| F1 | ✅ | Criar entrypoint e roteamento da aplicação (`index.html`, `src/main.tsx`, `src/App.tsx`) + cliente HTTP para `/api/v1` | `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/services/api.ts` | App Vite sobe com `npm run dev` e navega entre todas as etapas do fluxo |
| F2 | ✅ | Conectar `PlantationsPage.tsx`, `MapTerrainPage.tsx`, `CropHistoryStep.tsx` e `WaterDistributionStep.tsx` aos endpoints `[M1]` (`GET`/`POST`/`PUT`/`DELETE /api/v1/terrenos`), `[M3]` (`POST /api/v1/simular-rotacao`) e demo seed (`POST /api/v1/demo/seed`) | `frontend/src/pages/`, `frontend/src/features/onboarding/`, `frontend/src/services/api.ts` | Terrenos reais listados/criados/excluídos no Postgres sem mocks estáticos e onboarding conectado à API |
| F3 | ✅ | Implementar telas completas de Simulação `[M3]` (3 estratégias, blocos estruturados com números reais: `score_breakdown`, `kg/ha`, solo HWSD, faixa ECOCROP, risco Agrofit, Z-score e explicação IA + disclaimer), Calendário `[M4]` + Alertas `[M5]` e Relatório `[M6]` | `frontend/src/pages/` | Fluxo completo `[M1] -> [M3] -> [M4]/[M5] -> [M6]` + modo simulação sandbox testados (`tsc --noEmit && vite build`) |

## Ordem e dependências

1. ✅ **Rodada 1 concluída:** `A1–A6` · `B1–B4` · `C1–C5`.
2. ✅ **Rodada 2 concluída:** `A7–A9` · `B5–B7` · `C6–C8`.
3. ✅ **Rodada 3 concluída:** `A10–A14` · `B8` · `C9` · `F1–F2`.
4. ✅ **Rodada 4 concluída:** `A15` (ECOCROP) ✅ → `A16` (Agrofit × NASA) ✅ · `A17` (Z-score) ✅ · `A18` (Explicação estruturada + SRTM) ✅ · `F3` (telas finais + blocos numéricos no frontend) ✅.

## Regras de trabalho

- Branch por task a partir da `dev` atualizada (`feat/A7-geo-crop-history`, `feat/B5-cors-terrenos-crud`, `feat/C6-simulacao-breakdown`...), PR pequeno para a `dev`, `pytest backend/tests` verde antes de abrir.
- Mudou um contrato acima → avise os outros dois antes do merge.
- Sem `GOOGLE_API_KEY` o LLM usa resposta mockada; não commitar `.env` (usar `.env.example`).
- Rodar local: `python -m venv venv`, `pip install -r backend/requirements.txt`, `pytest backend/tests`.

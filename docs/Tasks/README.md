# Tasks do Hackathon — Dados/ML/IA e Backend

**Responsáveis:** **Dev A** = dados, ML e IA · **Dev B** = catálogo, relatórios e testes · **Dev C** = simulação, alertas e calendário.

**Legenda:** ✅ feito (mergeado na `dev`) · 🔄 em andamento · ⬜ pendente

## Estado atual (atualizado após A5 — Dev A concluída)

- Suíte `backend/tests`: **verde** (cobrindo A1–A6, C1–C3, C5 e B1–B4).
- **Feito:** A1, A2, A3, A4, A5, A6 (Dev A) · B1, B2, B3, B4 (Dev B) · C1, C2, C3, C5 (Dev C) · base de infra (`.env.example`, deps, healthcheck do Postgres, Alembic inicial, monitor de alertas ligado ao lifespan, disclaimer garantido no LLM, CI no GitHub Actions).
- **Por último:** C4 e integração/demo.

### O que a Dev A entregou (A1–A6)

- **A1 — Mock e provider** (`mock_nasa_data.py`, `geospatial.py`): `gpm_mock.nc` (precipitação em mm/dia) com padrão espacial (mais chuva/umidade perto do equador, mais calor ao norte); seed fixa; `.nc` ausentes são regerados. `extract_field_metrics` devolve `avg_precipitation_gpm`, `time_series` diário e `is_bare_field_period` (heurística do mock: umidade < 0,12 e temperatura ≥ 33 °C). Polígono menor que a célula usa a célula mais próxima (`data_quality = nearest_cell`).
- **A2 — `CropSimulator`** (`ml_models.py`): score ponderado por água, calor, solo e mercado (a água pesa mais com `agua: escassa` ou `water_conservation`). Devolve 3 estratégias, sempre incluindo a prática atual (`pratica_atual`, padrão "Milho -> Soja"), com `score_breakdown`. `predict_rotation_viability` usa `consumo_agua_mm` e `tempo_colheita_dias`. Aceita também as chaves de fallback da API (`umidade_solo_estimada`, etc.).
- **A3 — `ClimateAnomalyDetector`** (`ml_models.py`): limiares absolutos + `IsolationForest` sobre a série, confirmado por z-score robusto (MAD) e só com ≥ 10 pontos, para não marcar ~5% de qualquer série como anomalia.
- **A4 — `RotationExplainerAgent`** (`llm_agent.py`): adicionado `explain_strategies` (alias `generate_strategies_explanations`), que explica as 3 estratégias em uma única chamada ao LLM em linguagem simples para o pequeno produtor (com parse por `---ESTRATEGIA---`, fallback individualizado para mocks/respostas não delimitadas e disclaimer mandatório em todas as explicações), mantendo `generate_explanation` compatível.
- **A5 — `RealNASADataProvider` e `NASA_PROVIDER`** (`geospatial.py`, `api/simulacao.py`, `services/alert_tasks.py`): implementado `RealNASADataProvider` (`earthaccess` + `xr.open_mfdataset` com fallback sem `dask`, conversão Kelvin → Celsius e `is_bare_field_period` por NDVI `MOD13Q1`), selecionado pela fábrica `get_nasa_data_provider` via `NASA_PROVIDER=mock|real` (mantendo `mock` como padrão).
- **A6 — Testes unitários** (`backend/tests/test_data_ml.py`): 23 testes cobrindo `MockNASADataProvider`/`generate_synthetic_netcdf`, `RealNASADataProvider`/`get_nasa_data_provider`, `CropSimulator`, `ClimateAnomalyDetector` e `RotationExplainerAgent` (incluindo casos extremos).

### O que a Dev C entregou (C1 e C5)

- **C1** (`api/simulacao.py`, `schemas/simulacao.py`): `SimulacaoResponse` ganhou `origem` e `fallback_usado`; provider, simulator e agente LLM são instanciados uma vez (cache por módulo, respeitando a troca via `sys.modules` usada nos testes). Não remover o `importlib.import_module` de `get_nasa_processor`/`_get_cached_service`: o teste `test_m3_simulacao_integra_servicos_ia_geospatial_ml` depende dele.
- **C5** (`db/models.py`, `api/calendario.py`, `schemas/`): `datetime.utcnow()` trocado por datetime com timezone e schemas Pydantic migrados para `ConfigDict`/`json_schema_extra`.
- Testes em `backend/tests/test_c1_c5.py`.

### Pontos de atenção que ficaram abertos

- `EstrategiaRotacaoSugerida` (schema) **não expõe `score_breakdown`**: o simulador calcula, mas a API descarta. Decidir se entra na resposta (útil para o front explicar a nota) — toca `schemas/simulacao.py` e `api/simulacao.py` (Dev C) e o LLM (A4).
- O fallback de `_simular_viabilidade_ml` ainda devolve `0.85/low` e o de estratégias usa `_ROTACOES_PADRAO`; agora vem sinalizado por `fallback_usado`, mas o front precisa tratar.
- `alert_tasks.py` ainda coleta dado climático **global** (não por terreno) e não deduplica alertas → C2 e C3.
- A heurística de `is_bare_field_period` é do mock; o provider real (A5) precisará de NDVI/cobertura para isso.

## Contratos (não quebrar sem avisar os outros)

1. **`field_metrics`** (saída de `INASADataProvider.extract_field_metrics`):
   `avg_soil_moisture_smap`, `avg_surface_temp_ecostress`, `avg_precipitation_gpm` (mm/dia), `is_bare_field_period`, `data_quality` (`clip` | `nearest_cell` | `no_data`), `time_series` (lista por dia com `data`, `soil_moisture`, `surface_temp_c`, `precipitation_mm`), `coordinates`.
2. **`ClimateAnomalyDetector.detect_extremes(dict | list[dict])`** retorna
   `{anomaly_detected: bool, tipo_evento: onda_de_calor|seca|chuva_intensa|nenhum, severidade, detalhes}`; `detalhes` inclui `metodo` (`limiar` | `isolation_forest`) e `indices_outliers`.
3. **`CropSimulator.simulate_rotation_strategies`** retorna 3 itens (incluindo a prática atual, marcada com `(Atual)`) de
   `{strategy, viability (0–1), water_risk (low|medium|high), benefits, score_breakdown}`.
4. **`SimulacaoResponse`** inclui `origem` e `fallback_usado`.
5. **Aviso do LLM:** toda explicação termina com o disclaimer (garantido em `llm_agent.py`).

## Dev A — Dados, ML e IA

| # | Status | Task | Arquivos | Pronto quando |
|---|---|---|---|---|
| A1 | ✅ | Mock GPM/IMERG com recorte e `avg_precipitation_gpm`; `is_bare_field_period` dinâmico | `mock_nasa_data.py`, `geospatial.py` | Provider devolve precipitação e flag; teste unitário |
| A2 | ✅ | `CropSimulator` dinâmico (clima + prioridades); `predict_rotation_viability` usa `crop_requirements` | `ml_models.py` | Estratégias mudam com terreno/prioridades |
| A3 | ✅ | `ClimateAnomalyDetector` com `IsolationForest` + limiares | `ml_models.py` | Série com outlier dispara; normal não |
| A4 | ✅ | Agente LLM: explicar as 3 estratégias numa chamada, linguagem simples (o cache/singleton do agente já veio na C1) | `llm_agent.py` | Uma chamada → 3 explicações, todas com disclaimer |
| A5 | ✅ | `RealNASADataProvider` (`earthaccess` + `xr.open_mfdataset`) via `NASA_PROVIDER=mock\|real` | `geospatial.py` | Fábrica `get_nasa_data_provider` e `RealNASADataProvider` com NDVI/Earthdata testados; mock segue como padrão |
| A6 | ✅ | Testes unitários de `MockNASADataProvider`, `CropSimulator`, `ClimateAnomalyDetector` e `RotationExplainerAgent` | `backend/tests/` | `pytest` verde |

## Dev B — Catálogo, relatórios e qualidade

| # | Status | Task | Pronto quando |
|---|---|---|---|
| B1 | ✅ | **[M2]** CRUD completo de culturas/rotações do produtor (PUT/DELETE, validações); marcar customizadas vs seed e proteger as de seed; rotações preferenciais entram no simulador | Produtor cadastra/edita/remove; seed não removível |
| B2 | ✅ | **[M6]** Serviço e endpoints de relatório: histórico de umidade/temperatura, vigor, vulnerabilidade, adaptações (`ajustada_por_alerta`) | `GET` de relatório por terreno e período; usa `field_metrics` |
| B3 | ✅ | Persistir métricas históricas (tabela + migração/Alembic) para alimentar o M6 | Série por terreno consultável |
| B4 | ✅ | Testes de API para M2/M6 e CI rodando `pytest` | CI verde no PR |

## Dev C — Simulação, alertas e calendário

| # | Status | Task | Arquivos | Pronto quando |
|---|---|---|---|---|
| C1 | ✅ | `origem`/`fallback_usado` na resposta; provider/simulator/agente instanciados uma vez | `api/simulacao.py` | Resposta indica se houve fallback |
| C2 | ✅ | Monitor [M5]: métricas **por terreno** via `INASADataProvider` (polígono); alerta só com `anomaly_detected` (A3 já pronta) | `services/alert_tasks.py` | Terrenos diferentes → alertas diferentes |
| C3 | ✅ | Deduplicar alertas (mesmo terreno + tipo + data), cooldown; intervalo por env | `alert_tasks.py`, `api/alertas.py` | Dois ciclos seguidos não duplicam |
| C4 | ⬜ | Calendário gerado a partir da estratégia escolhida no M3 (`[M1]→[M3]→[M4]`); regras de ajuste pós-alerta testáveis | `api/calendario.py` | Fluxo ponta a ponta coberto por teste |
| C5 | ✅ | Datetimes com timezone e schemas Pydantic em `ConfigDict` | `api/calendario.py`, `schemas/` | `pytest` sem DeprecationWarning do projeto |

## Ordem e dependências

1. ✅ **Concluído:** A1, A2, A3, A4, A5, A6 · B1, B2, B3, B4 · C1, C2, C3, C4, C5.

## Regras de trabalho

- Branch por task a partir da `dev` atualizada (`feat/A4-llm-explainer`, `feat/A6-tests`, `feat/A5-real-provider`...), PR pequeno para a `dev`, `pytest backend/tests` verde antes de abrir.
- Mudou um contrato acima → avise os outros dois antes do merge.
- Sem `GOOGLE_API_KEY` o LLM usa resposta mockada; não commitar `.env` (usar `.env.example`).
- Rodar local: `python -m venv venv`, `pip install -r backend/requirements.txt`, `pytest backend/tests`.

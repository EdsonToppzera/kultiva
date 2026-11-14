# Tasks do Hackathon — Dados/ML/IA e Backend

**Responsáveis:** **Dev A** = dados, ML e IA · **Dev B** = catálogo, relatórios, terrenos e infra/demo · **Dev C** = simulação, alertas e calendário.

**Legenda:** ✅ feito (mergeado na `dev`) · 🔄 em andamento · ⬜ pendente

## Estado atual (Rodada 1 concluída · preparando Rodada 2)

- Suíte `backend/tests`: **verde** (cobrindo toda a Rodada 1: `A1–A6`, `B1–B4` e `C1–C5`).
- **Feito (Rodada 1):** `A1–A6` (Dev A) · `B1–B4` (Dev B) · `C1–C5` (Dev C) · base de infra (`.env.example`, deps, healthcheck do Postgres, Alembic inicial, monitor de alertas ligado ao lifespan, disclaimer garantido no LLM, CI no GitHub Actions).
- **Próximos em paralelo (Rodada 2 — Integração, Refinamento e Demo):** `A7, A8` (Dev A) · `B5` (Dev B) · `C6` (Dev C), seguidos por `A9 · B6, B7 · C7, C8`.

### Resumo do que foi entregue na Rodada 1

- **Dev A (`A1–A6`)**
  - **A1 — Mock e provider** (`mock_nasa_data.py`, `geospatial.py`): `gpm_mock.nc` (precipitação em mm/dia) com padrão espacial; seed fixa; `.nc` ausentes são regerados. `extract_field_metrics` devolve `avg_precipitation_gpm`, `time_series` diário e `is_bare_field_period` (heurística no mock: umidade < 0,12 e temperatura ≥ 33 °C). Polígono menor que a célula usa a célula mais próxima (`data_quality = nearest_cell`).
  - **A2 — `CropSimulator`** (`ml_models.py`): score ponderado por água, calor, solo e mercado; devolve 3 estratégias, sempre incluindo `pratica_atual` (padrão `"Milho -> Soja"`), com `score_breakdown`. `predict_rotation_viability` usa `consumo_agua_mm` e `tempo_colheita_dias`.
  - **A3 — `ClimateAnomalyDetector`** (`ml_models.py`): limiares absolutos + `IsolationForest` sobre a série, confirmado por z-score robusto (MAD) com ≥ 10 pontos.
  - **A4 — `RotationExplainerAgent`** (`llm_agent.py`): `explain_strategies` (alias `generate_strategies_explanations`) explica as 3 estratégias em uma única chamada ao LLM em linguagem simples (parse por `---ESTRATEGIA---`, fallback individualizado e disclaimer mandatório), mantendo `generate_explanation` compatível.
  - **A5 — `RealNASADataProvider` e `NASA_PROVIDER`** (`geospatial.py`, `api/simulacao.py`, `services/alert_tasks.py`): `RealNASADataProvider` (`earthaccess` + `xr.open_mfdataset` com fallback sem `dask`, Kelvin → Celsius e `is_bare_field_period` por NDVI `MOD13Q1`), selecionado por `get_nasa_data_provider` via `NASA_PROVIDER=mock|real` (`mock` como padrão).
  - **A6 — Testes unitários** (`backend/tests/test_data_ml.py`): 23 testes cobrindo `MockNASADataProvider`/`generate_synthetic_netcdf`, `RealNASADataProvider`/`get_nasa_data_provider`, `CropSimulator`, `ClimateAnomalyDetector` e `RotationExplainerAgent` (incluindo casos extremos).
- **Dev B (`B1–B4`)**
  - **B1 — Catálogo `[M2]`** (`api/cultura.py`, `db/models.py`, `main.py`, `api/simulacao.py`): CRUD completo de culturas e rotações do produtor (`rotacoes_produtor`), marcação e proteção de registros seed (`is_seed`/`customizada`) e inclusão de rotações preferenciais no simulador.
  - **B2 & B3 — Histórico e Relatórios `[M6]`** (`services/metrics_service.py`, `services/relatorio_service.py`, `api/relatorios.py`, `alembic/`): tabela `metricas_historicas_terreno` com migração Alembic e endpoints `GET /api/v1/relatorios/...` consolidando clima, vigor, vulnerabilidade e adaptações (`ajustada_por_alerta`).
  - **B4 — Qualidade e CI** (`backend/tests/test_b1_b2_b3.py`, `.github/workflows/ci.yml`): cobertura de API/migração para `[M2]` e `[M6]` com execução automática no GitHub Actions.
- **Dev C (`C1–C5`)**
  - **C1** (`api/simulacao.py`, `schemas/simulacao.py`): `SimulacaoResponse` com `origem` e `fallback_usado` e cache de serviços (`_SERVICE_CACHE`) respeitando troca via `sys.modules` (`importlib.import_module` em `get_nasa_processor`).
  - **C2 & C3** (`services/alert_tasks.py`, `api/alertas.py`): monitoramento `[M5]` por terreno via `INASADataProvider` somente com `anomaly_detected`, deduplicação (terreno + tipo + data), cooldown (`ALERT_COOLDOWN_HOURS`) e intervalo via `ALERT_MONITOR_INTERVAL_HOURS`.
  - **C4** (`api/calendario.py`, `schemas/calendario.py`, `services/alert_tasks.py`, `backend/tests/test_c4_fluxo.py`): geração do calendário `[M4]` a partir da estratégia simulada no `[M3]` e `aplicar_regras_ajuste_pos_alerta` testáveis ponta a ponta.
  - **C5** (`db/models.py`, `api/calendario.py`, `schemas/`): datetimes com timezone e schemas Pydantic migrados para `ConfigDict`/`json_schema_extra`.

### Pontos de atenção para a Rodada 2

- `EstrategiaRotacaoSugerida` (`schemas/simulacao.py`) **ainda não expõe `score_breakdown` nem `explicacao` individual** por estratégia (o simulador já calcula `score_breakdown` e a A4 já entrega `explain_strategies`, mas `api/simulacao.py` ainda descarta ambos) → **C6**.
- O fallback de `_simular_viabilidade_ml` e `_ROTACOES_PADRAO` em `api/simulacao.py` ainda retorna valores estáticos (`0.85/low`) quando o simulador falha → **A7 + C6**.
- O frontend Vite (`frontend/`) já iniciou a coleta de histórico de cultivos (`CropHistoryStep`), mas a API ainda não aceita `historico_cultivos` no simulador, não configura `CORSMiddleware` nem cria `Usuario` seed no startup → **A7, B5, C7**.
- Para a apresentação/demo do Hackathon e completude dos módulos `[M5]` e `[M6]`, falta gerar explicações em linguagem simples para alertas e relatórios, perfis climáticos simuláveis e um seed de demonstração ponta a ponta → **A8, A9, B6, B7, C8**.

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
| A7 | ✅ | Cálculo geoespacial de área (`area_hectares`) e centroide do polígono; `CropSimulator` considerando `historico_cultivos` (penaliza monocultura, bonifica quebra de ciclo) e fallback dinâmico | `geospatial.py`, `ml_models.py` | Área/centroide calculados do polígono; histórico altera ranking do simulador |
| A8 | ✅ | Expandir `RotationExplainerAgent` com `explain_alert` (orientações práticas de manejo para `[M5]`) e `explain_report` (resumo em linguagem simples para `[M6]`), mantendo `DISCLAIMER` e mock offline | `llm_agent.py` | Alertas e relatórios geram explicação acessível sempre com disclaimer |
| A9 | ⬜ | Perfis climáticos simuláveis (`normal`, `seca`, `chuva_extrema`, `onda_de_calor`) em `mock_nasa_data.py` para testes de estresse/demo + testes unitários de `A7–A9` | `mock_nasa_data.py`, `backend/tests/test_data_ml.py` | Perfis geram cenários distintos e `pytest` verde |

## Dev B — Catálogo, relatórios, terrenos e infra/demo

| # | Status | Task | Arquivos | Pronto quando |
|---|---|---|---|---|
| B1 | ✅ | **[M2]** CRUD completo de culturas/rotações do produtor (PUT/DELETE, validações); marcar customizadas vs seed e proteger as de seed; rotações preferenciais entram no simulador | `api/cultura.py`, `db/models.py` | Produtor cadastra/edita/remove; seed não removível |
| B2 | ✅ | **[M6]** Serviço e endpoints de relatório: histórico de umidade/temperatura, vigor, vulnerabilidade, adaptações (`ajustada_por_alerta`) | `services/relatorio_service.py`, `api/relatorios.py` | `GET` de relatório por terreno e período; usa `field_metrics` |
| B3 | ✅ | Persistir métricas históricas (tabela + migração/Alembic) para alimentar o M6 | `services/metrics_service.py`, `alembic/` | Série por terreno consultável |
| B4 | ✅ | Testes de API para M2/M6 e CI rodando `pytest` | `backend/tests/test_b1_b2_b3.py`, `.github/workflows/ci.yml` | CI verde no PR |
| B5 | ⬜ | Configurar `CORSMiddleware` para o frontend (`localhost:5173`), seed de `Usuario` padrão no startup e completar `PUT`/`DELETE /api/v1/terrenos/{terreno_id}` com cálculo automático de área/centroide (A7) | `main.py`, `api/terreno.py`, `schemas/terreno.py` | Frontend conecta sem CORS; terreno criado/editado/removido calcula área quando omitida |
| B6 | ⬜ | Enriquecer relatório `[M6]` com resumo interpretativo da IA (`explain_report` da A8 com fallback determinístico) e comparação entre início/fim do período | `services/relatorio_service.py`, `schemas/relatorio.py`, `api/relatorios.py` | `GET /api/v1/relatorios/...` inclui resumo acessível e comparativo do período |
| B7 | ⬜ | Endpoint/rotina de seed de demonstração (`POST /api/v1/demo/seed` com usuário, terrenos, métricas, atividades e alertas), atualização de `docs/Specs/README.md` e testes de `B5–B7` | `api/`, `docs/Specs/README.md`, `backend/tests/` | Demo populada em 1 chamada; specs e testes atualizados e verdes |

## Dev C — Simulação, alertas e calendário

| # | Status | Task | Arquivos | Pronto quando |
|---|---|---|---|---|
| C1 | ✅ | `origem`/`fallback_usado` na resposta; provider/simulator/agente instanciados uma vez | `api/simulacao.py` | Resposta indica se houve fallback |
| C2 | ✅ | Monitor [M5]: métricas **por terreno** via `INASADataProvider` (polígono); alerta só com `anomaly_detected` (A3 já pronta) | `services/alert_tasks.py` | Terrenos diferentes → alertas diferentes |
| C3 | ✅ | Deduplicar alertas (mesmo terreno + tipo + data), cooldown; intervalo por env | `alert_tasks.py`, `api/alertas.py` | Dois ciclos seguidos não duplicam |
| C4 | ✅ | Calendário gerado a partir da estratégia escolhida no M3 (`[M1]→[M3]→[M4]`); regras de ajuste pós-alerta testáveis | `api/calendario.py` | Fluxo ponta a ponta coberto por teste |
| C5 | ✅ | Datetimes com timezone e schemas Pydantic em `ConfigDict` | `api/calendario.py`, `schemas/` | `pytest` sem DeprecationWarning do projeto |
| C6 | ⬜ | Expor `score_breakdown` e `explicacao` individual em `EstrategiaRotacaoSugerida` (usando `explain_strategies` da A4, mantendo `explicacao_ia`/`explicacao_textual`) e fallback dinâmico | `schemas/simulacao.py`, `api/simulacao.py` | Cada uma das 3 estratégias traz `score_breakdown` e `explicacao` com disclaimer |
| C7 | ⬜ | Aceitar `historico_cultivos` no `SimulacaoRequest` (integrando onboarding + A7) e permitir gerar/atualizar cronograma `[M4]` direto pela estratégia escolhida na simulação | `schemas/simulacao.py`, `api/simulacao.py`, `api/calendario.py` | Simulação usa histórico do produtor e gera calendário direto da estratégia escolhida |
| C8 | ⬜ | Integrar `explain_alert` (A8 com fallback) nos alertas `[M5]`, adicionar resumo de alertas não lidos por terreno para o painel e testes de `C6–C8` | `api/alertas.py`, `services/alert_tasks.py`, `schemas/alerta.py`, `backend/tests/` | Alertas trazem orientação prática acessível; contagem de não lidos e testes verdes |

## Ordem e dependências

1. ✅ **Rodada 1 concluída:** `A1–A6` · `B1–B4` · `C1–C5`.
2. **Rodada 2 — Agora, em paralelo:** `A7` ✅, `A8` ✅ · `B5` · `C6` ✅.
3. **Rodada 2 — Em seguida:** `A9` · `B6` (depende de `A8`) · `B7` (depende de `B5`) · `C7` (depende de `A7`) · `C8` (depende de `A8`).
4. **Por último:** Integração completa com o `frontend/` e ensaio da demo do Hackathon.

## Regras de trabalho

- Branch por task a partir da `dev` atualizada (`feat/A7-geo-crop-history`, `feat/B5-cors-terrenos-crud`, `feat/C6-simulacao-breakdown`...), PR pequeno para a `dev`, `pytest backend/tests` verde antes de abrir.
- Mudou um contrato acima → avise os outros dois antes do merge.
- Sem `GOOGLE_API_KEY` o LLM usa resposta mockada; não commitar `.env` (usar `.env.example`).
- Rodar local: `python -m venv venv`, `pip install -r backend/requirements.txt`, `pytest backend/tests`.

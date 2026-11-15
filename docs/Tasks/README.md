# Tasks do Hackathon — Dados/ML/IA, Backend e Integração Demo

**Responsáveis:** **Dev A** = dados, ML e IA · **Dev B** = catálogo, relatórios, terrenos e infra/demo · **Dev C** = simulação, alertas e calendário.

**Legenda:** ✅ feito (mergeado na `dev` / `A10` pronta para PR) · 🔄 em andamento · ⬜ pendente

## Estado atual (Rodadas 1 e 2 concluídas · Rodada 3 em andamento)

- Suíte `backend/tests`: **verde** (cobrindo Rodadas 1 e 2 e evolução da Rodada 3: `A1–A10`, `B1–B7`, `C1–C9`).
- **Feito (Rodada 1):** `A1–A6` (Dev A) · `B1–B4` (Dev B) · `C1–C5` (Dev C) · base de infra (`.env.example`, deps, healthcheck do Postgres, Alembic inicial, monitor de alertas ligado ao lifespan, disclaimer garantido no LLM, CI no GitHub Actions).
- **Feito (Rodada 2):** `A7–A9` (Dev A) · `B5–B7` (Dev B) · `C6–C8` (Dev C).
- **Rodada 3 (Fechamento da Demo e Integração Frontend):** `A10` ✅ (nesta branch) · `C9` ✅ (mergeado na `dev`) · pendentes: `B8` (Dev B) + integração completa com `frontend/` (`F1–F3`).

### Resumo do que foi entregue

- **Dev A (`A1–A9`)**
  - **A1–A6 (Rodada 1):** NetCDFs sintéticos determinísticos (`mock_nasa_data.py`), `MockNASADataProvider` + `RealNASADataProvider` (`geospatial.py`, `NASA_PROVIDER=mock|real`), `CropSimulator` dinâmico e `ClimateAnomalyDetector` (`ml_models.py`), `RotationExplainerAgent.explain_strategies` com `DISCLAIMER` (`llm_agent.py`) e suíte unitária (`backend/tests/test_data_ml.py`).
  - **A7 — Geometria, histórico de cultivos e fallback dinâmico** (`geospatial.py`, `ml_models.py`): `calcular_geometria_terreno` (área em hectares e centroide do polígono); `CropSimulator` considerando `historico_cultivos` (penaliza monocultura e bonifica quebra de ciclo com leguminosas) e método `fallback_strategies`.
  - **A8 — Explicações de alertas `[M5]` e relatórios `[M6]`** (`llm_agent.py`): `explain_alert` com orientações práticas de manejo e `explain_report` em linguagem simples, mantendo `DISCLAIMER` e fallback determinístico offline.
  - **A9 — Perfis climáticos simuláveis** (`mock_nasa_data.py`, `geospatial.py`, `backend/tests/test_data_ml.py`): perfis `normal`, `seca`, `chuva_extrema` e `onda_de_calor` (via parâmetro `profile` ou `NASA_MOCK_PROFILE`) gerando cenários distintos que acionam `ClimateAnomalyDetector` e alteram o ranking do `CropSimulator`.
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

### Pontos de atenção para a Rodada 3 (Demo e Integração Frontend)

- `docker-compose.yml` e `.env.example` ainda não expõem `NASA_MOCK_PROFILE`, `backend/api/demo.py` ainda monta série demo própria em vez de aproveitar os perfis da `A9`, e `docs/index.md` ainda mantém o roadmap das Fases 1–3 como futuro → **B8**.
- O `frontend/` (`React 19 + Vite + Tailwind v4`) já iniciou componentes e fluxo de onboarding (`MapTerrainPage.tsx`, `PlantationsPage.tsx`, `CropHistoryStep.tsx`, passo 2 de água), faltando conectar `/api/v1` e implementar as telas integradas de `[M3]`, `[M4]`, `[M5]` e `[M6]`.

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
| A9 | ✅ | Perfis climáticos simuláveis (`normal`, `seca`, `chuva_extrema`, `onda_de_calor`) em `mock_nasa_data.py` para testes de estresse/demo + testes unitários de `A7–A9` | `mock_nasa_data.py`, `backend/tests/test_data_ml.py` | Perfis geram cenários distintos e `pytest` verde |
| A10 | ✅ | Expor `perfil_climatico` em runtime na extração/simulação (`get_nasa_processor` / `extract_field_metrics`) e usar `calcular_geometria_terreno` dentro de `_calcular_metricas_fallback` para incluir `area_hectares` em `metricas_geoespaciais` | `geospatial.py`, `api/simulacao.py`, `schemas/simulacao.py`, `backend/tests/test_data_ml.py` | Simulação aceita perfil climático sob demanda e sempre retorna `area_hectares` calculada do polígono |

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
| B8 | ⬜ | Alinhar `docker-compose.yml` e `.env.example` com `NASA_MOCK_PROFILE`, integrar `api/demo.py` aos perfis da `A9` e atualizar `docs/index.md` removendo itens já entregues do roadmap | `docker-compose.yml`, `.env.example`, `api/demo.py`, `docs/index.md` | Ambiente sobe com perfil configurável, demo usa perfis reais do mock e docs refletem estado atual |

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
| F1 | ⬜ | Criar entrypoint e roteamento da aplicação (`index.html`, `src/main.tsx`, `src/App.tsx`) + cliente HTTP para `/api/v1` | `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/App.tsx` | App Vite sobe com `npm run dev` e navega entre todas as etapas do fluxo |
| F2 | ⬜ | Conectar `PlantationsPage.tsx`, `MapTerrainPage.tsx` e `CropHistoryStep.tsx` aos endpoints `[M1]` (`GET`/`POST`/`DELETE /api/v1/terrenos`) e demo seed (`POST /api/v1/demo/seed`) | `frontend/src/pages/`, `frontend/src/features/onboarding/` | Terrenos reais listados/criados/excluídos no Postgres sem mocks estáticos |
| F3 | ⬜ | Implementar telas de Simulação `[M3]` (3 estratégias, `score_breakdown`, explicação IA + disclaimer), Calendário `[M4]` + Alertas `[M5]` e Relatório `[M6]` | `frontend/src/pages/` | Fluxo completo `[M1] -> [M3] -> [M4]/[M5] -> [M6]` testado no navegador |

## Ordem e dependências

1. ✅ **Rodada 1 concluída:** `A1–A6` · `B1–B4` · `C1–C5`.
2. ✅ **Rodada 2 concluída:** `A7–A9` · `B5–B7` · `C6–C8`.
3. **Rodada 3 — Em andamento:** `A10` ✅ · `C9` ✅ · pendentes: `B8` + `F1, F2, F3` (integração Frontend + ensaio final da demo).

## Regras de trabalho

- Branch por task a partir da `dev` atualizada (`feat/A7-geo-crop-history`, `feat/B5-cors-terrenos-crud`, `feat/C6-simulacao-breakdown`...), PR pequeno para a `dev`, `pytest backend/tests` verde antes de abrir.
- Mudou um contrato acima → avise os outros dois antes do merge.
- Sem `GOOGLE_API_KEY` o LLM usa resposta mockada; não commitar `.env` (usar `.env.example`).
- Rodar local: `python -m venv venv`, `pip install -r backend/requirements.txt`, `pytest backend/tests`.

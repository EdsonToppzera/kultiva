# Tasks do Hackathon — Dados/ML/IA e Backend

Base pronta (suíte `backend/tests` com 12 testes passando): `.env.example`, deps, mock NASA determinístico, `detect_extremes` com limiares, monitor de alertas ligado ao lifespan e fallback da simulação unificado.

**Responsáveis:** **Dev A** = dados, ML e IA · **Dev B** = catálogo, relatórios e testes · **Dev C** = simulação, alertas e calendário.

## Contratos (não quebrar sem avisar os outros)

1. **`field_metrics`** (saída de `INASADataProvider.extract_field_metrics`):
   `avg_soil_moisture_smap`, `avg_surface_temp_ecostress`, `avg_precipitation_gpm` *(Dev A, D1)*, `is_bare_field_period`, `data_quality` (`clip` | `nearest_cell` | `no_data`), `coordinates`.
2. **`ClimateAnomalyDetector.detect_extremes(dict | list[dict])`** retorna
   `{anomaly_detected: bool, tipo_evento: onda_de_calor|seca|chuva_intensa|nenhum, severidade, detalhes}`.
3. **`CropSimulator.simulate_rotation_strategies`** retorna lista (≥ 3, incluindo a prática atual) de
   `{strategy, viability (0–1), water_risk (low|medium|high), benefits}`.
4. **Aviso do LLM:** toda explicação termina com o disclaimer (já garantido em `llm_agent.py`).

## Dev A — Dados, ML e IA

| # | Task | Arquivos | Pronto quando |
|---|---|---|---|
| A1 | Mock GPM/IMERG (`gpm_mock.nc`) com recorte e `avg_precipitation_gpm`; `is_bare_field_period` dinâmico | `mock_nasa_data.py`, `geospatial.py` | `extract_field_metrics` devolve precipitação e flag; teste unitário |
| A2 | `CropSimulator` dinâmico: score ponderando umidade, temperatura, precipitação e `farmer_priorities`; `predict_rotation_viability` usa `crop_requirements` (consumo de água, ciclo) | `ml_models.py` | Estratégias mudam com o terreno/prioridades; **atualizar** os asserts `0.85` em `test_m3_m4_m5.py` |
| A3 | `ClimateAnomalyDetector`: somar `IsolationForest` sobre a série aos limiares atuais, mantendo o contrato | `ml_models.py` | Série com outlier dispara; série normal não |
| A4 | Agente LLM: explicar as 3 estratégias numa chamada, linguagem simples; cache/singleton do agente | `llm_agent.py` | Uma chamada → 3 explicações, todas com disclaimer |
| A5 | `RealNASADataProvider` (`earthaccess` + `xr.open_mfdataset`) selecionado por `NASA_PROVIDER=mock\|real` | `geospatial.py` | Último: só se sobrar tempo; mock segue como padrão |
| A6 | Testes unitários de `MockNASADataProvider`, `CropSimulator`, `ClimateAnomalyDetector` | `backend/tests/` | `pytest` verde |

## Dev B — Catálogo, relatórios e qualidade

| # | Task | Pronto quando |
|---|---|---|
| B1 | **[M2]** CRUD completo de culturas/rotações do produtor (PUT/DELETE, validações); marcar customizadas vs seed e proteger as de seed; rotações preferenciais entram no simulador | Produtor cadastra/edita/remove; seed não removível |
| B2 | **[M6]** Serviço e endpoints de relatório: histórico de umidade/temperatura, vigor, vulnerabilidade, adaptações (`ajustada_por_alerta`) | `GET` de relatório por terreno e período; usa `field_metrics` |
| B3 | Persistir métricas históricas (tabela + migração/Alembic) para alimentar o M6 | Série por terreno consultável |
| B4 | Testes de API para M2/M6 e CI rodando `pytest` | CI verde no PR |

## Dev C — Simulação, alertas e calendário

| # | Task | Arquivos | Pronto quando |
|---|---|---|---|
| C1 | Refatorar `api/simulacao.py`: devolver `origem`/`fallback_usado` na resposta, instanciar provider/simulator/agente uma vez (cuidar dos testes que trocam módulos via `sys.modules`) | `api/simulacao.py` | Resposta indica se houve fallback |
| C2 | Monitor [M5]: coletar métricas **por terreno** via `INASADataProvider` (polígono) em vez do dado global; alerta só com `anomaly_detected` | `services/alert_tasks.py` | Terrenos diferentes → alertas diferentes |
| C3 | Deduplicar alertas (mesmo terreno + tipo + data) e cooldown; intervalo por env | `alert_tasks.py`, `api/alertas.py` | Dois ciclos seguidos não duplicam |
| C4 | Calendário gerado a partir da estratégia escolhida no M3 (`[M1]→[M3]→[M4]`); regras de ajuste pós-alerta testáveis | `api/calendario.py` | Fluxo ponta a ponta coberto por teste |
| C5 | Trocar `datetime.utcnow()` por datetimes com timezone e migrar schemas Pydantic para `ConfigDict` (warnings atuais) | `api/calendario.py`, `schemas/` | `pytest` sem DeprecationWarning do projeto |

## Ordem e dependências

1. **Agora, em paralelo:** A1, A2, A3 · B1, B3 · C1, C5.
2. **Depois:** C2/C3 (dependem do A3) · B2 (depende do B3) · A4, A6, B4.
3. **Por último:** A5, C4, integração e demo.

## Regras de trabalho

- Branch por task (`feat/A2-crop-simulator`), PR pequeno, `pytest backend/tests` verde antes de abrir.
- Mudou um contrato acima → avise os outros dois antes do merge.
- Sem `GOOGLE_API_KEY` o LLM usa resposta mockada; não commitar `.env`.
- Rodar local: `python -m venv venv`, `pip install -r backend/requirements.txt`, `pytest backend/tests`.

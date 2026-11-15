# Especificações Técnicas (Specs)

Prefixo base da API: `/api/v1`  
Documentação interativa automática (Swagger UI): `GET /docs`

---

## [M1] Terrenos e Configuração Inicial (`backend/api/terreno.py`, `backend/main.py`)

### Configuração de Startup e CORS
- `CORSMiddleware` habilitado no FastAPI para origens locais do frontend (`http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000`, `http://localhost:8000`) e origens adicionais via `CORS_ALLOWED_ORIGINS`.
- Seed automático de `Usuario` padrão (`seed_usuario_padrao` / `produtor@kultiva.agro`) e do catálogo base no startup (`lifespan`).

### `POST /api/v1/terrenos/`
Cria um novo terreno com o polígono geográfico e prioridades do produtor. Quando `area_hectares` ou `localizacao_central` forem omitidos, são calculados automaticamente a partir de `coordenadas_poligono` via `calcular_geometria_terreno`.

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

**Response (`200 OK`):** Retorna os dados do terreno criado acrescidos de `"id"`, `"area_hectares"` e `"localizacao_central"`.

### `GET /api/v1/terrenos/` (`200 OK`) e `GET /api/v1/terrenos/{terreno_id}` (`200 OK`)
Lista terrenos (com filtro opcional `usuario_id`) ou busca um terreno específico (`404` se inexistente).

### `PUT /api/v1/terrenos/{terreno_id}` (`200 OK`)
Atualiza parcialmente ou integralmente um terreno. Ao alterar `coordenadas_poligono`, recalcula automaticamente `area_hectares` e `localizacao_central` quando não enviados no payload.

### `DELETE /api/v1/terrenos/{terreno_id}` (`204 No Content`)
Remove o terreno e limpa os registros dependentes associados (`metricas_historicas_terreno`, `alertas_climaticos`, `atividades_calendario` e rotações customizadas do terreno).

---

## [M2] Catálogo de Culturas e Rotações (`backend/api/cultura.py`)

### Culturas (`/api/v1/culturas`)
- `GET /api/v1/culturas/`: lista culturas com filtros opcionais (`is_seed`, `customizada`, `usuario_id`).
- `GET /api/v1/culturas/aptidao-gaez`: consulta **diretamente** os COGs do **FAO GAEZ v5** (*Suitability and Attainable Yield* `RES05-SUX`/`YLX`, solo `HWSDV201`, `SQ-IDX`, `SQX.SQ0`, declividade `SLOPE-MED` e projeção `CMIP6 FP2140 SSP370`) para a coordenada/terreno e perfil de manejo (`LRLM`, `HRLM`, `LILM`, `HILM`).
  - **Query Params:** `terreno_id` ou `lat` & `lng`; opcionais `agua`, `metodo_irrigacao`, `nivel_insumo` e `sincronizar_catalogo=true|false` (grava/atualiza culturas viáveis no catálogo `[M2]` preservando `is_seed=true`).
  - **Respostas:** `200 OK` (`origem`, `data_quality`, `input_level`, `ssp_scenario`, `centroid`, `soil`, `culturas_avaliadas`, `culturas_sincronizadas`) ou `503 Service Unavailable` caso o GAEZ v5 não responda (`no_data`, sem fallback inventado).
- `GET /api/v1/culturas/ecocrop`: consulta diretamente a base **FAO ECOCROP** (`EcoCrop_DB.csv` com cache local, sem fallback inventado) para retornar taxonomia (`scientific_name`, `family`, `family_canonical`) e zona de conforto (`tmin`/`tmax`, `topmin`/`topmax`, `rmin`/`rmax`, `gmin`/`gmax`).
  - **Query Params:** `q`, `nome`, `scientific_name`, `crop_code`, `ecoport_code` ou `cultura_id`.
  - **Respostas:** `200 OK`, `404 Not Found` (cultura não encontrada na base) ou `503 Service Unavailable` caso o CSV do ECOCROP esteja indisponível (`no_data`).
- `GET /api/v1/culturas/{cultura_id}`: obtém detalhes de uma cultura.
- `POST /api/v1/culturas/` (`200 OK`): cadastra cultura customizada (`is_seed=false`, `customizada=true`), validando nome único e valores positivos (`consumo_agua_mm > 0`, `tempo_colheita_dias > 0`).
- `PUT /api/v1/culturas/{cultura_id}` (`200 OK`): edita cultura customizada (retorna `403 Forbidden` para culturas `is_seed=true`).
- `DELETE /api/v1/culturas/{cultura_id}` (`204 No Content`): remove cultura customizada (retorna `403 Forbidden` para `is_seed=true`).

### Rotações do Produtor (`/api/v1/rotacoes`)
- `GET /api/v1/rotacoes/`: lista rotações com filtros (`usuario_id`, `terreno_id`, `preferencial`, `is_seed`).
- `GET /api/v1/rotacoes/{rotacao_id}`: obtém detalhes de uma rotação.
- `POST /api/v1/rotacoes/` (`201 Created`): cadastra rotação preferencial (`culturas` com pelo menos 2 culturas). Rotações com `preferencial=true` entram automaticamente no ranking do simulador `[M3]`.
- `PUT /api/v1/rotacoes/{rotacao_id}` (`200 OK`): atualiza rotação customizada (`403` se `is_seed=true`).
- `DELETE /api/v1/rotacoes/{rotacao_id}` (`204 No Content`): remove rotação customizada (`403` se `is_seed=true`).

---

## [M3] Simulador de Culturas e Rotações (`backend/api/simulacao.py`)

### `POST /api/v1/simular-rotacao`
*(Também disponível em `POST /api/v1/simulacoes/` e `POST /api/v1/simulacoes/simular-rotacao`)*

Recebe a requisição do frontend, aceita tanto `terreno_id` (busca no PostgreSQL) quanto `coordenadas_poligono`, `nome_propriedade` e `prioridades` enviados diretamente no JSON sem exigir cadastro prévio, e injeta `INASADataProvider` (`services/geospatial.py`), `GAEZDataProvider` (`services/gaez_service.py` — quando `GAEZ_ENABLED=true` ou `perfil_climatico="real"`), `CropSimulator` (`services/ml_models.py`) e `RotationExplainerAgent` (`services/llm_agent.py`), retornando as estratégias de rotação sugeridas (com `score_breakdown` e explicação por estratégia).

**Request Body (com `terreno_id` cadastrado ou com coordenadas diretas no JSON):**
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
> **Observação:** `terreno_id` é opcional se forem enviadas `coordenadas_poligono`/`prioridades` diretamente no payload (neste caso `terreno_id` retorna `null`). `perfil_climatico` aceita `normal`, `seca`, `chuva_extrema`, `onda_de_calor` ou `real`. Caso `cultura_id` e `nome_cultura` sejam omitidos, o controlador seleciona automaticamente a estratégia de maior viabilidade retornada por `CropSimulator.simulate_rotation_strategies()`.

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
    "Adequação do ciclo de Feijão Carioca ao planejamento da propriedade",
    "Aproveitamento dos dados ambientais para manejo preventivo de recursos"
  ],
  "riscos_identificados": [
    "Terreno com prioridade hídrica 'escassa' frente ao consumo estimado de 450 mm"
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

## [M4] Calendário de Atividades do Cultivo (`backend/api/calendario.py`)

O módulo utiliza o modelo `Activity` (`atividades_calendario`), que pode ser vinculado a um `terreno_id`, a um `usuario_id` ou a ambos, mantendo `status` (`pendente` / `concluida`) sincronizado com `concluida` (`bool`).

### `POST /api/v1/calendario/atividades` (`201 Created`)
Cria uma atividade diária programada no calendário (requer `terreno_id` ou `usuario_id`).

**Request Body:**
```json
{
  "terreno_id": 1,
  "usuario_id": 1,
  "cultura_id": null,
  "titulo": "Irrigação matinal dos canteiros",
  "descricao": "Aplicar lâmina leve de água antes das 9h",
  "tipo_atividade": "irrigacao",
  "data_programada": "2026-11-20",
  "prioridade": "alta",
  "status": "pendente"
}
```
Tipos suportados: `plantio`, `irrigacao`, `adubacao`, `manejo`, `colheita`, `inspecao`.  
Prioridades: `baixa`, `media`, `alta`, `critica`.  
Status válidos: `pendente`, `concluida`.

### `POST /api/v1/calendario/gerar-cronograma` (`201 Created`)
Gera automaticamente o cronograma inicial de um ciclo (plantio, irrigação inicial, inspeção fitossanitária, adubação de cobertura e colheita).

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
Lista atividades ordenadas por `data_programada` e `id`, com ênfase na consulta por período.  
**Query Params opcionais:** `terreno_id`, `usuario_id`, `status` (`pendente` / `concluida`), `concluida`, `tipo_atividade`, `data_inicio`, `data_fim`.

### `GET /api/v1/calendario/atividades/{atividade_id}` (`200 OK`)
Retorna os detalhes de uma atividade específica.

### `PATCH /api/v1/calendario/atividades/{atividade_id}/status` (`200 OK`)
*(Também disponível em `PATCH /api/v1/calendario/atividades/{atividade_id}/concluir`)*

Atualiza o status da atividade entre `pendente` e `concluida`, atualizando automaticamente `concluida` e `data_conclusao`.

**Request Body:**
```json
{
  "status": "concluida"
}
```
*(Aceita alternativamente `{"concluida": true}` ou `{"concluida": false}`).*

### `PUT /api/v1/calendario/atividades/{atividade_id}` (`200 OK`)
Atualiza parcialmente ou integralmente uma atividade programada.

### `DELETE /api/v1/calendario/atividades/{atividade_id}` (`204 No Content`)
Remove uma atividade do calendário.

---

## [M5] Alertas Climáticos e Background Tasks (`backend/api/alertas.py`)

### `POST /api/v1/alertas/monitorar` / `POST /api/v1/alertas/monitorar-clima` (`202 Accepted`)
Além do agendador periódico iniciado automaticamente no `lifespan` do FastAPI (configurável via `ALERT_MONITOR_INTERVAL_HOURS`, padrão `6` horas), estes endpoints permitem disparar sob demanda em segundo plano (`FastAPI BackgroundTasks`) um ciclo da rotina `executar_ciclo_monitoramento_alertas()` (`backend/services/alert_tasks.py`), que consulta dados climáticos (`services/mock_nasa_data.py`), executa `ClimateAnomalyDetector.detect_extremes()` e, caso anomalias sejam detectadas, persiste automaticamente um `AlertaClimatico` no banco (com `orientacao_pratica` via `explain_alert`) e adapta o calendário `[M4]`. Aceita opcionalmente `"perfil_climatico"` (`normal`, `seca`, `chuva_extrema`, `onda_de_calor`) para disparo imediato de cenários na demo.

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
  "mensagem": "Monitoramento climático em segundo plano agendado (janela configurada de 6h, perfil 'chuva_extrema').",
  "intervalo_horas": 6,
  "terreno_id": 1,
  "perfil_climatico": "chuva_extrema"
}
```

### `POST /api/v1/alertas/gatilho` (`202 Accepted`)
Recebe gatilhos explícitos de algoritmos de ML (ou dados NASA/manuais), aciona opcionalmente `ClimateAnomalyDetector.detect_extremes()`, grava o alerta e agenda em segundo plano a função `processar_alerta_e_adaptar_calendario()` para adaptar as tarefas pendentes na janela `[data_evento, data_evento + 3 dias]`.

**Request Body:**
```json
{
  "terreno_id": 1,
  "tipo_evento": "chuva_intensa",
  "severidade": "alta",
  "data_evento": "2026-11-20",
  "titulo": "Alerta de precipitação intensa",
  "mensagem": "Previsão de chuva acima de 70 mm nas próximas 48 horas.",
  "origem_gatilho": "ml_anomaly_detector",
  "serie_temporal_clima": [
    {"data": "2026-11-19", "precipitacao_mm": 12.0, "temp_max_c": 29.0},
    {"data": "2026-11-20", "precipitacao_mm": 78.5, "temp_max_c": 23.0}
  ],
  "dias_adiamento": 2
}
```

### `GET /api/v1/alertas/` (`200 OK`)
Lista alertas climáticos ordenados por `data_evento` decrescente.  
**Query Params opcionais:** `terreno_id`, `lido`, `severidade`, `tipo_evento`.

### `GET /api/v1/alertas/resumo-nao-lidos` (`200 OK`)
Retorna `total_nao_lidos` e agrupamento `por_terreno` (incluindo contagem de críticos não lidos e último evento) para o painel do produtor (`terreno_id` opcional).

### `GET /api/v1/alertas/{alerta_id}` (`200 OK`)
Obtém os detalhes do alerta, `orientacao_pratica` e o campo `resumo_adaptacao`.

### `PATCH /api/v1/alertas/{alerta_id}/ler` (`200 OK`)
Marca o alerta como lido (`"lido": true`).

---

## [M6] Relatórios Periódicos e Histórico de Métricas (`backend/api/relatorios.py`)

### `GET /api/v1/relatorios/terreno/{terreno_id}` (`200 OK`)
*(Também acessível em `GET /api/v1/relatorios/?terreno_id=...`)*

Consolida o relatório periódico de adaptação para o terreno (`data_inicio` e `data_fim` opcionais, padrão últimos 30 dias):
- Série histórica de umidade, temperatura, precipitação e indicador de solo exposto (`metricas_historicas_terreno`). Se não houver snapshots gravados no período, consulta `INASADataProvider.extract_field_metrics()` sob demanda e persiste a série.
- Índices calculados de **vigor** (`indice`, `classificacao`, `tendencia`) e **vulnerabilidade** (`indice`, `nivel`, `fatores_risco`).
- Contabilização de **adaptações** no calendário (`ajustada_por_alerta == true`) e alertas climáticos do período.
- **Comparativo do período** (`comparativo_periodo`): variações entre a primeira e a última medição da série histórica (`umidade_inicial`/`umidade_final`, `variacao_umidade`, `variacao_umidade_percentual`, temperatura, precipitação e `tendencia_geral`).
- **Resumo interpretativo da IA** (`resumo_ia` e `explicacao_ia`): síntese em linguagem simples gerada via `RotationExplainerAgent.explain_report()` (com fallback determinístico offline), sempre concluída com o aviso legal (`DISCLAIMER`).

### `GET /api/v1/relatorios/terreno/{terreno_id}/metricas` (`200 OK`)
Lista os snapshots diários persistidos para o terreno com filtro opcional por `data_inicio` e `data_fim`.

### `POST /api/v1/relatorios/terreno/{terreno_id}/metricas` (`201 Created`)
Permite registrar manualmente uma medição climática ou acionar a sincronização via `INASADataProvider` quando o corpo JSON é omitido.

---

## [Demo] Seed de Demonstração (`backend/api/demo.py`)

### `POST /api/v1/demo/seed` (`200 OK`)
*(Query param opcional: `reset=false|true`)*

Popula o ambiente de demonstração completo em uma única chamada (usuário padrão, culturas/rotações seed e customizada, dois terrenos com perfis climáticos da A9 — `seca` e `chuva_extrema` — extraídos via `MockNASADataProvider`, métricas históricas alinhadas ao período recente, atividades no calendário com registros `ajustada_por_alerta=true` e alertas climáticos com explicação prática):
- `reset=false` *(padrão)*: operação **idempotente** que cria apenas o que ainda não existir, preservando IDs e contagens entre chamadas consecutivas.
- `reset=true`: remove e recria do zero os dados associados aos terrenos de demonstração.

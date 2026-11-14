# Especificações Técnicas (Specs)

Prefixo base da API: `/api/v1`  
Documentação interativa automática (Swagger UI): `GET /docs`

---

## [M1] Terrenos (`backend/api/terreno.py`)

### `POST /api/v1/terrenos/`
Cria um novo terreno com o polígono geográfico e prioridades do produtor.

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

**Response (`200 OK`):** Retorna os dados do terreno criado acrescidos de `"id"`.

---

## [M3] Simulador de Culturas e Rotações (`backend/api/simulacao.py`)

### `POST /api/v1/simulacoes/`
Recebe a requisição do frontend, consulta o terreno/cultura no banco, aciona `NasaDataProcessor` (`services/geospatial.py`), `CropSimulator` (`services/ml_models.py`) e `RotationExplainerAgent` (`services/llm_agent.py`), devolvendo o JSON estruturado da simulação.

**Request Body:**
```json
{
  "terreno_id": 1,
  "cultura_id": null,
  "nome_cultura": "Feijão Carioca",
  "culturas_rotacao": ["Milho", "Crotalária"],
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
> **Observação:** Deve ser informado `cultura_id` ou `nome_cultura` (caso contrário retorna `400 Bad Request`).

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
    "origem": "fallback_geoespacial",
    "total_vertices_poligono": 3,
    "centroide": {"lat": -23.5515, "lng": -46.6333},
    "precipitacao_estimada_mm": 480.0,
    "temperatura_media_c": 26.0,
    "umidade_solo_estimada": 0.42
  },
  "beneficios_esperados": [
    "Adequação do ciclo de Feijão Carioca ao planejamento da propriedade",
    "Aproveitamento dos dados ambientais para manejo preventivo de recursos",
    "Diversificação produtiva com rotação envolvendo Milho, Crotalária"
  ],
  "riscos_identificados": [
    "Terreno com prioridade hídrica 'escassa' frente ao consumo estimado de 450 mm"
  ],
  "explicacao_ia": "...",
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

### `POST /api/v1/calendario/atividades` (`201 Created`)
Cria uma atividade diária programada no calendário do terreno.

**Request Body:**
```json
{
  "terreno_id": 1,
  "cultura_id": null,
  "titulo": "Irrigação matinal dos canteiros",
  "descricao": "Aplicar lâmina leve de água antes das 9h",
  "tipo_atividade": "irrigacao",
  "data_programada": "2026-11-20",
  "prioridade": "alta"
}
```
Tipos suportados: `plantio`, `irrigacao`, `adubacao`, `manejo`, `colheita`, `inspecao` (e quaisquer categorias operacionais adicionais).  
Prioridades: `baixa`, `media`, `alta`, `critica`.

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
Lista atividades ordenadas por `data_programada` e `id`.  
**Query Params opcionais:** `terreno_id`, `concluida`, `tipo_atividade`, `data_inicio`, `data_fim`.

### `GET /api/v1/calendario/atividades/{atividade_id}` (`200 OK`)
Retorna os detalhes de uma atividade específica.

### `PATCH /api/v1/calendario/atividades/{atividade_id}/concluir` (`200 OK`)
Marca ou desmarca uma atividade como `"concluída"` pelo agricultor (preenche `data_conclusao` automaticamente).

**Request Body:**
```json
{
  "concluida": true
}
```

### `PUT /api/v1/calendario/atividades/{atividade_id}` (`200 OK`)
Atualiza parcialmente ou integralmente uma atividade programada.

### `DELETE /api/v1/calendario/atividades/{atividade_id}` (`204 No Content`)
Remove uma atividade do calendário.

---

## [M5] Alertas Climáticos e Background Tasks (`backend/api/alertas.py`)

### `POST /api/v1/alertas/gatilho` (`202 Accepted`)
Recebe gatilhos de algoritmos de ML (ou dados NASA/manuais), aciona opcionalmente `ClimateAnomalyDetector.detect_extremes()`, grava o alerta e agenda em segundo plano (`BackgroundTasks`) a função `processar_alerta_e_adaptar_calendario()` para adaptar as tarefas pendentes na janela `[data_evento, data_evento + 3 dias]`.

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

**Response (`202 Accepted`):**
```json
{
  "status": "accepted",
  "mensagem": "Alerta registrado e rotina de adaptação do calendário agendada em segundo plano.",
  "alerta": {
    "id": 1,
    "terreno_id": 1,
    "tipo_evento": "chuva_intensa",
    "severidade": "alta",
    "titulo": "Alerta de precipitação intensa",
    "mensagem": "Previsão de chuva acima de 70 mm nas próximas 48 horas.",
    "data_evento": "2026-11-20",
    "origem_gatilho": "ml_anomaly_detector",
    "dados_gatilho": { "...": "..." },
    "processado_background": false,
    "resumo_adaptacao": null,
    "lido": false,
    "criado_em": "2026-11-14T11:05:00"
  }
}
```
> Após a conclusão da `BackgroundTask`, `processado_background` passa para `true` e `resumo_adaptacao` detalha as atividades ajustadas e criadas no módulo `[M4]`.

### `GET /api/v1/alertas/` (`200 OK`)
Lista alertas climáticos ordenados por `data_evento` descrescente.  
**Query Params opcionais:** `terreno_id`, `lido`, `severidade`, `tipo_evento`.

### `GET /api/v1/alertas/{alerta_id}` (`200 OK`)
Obtém os detalhes do alerta e o campo `resumo_adaptacao`.

### `PATCH /api/v1/alertas/{alerta_id}/ler` (`200 OK`)
Marca o alerta como lido (`"lido": true`).

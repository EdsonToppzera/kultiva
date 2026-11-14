# Arquitetura do Sistema

Este documento descreve a modelagem relacional do banco de dados (PostgreSQL/SQLAlchemy) e a orquestração entre os módulos da API **Kultiva**.

## 1. Modelagem do Banco de Dados (DER)

```mermaid
erDiagram
    usuarios ||--o{ terrenos : possui
    terrenos ||--o{ atividades_calendario : agenda
    culturas ||--o{ atividades_calendario : referencia
    terrenos ||--o{ alertas_climaticos : recebe

    usuarios {
        int id PK
        string nome
        string email
    }

    terrenos {
        int id PK
        string nome_propriedade
        int usuario_id FK
        json coordenadas_poligono
        json prioridades
    }

    culturas {
        int id PK
        string nome
        float consumo_agua_mm
        int tempo_colheita_dias
    }

    atividades_calendario {
        int id PK
        int terreno_id FK
        int cultura_id FK
        string titulo
        text descricao
        string tipo_atividade
        date data_programada
        string prioridade
        boolean concluida
        datetime data_conclusao
        boolean ajustada_por_alerta
        string motivo_ajuste
        datetime criado_em
    }

    alertas_climaticos {
        int id PK
        int terreno_id FK
        string tipo_evento
        string severidade
        string titulo
        text mensagem
        date data_evento
        string origem_gatilho
        json dados_gatilho
        boolean processado_background
        text resumo_adaptacao
        boolean lido
        datetime criado_em
    }
```

## 2. Orquestração do Simulador de Culturas e Rotações (M3)

O controlador `backend/api/simulacao.py` atua como camada de orquestração síncrona para a requisição do frontend:

```mermaid
flowchart LR
    FE["Frontend (PWA)"] -->|"POST /api/v1/simulacoes/"| M3["Controlador M3 (backend/api/simulacao.py)"]
    M3 -->|"Consulta Terreno e Cultura"| DB[("PostgreSQL (SQLAlchemy)")]
    M3 -->|"extract_field_metrics()"| GEO["NasaDataProcessor (services/geospatial.py)"]
    M3 -->|"predict_rotation_viability()"| ML["CropSimulator (services/ml_models.py)"]
    M3 -->|"generate_explanation()"| LLM["RotationExplainerAgent (services/llm_agent.py)"]
    M3 -->|"JSON SimulacaoResponse"| FE
```

- **Resiliência (Graceful Fallback):** Caso os dados geoespaciais NetCDF ou a chave de API do provedor LLM ainda não estejam disponíveis no ambiente de execução, o controlador aplica fallbacks determinísticos para manter o contrato JSON estável para o frontend.

## 3. Fluxo Assíncrono de Alertas Climáticos e Calendário Maleável (M4 e M5)

Para manter o ambiente containerizado enxuto (sem necessidade de broker externo no `docker-compose.yml` atual), os alertas `[M5]` utilizam `FastAPI BackgroundTasks` encapsuladas em `backend/services/alert_tasks.py`:

```mermaid
flowchart TD
    ML["Gatilho ML / NASA / Sensor"] -->|"POST /api/v1/alertas/gatilho"| API["Endpoint Alertas M5 (backend/api/alertas.py)"]
    API -->|"detect_extremes() opcional"| DET["ClimateAnomalyDetector (services/ml_models.py)"]
    API -->|"1. Persiste AlertaClimatico"| DB[("PostgreSQL")]
    API -->|"2. Retorna HTTP 202 Accepted"| ML
    API -->|"3. Agenda BackgroundTask"| TASK["processar_alerta_e_adaptar_calendario()"]
    TASK -->|"Abre sessão própria (SessionLocal)"| DB
    TASK -->|"Adia/Ajusta/Cria AtividadeCalendario (M4)"| DB
```

### Regras de Adaptação Dinâmica do Calendário
1. **`chuva_intensa` / `tempestade` / `heavy_rain`**:
   - Adia atividades pendentes de `irrigacao`, `adubacao` e `pulverizacao` na janela do evento em `dias_adiamento` dias (padrão `2` dias).
   - Cria atividade de `inspecao` para verificação de drenagem e escoamento pós-chuva.
2. **`onda_de_calor` / `seca` / `heatwave` / `drought`**:
   - Eleva a prioridade de atividades pendentes de `irrigacao` na janela para `critica`.
   - Cria atividade emergencial de `irrigacao` suplementar e proteção térmica do solo na data do evento.
3. **`geada` / `vendaval` / `frost` / `windstorm` (e demais extremos)**:
   - Adia atividades pendentes de `plantio` e `adubacao` na janela em `dias_adiamento` dias.
   - Cria atividade de `manejo` emergencial para proteção da lavoura.

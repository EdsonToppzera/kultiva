# Arquitetura do Sistema

Este documento descreve a modelagem relacional do banco de dados (PostgreSQL/SQLAlchemy) e a orquestração entre os módulos da API **Kultiva**.

## 1. Modelagem do Banco de Dados (DER)

```mermaid
erDiagram
    usuarios ||--o{ terrenos : possui
    usuarios ||--o{ atividades_calendario : acompanha
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
        int usuario_id FK
        int cultura_id FK
        string titulo
        text descricao
        string tipo_atividade
        date data_programada
        string prioridade
        string status
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

> **Nota de modelagem:** A tabela `atividades_calendario` é mapeada pela classe `Activity` (`backend/db/models.py`, com alias `AtividadeCalendario`) permitindo vínculo direto a um `Terreno` ou `Usuario`, além do campo textual `status` (`pendente` / `concluida`) sincronizado com `concluida` e `data_conclusao`.

## 2. Orquestração do Simulador de Culturas e Rotações (M3)

O controlador `backend/api/simulacao.py` atua como camada de orquestração síncrona via injeção de dependências (`Depends`) para o endpoint `POST /api/v1/simular-rotacao` (também exposto em `/api/v1/simulacoes/`):

```mermaid
flowchart LR
    FE["Frontend (PWA)"] -->|"POST /api/v1/simular-rotacao"| M3["Controlador M3 (backend/api/simulacao.py)"]
    M3 -->|"Consulta Terreno e Cultura"| DB[("PostgreSQL (SQLAlchemy)")]
    M3 -->|"extract_field_metrics()"| GEO["NasaDataProcessor (services/geospatial.py)"]
    M3 -->|"simulate_rotation_strategies() e predict_rotation_viability()"| ML["CropSimulator (services/ml_models.py)"]
    M3 -->|"generate_explanation() (Gemini / FakeListLLM)"| LLM["RotationExplainerAgent (services/llm_agent.py)"]
    M3 -->|"JSON SimulacaoResponse"| FE
```

- **Resiliência (Graceful Fallback) e Flexibilidade de Entrada:** O controlador aceita tanto `terreno_id` (buscando no banco) quanto `coordenadas_poligono` e `prioridades` enviados diretamente no JSON sem exigir cadastro prévio. Caso dados geoespaciais NetCDF ou pacotes científicos opcionais não estejam presentes no ambiente de execução, o controlador aplica fallbacks determinísticos para manter o contrato JSON estável para o frontend.

## 3. Fluxo Assíncrono de Alertas Climáticos e Calendário Maleável (M4 e M5)

Para manter o ambiente containerizado enxuto (sem necessidade de broker externo no `docker-compose.yml` atual), os alertas `[M5]` utilizam `FastAPI BackgroundTasks` e o ciclo de vida (`lifespan`) nativo do FastAPI em `backend/services/alert_tasks.py` (`lifespan_monitoramento_alertas`), que inicia automaticamente o agendador periódico em segundo plano no startup da aplicação (configurável via variável de ambiente `ALERT_MONITOR_INTERVAL_HOURS`, padrão `6` horas):

```mermaid
flowchart TD
    MON["Rotina Periódica (6h / 12h) ou POST /api/v1/alertas/monitorar"] -->|"Coleta dados climáticos"| MOCK["generate_synthetic_netcdf() (services/mock_nasa_data.py)"]
    MOCK -->|"Série / métricas"| DET["ClimateAnomalyDetector (services/ml_models.py)"]
    ML["Gatilho ML / NASA / Sensor"] -->|"POST /api/v1/alertas/gatilho"| API["Endpoint Alertas M5 (backend/api/alertas.py)"]
    API -->|"detect_extremes()"| DET
    DET -->|"Anomalia detectada"| PERSIST["Persiste AlertaClimatico no PostgreSQL"]
    API -->|"Retorna HTTP 202 Accepted"| ML
    PERSIST -->|"Agenda / Executa BackgroundTask"| TASK["processar_alerta_e_adaptar_calendario()"]
    TASK -->|"Abre sessão própria (SessionLocal)"| DB[("PostgreSQL")]
    TASK -->|"Adia/Ajusta/Cria Activity (M4)"| DB
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

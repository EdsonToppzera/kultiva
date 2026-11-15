# Arquitetura do Sistema

Este documento descreve a modelagem relacional do banco de dados (PostgreSQL/SQLAlchemy) e a orquestração entre os módulos da API **Kultiva**.

## 1. Modelagem do Banco de Dados (DER)

```mermaid
erDiagram
    usuarios ||--o{ terrenos : possui
    usuarios ||--o{ culturas : personaliza
    usuarios ||--o{ rotacoes_produtor : define
    usuarios ||--o{ atividades_calendario : acompanha
    terrenos ||--o{ rotacoes_produtor : prefere
    terrenos ||--o{ metricas_historicas_terreno : registra
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
        boolean is_seed
        boolean customizada
        int usuario_id FK
    }

    rotacoes_produtor {
        int id PK
        string nome
        json culturas
        int usuario_id FK
        int terreno_id FK
        boolean preferencial
        boolean is_seed
    }

    metricas_historicas_terreno {
        int id PK
        int terreno_id FK
        date data_medicao
        float soil_moisture
        float surface_temp_c
        float precipitation_mm
        boolean is_bare_field_period
        string data_quality
        string origem
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

## 2. Arquitetura Geoespacial em 2 Camadas (Estratégica FAO GAEZ v5 + Operacional NASA)

Para unir adequação estrutural de longo prazo ao território brasileiro com monitoramento climático contínuo em tempo real, o backend separa a coleta de dados em duas camadas complementares:

1. **Camada Estratégica (`backend/services/gaez_service.py` — ~10 km / 5 arc-min):**
   - `GAEZDataProvider` acessa **diretamente** via HTTP Range Requests os rasters Cloud-Optimized GeoTIFF (COG) públicos do **FAO GAEZ v5** (`RES05-SUX` / `RES05-YLX` *Suitability and Attainable Yield*, projeção `CMIP6 FP2140 SSP370`, solo `HWSDV201`, qualidade `SQX.SQ0`, fator limitante `SQ-IDX` e declividade `SLOPE-MED`), escolhendo entre os 4 regimes de manejo (`LRLM`, `HRLM`, `LILM`, `HILM`) pelas prioridades do produtor e mantendo cache local em `data/gaez_cache/`.
   - **Política sem fallbacks inventados:** quando o serviço GAEZ não responde, retorna explicitamente `data_quality="no_data"` (HTTP `503` em `GET /api/v1/culturas/aptidao-gaez`).
2. **Camada Operacional (`backend/services/geospatial.py`):**
   - `INASADataProvider` (`MockNASADataProvider` com perfis simuláveis ou `RealNASADataProvider` via `data/real/`, Earthdata `SPL3SMP_E`, `ECO2LSTE`, `GPM_3IMERGDF`, `MOD13Q1` e fallback público **NASA POWER**) fornece séries recentes de umidade, temperatura superficial, precipitação e solo descoberto.

## 3. Orquestração do Simulador de Culturas e Rotações (M3)

O controlador `backend/api/simulacao.py` atua como camada de orquestração síncrona via injeção de dependências (`Depends`) para o endpoint `POST /api/v1/simular-rotacao` (também exposto em `/api/v1/simulacoes/`):

```mermaid
flowchart LR
    FE["Frontend (PWA)"] -->|"POST /api/v1/simular-rotacao"| M3["Controlador M3 (backend/api/simulacao.py)"]
    M3 -->|"Consulta Terreno e Cultura"| DB[("PostgreSQL (SQLAlchemy)")]
    M3 -->|"Camada Operacional: extract_field_metrics()"| GEO["INASADataProvider (services/geospatial.py)"]
    M3 -->|"Camada Estratégica: extract_gaez_metrics()"| GAEZ["GAEZDataProvider (services/gaez_service.py -> FAO COG)"]
    GEO -->|"Série temporal + clima atual"| ML
    GAEZ -->|"Suitability, Yield kg/ha, HWSD, CMIP6"| ML["CropSimulator (RandomForest + GAEZ em ml_models.py)"]
    ML -->|"3 estratégias + score_breakdown"| LLM["RotationExplainerAgent (Gemini / FakeListLLM em llm_agent.py)"]
    M3 -->|"JSON SimulacaoResponse"| FE
```

- **Resiliência e Flexibilidade de Entrada:** O controlador aceita tanto `terreno_id` (buscando no banco) quanto `coordenadas_poligono` e `prioridades` enviados diretamente no JSON sem exigir cadastro prévio. Na camada operacional NASA, caso dados NetCDF ou pacotes opcionais não estejam disponíveis, aplica fallback seguro para manter o contrato JSON estável; já a camada FAO GAEZ v5 só enriquece a simulação quando os dados reais do COG/cache estão disponíveis (`GAEZ_ENABLED=true` ou `perfil_climatico="real"`).

## 4. Fluxo Assíncrono de Alertas Climáticos e Calendário Maleável (M4 e M5)

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

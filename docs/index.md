# Kultiva — Documentação Técnica e Contexto do Projeto

**Kultiva** é um sistema de apoio à decisão para pequenos produtores rurais, desenvolvido para o NASA Space Apps Challenge. A plataforma une dados geoespaciais de satélite da NASA, modelos de Machine Learning e agentes de IA generativa (Google Gemini) para planejar rotações de culturas resilientes às mudanças climáticas.

O projeto visa democratizar o acesso à tecnologia avançada, traduzindo dados complexos em recomendações práticas, interativas e de fácil compreensão.

---

## 🎯 Visão Geral e Público-Alvo

O **Kultiva** é uma ferramenta de auxílio na tomada de decisões acerca da rotação de culturas. A interface permite simular rotações com base nas prioridades do agricultor, interligando essas informações aos dados da NASA e fornecendo sugestões de modificação, se necessário. Após definido o plantio, é emitido um calendário de todo o período de cultivo, com atividades diárias programadas para manter o bem-estar da plantação, que podem ser marcadas como "concluídas".

Como as bases da NASA são atualizadas periodicamente, o projeto visa manter alertas constantes e modificação do calendário, se necessário, com base em mudanças climáticas capturadas por essas atualizações.

*   **Público-alvo:** Pequenos agricultores comerciais ou agricultura familiar.
*   **Perfil:** Indivíduos que tendem a não possuir muitas ferramentas tecnológicas ou alto conhecimento técnico para manter o monitoramento constante e a adaptação da plantação a adversidades. Por isso, a linguagem do sistema (IA) é sempre acessível e transparente.

---

## 🧩 Módulos do Sistema

O sistema é dividido em 6 módulos principais, categorizados por prioridade de implementação:

| Módulo | Descrição | Prioridade | Regras de Negócio Específicas |
| :--- | :--- | :--- | :--- |
| **[M1]** | Criação e cadastro geográfico do terreno | Obrigatório | Coleta o polígono/coordenadas da propriedade e as prioridades do agricultor (ex: economia de água). |
| **[M2]** | Sugestões de culturas e rotações | Obrigatório | Deve permitir a inclusão de culturas/rotações da preferência do próprio produtor no catálogo. |
| **[M3]** | Simulador de culturas e rotações | Obrigatório* | Compara e retorna **pelo menos 3 estratégias** de rotação, incluindo a prática atual do agricultor. |
| **[M4]** | Calendário com atividades diárias | Opcional | Permite marcar tarefas como "concluídas". O calendário possui rotina **maleável** a eventos climáticos. |
| **[M5]** | Alertas de mudanças climáticas | Opcional | Background tasks monitoram anomalias (ondas de calor, chuvas) para engatilhar adaptações no [M4]. |
| **[M6]** | Relatórios periódicos de adaptação | Opcional | Monitoramento de longo prazo do vigor das culturas e vulnerabilidade do terreno. |

---

## 🧠 Inteligência e Dados da NASA

Para atender à realidade do Brasil e manter a modularidade, o Kultiva adotou as seguintes estratégias:

1. **Dados Globais da NASA (Adaptação para o Brasil):**
   - **SMAP:** Umidade do solo.
   - **ECOSTRESS:** Temperatura da superfície e evapotranspiração (ondas de calor).
   - **GPM / IMERG:** Precipitação e alertas de chuvas extremas.
   - *Padrão de Projeto:* Utilização do padrão *Adapter/Interface* (`INASADataProvider`). O sistema funciona offline no desenvolvimento com dados sintéticos (`MockNASADataProvider` e arquivos `.nc`) gerados via `xarray`, `rioxarray` e `geopandas`, mas está pronto para a API real.

2. **Machine Learning (`ml_models.py`):**
   - **CropSimulator:** Processa as métricas extraídas do polígono do usuário cruzando com as prioridades informadas, retornando as 3 estratégias de viabilidade exigidas pelo [M3].
   - **ClimateAnomalyDetector:** Utiliza *IsolationForest* ou thresholds baseados no ECOSTRESS/GPM para disparar os alertas do [M5].

3. **IA Generativa / LangChain (`llm_agent.py`):**
   - **Modelo:** Google Gemini (`gemini-1.5-flash`) via `langchain-google-genai`.
   - **Função:** Traduzir os resultados matemáticos do ML para uma linguagem acessível e humana.
   - **Regra de Segurança Mandatória:** O prompt do LLM exige que toda explicação termine com um aviso claro de que *a ferramenta serve para apoiar a decisão, mas nunca substitui o julgamento do agricultor ou sua experiência local*.

---

## 🛠️ Stack Tecnológica

O backend do sistema aplica o padrão MVC/Service-Layer e isola a lógica de IA/Dados (`backend/services/`) das rotas da API (`backend/api/`).

- **Linguagem:** Python 3.11-slim
- **API & Web Framework:** FastAPI + Uvicorn
- **Banco de Dados & ORM:** PostgreSQL 15 + SQLAlchemy (`psycopg2-binary`) + Pydantic (Validação)
- **Dados Geoespaciais:** Xarray, NetCDF4, Rasterio, Rioxarray, GeoPandas, Shapely, Pandas
- **Machine Learning & IA:** Scikit-Learn, LangChain (`langchain-google-genai`, `langchain-core`)
- **Infraestrutura:** Docker e Docker Compose (`.env` para gerenciamento de chaves como `GOOGLE_API_KEY`)

---

## 🚀 Como Rodar Localmente

Suba os serviços da API e do PostgreSQL com Docker Compose. Certifique-se de que os dados sintéticos da NASA (`.nc`) foram gerados para a pasta `data/` se for testar a extração geoespacial.

```bash
docker-compose up --build
```

Após iniciar os containers:

- **API Base:** `http://localhost:8000`
- **Health Check:** `GET http://localhost:8000/health`
- **Swagger UI (OpenAPI):** `http://localhost:8000/docs`

---

## 📂 Navegação Rápida

- [Requisitos e Regras de Negócio](Requisitos/README.md) — Escopo funcional dos módulos `[M1]` a `[M6]`.
- [Arquitetura do Sistema](Arquitetura/README.md) — Modelagem do banco de dados (DER) e fluxos de orquestração síncrona e em segundo plano.
- [Especificações Técnicas (Specs)](Specs/README.md) — Contratos REST, parâmetros de consulta e payloads JSON dos endpoints.
- [Design e UI/UX](Design/README.md) — Diretrizes de interface Mobile-First, Offline-First (PWA) e ativos visuais.

---

## 🗺️ Roadmap e Próximos Passos

### Fase 1 — Inteligência e Dados Geoespaciais (`backend/services/`)
1. **Lógica Dinâmica no Simulador [M3] (`backend/services/ml_models.py`):**
   - Evoluir `CropSimulator.simulate_rotation_strategies` e `predict_rotation_viability` de retornos estáticos para cálculo dinâmico ponderando `avg_soil_moisture_smap`, `avg_surface_temp_ecostress`, precipitação e `farmer_priorities` (ex.: conservação de água), preparando a base para modelos treinados (`RandomForest`/`XGBoost`).
2. **Detecção de Anomalias Climáticas [M5] (`backend/services/ml_models.py`):**
   - Implementar `ClimateAnomalyDetector.detect_extremes(time_series_data)` usando `IsolationForest` e limiares de calor/chuva extrema para integrar diretamente com `_executar_detector_anomalias` em `backend/api/alertas.py`.
3. **Cobertura GPM/IMERG e Provedor Real (`backend/services/mock_nasa_data.py` e `backend/services/geospatial.py`):**
   - Incluir geração e recorte espacial (`.rio.clip()`) de precipitação (`gpm_mock.nc`) e detecção de solo exposto (`is_bare_field_period`) no `MockNASADataProvider`.
   - Implementar `RealNASADataProvider` para ingestão real via NASA Earthdata (`earthaccess` e `xr.open_mfdataset`).

### Fase 2 — Fechamento dos Módulos Funcionais (`[M1]` a `[M6]`)
4. **Catálogo do Produtor [M2]:**
   - Criar rotas CRUD para que o próprio agricultor cadastre culturas e rotações preferenciais no banco, expandindo o catálogo além do `seed_culturas` inicial em `backend/main.py`.
5. **Orquestração Contínua [M4] + [M5] (`backend/services/alert_tasks.py`):**
   - Conectar o ciclo `executar_ciclo_monitoramento_alertas` às métricas extraídas pelo `INASADataProvider` e às predições do `ClimateAnomalyDetector`, disparando ajustes automáticos no calendário de atividades.
6. **Relatórios Periódicos [M6]:**
   - Implementar serviço e endpoints de relatório consolidando histórico de umidade/temperatura do terreno, vigor das culturas e histórico de adaptações realizadas no calendário.

### Fase 3 — Qualidade, Testes e Configuração
7. **Execução e Ampliação da Suíte de Testes:**
   - Adicionar `pytest` e `httpx` às dependências de desenvolvimento/container para executar `backend/tests/test_m3_m4_m5.py` e incluir testes unitários diretos para `MockNASADataProvider.extract_field_metrics` (`.rio.clip()`), `CropSimulator` e `ClimateAnomalyDetector`.
8. **Configuração do Gemini e Ambiente:**
   - Criar `.env.example` documentando `GOOGLE_API_KEY` e manter alinhada a versão do modelo configurada em `backend/services/llm_agent.py` e documentada em `docs/index.md`.

### Fase 4 — Frontend (Mobile-First / Offline-First PWA)
9. **Integração com a UI do Agricultor:**
   - Conectar o frontend ao fluxo `[M1] -> [M3] -> [M4]/[M5]` (desenho do polígono no mapa, exibição comparativa das 3 estratégias com explicação em linguagem acessível e checklist diário de manejo).

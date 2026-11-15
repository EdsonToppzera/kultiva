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
   - *Padrão de Projeto:* Utilização do padrão *Adapter/Interface* (`INASADataProvider` + fábrica `get_nasa_data_provider`). No desenvolvimento offline, `MockNASADataProvider` lê arquivos NetCDF sintéticos (`.nc`) via `xarray`, `rioxarray` e `geopandas` com suporte a perfis climáticos simuláveis (`normal`, `seca`, `chuva_extrema`, `onda_de_calor` via `NASA_MOCK_PROFILE`). Para ingestão real via NASA Earthdata, `RealNASADataProvider` é ativado via `NASA_PROVIDER=real`.

2. **Machine Learning (`ml_models.py`):**
   - **CropSimulator:** Processa as métricas extraídas do polígono do usuário cruzando com as prioridades informadas, retornando as 3 estratégias de viabilidade exigidas pelo [M3].
   - **ClimateAnomalyDetector:** Utiliza *IsolationForest* ou thresholds baseados no ECOSTRESS/GPM para disparar os alertas do [M5].

3. **IA Generativa / LangChain (`llm_agent.py`):**
   - **Modelo:** Google Gemini (`gemini-2.5-flash`, configurável via `GEMINI_MODEL`) via `langchain-google-genai`.
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

Copie o arquivo `.env.example` para `.env` (ajuste `NASA_MOCK_PROFILE`, `CORS_ALLOWED_ORIGINS` ou `GOOGLE_API_KEY` se desejar) e suba a API + PostgreSQL com Docker Compose:

```bash
cp .env.example .env
docker-compose up --build
```

Após iniciar os containers:

- **API Base:** `http://localhost:8000`
- **Health Check:** `GET http://localhost:8000/health`
- **Swagger UI (OpenAPI):** `http://localhost:8000/docs`
- **Seed de Demonstração:** `POST http://localhost:8000/api/v1/demo/seed` (popula usuário padrão, terrenos com perfis `seca` e `chuva_extrema`, métricas históricas, atividades adaptadas e alertas).

---

## 📂 Navegação Rápida

- [Requisitos e Regras de Negócio](Requisitos/README.md) — Escopo funcional dos módulos `[M1]` a `[M6]`.
- [Arquitetura do Sistema](Arquitetura/README.md) — Modelagem do banco de dados (DER) e fluxos de orquestração síncrona e em segundo plano.
- [Especificações Técnicas (Specs)](Specs/README.md) — Contratos REST, parâmetros de consulta e payloads JSON dos endpoints.
- [Design e UI/UX](Design/README.md) — Diretrizes de interface Mobile-First, Offline-First (PWA) e ativos visuais.

---

## ✅ Funcionalidades Entregues e Próximos Passos

### Já implementado (Backend, Dados/ML/IA e Infraestrutura)
- **Dados Geoespaciais & Clima (`[M1]` / NASA):** `MockNASADataProvider` com recorte espacial (`.rio.clip()`), precipitação GPM/IMERG, perfis simuláveis (`normal`, `seca`, `chuva_extrema`, `onda_de_calor`), cálculo de área/centroide (`calcular_geometria_terreno`) e `RealNASADataProvider` (`NASA_PROVIDER=real`).
- **Simulação, ML & IA Explicável (`[M2]` / `[M3]`):** CRUD completo de culturas e rotações do produtor, `CropSimulator` considerando clima, prioridades e histórico de cultivos (com `score_breakdown`), `ClimateAnomalyDetector` (`IsolationForest` + limiares) e `RotationExplainerAgent` (estratégias, alertas e relatórios sempre com disclaimer).
- **Calendário, Alertas & Relatórios (`[M4]` / `[M5]` / `[M6]`):** Orquestração `[M1] → [M3] → [M4]` com geração de cronograma pela estratégia escolhida, monitor climático em segundo plano com deduplicação/cooldown e perfis simuláveis, métricas históricas persistidas (Alembic), comparativo de período e resumo interpretativo em linguagem simples.
- **Qualidade, Ambiente & Demo:** Suíte de testes automatizados (`pytest backend/tests`), CI no GitHub Actions, `CORSMiddleware` configurado para o frontend e endpoint idempotente `POST /api/v1/demo/seed`.

### Próximos Passos (Integração Final e Demo)
1. **Integração Completa com o Frontend (`frontend/`):**
   - Conectar todas as telas React/Vite (`localhost:5173`) aos fluxos da API (`[M1] -> [M3] -> [M4]/[M5]/[M6]`) e validar a navegação ponta a ponta.
2. **Ensaio Final da Demo:**
   - Validar cenários interativos com `POST /api/v1/demo/seed` e disparo de alertas climáticos simulados (`seca`, `chuva_extrema`, `onda_de_calor`) para a apresentação do Hackathon.

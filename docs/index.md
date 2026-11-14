# Kultiva — Documentação Técnica

**Kultiva** é um sistema de apoio à decisão para pequenos produtores rurais (NASA Space Apps Challenge), unindo dados geoespaciais de satélite da NASA, modelos de Machine Learning e agentes de IA generativa para planejar rotações de culturas resilientes às mudanças climáticas.

---

## Módulos do Sistema

| Módulo | Descrição | Prioridade |
| :--- | :--- | :--- |
| **[M1]** | Criação e cadastro geográfico do terreno | Obrigatório |
| **[M2]** | Sugestões de culturas e rotações | Obrigatório |
| **[M3]** | Simulador de culturas e rotações | Obrigatório* |
| **[M4]** | Calendário com atividades diárias para o cultivo | Opcional |
| **[M5]** | Alertas de mudanças climáticas e adaptação dinâmica | Opcional |
| **[M6]** | Relatórios periódicos de adaptação | Opcional |

---

## Stack Tecnológica

- **API & Web Framework:** FastAPI + Uvicorn
- **Banco de Dados & ORM:** PostgreSQL 15 + SQLAlchemy
- **Dados Geoespaciais (NASA):** Xarray, NetCDF4, Rasterio, GeoPandas, Pandas
- **Machine Learning & IA Generativa:** Scikit-Learn, LangChain (`langchain-openai`)
- **Infraestrutura:** Docker e Docker Compose

---

## Como Rodar Localmente

Suba os serviços da API e do PostgreSQL com Docker Compose:

```bash
docker-compose up --build
```

Após iniciar os containers:

- **API Base:** `http://localhost:8000`
- **Health Check:** `GET http://localhost:8000/health`
- **Swagger UI (OpenAPI):** `http://localhost:8000/docs`

---

## Navegação Rápida

- [Requisitos e Regras de Negócio](Requisitos/README.md) — Escopo funcional dos módulos `[M1]` a `[M6]`.
- [Arquitetura do Sistema](Arquitetura/README.md) — Modelagem do banco de dados (DER) e fluxos de orquestração síncrona e em segundo plano.
- [Especificações Técnicas (Specs)](Specs/README.md) — Contratos REST, parâmetros de consulta e payloads JSON dos endpoints.
- [Design e UI/UX](Design/README.md) — Diretrizes de interface Mobile-First, Offline-First (PWA) e ativos visuais.

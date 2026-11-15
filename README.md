# Kultiva

Aplicação **Kultiva** (NASA Space Apps Challenge): sistema de apoio à decisão para pequenos produtores rurais, unindo dados de satélite da NASA, bases agronômicas e IA para rotação de culturas resiliente.

## Pré-requisitos

- **Backend:** Python 3.11+ (ou Docker + Docker Compose)
- **Frontend:** Node.js 18+ e npm

---

## Configuração inicial (`.env`)

Na raiz do projeto, crie seu arquivo `.env` a partir do exemplo:

```bash
cp .env.example .env
```

> Sem `GOOGLE_API_KEY` configurada, o agente LLM utiliza respostas determinísticas/mockadas localmente.

---

## Como rodar o Backend

### Opção 1: Com Docker Compose (recomendado)

Sobe a API FastAPI (`http://localhost:8000`) e o banco PostgreSQL (`5432`):

```bash
docker-compose up --build
```

### Opção 2: Localmente sem Docker

1. Crie e ative um ambiente virtual na raiz do projeto:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Instale as dependências:

   ```bash
   pip install -r backend/requirements.txt
   ```

3. (Opcional) Execute as migrações do banco, se aplicável ao seu `DATABASE_URL`:

   ```bash
   alembic upgrade head
   ```

4. Inicie o servidor FastAPI com *hot reload*:

   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

- API disponível em: `http://localhost:8000`
- Documentação interativa (Swagger): `http://localhost:8000/docs`

---

## Como rodar o Frontend

1. Acesse a pasta `frontend/` e instale as dependências:

   ```bash
   cd frontend
   npm install
   ```

2. Inicie o servidor de desenvolvimento (Vite):

   ```bash
   npm run dev
   ```

- Aplicação disponível em: `http://localhost:5173`
- Por padrão, o frontend consome a API em `http://localhost:8000/api/v1`. Caso precise apontar para outro endereço, defina `VITE_API_BASE_URL` em `frontend/.env`.

Para validar o build de produção e checagem de tipos (`tsc --noEmit && vite build`):

```bash
npm run build
```

---

## Documentação (MkDocs)

A documentação técnica do projeto utiliza **MkDocs Material**. Para visualizá-la localmente com *live reload*:

```bash
pip install mkdocs-material
mkdocs serve
```

Para validar o build estático da documentação:

```bash
mkdocs build --strict
```

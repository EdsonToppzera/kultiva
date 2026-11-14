# Kultiva - Backend

Repositório do backend da aplicação **Kultiva** (NASA Space Apps Challenge). 
Sistema de apoio à decisão para pequenos produtores rurais, unindo dados de satélite da NASA com IA para rotação de culturas resiliente.

## Como rodar localmente
```bash
docker-compose up --build
```

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

# Design e UI/UX

Diretrizes de interface Mobile-First, Offline-First (PWA) e padrões visuais para evolução do frontend React/Vite (`frontend/`).

## Sugestões de UX Geoespacial (Inspiradas no Portal FAO GAEZ v5)

Para aproximar a camada estratégica do agricultor sem expor complexidade técnica de SIG no `frontend/src/pages/MapTerrainPage.tsx` e nas telas `[M2]`/`[M3]`:

1. **Camadas WMS/WMTS Direto no Leaflet:**
   - Consumir o serviço OGC WMS público da FAO (`https://data.apps.fao.org/geoserver/wms`) sobre o mapa interativo para visualizar aptidão regional da cultura selecionada e classe de solo sem baixar rasters completos no cliente.
2. **Comparação Lado a Lado (Split View):**
   - Controle deslizante dividindo o mapa entre **clima histórico (`HP0120`) vs. cenário futuro CMIP6 (`2021–2040 SSP370`)** ou entre **manejo Sequeiro (`LRLM`) vs. Irrigado (`HILM`)**.
3. **Consulta Pontual (Feature Information):**
   - Ao clicar em um ponto/talhão no mapa, exibir um resumo simples conectado a `GET /api/v1/culturas/aptidao-gaez` contendo:
     - Cultura recomendada e produtividade atingível estimada (`kg/ha`);
     - Classe de solo (HWSD v2.01) e declividade (`SLOPE-MED`);
     - Principal fator limitante (`SQ-IDX`, ex.: retenção de nutrientes, drenagem ou acidez) traduzido para linguagem cotidiana.
4. **Transparência nos Cards do Simulador `[M3]`:**
   - Exibir o `score_breakdown` de forma visual (aptidão hídrica, estresse térmico, estabilidade temporal, aptidão FAO GAEZ e `kg/ha`) sempre acompanhado da explicação acessível e do aviso legal (`DISCLAIMER`).

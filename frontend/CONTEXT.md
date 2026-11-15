# Kultiva - Documento de Contexto para Front-End

## 1. Visão Geral do Produto
O **Kultiva** é uma ferramenta de apoio à decisão para rotação de culturas, voltada para pequenos produtores comerciais e agricultura familiar. O sistema cruza dados locais do agricultor com dados climáticos e de solo da NASA para sugerir opções de plantio e gerar um calendário de manejo dinâmico.

*   **Público-Alvo:** Agricultores com possível limitação técnica ou tecnológica.
*   **Tom da Interface:** Direto ao ponto, consultivo, parceiro.
*   **O que Evitar:** Interfaces de "chat com IA" (estilo ChatGPT), formulários longos/burocráticos e gamificação excessiva/infantil.

## 2. Princípios de UI/UX
*   **Linguagem Simples e Regional:** Evitar jargões botânicos complexos (ex: usar "Terra preta/barro/areia" em vez de "Latossolo argiloso").
*   **Ações Baseadas em Visão:** Utilizar ícones grandes e fotos para facilitar a identificação (especialmente para plantas e pragas).
*   **Flexibilidade:** A agricultura não segue o relógio. Os componentes de tempo devem focar em "janelas" (manhã, tarde) e não em horas fixas.

---

## 3. Estrutura de Telas e Componentes Principais

### A. Coleta de Dados Iniciais (Onboarding)
Não usar formulário longo. Dividir em passos rápidos. O Front-End deve coletar:
1.  **Histórico de Cultivo:** O que foi plantado na área nos últimos 2 ciclos.
2.  **Capacidade de Irrigação:** Sequeiro (só chuva), poço/caixa d'água, gotejamento, etc.
3.  **Textura Visual do Solo:** Areia (drena rápido), Barro (retém água), Terra Preta (rica).
4.  **Objetivo Principal:** Recuperar o solo, venda rápida, consumo/ração.

### B. Módulo de Simulação de Rotação (Painel de Cenários)
Ao invés de uma IA respondendo em texto, o Front-End deve exibir **3 Cards de Cenários Comparativos**.
*   **Estrutura do Card:**
    *   **Trilha Visual:** Ícones de sequência (ex: `[🌽 Milho] ➔ [🌱 Feijão-de-porco] ➔ [💤 Descanso]`).
    *   **Tradução da NASA:** Frase curta de apoio (ex: *"Dados indicam seca; o feijão protege o solo"*).
    *   **Prós e Contras:** Lista com bullets (🟢 Vantagem / 🔴 Desvantagem local).
    *   **Call to Action:** Botão primário grande "Escolher este plano".

### C. Módulo de Calendário e Manejo (O "Painel do Dia")
*   **Blocos de Turno:** Agrupar tarefas em "Manhã Cedo", "Fim de Tarde" e "Qualquer Momento".
*   **Checklist:** Sistema simples de marcar tarefa como concluída.
*   **Alertas Dinâmicos (UI Preditiva):** Cartões de aviso sobrepostos ou riscados automaticamente. Ex: Tarefa de "Irrigar" riscada com tag azul *"Pausado: Chuva prevista para hoje"*.
*   **Botão "Aconteceu Diferente" (Feedback Loop):** Acesso rápido e fixo na tela para o usuário corrigir o sistema:
    *   🌧️ "Choveu e não estava previsto"
    *   ☀️ "Não choveu como o esperado"
    *   🐛 "Encontrei uma praga" (Abre fluxo de identificação visual)

### D. Input de Culturas e Pragas (O Desafio dos Dicionários)
**NUNCA usar input de texto livre puro para nomes de plantas.**
*   **Componente:** Combobox/Autocomplete inteligente (Fuzzy Search).
*   **Comportamento:** O usuário digita o nome regional (ex: "Macaxeira"), o componente busca nos sinônimos e exibe a sugestão unificada: *Mandioca (conhecida como Macaxeira)*. O Front envia apenas o `ID` para o Back-End.
*   **Fluxo de Desambiguação Visual:** Se o usuário buscar algo genérico (ex: "Feijão"), abrir um Modal ou Cards com fotos para ele escolher o tipo exato (Carioca vs. Feijão de Corda vs. Feijão-de-porco), garantindo que o sistema puxe os dados corretos de nutrientes e pragas do Back-End.

## E. Paleta de Cores
*  #511D4E
*  #CAD17A
*  #FCF59B
*  #91C494
*  #C42311

## 4. Plataforma, Arquitetura e Stack Tecnológica

### A. Formato Web e Mobile-First

Plataforma: O projeto será desenvolvido como uma aplicação Web (Site) para reduzir atritos de instalação e facilitar a submissão e avaliação por bancas.

Responsividade: O design deve ser estritamente Mobile-First. O uso em campo será quase exclusivamente via smartphone, exigindo botões amigáveis ao toque (touch-friendly) e layout em coluna única. No desktop (tela do avaliador), aproveitar o espaço para exibir o Painel de Cenários em formato de grid comparativo lado a lado.

### B. Offline-First via PWA (Progressive Web App)

Conectividade Rural: Para resolver o problema de áreas rurais sem internet, o site deve ser configurado como um PWA (usando Service Workers e manifest.json).

Comportamento Esperado: O agricultor poderá "instalar" o site na tela inicial do celular. Ele poderá acessar o calendário do dia e marcar tarefas offline (dados salvos no LocalStorage/IndexedDB). Quando o dispositivo se conectar novamente à internet, os dados serão sincronizados em background.

### C. Stack Tecnológica (Front-end)
* **Core:** React com TypeScript, inicializado via **Vite**.
* **Estilização e UI:** **Tailwind CSS** (mobile-first, responsividade via utilitários) + **Shadcn UI** (componentes acessíveis de alta qualidade, sem estilo engessado).
* **Motor Offline (PWA):** `vite-plugin-pwa` para gerar manifest e Service Workers (cache de dados e funcionamento em campo sem sinal).
* **Mapas e Geolocalização:** `react-leaflet` + `leaflet`. Renderização com OpenStreetMap e visão de satélite gratuita via **Esri World Imagery**.
* **Estado Assíncrono:** **TanStack Query (React Query)** para cache de requisições de API e sincronização pós-offline.
* **Roteamento:** **React Router DOM**.

### D. Experiência de Uso (UX) e Fluxo de Telas (Onboarding)
A interface deve ser direta e visual, substituindo jargões complexos por linguagem acessível. A interface será testada tanto no mobile (campo) quanto no desktop (banca de avaliação).

### E. Localização (Padrão "Uber")
* Tela com mapa de satélite interativo (visão base: Esri World Imagery).
* Um pino **fixo no centro da tela**. O usuário arrasta o mapa por baixo do pino para indicar a localização exata da fazenda (mesmo que ele esteja configurando o app na cidade).
* Ao confirmar ("Minha plantação é aqui"), o componente captura **Latitude e Longitude** para enviar ao back-end (crucial para o cruzamento de dados climáticos e espaciais da NASA).
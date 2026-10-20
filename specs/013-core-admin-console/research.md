# Research — 013 Admin Console

Insumos: [spec.md](spec.md) (com a clarificação de 2026-10-13), [design.md](design.md), ADR-029, ADR-031–ADR-034, o
contrato [admin-api.md](../008-core-http-api/contracts/admin-api.md) da 008, o protocolo da 012
([oidc.md](../012-core-identity/contracts/oidc.md)), o desenho aprovado no Penpot (páginas "Fundamentos", "Console —
claro", "Console — escuro"), o `PRODUCT.md` e o contrato de direção em `.impeccable/surfaces/ai-core-console.md`.

## R1 — Pilha e versões

- **Decision**: Node 24 (`.nvmrc` = `24`; `engines.node` `>=22.12`), npm com `package-lock.json`, versões exatas (sem
  `^`), todas publicadas há mais de duas semanas em 2026-10-14 e compatíveis entre si pelos `peerDependencies`:
  `react`/`react-dom` 19.3.0, `react-router` 8.4.0, `@tanstack/react-query` 5.104.0, `react-hook-form` 7.89.0, `zod`
  4.6.5, `oidc-client-ts` 3.5.0, primitivas `@radix-ui/react-*` (dialog 1.1.23 e as do mesmo lote), `d3-scale` 4.0.2;
  desenvolvimento: `vite` 8.3.1 + `@vitejs/plugin-react` 6.1.1, `typescript` 6.0.3 (o `typescript-eslint` 8.71.0 exige
  `<6.1`), `eslint` 10.11.0 + `typescript-eslint` 8.71.0, `vitest` 5.0.2 + `jsdom`, `@testing-library/react` 16.3.3,
  `msw` 3.0.0, `@playwright/test` 1.63.0, `@axe-core/playwright` 4.13.0, `prettier`.
- **Rationale**: a escolha do mantenedor (SPA React + TypeScript, ADR-029) com o que é atual e estável; versões exatas
  tornam o build da imagem reproduzível (002).
- **Alternatives considered**: TypeScript 7 (o `typescript-eslint` ainda não o aceita); Next.js/Remix (servidor
  próprio, desnecessário para uma SPA estática na mesma origem).

## R2 — Gráficos em SVG próprio com `d3-scale`

- **Decision**: os gráficos (barras empilhadas por dia, marcos, dica de passar o mouse) são componentes React que
  desenham SVG, com `d3-scale` para as escalas; nenhuma biblioteca de gráficos. Regras da skill `dataviz`: barras de até
  24 px com topo arredondado de 4 px e base reta, vão de 2 px no fundo entre segmentos, grade de 1 px sólida, legenda
  sempre com 2+ séries, texto nas cores de texto, dica com foco de teclado e uma tabela equivalente logo abaixo. Paleta
  das séries: a validada (claro `#2A78D6 #EB6834 #1BAF7A #EDA100`, escuro `#3987E5 #D95926 #199E70 #C98500`), em ordem
  fixa e seguindo a entidade, nunca a posição.
- **Rationale**: o desenho aprovado pede exatamente esse acabamento, que as bibliotecas fazem pela metade (contorno no
  lugar de vão, raio nos dois lados); um gráfico de barras é pouco código.
- **Alternatives considered**: Recharts (vão por contorno, ARIA fraco), visx (mais peças para o mesmo resultado).

## R3 — Estilos: CSS Modules sobre variáveis de tema

- **Decision**: `src/ui/tokens.css` com as variáveis dos temas (os 26 tokens de cor da biblioteca do Penpot —
  `cor.fundo.base` → `--fundo-base` etc. — mais espaço, raio e tipo), `:root[data-theme="light"|"dark"]` e o padrão do
  sistema por `prefers-color-scheme`; componentes com CSS Modules. Sem Tailwind. Seleção de texto, cursor, barras de
  rolagem, anel de foco e algarismos tabulares tematizados (craft floor).
- **Rationale**: os tokens já têm nomes e valores no Penpot; CSS Modules não precisam de plugin e mantêm o CSS legível.
- **Alternatives considered**: Tailwind v4 (camada a mais para traduzir tokens já nomeados).

## R4 — Fontes e ícones

- **Decision**: Mona Sans e JetBrains Mono servidas pela própria console (`@fontsource/mona-sans` 5.3.0,
  `@fontsource/jetbrains-mono` 5.3.0; só os pesos 400/500/600/700 e o subconjunto latino); ícones: o conjunto desenhado
  no Penpot (16 px, traço 1,5) como componentes SVG em `src/ui/icons.tsx`, e o "G" oficial do Google só no lugar de login.
- **Rationale**: CSP `default-src 'self'` sem fonte de terceiros; ícones idênticos aos do desenho.
- **Alternatives considered**: Google Fonts (CSP e privacidade); Lucide (a taste-skill e o desenho pedem outro traço).

## R5 — Autenticação com `oidc-client-ts`

- **Decision**: `UserManager` com `client_id: "console"`, `authority = window.location.origin` (a descoberta da 012 é
  repassada pelo nginx na mesma origem), `redirect_uri = origin + "/callback"`, `post_logout_redirect_uri = origin +
  "/"`, `response_type: "code"` (PKCE S256 automático), `scope: "openid profile email groups offline_access"`,
  `userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() })` (FR-002: nada persistido), renovação pelo
  token de renovação (`automaticSilentRenew` com `refresh_token`; sem iframe — a CSP da 012 tem `frame-ancestors
  'none'`). Ao recarregar a página, `signinRedirect` com `state` = a rota pedida: a sessão de 30 dias da 012 devolve o
  código sem mostrar o login. `GET /admin/v1/me` decide: 200 → shell; 404 → "Sua conta não tem acesso à console".
  Sair = `signoutRedirect` com `id_token_hint`.
- **Rationale**: ADR-031 (cliente público, audiência própria); tokens só em memória fecham o roubo por XSS persistido.
- **Alternatives considered**: guardar o token em `sessionStorage` (sobrevive a XSS na mesma aba); BFF com cookie
  (rejeitado no ADR-031).

## R6 — Cliente da API e dados

- **Decision**: `src/api/client.ts` com `fetch` same-origin, `Authorization: Bearer`, `401` → uma renovação e uma nova
  tentativa, depois `signinRedirect`; erro no envelope da 008 vira `ApiError(status, code, param, message)`. Esquemas
  `zod` em `src/api/schemas.ts` espelhando o contrato `admin-api.md`; respostas que não casam com o esquema viram erro
  explícito (pega divergência de contrato). TanStack Query para leitura e mutação, com invalidação por recurso; nenhuma
  regra de negócio no cliente — o motivo de toda recusa vem do `message`/`param` da API (FR-001).
- **Rationale**: o OpenAPI da 008 não tem corpos (decisão anterior da 008), então os esquemas são escritos à mão a
  partir do contrato e validados em teste.
- **Alternatives considered**: geração de cliente por OpenAPI (sem corpos não há o que gerar).

## R7 — Formulários e versão

- **Decision**: `react-hook-form` + `zodResolver` só para **forma** (campo obrigatório, tipo); validação de negócio é da
  API. Toda escrita manda a `version` lida; `409 version_conflict` abre o aviso "Outra pessoa salvou antes" com
  "Recarregar" e mantém o rascunho num estado local até a pessoa decidir (FR-008). Senha temporária mostrada uma vez no
  diálogo de pessoa cadastrada, com "Copiar" (FR-013); o diálogo é o único modal (proteção de foco para um segredo
  mostrado uma vez).
- **Rationale**: a regra fica no core (ADR-029); o rascunho preservado evita perder trabalho num conflito.
- **Alternatives considered**: validar regras no cliente (duplicaria a 003/009/012).

## R8 — Rotas e telas

- **Decision**: as rotas do `design.md` (`/uso`, `/uso/precos`, `/assistentes`, `/assistentes/:nome` com abas
  `modelos`, `mcp`, `historico`, `/servidores-mcp`, `/observabilidade`, `/acesso` com abas `usuarios`, `grupos`,
  `login`), mais `/callback` e a página de acesso negado; `/` redireciona para `/uso`. Mapa tela → chamadas → estados em
  [contracts/screens.md](contracts/screens.md).
- **Rationale**: o desenho aprovado; slugs em português não colidem com os prefixos repassados ao core.
- **Alternatives considered**: —

## R9 — Tema, idioma e formatos

- **Decision**: `data-theme` na raiz, padrão do sistema, botão de três estados (claro, escuro, sistema) lembrado em
  `localStorage` (`console.theme` — a única coisa guardada no navegador, FR-019). `Intl` em `pt-BR`: números com ponto de
  milhar, tokens compactos ("21,1 M"), dinheiro em USD como "US$ 41,87" (valores da API são string decimal, convertidos
  só para exibir), datas "dd/mm" e "sex, 10/10" no fuso que a API informa. Textos em `src/i18n/pt-BR.ts`.
- **Rationale**: FR-016, FR-019, `PRODUCT.md`.
- **Alternatives considered**: —

## R10 — Servir a console (nginx)

- **Decision**: `deploy/nginx.conf.template` (renderizado por `envsubst` com `AI_CORE_UPSTREAM`, padrão
  `http://ai-core:8000`): SPA com fallback para `index.html`; arquivos com hash com `Cache-Control: public,
  max-age=31536000, immutable`, `index.html` com `no-cache`; repasse **sem reescrita** de `/v1/`, `/private/v1/`,
  `/admin/v1/`, `/oauth2/` e `/.well-known/` com `X-Forwarded-Proto/Host/For` (o core confia neles pela
  `AI_CORE_TRUSTED_PROXIES`); `proxy_buffering off` nos SSE de `/v1/`; CSP da console `default-src 'self'; img-src 'self'
  data:; style-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action
  'self'`; HSTS quando atrás de `https`. Contrato em [contracts/serving.md](contracts/serving.md); o estágio de imagem é
  da 002.
- **Rationale**: mesma origem, sem CORS (008 FR-028); o emissor e os endereços são os mesmos com ou sem console.
- **Alternatives considered**: o core servir os arquivos (acoplaria a console à imagem do core, contra a instalação
  opcional).

## R11 — Testes

- **Decision**: Vitest + Testing Library + MSW para componentes, hooks e o cliente (cada esquema `zod` testado contra
  os exemplos do contrato da 008); Playwright para ponta a ponta com `webServer` duplo: (1) `uv run python
  e2e/serve_platform.py`, que sobe `platform(profile="test")` com a identidade ligada, provider de modelo programado,
  Google simulado, admin semeado, Assistants com `overrides`, servidores MCP de teste e uso semeado; (2) `vite preview`
  com as mesmas regras de repasse do nginx. Cenários das sete US; `@axe-core/playwright` (WCAG 2.2 AA) nos estados
  com dados, vazio e erro, nos dois temas (SC-005); capturas de referência em 1440 e 768 de largura. O MCP do Playwright
  serve aos ciclos de crítica da impeccable.
- **Rationale**: SC-002 (toda ação tem rota — o e2e passa pela API real), SC-005.
- **Alternatives considered**: e2e contra mocks (não provaria o contrato).

## R12 — Acabamento pela impeccable

- **Decision**: depois de construir, uma rodada de inspeção (desktop 1440 e tablet 768, claro e escuro), o detector
  `impeccable detect` nos arquivos alterados, a revisão final pelo `impeccable-finish-reviewer` contra o contrato de
  direção e as telas do Penpot, e o `DESIGN.md` com `.impeccable/design.json` pelo `impeccable-documenter` (o mundo
  visual é novo).
- **Rationale**: o fluxo da skill escolhida pelo mantenedor; a revisão roda fora do contexto de quem construiu.
- **Alternatives considered**: —

## R13 — CI

- **Decision**: `.github/workflows/console.yml` com filtro de caminhos (`ai-core/console/**`, os contratos da 008 e da
  012): Node pelo `.nvmrc`, `npm ci`, `npm run typecheck`, `lint`, `test`, `build`; job de e2e com uv e Python 3.14 e o
  Chromium do Playwright.
- **Rationale**: o padrão das CIs do repositório.
- **Alternatives considered**: —

## R14 — Notas da implementação (2026-10-14)

- **Decision**: o que a construção ajustou nas decisões acima, sem mudar nenhuma delas:
  - **Lint de acessibilidade**: o `eslint-plugin-jsx-a11y` (6.10.2, a última versão) não aceita o ESLint 10 nos
    peers; ficou de fora. A acessibilidade é provada pelo axe — `axe-core` nos testes de componente e
    `@axe-core/playwright` no e2e, em todas as telas, nos dois temas e em 768 px.
  - **Algarismos proporcionais**: os tabulares da Mona Sans desenham o zero cortado, que o desenho aprovado não tem;
    as colunas numéricas ficam alinhadas à direita.
  - **`nonce`**: a 012 exige `nonce` no `authorize` e o `oidc-client-ts` não o manda no fluxo de código; a console
    passa um aleatório no `signinRedirect`, guardado no estado e conferido no `id_token`. O estado do redirecionamento
    vive no `sessionStorage` só durante a ida ao login (a biblioteca usa o `localStorage` por padrão).
  - **Sobreposição de modelos é a seção inteira** (003 FR-018): a aba Modelos manda todos os papéis preenchidos; papel
    vazio fica sem modelo. O exemplo do `admin-api.md` da 008 mesclava a efetiva com o YAML e foi corrigido. A recusa
    de um papel chega como `models.<papel>` (regra da 003) ou `roles.<papel>` (forma do corpo, 008) — a tela aceita os
    dois.
  - **Campo de modelo**: entrada com sugestões (`datalist`) dos modelos conhecidos (YAML, efetivos e preços), porque a
    API não tem catálogo de modelos; a allowlist é conferida pela API.
  - **E2e na porta 8765** (`CONSOLE_E2E_PORT`): a 8000 costuma estar tomada pelo encaminhamento de portas do editor. O
    `serve_platform.py` usa o relógio do sistema — o perfil `test` tem relógio fixo, e o navegador confere `iat`/`exp`.
  - **Nginx sem privilégio e somente leitura**: `tmpfs` em `/tmp` e em `/etc/nginx/conf.d` com o dono do processo
    (uid 101), onde o `envsubst` da imagem renderiza o template (`e2e/serve_nginx.sh`).
  - **Achados em outros módulos**, corrigidos nas próprias specs: a 012 mandava `Referrer-Policy: no-referrer`, e o
    Chromium serializava a origem do POST do formulário como `null` — o login pelo navegador era recusado (012 R18); as
    páginas da 012 declaravam a Mona Sans sem servi-la (012 R19); o código 401 do contrato da administração é o
    `invalid_credential` já existente (008).
  - **Revisão final (T040)**: veredito "liberar depois dos ajustes", aplicados num lote com uma rodada de confirmação.
    Rótulos dos marcos medidos e numa faixa acima das barras, a 6 px da própria linha e sem cruzar outra. Tabela do
    gráfico para leitor de tela num invólucro oculto (tabela ignora a altura de 1 px e criava rolagem). Busca com
    ícone vencendo o padding do campo. `word-spacing` nos títulos em 600. Ações do cabeçalho centradas. Abaixo de
    1100 px: tema empilhado e colunas secundárias escondidas (`wideOnly`), com o YAML e o endereço sob o nome e
    identificadores sem quebra no meio. Servidores MCP com o endereço secundário e o detalhe somente leitura das
    entradas do `mcp.yaml`. Falta de credencial dita como a ação do operador (`mcpReason`). `::selection` e
    `caret-color` nas páginas da 012 e `theme-color` na console.
  - **Sistema visual registrado** em `DESIGN.md` e `.impeccable/design.json` (T041), derivados da build. As
    divergências pequenas que o registro achou, sem correção por ora:
    - raio de 12 px no diálogo e no acesso negado;
    - sombra e branco literal no polegar do interruptor;
    - tokens da 012 com outros nomes (`--ok-texto`, `--erro-*`);
    - alguns tamanhos literais (iniciais do avatar, eixo do gráfico);
    - o CSS do menu flutuante repetido em Acesso e em Servidores MCP.
- **Rationale**: manter o desenho aprovado e as decisões R1–R13 com o que as bibliotecas e os módulos de fato fazem.
- **Alternatives considered**: —

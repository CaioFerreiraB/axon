---

description: "Task list for 013 — Console de administração, Fase 9"
---

# Tasks: Console de administração

**Input**: Design documents from `/specs/013-core-admin-console/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md); o contrato
[admin-api.md](../008-core-http-api/contracts/admin-api.md); o desenho aprovado no Penpot

**Tests**: incluídos. SC-002, SC-005, SC-006 e SC-007 só se demonstram por teste, e o e2e contra a plataforma real é o
que prova que a console não tem regra própria.

**Organization**: **US1–US7**. Pré-requisito de execução: as passadas da Fase 9 da 012, 003, 009, 008 e 011 (a API de
administração e o login existem). Nada fora de `ai-core/console/`, `.github/workflows/console.yml` e `specs/README.md`.

## Format: `[ID] [P?] [Story] Description`

## Path Conventions

- Caminhos relativos a `ai-core/console/`; comandos com `source ~/.nvm/nvm.sh && nvm use` (Node 24)

---

## Phase 1: Setup

- [X] T001 Criar o projeto: `.nvmrc` (`24`), `package.json` (nome `@agentic/console`, `private`, `engines.node`
  `>=22.12`, scripts `dev`, `build`, `preview`, `typecheck`, `lint`, `test`, `e2e`) com as versões **exatas** de
  [research.md](research.md) R1; `npm install` gera `package-lock.json`; `tsconfig.json` estrito; `vite.config.ts` com o
  plugin React e o repasse de `/v1`, `/private/v1`, `/admin/v1`, `/oauth2`, `/.well-known` para
  `process.env.AI_CORE_UPSTREAM ?? "http://127.0.0.1:8000"` em `dev` e `preview`
- [X] T002 [P] `eslint.config.js` (flat, `typescript-eslint`, `react-hooks`, `jsx-a11y`, e `no-restricted-imports`/
  `no-restricted-globals`: `fetch` e `oidc-client-ts` só em `src/api/` e `src/auth/`), `.prettierrc`, `.gitignore`
  (`dist/`, `node_modules/`, `test-results/`, `playwright-report/`)
- [X] T003 [P] `index.html` (`lang="pt-BR"`, sem script inline, título "Console"), `src/main.tsx` vazio que monta o
  `App`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: nenhuma user story antes de T004–T016

- [X] T004 `src/ui/tokens.css`: as variáveis dos temas a partir dos tokens do Penpot (26 cores por tema —
  `--fundo-base`, `--fundo-sutil`, `--fundo-realce`, `--borda-base`, `--borda-forte`, `--texto-primario`,
  `--texto-secundario`, `--texto-terciario`, `--texto-sobre-acao`, `--acao-*`, `--estado-*`, `--serie-1..4` —, espaço
  4–48, raio 6/8/999, tamanhos 12/13/14/16/24/28/48); `:root[data-theme="light"]`, `:root[data-theme="dark"]` e o padrão
  por `prefers-color-scheme`; no escuro, `--acao-base` = `#2563EB` (contraste 5,2:1 com texto branco)
- [X] T005 [P] `src/ui/global.css`: fontes self-host (Mona Sans e JetBrains Mono do `@fontsource`, pesos
  400/500/600/700, latino), `font-variant-numeric: tabular-nums` nas tabelas, seleção, cursor, barra de rolagem, anel de
  foco (2 px `--acao-base` com 2 px de afastamento), `prefers-reduced-motion`
- [X] T006 [P] `src/ui/icons.tsx`: os 22 ícones do Penpot (16 px, traço 1,5, `currentColor`) e o "G" do Google
- [X] T007 Componentes de `src/ui/` conforme a folha "Componentes" do Penpot, com CSS Modules e testes de unidade e axe
  em `tests/ui/`: `Button` (primary, secondary, ghost, danger; sm/md/lg; ícone; desabilitado), `Badge` (ok, warn, bad,
  accent, neutral; ponto; ícone), `Field` (rótulo, ajuda, erro, somente leitura com selo "Definido na instalação",
  monoespaçado para identificadores), `Select`, `Segmented`, `Tabs`, `Toggle`, `Checkbox`, `Notice` (info, warn, bad,
  neutral, ok; ação), `Table` (cabeçalho, linhas, rodapé, alinhamento numérico), `Dialog` (Radix), `Skeleton`,
  `EmptyState`
- [X] T008 [P] `src/i18n/pt-BR.ts` (textos das telas do Penpot) e `src/i18n/format.ts` (`Intl` `pt-BR`: números,
  tokens compactos "21,1 M", "US$ 41,87" a partir de string decimal, datas no fuso informado) com testes em
  `tests/i18n/`
- [X] T009 `src/api/errors.ts` (`ApiError(status, code, param, message, currentVersion)`) e `src/api/schemas.ts` (os
  esquemas `zod` de [data-model.md](data-model.md)); `tests/api/schemas.test.ts` valida cada exemplo de
  [admin-api.md](../008-core-http-api/contracts/admin-api.md) e recusa variações (campo faltando, tipo errado)
- [X] T010 `src/auth/userManager.ts` (R5: cliente `console`, `authority` = origem, PKCE, `InMemoryWebStorage`,
  renovação por token de renovação), `AuthProvider.tsx`, `Callback.tsx` (volta à rota do `state`); testes em
  `tests/auth/` com o `UserManager` simulado
- [X] T011 `src/api/client.ts`: `fetch` same-origin com `Bearer`; `401` → uma renovação e uma nova tentativa, depois
  `signinRedirect`; envelope de erro → `ApiError`; validação pelo esquema; testes com MSW em `tests/api/client.test.ts`
- [X] T012 `src/app/router.tsx` (rotas de [contracts/screens.md](contracts/screens.md), carregadas sob demanda),
  `src/app/RequireAdmin.tsx` (`GET /me`: 200 → shell; 404 → `AccessDenied`), `src/app/AccessDenied.tsx` (desenho
  "Acesso negado"), `src/app/ErrorBoundary.tsx`
- [X] T013 `src/app/Shell.tsx` e `src/app/Sidebar.tsx`: barra lateral de 240 px com nome e logotipo da instalação do
  `/me` (FR-020), navegação, seletor de tema de três estados (FR-019, `localStorage["console.theme"]`), usuário e "Sair"
- [X] T014 [P] MSW: `tests/msw/handlers.ts` com respostas do contrato para todas as rotas (dados do desenho)
- [X] T015 `e2e/serve_platform.py`: escreve um `identity.yaml` temporário com os clientes `console` (retorno
  `http://127.0.0.1:4173/callback`, pós-logout `http://127.0.0.1:4173/`) e `open-webui` (retorno de teste) e aponta
  `AI_CORE_IDENTITY_CLIENTS_FILE` para ele; sobe `platform(profile="test")` com `AI_CORE_IDENTITY_ENABLED=true`,
  `AI_CORE_PUBLIC_URL=http://127.0.0.1:4173`, provider de
  modelo programado, Google simulado, admin semeado, Assistants `geral` (`overrides: [models, mcp]`), `rascunho` (sem
  `overrides`), `documentos` (sobreposição que o YAML mudou), servidores MCP de teste e uso semeado de 30 dias; serve
  `platform.app` com uvicorn em `127.0.0.1:8000`; `playwright.config.ts` com os dois `webServer` (R11) — o da plataforma
  com `command: "uv run python console/e2e/serve_platform.py"` e `cwd: ".."` (o workspace `ai-core/`), o do
  `vite preview` na porta 4173 —, projetos claro e escuro, 1440 e 768 de largura
- [X] T016 [P] `e2e/fixtures/` (login como admin e como não admin pelo formulário da 012) e o helper de axe

**Checkpoint**: shell navegável, login e acesso negado funcionando contra a plataforma em memória

---

## Phase 3: User Story 1 — Admin entra na console (Priority: P1) 🎯 MVP

- [X] T017 [P] [US1] `e2e/auth.spec.ts`: sem sessão → página de login da 012 → volta à rota pedida; Google simulado;
  não admin → acesso negado sem nenhuma chamada administrativa além do `/me` (SC-007); token vence durante a edição →
  renovação sem perder o rascunho; sair encerra a sessão na 012 e a volta exige login; nada no `localStorage` além de
  `console.theme` e nada no `sessionStorage` (SC-006)
  (a renovação do token é provada no cliente, `tests/api/client.test.ts`: o e2e não espera os 10 min do token)
- [X] T018 [US1] Ajustes de T010–T013 até T017 verde; axe na página de acesso negado e no shell, nos dois temas

---

## Phase 4: User Story 2 — Trocar os modelos de um Assistant (Priority: P1)

- [X] T019 [P] [US2] Testes de componente em `tests/assistants/` (MSW): estados carregando, vazio e erro da lista e do
  detalhe; lista com os selos; aba Modelos editável, travada e com sobreposição inativa; `422` mostrado junto ao papel; `409` mantém o rascunho e oferece "Recarregar"; descarte
  com confirmação na própria tela
- [X] T020 [P] [US2] `e2e/assistant-models.spec.ts`: cenários 1–6 da US2 contra a plataforma; SC-001 (troca e conversa
  seguinte com o modelo novo, pela API de chat do perfil de teste)
- [X] T021 [US2] `src/api/hooks/assistants.ts` e `src/features/assistants/AssistantsPage.tsx` (busca, filtros pela URL,
  selos)
- [X] T022 [US2] `src/features/assistants/AssistantDetail.tsx` (cabeçalho com estado, anterior/próximo, abas) e
  `ModelsTab.tsx` (por papel: YAML, sobreposição com `Select` e "Testar modelo" por `POST …/models/check`, efetivo;
  travado; inativa; rodapé com autor, versão e alterações não salvas; salvar e descartar)
- [X] T023 [US2] `HistoryTab.tsx` (histórico da 003) e rodar T019–T020 até verde

---

## Phase 5: User Story 3 — Gerenciar os MCPs de um Assistant (Priority: P1)

- [X] T024 [P] [US3] Testes de componente da aba MCP (MSW; estados carregando, sem servidores globais e erro) e
  `e2e/assistant-mcp.spec.ts` (cenários 1–4 da US3)
- [X] T025 [US3] `src/features/assistants/McpTab.tsx`: um cartão por servidor global com `Toggle`, estado e contagem;
  tools da saúde do servidor com "Permitida" e "Escrita" (bloqueada em Assistant público, com o aviso); servidor
  indisponível com o motivo; salvar e descartar; rodar T024 até verde

---

## Phase 6: User Story 4 — Ver uso e custo (Priority: P2)

- [X] T026 [P] [US4] Testes de `tests/usage/` (MSW): faixa de números (custo como figura principal, "Incompleto"),
  gráfico (barras empilhadas na ordem fixa da paleta, legenda, dica por teclado, tabela equivalente), estados vazio,
  carregando e erro; `e2e/usage.spec.ts` (cenários 1–4 da US4; SC-004 com o uso semeado de 90 dias)
- [X] T027 [US4] `src/features/usage/StatStrip.tsx` e `UsageTable.tsx`
- [X] T028 [US4] `src/features/usage/DailyCostChart.tsx` (SVG + `d3-scale`, R2): barras ≤ 24 px, topo 4 px, vão de
  2 px, grade de 1 px, marcos de preço novo (das vigências do período) e de sobreposição (do histórico de cada
  Assistant, chamadas em paralelo e em cache pelo TanStack Query), coluna em foco com dica, `role="img"` com descrição e
  a tabela como alternativa
- [X] T029 [US4] `src/features/usage/UsagePage.tsx` (período, agrupamento e origem na URL) e `PricesPage.tsx` (formulário
  de novo preço, modelos usados sem preço destacados, vigências); rodar T026 até verde

---

## Phase 7: User Story 5 — Configurar o Langfuse (Priority: P2)

- [X] T030 [P] [US5] Testes de `tests/observability/` (MSW; estados carregando e erro) e `e2e/observability.spec.ts`
  (cenários 1–4 da US5): campos
  da instalação somente leitura; segredo só "definido"; `master_key_missing` explicado; captura só depois de marcar "Li e
  quero capturar o texto"
- [X] T031 [US5] `src/features/observability/ObservabilityPage.tsx` e `CaptureConsent.tsx`; rodar T030 até verde

---

## Phase 8: User Story 6 — Login e contas (Priority: P2)

- [X] T032 [P] [US6] Testes de `tests/access/` (MSW; estados carregando, vazio — só o admin inicial — e erro) e
  `e2e/access.spec.ts` (cenários 1–4 da US6; cadastrar e entrar com
  a senha temporária; desativar e ver o login recusado)
- [X] T033 [US6] `src/features/access/AccessPage.tsx`, `UsersTab.tsx` (busca, estados, ações), `PersonDialog.tsx`
  (cadastro e senha temporária mostrada uma vez, "Copiar"), `GroupsTab.tsx` (grupo de administração protegido),
  `LoginTab.tsx` (Google, endereço de retorno copiável, "Definido na instalação"); rodar T032 até verde

---

## Phase 9: User Story 7 — Servidores MCP globais (Priority: P3)

- [X] T034 [P] [US7] Testes de componente (estados carregando, vazio e erro) e `e2e/mcp-servers.spec.ts` (cenários 1–2
  da US7)
- [X] T035 [US7] `src/features/mcp/McpServersPage.tsx` e `McpServerForm.tsx` (somente leitura para o arquivo do
  operador; credencial só por referência, nunca valor); rodar T034 até verde

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T036 `deploy/nginx.conf.template` conforme [contracts/serving.md](contracts/serving.md) e um teste de fumaça em
  `e2e/serving.spec.ts` contra `nginx` em contêiner (CSP, cache, repasse sem reescrita, SSE)
- [X] T037 [P] `.github/workflows/console.yml` (R13)
- [X] T038 Rodada de inspeção da impeccable: capturas em 1440 e 768, claro e escuro, de todas as telas e estados em
  `.impeccable/review/`; `impeccable detect --json` nos arquivos alterados; corrigir o que for mecânico; o axe roda em
  `e2e/a11y.spec.ts` em todas as telas nos estados com dados, vazio e erro, nos dois temas (SC-005)
- [X] T039 `e2e/keyboard.spec.ts` (FR-017): cada tela percorrida só com Tab, Shift+Tab, Enter, Espaço e setas (abas,
  segmentados, tabelas, formulários, dica do gráfico); foco sempre visível; o diálogo prende o foco e o devolve a quem o
  abriu; nenhuma ação só com mouse
- [X] T040 Revisão final pelo `impeccable-finish-reviewer` (contrato de direção, telas do Penpot como referência, o
  craft floor, as capturas, os achados do detector); aplicar as correções em um lote e uma segunda rodada no máximo
- [X] T041 `DESIGN.md` e `.impeccable/design.json` pelo `impeccable-documenter` a partir da console construída
- [X] T042 [P] `specs/README.md` (status da 013) e `CLAUDE.md` (a console existe; como rodar)
- [X] T043 Rodar o [quickstart.md](quickstart.md) inteiro (typecheck, lint, test, e2e com axe)

---

## Dependencies & Execution Order

- Pré-requisito externo: as passadas da Fase 9 da 012, 003, 009, 008 e 011
- Setup (T001–T003) → Foundational (T004–T016) → US1 → US2 → US3 (usa o detalhe da US2) → US4, US5, US6, US7 em
  qualquer ordem → Polish

## Parallel Example: Foundational

```text
T005 + T006 + T008 + T014   # arquivos diferentes
```

## Implementation Strategy

1. **MVP**: Setup + Foundational + US1 — entrar, ver o shell e o acesso negado.
2. US2 e US3: o motivo principal da console (modelos e MCPs por Assistant).
3. US4–US7: uso e custo, Langfuse, contas, servidores.
4. Polish: nginx, CI e o acabamento da impeccable (revisão final e `DESIGN.md`).

---

## Passada de 2026-10-20: identidade Axon — US8 ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md), [ADR-038](../../docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md), [ADR-039](../../docs/adr/ADR-039-hover-do-botao-primario-no-escuro.md); research R15–R21)

**Goal**: a console com a marca Axon ou a da instalação, favicon, título da aba, tokens do `DESIGN.md` com o hover escuro
`#1D4ED8` (também no `identity.css`), `@axon/console`; Vitest, e2e com axe e capturas verdes.

**Independent Test**: [quickstart.md, "Fase 9, incremento 9.5"](quickstart.md).

### Setup

- [X] T044 [US8] `brand-kit/svg/axon-wordmark-light.svg` (`fill="#111827"`) e `axon-wordmark-dark.svg` (`fill="#FFFFFF"`):
  o `<path>` do wordmark de `axon-lockup-light.svg`, sem o `transform`, com `viewBox="252.38 132.47 252.12 62.78"`,
  `role="img"` e `aria-label="Axon"`; duas linhas novas no `brand-kit/svg/README.md` ("recorte do lockup, mesmo traço",
  R15). Copiar para `axon-ai/console/src/brand/` esses dois e `axon-symbol.svg`, `axon-symbol-light.svg`,
  `axon-lockup-light.svg`, `axon-lockup-dark.svg` e `favicon.svg`
- [X] T045 [US8] `axon-ai/console/package.json` → `"name": "@axon/console"` e `npm install --package-lock-only` (R20)

### Tests (antes das T049–T054)

- [X] T046 [P] [US8] `axon-ai/console/tests/app/sidebar.test.tsx` (R17, R18, R21): com o MSW do `me` em `custom: false`, a
  barra lateral tem o símbolo, o wordmark (`alt="Axon"`) e "Console", e nenhum "com Axon"; com `custom: true` e o nome
  "Instituto Exemplo", o nome, a inicial "I" e "com Axon"; o `document.title` de uma tela (`/uso`) é "Uso e custo ·
  Axon" e, com nome próprio, "Uso e custo · Instituto Exemplo". `tests/msw/fixtures.ts`: `instance: { name: "Axon",
  logo_url: null, custom: false }`
- [X] T047 [P] [US8] `axon-ai/console/tests/app/access-denied.test.tsx`: o lockup (`alt="Axon"`) e o título "Sem acesso · Axon"
  (cen. 4); `axon-ai/console/tests/ui/brand-assets.test.ts`: cada SVG de `src/brand/` é igual ao do `brand-kit/svg/`
  (FR-023); `axon-ai/console/tests/ui/contrast.test.ts`: lê os três blocos de `src/ui/tokens.css` e confere ≥ 4,5:1 para
  primário, secundário e terciário sobre `--fundo-base` e `--fundo-sutil`, `--acao-texto` sobre `--fundo-base`,
  `--texto-sobre-acao` sobre `--acao-base` **e sobre `--acao-hover`**, os três estados sobre os fundos deles e `--foco`
  sobre os dois fundos (FR-021)
- [X] T048 [P] [US8] `axon-ai/packages/core/tests/identity/unit/test_page_contrast.py` (ADR-039): o par
  `texto-sobre-acao`/`acao-hover` entra nos pares, nos dois temas; a docstring perde a exceção. Rodar T046–T048 e ver falhar

### Implementation

- [X] T049 [US8] `axon-ai/console/src/app/brand/Mark.tsx` e `Mark.module.css` (R16): `AxonSymbol({ size, alt })`,
  `AxonWordmark({ height })` e `AxonLockup({ height })`, cada um com as duas `<img>` (versão para fundo claro e para fundo
  escuro) e as classes que mostram uma delas pelos seletores de tema do `tokens.css`
- [X] T050 [US8] `axon-ai/console/src/api/schemas.ts`: `instance: z.object({ name, logo_url, custom: z.boolean() })` (R17)
- [X] T051 [US8] `axon-ai/console/src/app/Sidebar.tsx` e `Sidebar.module.css` (R17): o padrão `{ name: "Axon", logo_url:
  null, custom: false }`; sem marca própria, `AxonSymbol` de 32px + coluna com `AxonWordmark` (13px) e "Console"; com marca,
  o `Brand` de hoje + nome + "Console" e, no rodapé, `.attribution` (símbolo de 16px e "com Axon", caption terciário);
  no trilho, "com Axon" só para leitor de tela
- [X] T052 [US8] `axon-ai/console/src/app/AccessDenied.tsx` (R17, R18): `AxonLockup` de 32px no lugar do `Brand`, e
  `document.title = "Sem acesso · Axon"`
- [X] T053 [US8] Título da aba (R18): `axon-ai/console/src/ui/Page.tsx` com `PageTitleSuffix` (contexto, padrão "Axon") e o
  efeito do `PageHeader`; `axon-ai/console/src/app/Shell.tsx` fornece `me.instance.name`; `axon-ai/console/index.html` com o
  favicon, `<title>Axon</title>` e `theme-color` escuro `#0b0f19`
- [X] T054 [US8] Tokens (R19): `axon-ai/console/src/ui/tokens.css` nos três blocos com os valores do `DESIGN.md` (claro:
  `--fundo-sutil #f8fafc`, `--fundo-realce #f1f5f9`, `--borda-base #e5e7eb`, `--borda-forte #d1d5db`, `--texto-primario
  #111827`, `--texto-secundario #556070`, `--texto-terciario #666d7c`; escuro: `--fundo-base #0b0f19`, `--fundo-sutil
  #111724`, `--fundo-realce #1a2130`, `--borda-base #242b3a`, `--borda-forte #353d4f`, `--texto-primario #f1f3f7`,
  `--texto-secundario #a3abbb`, `--texto-terciario #8c94a6`, `--acao-hover #1d4ed8`, `--acao-sutil #14223f`) e o
  comentário; `axon-ai/packages/core/src/axon_ai/identity/adapters/assets/identity.css` com `--acao-hover: #1d4ed8` no
  escuro

### Integration e verificação

- [X] T055 [US8] E2E (R21): `axon-ai/console/e2e/a11y.spec.ts` ganha a conferência do título ("Uso e custo · Axon") e do
  `<link rel="icon">`; rodar `npm run e2e` (axe nos três projetos)
- [X] T056 [US8] Suítes: na console, `npm ci && npm run typecheck && npm run lint && npm test && npm run e2e`; no core, a
  suíte de `identity/` (o teste de contraste da 012) e o `ruff`
- [X] T057 [US8] Capturas (R21): a barra lateral sem e com marca da instalação, claro e escuro, e o acesso negado, pelo
  Playwright do MCP; guardar no scratchpad
- [X] T058 [US8] Resíduos (SC-008): `git grep -nE 'Agentic|@agentic/console'` fora do histórico (e do `agentic.exemplo.org`
  dos exemplos) só nos textos que nomeiam o antigo; nenhuma palavra `agentic` removida (`--word-diff`)
- [X] T059 [P] [US8] `specs/README.md` (linha da 013 com a US8; o ADR-039) e `docs/roadmap.md` (andamento do 9.5: 013 feita)

### Dependencies (US8)

T044 → T045 → T046 ∥ T047 ∥ T048 (veem falhar) → T049 → T050 → T051 → T052 → T053 → T054 → T055 → T056 → T057 → T058; T059
em paralelo com a T056.

### Notas da execução (US8)

- O hover escuro foi decidido pelo mantenedor antes da spec (`#1D4ED8`, ADR-039); `DESIGN.md` e `.impeccable/design.json`
  (o `canonical` do token; a rampa tonal, gerada do valor antigo, ficou) acompanham.
- `npm install --package-lock-only` tirava 345 linhas do lock (dependências opcionais de outras plataformas, por diferença
  de versão do npm): desfeito, e só as duas linhas do nome foram trocadas à mão; `npm ci` aceita.
- O teste de contraste da console achou o mesmo par que já reprovava na 012 (terciário sobre o fundo sutil no claro) e o
  hover escuro; os dois passam com os tokens novos.
- Os testes que leem arquivos (`brand-assets`, `contrast`) resolvem os caminhos por `process.cwd()`: no jsdom o
  `import.meta.url` não é `file:`, e o `setup.ts` global exige `window`.
- O `Mark.module.css` troca a versão pela especificidade dos seletores de tema, sem `!important`.
- Trilho (cen. 3) e troca de tema na hora: cobertos pelo projeto `tablet` do e2e (768px, com axe) e pelas capturas; o
  jsdom não aplica media query.
- Nas capturas, a troca de tema logo antes do `screenshot` pega as transições de CSS no meio (item ativo e segmentado
  com a cor do tema anterior); com uma pausa, ficam certas. Capturas no scratchpad da sessão, `capturas-013/`; a pasta
  `.playwright-mcp/` foi apagada. O Penpot não estava conectado.
- `agentic` removido no diff: só o nome do pacote `@agentic/console` (ADR-037), não o flow.
- Suítes: console typecheck e lint limpos, 121 testes, e2e 42 passed e 4 skipped (o nginx, sem `CONSOLE_NGINX_URL`); core,
  `identity/` 336 passed, 40 skipped, e ruff limpo.

---

## Passada de 2026-10-21: chaves de API e permissões dos Assistants — US9, US10 ([ADR-040](../../docs/adr/ADR-040-rotacao-de-chaves-e-acesso-sobreponivel.md); research R22–R27)

**Goal**: aba "Chaves de API" (`/acesso/chaves`) com criação, chave em claro uma vez, rotação e revogação confirmadas na
linha; aba "Permissões" (`/assistentes/:nome/permissoes`) que edita `auth` como as outras sobreposições.

**Independent Test**: [quickstart.md, "Fase 9 (2026-10-21)"](quickstart.md).

### Foundational

- [X] T060 `axon-ai/console/src/api/schemas.ts` (R26, R23): `SECTIONS = ["models", "mcp", "auth"]`;
  `authSelectionSchema` (`schemes: z.array(z.enum(["oidc", "api_key"]))`, `allow: z.array(z.string())`) e o tipo
  `AuthSelection`; `auth` em `yaml` e `effective`; `payload` de `overrideViewSchema` e `historyEntrySchema` com
  `authSelectionSchema` na união e `isAuthPayload`; `apiKeySchema` com `rotated_at: instant.nullable()`;
  `apiKeyListSchema`; `issuedKeySchema = apiKeySchema.extend({ key: z.string() })`. `tests/api/schemas.test.ts`: uma
  visão com sobreposição e histórico de `auth` passa; chave com `rotated_at` passa; `isMcpPayload` continua falso para
  `auth`
- [X] T061 [P] `axon-ai/console/eslint.config.js` (R23): `"no-console": "error"` para `src/**`; `npm run lint` verde
- [X] T062 [P] `axon-ai/console/tests/msw/{fixtures,handlers}.ts`: fixtures `apiKeys` (duas ativas de `svc:relatorios`
  com rótulos `prod`/`homolog`, uma revogada, uma `user:` com grupos), `geral`/`documentos` com `yaml.auth` e
  `effective.auth`, um Assistant `aberto` público com `overridable` incluindo `auth`; handlers `GET /keys`

### US9 — Tests (antes das T064–T066)

- [X] T063 [P] [US9] `axon-ai/console/tests/access/keys.test.tsx` (R22–R24): lista com sistema, identificador, grupos,
  rótulo, criação, rotação e estado, ativas antes das revogadas, sem `key`; "Criar chave" → formulário com nome e
  rótulo → `POST /keys` com `subject: "svc:relatorios"` → diálogo com a chave, "Copiar" e o aviso; "Concluir" fecha, a
  chave some do documento **e** do `queryClient` (nenhuma query nem mutação guarda `key`); 422 `param: "subject"` no campo
  do nome; "Revogar" pede confirmação na linha, "Cancelar" tem foco, confirmar chama `DELETE`; "Rotacionar" confirma e abre
  o diálogo com "a chave anterior já não vale"; 409 `key_revoked` mostra o motivo e relê a lista; vazio "Nenhuma chave".
  Rodar e ver falhar

### US9 — Implementation

- [X] T064 [US9] `axon-ai/console/src/api/hooks/keys.ts` (`apiKeys: ["api-keys"]`) e `src/api/hooks/apiKeys.ts` (R23):
  `useApiKeys`; `useCreateKey` e `useRotateKey` com `gcTime: 0` e só `invalidateQueries(keys.apiKeys)` no sucesso;
  `useRevokeKey` (invalida a lista)
- [X] T065 [US9] `axon-ai/console/src/features/access/IssuedKeyDialog.tsx` (R23): o `Dialog` com título ("Chave criada"
  / "Segredo novo"), descrição com o aviso de que não aparece de novo (e, na rotação, que a anterior já não vale), campo
  somente leitura `mono` com a chave, "Copiar" (`navigator.clipboard`) e "Concluir"; ao fechar, `onClose` limpa o
  estado e chama `reset()` da mutação
- [X] T066 [US9] `axon-ai/console/src/features/access/KeysTab.tsx` (R22, R24): formulário de criação aberto por
  `?criar=1` (nome do sistema com a ajuda do padrão e o erro de `subject`; rótulo opcional), tabela, confirmação na
  linha (padrão do `DiscardButton`), avisos de erro; `AccessPage.tsx`: aba "Chaves de API" e o botão "Criar chave" no
  cabeçalho quando ela está aberta; `src/app/router.tsx`: rota `chaves`. Rodar T063: verde

### US10 — Tests (antes das T068–T070)

- [X] T067 [P] [US10] `axon-ai/console/tests/assistants/permissions.test.tsx` (R25): travada sem `auth` em
  `overridable` (YAML só leitura, "Só muda por novo deploy"); com `auth`: os dois `Toggle`, a lista com rótulos e
  "Remover"; "Adicionar" com sugestões (`svc:relatorios` uma vez, mesmo com duas chaves; sem o sistema só revogado;
  `group:…`), `user:ana` digitado aceito, `caio` sem prefixo recusado antes de entrar na lista; `*` só no público, com
  nota, e ausente no privado com o motivo; marcas "sem correspondência" e "não entra com os esquemas ligados"; salvar
  desabilitado sem esquema ou sem entrada, com o motivo; `PUT …/auth` com `schemes` ordenado, `allow` e `version`;
  409 `version_conflict` com "Recarregar e manter meu rascunho"; descarte confirmado na tela; `HistoryTab` mostra
  "Permissões" e o resumo; a lista de Assistants mostra o selo "Permissões". Rodar e ver falhar

### US10 — Implementation

- [X] T068 [US10] `axon-ai/console/src/api/hooks/assistants.ts`: `useSaveAuth(name)` (`PUT …/auth`, como `useSaveMcp`)
- [X] T069 [US10] `axon-ai/console/src/features/assistants/PermissionsTab.tsx` (R25) e
  `src/features/assistants/Permissions.module.css` (tokens do `DESIGN.md`); `AssistantDetail.tsx`: aba "Permissões"
  entre MCP e Histórico; `router.tsx`: rota `permissoes`
- [X] T070 [US10] Seção `auth` nas telas existentes (R26): `editorParts.overrideMeta` (resumo de `auth`),
  `HistoryTab` (seção "Permissões", esquemas e entradas), `AssistantsPage` (selo "Permissões" ao lado de Modelos e MCP),
  `i18n` se houver texto de seção centralizado. Rodar T067: verde

### E2E e verificação

- [X] T071 [P] `axon-ai/console/e2e/serve_platform.py`: um Assistant `overrides: [auth]` público e um privado, com
  `auth` próprios; `e2e/keys.spec.ts` (criar `relatorios`, copiar, "Concluir", a chave ausente da página; rotacionar e
  conferir pela API — `request` do Playwright em `/private/v1/health` — a antiga 401 e a nova 200; revogar com
  confirmação na linha) e `e2e/permissions.spec.ts` (ligar "Chave de API", adicionar `svc:relatorios`, salvar, ver o
  efetivo; travada no Assistant sem `auth`); `e2e/a11y.spec.ts`: `/acesso/chaves`, o diálogo aberto e
  `/assistentes/<nome>/permissoes`
- [X] T072 Suítes (a partir de `axon-ai/console/`, `source ~/.nvm/nvm.sh && nvm use`): `npm ci && npm run typecheck &&
  npm run lint && npm test` e `npm run e2e`
- [X] T073 [P] `specs/README.md` (linha da 013 com US9 e US10) e `contracts/screens.md` conferido contra a tela

### Dependencies (US9, US10)

T060 → T061 ∥ T062 → (US9) T063 → T064 → T065 → T066; (US10) T067 → T068 → T069 → T070; T071 depois das duas →
T072 → T073.

### Notas da execução (US9, US10)

- `renderAt` (`tests/render.tsx`) passou a devolver também o `QueryClient`, para o teste conferir que a chave em claro
  não fica em nenhuma query nem mutação depois de fechado o diálogo (SC-009).
- A seção `auth` no `zod` exigiu um terceiro guarda, `isModelsPayload`: o `ModelsTab` tratava "não é MCP" como "é
  modelos", o que, com `auth`, leria as permissões como papéis.
- Os nomes das seções foram para um lugar só (`SECTION_TEXT` em `i18n/pt-BR.ts`), usados pela lista, pelo histórico e
  pelos selos.
- Conferência visual (capturas pelo Playwright, nos dois temas): a chave no diálogo aparecia rolada até o fim — o
  diálogo foca o campo e a seleção no foco rola o `input` —, escondendo o começo `axn_<identificador>`; virou um
  `textarea` somente leitura de duas linhas, com a chave inteira, sem seleção no foco.
- Dois testes de unidade corrigidos antes de passar: as sugestões chegam por duas requisições (chaves e grupos), e o
  texto "Permissões" casava primeiro com a aba, não com a célula do histórico.
- Suítes: `npm ci`, typecheck e lint limpos (com `no-console` em `src/`); 146 testes de unidade; e2e 48 passed e 4
  skipped (o teste de fumaça do nginx, sem `CONSOLE_NGINX_URL`), inclusive `keys.spec.ts`, `permissions.spec.ts` e o
  axe nas telas novas e no diálogo, nos temas claro e escuro e na largura de tablet.


---

## Passada de 2026-10-22: `vision` na aba Modelos ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md); research R28)

- [X] T074 `roleValue`, `refOfRole`, `sees` em `api/schemas.ts`; PUT de `models` com `{model, vision}`; a aba Modelos com
  a caixa "Enxerga imagens" e o selo "Visão"; resumo, histórico e lista lendo as duas formas (R28)
- [X] T075 [P] Testes: Vitest (marcar e enviar; ler o objeto e mostrar o selo) e e2e (`assistant-models.spec.ts`: 400
  `vision_unsupported` antes, 200 depois de salvar)

---

## Passada de 2026-10-28: o repasse dos scripts dos gráficos ([ADR-052](../../docs/adr/ADR-052-graficos-na-conversa.md))

**Goal**: com a console, o `AXON_PUBLIC_URL` é o domínio dela; o iframe do Open WebUI carrega os scripts dos gráficos
desse domínio, então o nginx repassa `/static/` ao core, como os outros prefixos.

- [X] `deploy/nginx.conf.template`: `location /static/` com `proxy_pass` ao core, sem cabeçalho próprio (os do core:
  cache imutável, CORS, `nosniff`); `contracts/serving.md` com o prefixo
- [X] `e2e/serving.spec.ts`: o locale do ECharts pelo nginx, 200, imutável, com CORS e sem a CSP da SPA — 5 passed com
  o nginx da instalação (`e2e/serve_nginx.sh`) e a plataforma do e2e

## Correção de 2026-10-30: MCP delegado na console (ADR-055)

- [X] T076 Reproduzir lista mista rejeitada e cobrir detalhes, edição sem downgrade e aba do Assistant.
- [X] T077 Aceitar o contrato delegado e distinguir verificação por execução nos dois consumidores de saúde.
- [X] T078 Validar typecheck, lint, Vitest e e2e contra API real: 153 testes de unidade e 5 e2e MCP passaram;
  publicação segue a versão 0.7.0rc15.

## Passada de 2026-11-03: Meio ambiente — US11 ([ADR-056](../../docs/adr/ADR-056-impacto-ambiental-estimado-pelo-ecologits.md); research R29, R30)

- [X] T079 [US11] `axon-ai/console/src/api/schemas.ts` (`impactReportSchema`), `src/api/hooks/impact.ts`
  (`useImpact`) e `keys.ts`
- [X] T080 [P] [US11] `src/i18n/format.ts` (`measureParts`, `formatMeasure`, `measureFormatter`, `formatTrees`,
  `formatPercent`) e `src/features/impact/grain.ts` (rótulos do grão, semana ISO)
- [X] T081 [US11] `src/features/usage/DailyChart.tsx`: props opcionais para baldes (R29), sem mudar Uso e custo
- [X] T082 [US11] `src/features/impact/ImpactPage.tsx`, `ImpactTable.tsx` e `ImpactPage.module.css`: filtros, período
  personalizado, faixas, cinco gráficos, tabela com "Aproximado", nota de método e estados (desligado, vazio, erro)
- [X] T083 [US11] `src/i18n/pt-BR.ts` (`NAV`), `src/ui/icons.tsx` (`folha`), `src/app/router.tsx` (`meio-ambiente`)
- [X] T084 [US11] `src/features/usage/StatStrip.tsx`, `StatStrip.module.css` e `UsagePage.tsx`: a célula Emissões
  (FR-036)
- [X] T085 [P] [US11] `tests/msw/fixtures.ts` e `handlers.ts` (`/impact`, ordens de grandeza do EcoLogits);
  `tests/impact/impact.test.tsx` (faixas, gráficos, grão, período personalizado com recusa no campo, desligado, vazio,
  erro, célula Emissões)
- [X] T086 [P] [US11] `e2e/impact.spec.ts`; `/meio-ambiente` (por dia e por semana) em `e2e/a11y.spec.ts`;
  `e2e/serve_platform.py` estima o uso semeado com `ImpactService.backfill`
- [X] T087 `npm run typecheck && npm run lint && npm test`; `npx playwright test` (impacto, a11y nos dois temas e no
  tablet, uso, teclado); capturas comparadas com o mockup aprovado


## Passada de 2026-11-05: US12 — escopos, apagar conta e um grupo de cada vez (incremento 9.7; [ADR-057](../../docs/adr/ADR-057-escopos-da-chave-de-api.md), [ADR-058](../../docs/adr/ADR-058-apagar-conta-em-cascata.md), [ADR-059](../../docs/adr/ADR-059-o-que-fica-do-apagamento-e-pseudonimizado.md); research R31–R36)

**Goal**: escopos na emissão e na lista de chaves; apagar uma conta pelo nome, com o relatório completo ou parcial; o
selo "Em apagamento" com "Concluir apagamento"; os grupos da ficha valendo na hora.

**Independent Test**: a partir de `axon-ai/console/`, `npm test -- access keys` e `npx playwright test e2e/access.spec.ts
e2e/keys.spec.ts e2e/a11y.spec.ts`.

**Pré-requisito**: as tarefas T152–T153 da 008 (`deleting` na visão da conta).

### Fundação

- [X] T088 [US12] `console/src/api/schemas.ts`: `apiKeySchema.scopes` (`z.array(z.enum(["inference", "users",
  "admin"]))`), `accountSchema.deleting` (`z.boolean().default(false)`) e `deletionReportSchema` (data-model);
  `console/src/api/errors.ts` e `client.ts`: `ApiError.body` (o corpo JSON do erro, opcional nas opções do construtor, como `param` — achado I1) e
  `deletionReportOf(error)`
- [X] T089 [US12] `console/src/api/hooks/apiKeys.ts`: `useCreateKey` envia `scopes`; `console/src/api/hooks/access.ts`:
  `useDeleteUser`, `useAddGroup`, `useRemoveGroup` (invalidam pessoas e grupos) e `useUpdateUser` sem `groups`
- [X] T090 [P] [US12] `console/src/i18n/pt-BR.ts`: rótulos dos escopos (`admin` → "Administração"), das partes do
  relatório (`assistants` → "Assistants e chaves", `mcp` → "Servidores MCP", `conversations` → "Conversas", `audit` →
  "Auditoria de tools", `observability` → "Preços e ajustes") e das contagens, com o nome cru como reserva
- [X] T091 [P] [US12] `console/tests/msw/handlers.ts` e `fixtures.ts`: `scopes` nas chaves, `deleting` nas contas,
  `DELETE /users/{u}` (200 com relatório; 503 `deletion_incomplete` com `report` quando a fixture pede), `PUT`/`DELETE
  /users/{u}/groups/{g}` (200; 409 `protected_group`; 404)

### Testes primeiro

- [X] T092 [P] [US12] `console/tests/access/keys.test.tsx`: escopos no diálogo (padrão `inference`, nenhum bloqueia,
  `users` sozinho), recusa `param: "scopes"` no `fieldset`, coluna "Escopos" com `admin` e a nota, escopos no diálogo da
  chave em claro
- [X] T093 [P] [US12] `console/tests/access/access.test.tsx`: "Apagar conta" ausente na própria conta; botão desabilitado
  até o nome exato; relatório completo sem `deleted:`; 503 com o parcial, a parte "Falhou" e "Tentar de novo" que conclui;
  conta com `deleting` com o selo e só "Concluir apagamento"; 409 do último admin com o motivo; grupos da ficha valendo na
  hora (sucesso; recusa volta a caixa e mostra o motivo; o clique manda só `PUT /users/bia/groups/equipe`, nenhum `PATCH`
  com a lista — achado C1); o "Salvar" sem `groups`

### Implementação

- [X] T094 [US12] `console/src/features/access/KeysTab.tsx` e `IssuedKeyDialog.tsx` (R31): `fieldset` de escopos,
  coluna "Escopos", escopos na chave emitida
- [X] T095 [US12] `console/src/features/access/DeleteAccountDialog.tsx` (novo; R32, R33, R34): confirmação pelo nome,
  relatório completo e parcial, "Tentar de novo", modo "Concluir apagamento" — a explicação curta e um botão "Concluir",
  sem o nome, que só então envia (achado A1)
- [X] T096 [US12] `console/src/features/access/UsersTab.tsx` (R32, R34): "Apagar conta" no menu (último, tom de perigo,
  fora da própria conta), selo "Em apagamento" e o menu só com "Concluir apagamento"
- [X] T097 [US12] `console/src/features/access/GroupToggles.tsx` (novo) e `PersonDialog.tsx` (R35): grupos fora do
  formulário, uma caixa por grupo com `aria-busy`, recusa ao lado e a caixa de volta; "Salvar" com nome e e-mail. Rodar
  T092–T093 e ver passar

### e2e e polish

- [X] T098 [P] [US12] `console/e2e/keys.spec.ts` e `e2e/access.spec.ts`: criar uma chave só com "Gerenciar usuários e
  grupos" e ver a coluna; cadastrar uma pessoa, apagá-la digitando o nome, ver o relatório e a lista sem ela, sem
  `deleted:` na página; pôr e tirar um grupo pela ficha
- [X] T099 [P] [US12] `console/e2e/a11y.spec.ts` (SC-012): axe no diálogo de chave com os escopos, no de apagar
  (confirmação e relatório) e na ficha com os grupos, nos dois temas; o fluxo de apagar só pelo teclado
- [X] T100 Verificação a partir de `axon-ai/console/`: `npm run typecheck && npm run lint && npm test` e `npm run e2e`;
  `specs/README.md` (linha da 013), `docs/roadmap.md` e `graphify update .`

**Dependências**: T152–T153 da 008 antes de tudo; T088 → T089; T090 e T091 em paralelo com T089; T092–T093 antes de
T094–T097; T098–T099 depois da implementação; T100 por último.

**Paralelo**: T090, T091, T092 e T093; T098 e T099. **MVP**: a passada inteira (cada parte é pequena; o apagamento
— T095, T096 — é o centro).

**Execução (2026-11-05)**: T088–T100 feitas, depois de T152–T153 da 008. Notas:
- A ordem foi fundação → implementação → testes novos: o código precisava existir para a tipagem das fixtures fechar.
  Os testes novos (13 no Vitest, 3 no e2e, 3 no axe) foram escritos depois, contra o comportamento da spec.
- O e2e achou dois defeitos, corrigidos: a caixa de grupo só mudava depois da resposta (agora muda na hora e volta se a
  plataforma recusa, R35); e o relatório tinha um segundo botão "Fechar", além do X do diálogo (agora "Concluir" no
  completo e "Deixar para depois" no parcial).
- `ScopeList` ficou num arquivo próprio para não criar ciclo entre `KeysTab` e `IssuedKeyDialog`.
- Testes existentes atualizados pelo contrato novo: a fixture `issued()` e o corpo esperado da emissão em
  `keys.test.tsx` (`scopes`), e as fixtures do MSW (`scopes`, `deleting`, a conta `bia`).
- Console: tipagem e lint limpos; Vitest 170 passaram; Playwright 65 passaram (com o axe nos dois temas e no tablet).


## Passada de 2026-11-08: US13 — a console no celular e instalável ([ADR-060](../../docs/adr/ADR-060-console-no-celular-e-instalavel.md); research R37–R43)

**Goal**: abaixo de 640px, layout de app (cabeçalho de app, barra inferior e "Mais", tabelas em lista, diálogos como
folha, alvos de 44px), sem nenhuma tela rolando de lado; a console instalável como PWA (manifest, ícones, service
worker da casca, "Sem conexão", `theme-color` pelo tema).

**Independent Test**: a partir de `axon-ai/console/`, `npm test` e `npx playwright test --project=celular
--project=celular-escuro --project=pwa`; com o nginx (`e2e/serve_nginx.sh`), `CONSOLE_NGINX_URL=http://127.0.0.1:8080
npx playwright test e2e/serving.spec.ts`.

**Referência visual**: Penpot, "axon mockup", página "Console — celular" (Uso e custo claro e escuro, "Mais", Assistentes,
Assistant — Modelos, Acesso — usuários, Cadastrar pessoa como folha, Sem conexão claro e escuro, Ícone do app).

### Desenho e fundação

- [X] T101 [US13] Penpot: página "Console — celular" com os boards acima, a partir dos tokens e ícones da console
- [X] T102 [US13] `console/src/i18n/pt-BR.ts`: `NAV_PRIMARY` e `NAV_SECONDARY`; `src/ui/icons.tsx`: ícone `instalar`
- [X] T103 [US13] `console/src/ui/Page.tsx`: `PageChrome`/`PageChromeSetter` (título e "voltar" publicados pelo
  `PageHeader`); `Page.module.css` abaixo de 640px

### Testes primeiro

- [X] T104 [P] [US13] `console/tests/app/mobile-shell.test.tsx` (barra inferior, "Mais" ativo nas secundárias, folha
  com o foco devolvido, "voltar" no detalhe), `tests/app/theme-color.test.ts`, `tests/ui/table-labels.test.tsx`
- [X] T105 [P] [US13] `console/e2e/mobile.spec.ts` (nenhuma tela rola de lado, barra inferior e "Mais", lista de linhas,
  folha), `e2e/pwa.spec.ts` (manifest e ícones, service worker, "Sem conexão", nada da API no cache, `theme-color`) e o
  caso do app instalável em `e2e/serving.spec.ts`; projetos `celular`, `celular-escuro` e `pwa` no
  `playwright.config.ts`, com `serviceWorkers: "block"` nos outros

### Implementação

- [X] T106 [US13] Casca (R38): `src/app/Shell.tsx`, `AppBar.tsx`, `BottomNav.tsx`, `MoreSheet.tsx`, `src/ui/Sheet.tsx`;
  `Sidebar.tsx` exporta `THEMES`, `adminLabel` e `Brand`, e some abaixo de 640px
- [X] T107 [US13] Primitivas (R39, R40): `Table` (rótulos e papéis explícitos, lista no celular, `stack={false}`),
  `Dialog` (folha, fileiras só de botões empilhadas), `TabNav` e `Segmented` (rolam de lado), `Button`, `Field` e
  `Checkbox` (44px, 16px), `global.css` (`100dvh`, toque e `display-mode: standalone`)
- [X] T108 [US13] Telas: `StatStrip`, `DailyChart` (piso de 240px, toque, marcos com reticências), `ImpactPage`
  (filtros), `PricesPage`, `Editor.module.css` (rodapé preso só com alteração, `data-dirty`), `McpServersPage`,
  `Access.module.css`
- [X] T109 [US13] PWA (R41, R42): `public/manifest.webmanifest`, `public/icons/` (gerados por `scripts/pwa-icons.mjs`),
  `public/offline.html` e `offline.css`, `src/pwa/sw.js` e o plugin `pwaServiceWorker` no `vite.config.ts`,
  `src/app/pwa/registerServiceWorker.ts` e `useInstallPrompt.ts`, meta do app em `index.html`, `theme-color` em
  `src/app/theme.ts`
- [X] T110 [US13] `console/deploy/nginx.conf.template`: `location = /manifest.webmanifest` com
  `application/manifest+json` (o `mime.types` do nginx 1.28 não tem `webmanifest`)

**Execução (2026-11-08)**: T101–T110 feitas. Notas:
- A linha de base em 390×844 tinha 5 das 7 telas principais rolando de lado (Assistentes a 745px) e a faixa de números
  sobreposta; depois, nenhuma tela rola, nos dois temas.
- O e2e achou três defeitos, corrigidos: a barra inferior por cima da folha do diálogo (`z-index`), as caixas de seleção
  de 16px empilhadas (axe `target-size`; a linha passou a 44px) e o foco que não voltava ao "Mais" (a `Sheet` guarda
  quem abriu, como o `Dialog`).
- O seletor de cinco períodos de Meio ambiente alargava o cabeçalho: as ações do `PageHeader` têm `contain:
  inline-size` no celular.
- Console: tipagem e lint limpos; Vitest 178 passaram; Playwright 91 passaram (claro, escuro, tablet, celular,
  celular-escuro e pwa) e os 6 do nginx.

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

- [ ] T001 Criar o projeto: `.nvmrc` (`24`), `package.json` (nome `@agentic/console`, `private`, `engines.node`
  `>=22.12`, scripts `dev`, `build`, `preview`, `typecheck`, `lint`, `test`, `e2e`) com as versões **exatas** de
  [research.md](research.md) R1; `npm install` gera `package-lock.json`; `tsconfig.json` estrito; `vite.config.ts` com o
  plugin React e o repasse de `/v1`, `/private/v1`, `/admin/v1`, `/oauth2`, `/.well-known` para
  `process.env.AI_CORE_UPSTREAM ?? "http://127.0.0.1:8000"` em `dev` e `preview`
- [ ] T002 [P] `eslint.config.js` (flat, `typescript-eslint`, `react-hooks`, `jsx-a11y`, e `no-restricted-imports`/
  `no-restricted-globals`: `fetch` e `oidc-client-ts` só em `src/api/` e `src/auth/`), `.prettierrc`, `.gitignore`
  (`dist/`, `node_modules/`, `test-results/`, `playwright-report/`)
- [ ] T003 [P] `index.html` (`lang="pt-BR"`, sem script inline, título "Console"), `src/main.tsx` vazio que monta o
  `App`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: nenhuma user story antes de T004–T016

- [ ] T004 `src/ui/tokens.css`: as variáveis dos temas a partir dos tokens do Penpot (26 cores por tema —
  `--fundo-base`, `--fundo-sutil`, `--fundo-realce`, `--borda-base`, `--borda-forte`, `--texto-primario`,
  `--texto-secundario`, `--texto-terciario`, `--texto-sobre-acao`, `--acao-*`, `--estado-*`, `--serie-1..4` —, espaço
  4–48, raio 6/8/999, tamanhos 12/13/14/16/24/28/48); `:root[data-theme="light"]`, `:root[data-theme="dark"]` e o padrão
  por `prefers-color-scheme`; no escuro, `--acao-base` = `#2563EB` (contraste 5,2:1 com texto branco)
- [ ] T005 [P] `src/ui/global.css`: fontes self-host (Mona Sans e JetBrains Mono do `@fontsource`, pesos
  400/500/600/700, latino), `font-variant-numeric: tabular-nums` nas tabelas, seleção, cursor, barra de rolagem, anel de
  foco (2 px `--acao-base` com 2 px de afastamento), `prefers-reduced-motion`
- [ ] T006 [P] `src/ui/icons.tsx`: os 22 ícones do Penpot (16 px, traço 1,5, `currentColor`) e o "G" do Google
- [ ] T007 Componentes de `src/ui/` conforme a folha "Componentes" do Penpot, com CSS Modules e testes de unidade e axe
  em `tests/ui/`: `Button` (primary, secondary, ghost, danger; sm/md/lg; ícone; desabilitado), `Badge` (ok, warn, bad,
  accent, neutral; ponto; ícone), `Field` (rótulo, ajuda, erro, somente leitura com selo "Definido na instalação",
  monoespaçado para identificadores), `Select`, `Segmented`, `Tabs`, `Toggle`, `Checkbox`, `Notice` (info, warn, bad,
  neutral, ok; ação), `Table` (cabeçalho, linhas, rodapé, alinhamento numérico), `Dialog` (Radix), `Skeleton`,
  `EmptyState`
- [ ] T008 [P] `src/i18n/pt-BR.ts` (textos das telas do Penpot) e `src/i18n/format.ts` (`Intl` `pt-BR`: números,
  tokens compactos "21,1 M", "US$ 41,87" a partir de string decimal, datas no fuso informado) com testes em
  `tests/i18n/`
- [ ] T009 `src/api/errors.ts` (`ApiError(status, code, param, message, currentVersion)`) e `src/api/schemas.ts` (os
  esquemas `zod` de [data-model.md](data-model.md)); `tests/api/schemas.test.ts` valida cada exemplo de
  [admin-api.md](../008-core-http-api/contracts/admin-api.md) e recusa variações (campo faltando, tipo errado)
- [ ] T010 `src/auth/userManager.ts` (R5: cliente `console`, `authority` = origem, PKCE, `InMemoryWebStorage`,
  renovação por token de renovação), `AuthProvider.tsx`, `Callback.tsx` (volta à rota do `state`); testes em
  `tests/auth/` com o `UserManager` simulado
- [ ] T011 `src/api/client.ts`: `fetch` same-origin com `Bearer`; `401` → uma renovação e uma nova tentativa, depois
  `signinRedirect`; envelope de erro → `ApiError`; validação pelo esquema; testes com MSW em `tests/api/client.test.ts`
- [ ] T012 `src/app/router.tsx` (rotas de [contracts/screens.md](contracts/screens.md), carregadas sob demanda),
  `src/app/RequireAdmin.tsx` (`GET /me`: 200 → shell; 404 → `AccessDenied`), `src/app/AccessDenied.tsx` (desenho
  "Acesso negado"), `src/app/ErrorBoundary.tsx`
- [ ] T013 `src/app/Shell.tsx` e `src/app/Sidebar.tsx`: barra lateral de 240 px com nome e logotipo da instalação do
  `/me` (FR-020), navegação, seletor de tema de três estados (FR-019, `localStorage["console.theme"]`), usuário e "Sair"
- [ ] T014 [P] MSW: `tests/msw/handlers.ts` com respostas do contrato para todas as rotas (dados do desenho)
- [ ] T015 `e2e/serve_platform.py`: escreve um `identity.yaml` temporário com os clientes `console` (retorno
  `http://127.0.0.1:4173/callback`, pós-logout `http://127.0.0.1:4173/`) e `open-webui` (retorno de teste) e aponta
  `AI_CORE_IDENTITY_CLIENTS_FILE` para ele; sobe `platform(profile="test")` com `AI_CORE_IDENTITY_ENABLED=true`,
  `AI_CORE_PUBLIC_URL=http://127.0.0.1:4173`, provider de
  modelo programado, Google simulado, admin semeado, Assistants `geral` (`overrides: [models, mcp]`), `rascunho` (sem
  `overrides`), `documentos` (sobreposição que o YAML mudou), servidores MCP de teste e uso semeado de 30 dias; serve
  `platform.app` com uvicorn em `127.0.0.1:8000`; `playwright.config.ts` com os dois `webServer` (R11) — o da plataforma
  com `command: "uv run python console/e2e/serve_platform.py"` e `cwd: ".."` (o workspace `ai-core/`), o do
  `vite preview` na porta 4173 —, projetos claro e escuro, 1440 e 768 de largura
- [ ] T016 [P] `e2e/fixtures/` (login como admin e como não admin pelo formulário da 012) e o helper de axe

**Checkpoint**: shell navegável, login e acesso negado funcionando contra a plataforma em memória

---

## Phase 3: User Story 1 — Admin entra na console (Priority: P1) 🎯 MVP

- [ ] T017 [P] [US1] `e2e/auth.spec.ts`: sem sessão → página de login da 012 → volta à rota pedida; Google simulado;
  não admin → acesso negado sem nenhuma chamada administrativa além do `/me` (SC-007); token vence durante a edição →
  renovação sem perder o rascunho; sair encerra a sessão na 012 e a volta exige login; nada no `localStorage` além de
  `console.theme` e nada no `sessionStorage` (SC-006)
- [ ] T018 [US1] Ajustes de T010–T013 até T017 verde; axe na página de acesso negado e no shell, nos dois temas

---

## Phase 4: User Story 2 — Trocar os modelos de um Assistant (Priority: P1)

- [ ] T019 [P] [US2] Testes de componente em `tests/assistants/` (MSW): estados carregando, vazio e erro da lista e do
  detalhe; lista com os selos; aba Modelos editável, travada e com sobreposição inativa; `422` mostrado junto ao papel; `409` mantém o rascunho e oferece "Recarregar"; descarte
  com confirmação na própria tela
- [ ] T020 [P] [US2] `e2e/assistant-models.spec.ts`: cenários 1–6 da US2 contra a plataforma; SC-001 (troca e conversa
  seguinte com o modelo novo, pela API de chat do perfil de teste)
- [ ] T021 [US2] `src/api/hooks/assistants.ts` e `src/features/assistants/AssistantsPage.tsx` (busca, filtros pela URL,
  selos)
- [ ] T022 [US2] `src/features/assistants/AssistantDetail.tsx` (cabeçalho com estado, anterior/próximo, abas) e
  `ModelsTab.tsx` (por papel: YAML, sobreposição com `Select` e "Testar modelo" por `POST …/models/check`, efetivo;
  travado; inativa; rodapé com autor, versão e alterações não salvas; salvar e descartar)
- [ ] T023 [US2] `HistoryTab.tsx` (histórico da 003) e rodar T019–T020 até verde

---

## Phase 5: User Story 3 — Gerenciar os MCPs de um Assistant (Priority: P1)

- [ ] T024 [P] [US3] Testes de componente da aba MCP (MSW; estados carregando, sem servidores globais e erro) e
  `e2e/assistant-mcp.spec.ts` (cenários 1–4 da US3)
- [ ] T025 [US3] `src/features/assistants/McpTab.tsx`: um cartão por servidor global com `Toggle`, estado e contagem;
  tools da saúde do servidor com "Permitida" e "Escrita" (bloqueada em Assistant público, com o aviso); servidor
  indisponível com o motivo; salvar e descartar; rodar T024 até verde

---

## Phase 6: User Story 4 — Ver uso e custo (Priority: P2)

- [ ] T026 [P] [US4] Testes de `tests/usage/` (MSW): faixa de números (custo como figura principal, "Incompleto"),
  gráfico (barras empilhadas na ordem fixa da paleta, legenda, dica por teclado, tabela equivalente), estados vazio,
  carregando e erro; `e2e/usage.spec.ts` (cenários 1–4 da US4; SC-004 com o uso semeado de 90 dias)
- [ ] T027 [US4] `src/features/usage/StatStrip.tsx` e `UsageTable.tsx`
- [ ] T028 [US4] `src/features/usage/DailyCostChart.tsx` (SVG + `d3-scale`, R2): barras ≤ 24 px, topo 4 px, vão de
  2 px, grade de 1 px, marcos de preço novo (das vigências do período) e de sobreposição (do histórico de cada
  Assistant, chamadas em paralelo e em cache pelo TanStack Query), coluna em foco com dica, `role="img"` com descrição e
  a tabela como alternativa
- [ ] T029 [US4] `src/features/usage/UsagePage.tsx` (período, agrupamento e origem na URL) e `PricesPage.tsx` (formulário
  de novo preço, modelos usados sem preço destacados, vigências); rodar T026 até verde

---

## Phase 7: User Story 5 — Configurar o Langfuse (Priority: P2)

- [ ] T030 [P] [US5] Testes de `tests/observability/` (MSW; estados carregando e erro) e `e2e/observability.spec.ts`
  (cenários 1–4 da US5): campos
  da instalação somente leitura; segredo só "definido"; `master_key_missing` explicado; captura só depois de marcar "Li e
  quero capturar o texto"
- [ ] T031 [US5] `src/features/observability/ObservabilityPage.tsx` e `CaptureConsent.tsx`; rodar T030 até verde

---

## Phase 8: User Story 6 — Login e contas (Priority: P2)

- [ ] T032 [P] [US6] Testes de `tests/access/` (MSW; estados carregando, vazio — só o admin inicial — e erro) e
  `e2e/access.spec.ts` (cenários 1–4 da US6; cadastrar e entrar com
  a senha temporária; desativar e ver o login recusado)
- [ ] T033 [US6] `src/features/access/AccessPage.tsx`, `UsersTab.tsx` (busca, estados, ações), `PersonDialog.tsx`
  (cadastro e senha temporária mostrada uma vez, "Copiar"), `GroupsTab.tsx` (grupo de administração protegido),
  `LoginTab.tsx` (Google, endereço de retorno copiável, "Definido na instalação"); rodar T032 até verde

---

## Phase 9: User Story 7 — Servidores MCP globais (Priority: P3)

- [ ] T034 [P] [US7] Testes de componente (estados carregando, vazio e erro) e `e2e/mcp-servers.spec.ts` (cenários 1–2
  da US7)
- [ ] T035 [US7] `src/features/mcp/McpServersPage.tsx` e `McpServerForm.tsx` (somente leitura para o arquivo do
  operador; credencial só por referência, nunca valor); rodar T034 até verde

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T036 `deploy/nginx.conf.template` conforme [contracts/serving.md](contracts/serving.md) e um teste de fumaça em
  `e2e/serving.spec.ts` contra `nginx` em contêiner (CSP, cache, repasse sem reescrita, SSE)
- [ ] T037 [P] `.github/workflows/console.yml` (R13)
- [ ] T038 Rodada de inspeção da impeccable: capturas em 1440 e 768, claro e escuro, de todas as telas e estados em
  `.impeccable/review/`; `impeccable detect --json` nos arquivos alterados; corrigir o que for mecânico; o axe roda em
  `e2e/a11y.spec.ts` em todas as telas nos estados com dados, vazio e erro, nos dois temas (SC-005)
- [ ] T039 `e2e/keyboard.spec.ts` (FR-017): cada tela percorrida só com Tab, Shift+Tab, Enter, Espaço e setas (abas,
  segmentados, tabelas, formulários, dica do gráfico); foco sempre visível; o diálogo prende o foco e o devolve a quem o
  abriu; nenhuma ação só com mouse
- [ ] T040 Revisão final pelo `impeccable-finish-reviewer` (contrato de direção, telas do Penpot como referência, o
  craft floor, as capturas, os achados do detector); aplicar as correções em um lote e uma segunda rodada no máximo
- [ ] T041 `DESIGN.md` e `.impeccable/design.json` pelo `impeccable-documenter` a partir da console construída
- [ ] T042 [P] `specs/README.md` (status da 013) e `CLAUDE.md` (a console existe; como rodar)
- [ ] T043 Rodar o [quickstart.md](quickstart.md) inteiro (typecheck, lint, test, e2e com axe)

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

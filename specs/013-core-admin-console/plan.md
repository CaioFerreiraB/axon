# Implementation Plan: Console de administração

**Branch**: `013-core-admin-console` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/013-core-admin-console/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/013-core-admin-console/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-029, ADR-031–ADR-034, o contrato
[admin-api.md](../008-core-http-api/contracts/admin-api.md), o protocolo da 012, o desenho aprovado no Penpot, o
`PRODUCT.md` e o contrato de direção (`.impeccable/surfaces/ai-core-console.md`). **Refinamentos do `design.md`, sem
divergência de decisão**: gráficos em SVG próprio com `d3-scale` (R2, no lugar de Recharts/visx), CSS Modules (R3) e as
versões fixadas (R1). **Nenhum ADR novo.**

## Summary

Uma SPA React + TypeScript em `ai-core/console/`, servida por nginx na mesma origem da plataforma, que entra pelo
provedor da 012 como cliente público com PKCE e fala só com `/admin/v1` (ADR-029, ADR-031). Sete áreas, no desenho
aprovado (padrão da categoria, no acabamento de Vercel e Linear, Mona Sans, temas claro e escuro): uso e custo, preços,
Assistants (modelos, MCP e histórico), servidores MCP, observabilidade, acesso (usuários, grupos e login) e acesso
negado. Nenhuma regra de negócio: validação, autorização e precedência vêm da API. Escopo: **US1–US7**.

## Technical Context

**Language/Version**: TypeScript 6.0.3 sobre Node 24 (build e testes); o artefato é HTML/CSS/JS estático

**Primary Dependencies**: React 19.3, React Router 8.4, TanStack Query 5.104, react-hook-form 7.89 + zod 4.6,
oidc-client-ts 3.5, primitivas Radix, d3-scale 4 (R1, R2)

**Storage**: nenhum; sessão OIDC em memória; `localStorage` só para o tema

**Testing**: Vitest 5 + Testing Library + MSW 3; Playwright 1.63 + axe contra a plataforma em memória (R11)

**Target Platform**: navegadores atuais de desktop e tablet (Chrome, Firefox, Safari, Edge — duas últimas versões);
nginx `unprivileged` na imagem da instalação (002)

**Project Type**: aplicação web (SPA) fora do workspace Python

**Performance Goals**: dashboard de 90 dias pronto em < 2 s com 100 mil chamadas (SC-004; o relatório da 009 responde em
< 1 s); bundle inicial < 250 KB gzip; rotas carregadas sob demanda

**Constraints**: CSP `default-src 'self'` (nada de terceiros em tempo de execução); nenhum token nem dado
administrativo no armazenamento persistente (SC-006); WCAG 2.2 AA nos dois temas (SC-005); pt-BR

**Scale/Scope**: 12 rotas, ~40 componentes, 1 instalação com poucos admins

Nenhum `NEEDS CLARIFICATION`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | Nome e logotipo da instalação vêm da API; nenhum termo de domínio na console |
| II. Seams | ✅ | Consome só o contrato HTTP da 008 e o protocolo da 012; não importa código do core |
| IV. Assistant é a fronteira | ✅ | A console não decide permissão: 404 do `/me` mostra acesso negado; cada recusa vem da API |
| VI. Conteúdo externo | ✅ | Segredo só de escrita; senha temporária só no diálogo; tokens em memória; CSP restrita |
| XI. API independente da interface | ✅ | Toda ação tem rota (SC-002); a console é opcional (ADR-029) |
| XII. Simplicidade | ✅ | Sem biblioteca de gráficos nem de estilos utilitários; uma SPA estática |
| XIII. Portas e adapters | ✅ (adaptado) | Não é módulo do núcleo; por dentro, telas não chamam `fetch` nem o cliente OIDC direto — só hooks de `src/api/` e `src/auth/` (design, "Portas e adapters") |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-core/console/**`; fora dele, `.github/workflows/console.yml`
  e `specs/README.md`
- [x] Every consumed seam is listed with its owner spec — API de administração (008), protocolo OIDC (012)
- [x] Every seam this module exposes has a conformance test planned — não expõe seam; os esquemas do contrato da 008
  têm teste (R6)
- [x] No seam changes
- [x] Import boundaries cover the new code — regra de ESLint (`no-restricted-imports`) impede `fetch`/`oidc-client-ts`
  fora de `src/api/` e `src/auth/`

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / … — **não se aplica** a um cliente web; a separação equivalente está no `design.md`
  (cliente da API e sessão OIDC como portas de saída; telas como entrada)
- [x] No infrastructure framework in the core layers — telas sem `fetch` nem cliente OIDC (regra de ESLint)
- [x] Other modules are imported only through their `api.py` — a console não importa módulo nenhum
- [x] All I/O … go through a port — rede só em `src/api/client.ts` e `src/auth/`; tempo só para exibir
- [x] Every port exists for I/O … — duas: API e sessão
- [x] In-memory adapter and conformance — MSW nos testes de unidade; plataforma real em memória no e2e
- [x] Services and adapters of other modules are instantiated only in the composition root — não se aplica

**Resultado do gate (antes da Phase 0)**: PASS. **Depois da Phase 1**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/013-core-admin-console/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md          # R1–R13
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── screens.md       # tela → chamadas → ações → estados
│   └── serving.md       # nginx: SPA, repasse, cache, CSP
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-core/console/
├── .nvmrc  package.json  package-lock.json  tsconfig.json  vite.config.ts  eslint.config.js  .prettierrc  index.html
├── src/
│   ├── main.tsx  app/{router.tsx, Shell.tsx, Sidebar.tsx, ErrorBoundary.tsx, AccessDenied.tsx}
│   ├── auth/{userManager.ts, AuthProvider.tsx, Callback.tsx, RequireAdmin.tsx}
│   ├── api/{client.ts, errors.ts, schemas.ts, hooks/*.ts}
│   ├── features/
│   │   ├── usage/{UsagePage.tsx, StatStrip.tsx, DailyCostChart.tsx, UsageTable.tsx, PricesPage.tsx}
│   │   ├── assistants/{AssistantsPage.tsx, AssistantDetail.tsx, ModelsTab.tsx, McpTab.tsx, HistoryTab.tsx}
│   │   ├── mcp/{McpServersPage.tsx, McpServerForm.tsx}
│   │   ├── observability/{ObservabilityPage.tsx, CaptureConsent.tsx}
│   │   └── access/{AccessPage.tsx, UsersTab.tsx, PersonDialog.tsx, GroupsTab.tsx, LoginTab.tsx}
│   ├── ui/{tokens.css, global.css, icons.tsx, Button, Badge, Field, Select, Segmented, Tabs, Toggle, Checkbox,
│   │       Notice, Table, Dialog, Skeleton, EmptyState}
│   └── i18n/{pt-BR.ts, format.ts}
├── tests/               # Vitest + Testing Library + MSW
├── e2e/                 # Playwright + axe; serve_platform.py; fixtures/
└── deploy/nginx.conf.template
.github/workflows/console.yml
```

**Structure Decision**: o layout do `design.md`, com os componentes de UI nomeados pelo kit do Penpot.

## Complexity Tracking

Nenhuma violação a justificar.

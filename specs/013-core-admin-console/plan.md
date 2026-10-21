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

---

# Passada de 2026-10-20: identidade Axon (US8; [ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md), [ADR-038](../../docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md), [ADR-039](../../docs/adr/ADR-039-hover-do-botao-primario-no-escuro.md))

> As seções acima são os planos das passadas anteriores e ficam como foram executadas (ADR-037, item 6); os nomes
> antigos nelas se leem pela tabela do ADR-037. Esta seção é o plano da US8.

**Insumos lidos**: [spec.md](spec.md) (US8, FR-020 reescrita, FR-021–FR-023, SC-008, clarificações de 2026-10-20),
[design.md](design.md), ADR-037, ADR-038, ADR-039 (escrito nesta passada, por decisão do mantenedor), `DESIGN.md`
("Brand" e tokens, com o hover escuro novo), `brand-kit/svg/`, a passada da 008 (`me.instance.custom`) e a da 012 (os
mesmos tokens e SVG nas páginas). Research: R15–R21. **Sem divergência do `design.md`** além do desenho da marca, que os
ADRs decidem.

## Summary (US8)

A console mostra a marca Axon ou a da instalação pela regra do ADR-038, com os SVG do `brand-kit` (mais o recorte do
wordmark) e a versão que segue o tema escolhido (R15–R17); o título da aba leva o nome da instalação, o favicon é o símbolo
e a barra do navegador usa o `axon-night` (R18); os tokens passam aos do `DESIGN.md`, com o hover escuro `#1D4ED8`, nos
dois CSS (R19); o pacote vira `@axon/console` (R20). Testes de unidade, e2e com axe e capturas (R21).

## Technical Context (US8)

- **Language/Version, dependências**: sem mudança; o lock do npm é regenerado só pelo nome.
- **Testing**: Vitest (barra lateral, acesso negado, título, SVG, contraste), Playwright + axe nos três projetos, capturas.
- **Constraints**: CSP do nginx (`img-src 'self' data:`); fronteira do ESLint (`fetch` só em `src/api/`); a marca da
  instalação continua vindo da API.
- Nenhum `NEEDS CLARIFICATION`.

## Constitution Check (US8)

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico de domínio | ✅ | Axon é a marca da plataforma; exemplos com "Instituto Exemplo" |
| II. Módulos substituíveis por seams | ✅ | A console só lê `me.instance` (008) e o protocolo da 012; nenhum seam novo |
| XI. API independente da interface | ✅ | A regra de marca própria vem pronta da API (`custom`); a console só a desenha |
| XIII. Portas e adapters | ✅ | Nada muda na fronteira: os SVG são assets, e o `me` continua em `src/api/` |

**Module boundary gate**: `axon-ai/console/**`. Fora da console, o `identity.css` e o teste de contraste da 012 (ADR-039,
os mesmos tokens), o `brand-kit` (o recorte do wordmark), o `DESIGN.md` e o `.impeccable/design.json` (o hover escuro).
**Resultado**: PASS.

## Project Structure (US8)

```text
brand-kit/svg/axon-wordmark-{light,dark}.svg         # recorte do lockup (R15); README com as linhas novas
axon-ai/console/
├── package.json                                     # @axon/console (R20)
├── index.html                                       # favicon, <title>Axon</title>, theme-color #0b0f19 (R18)
└── src/
    ├── brand/*.svg                                  # cópias do brand-kit (R15)
    ├── app/brand/{Mark.tsx,Mark.module.css}         # símbolo, wordmark e lockup nas duas versões (R16)
    ├── app/Sidebar.tsx (+ .module.css)              # marca, atribuição, trilho (R17)
    ├── app/AccessDenied.tsx                         # lockup, título (R17, R18)
    ├── app/Shell.tsx                                # PageTitleSuffix (R18)
    ├── ui/Page.tsx                                  # PageTitleSuffix e document.title (R18)
    ├── ui/tokens.css                                # tokens do DESIGN.md; hover escuro (R19)
    └── api/schemas.ts                               # instance.custom (R17)
axon-ai/packages/core/src/axon_ai/identity/adapters/assets/identity.css   # hover escuro (R19)
```

## Seam Notes for Consumers (US8)

| Consumidor | O que muda para ele |
|---|---|
| 008 | Nada: a console passa a ler `instance.custom`, que já existe |
| 012 | O hover escuro do `identity.css` e o par no teste de contraste (ADR-039) |
| Instalação | A imagem da console sai com o nome novo do pacote na passada dela; nada muda no nginx |

## Complexity Tracking (US8)

Nenhuma linha nova.

## Constitution Check — pós-design (US8)

Reavaliado com [contracts/screens.md](contracts/screens.md), [data-model.md](data-model.md) e
[quickstart.md](quickstart.md) ("Fase 9, incremento 9.5"): **PASS**.

---

# Passada de 2026-10-21: chaves de API e permissões dos Assistants (US9, US10; [ADR-040](../../docs/adr/ADR-040-rotacao-de-chaves-e-acesso-sobreponivel.md))

> As seções acima ficam como foram executadas. Esta é o plano das US9 e US10.

**Insumos lidos**: [spec.md](spec.md) (US9, US10, FR-024–FR-031, SC-009, SC-010, clarificações de 2026-10-21),
[design.md](design.md), ADR-029, ADR-031, ADR-040, `specs/008-core-http-api/contracts/admin-api.md` (US11 da 008),
constituição 1.3.1. Research: R22–R27. **Sem divergência**; sem ADR novo.

## Summary (US9, US10)

A aba "Chaves de API" na tela Acesso cria chaves para sistemas, mostra a chave em claro uma vez num diálogo e lista,
revoga e rotaciona com confirmação na linha (R22–R24). A aba "Permissões" no detalhe do Assistant edita `auth` com o
mecanismo das outras seções sobreponíveis, com sugestões de sistemas e grupos tiradas das listagens que a API já tem
(R25). Os esquemas `zod` aceitam a seção `auth` e `rotated_at` (R26). Testes de unidade e e2e com axe (R27).

## Technical Context (US9, US10)

- **Language/Version, dependências**: sem mudança (React 19, TanStack Query, `zod`, Radix); nenhum pacote novo.
- **Testing**: Vitest + MSW (dois arquivos novos e acréscimos), Playwright + axe (dois specs novos e a varredura de
  telas).
- **Scale/Scope**: 2 telas novas, 1 diálogo, hooks de chaves, esquemas, 3 telas tocadas (histórico, lista de Assistants,
  rodapé das abas), regra `no-console` no ESLint.
- Nenhum `NEEDS CLARIFICATION`.

## Constitution Check (US9, US10)

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Módulos substituíveis por seams | ✅ | Só `/admin/v1` (contrato da 008); nenhuma rota sob medida (FR-029) |
| IV. O Assistant é a fronteira | ✅ | A console não decide quem entra: a 003 valida; a tela só antecipa a forma e aponta pendências |
| VII. Falha fechada e explícita | ✅ | Recusas com o motivo no campo; 409 `key_revoked` explicado; entradas pendentes marcadas, nunca escondidas |
| XI. API independente da interface | ✅ | Tudo que a tela faz existe na API (FR-018) |
| XIII. Portas e adapters | ✅ | `fetch` só em `src/api/` (ESLint); telas só usam hooks |

**Module boundary gate**: `axon-ai/console/**` e `specs/013-core-admin-console/**`. **Resultado**: PASS.

## Project Structure (US9, US10)

```text
axon-ai/console/
├── eslint.config.js                       # no-console em src/ (R23)
├── src/
│   ├── api/schemas.ts                     # auth, rotated_at, issuedKeySchema (R26, R23)
│   ├── api/hooks/{apiKeys,keys}.ts        # useApiKeys, useCreateKey, useRotateKey, useRevokeKey; keys.apiKeys (R23)
│   ├── api/hooks/assistants.ts            # useSaveAuth (R25)
│   ├── app/router.tsx                     # /acesso/chaves, /assistentes/:nome/permissoes (R22)
│   └── features/
│       ├── access/{AccessPage,KeysTab,IssuedKeyDialog}.tsx     # R22–R24
│       └── assistants/{AssistantDetail,PermissionsTab,HistoryTab,AssistantsPage,editorParts}.tsx   # R25, R26
├── tests/{access/keys,assistants/permissions}.test.tsx, tests/api/schemas.test.ts, tests/msw/*   # R27
└── e2e/{keys,permissions,a11y}.spec.ts, e2e/serve_platform.py                                    # R27
```

## Seam Notes for Consumers (US9, US10)

A console não expõe seam. Operador: a aba "Permissões" só edita Assistants com `overrides: [auth]`.

## Complexity Tracking (US9, US10)

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Segundo modal (R23) | foco protegido para a chave mostrada uma vez, como a senha temporária | mostrar na tabela: o segredo ficaria no DOM depois da ação |

## Constitution Check — pós-design (US9, US10)

Reavaliado com [contracts/screens.md](contracts/screens.md), [data-model.md](data-model.md) e
[quickstart.md](quickstart.md) ("Fase 9 (2026-10-21)"): **PASS**.

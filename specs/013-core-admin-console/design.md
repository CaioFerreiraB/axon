# Design — 013 Admin Console

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: ADR-029 (console própria), ADR-031 (superfície de
> administração), ADR-032, ADR-033, ADR-034; plano da Fase 9 (2026-10-13), com as decisões do mantenedor: SPA React +
> TypeScript, contêiner opcional, design com as skills impeccable e taste-skill, Penpot e Playwright.

## Localização

```text
axon-ai/console/                 # fora de packages/: o workspace do uv casa packages/* e exigiria pyproject.toml
├── .nvmrc                       # 24 (Active LTS)
├── package.json                 # engines node >= 22.12
├── vite.config.ts  tsconfig.json  eslint.config.js  index.html
├── src/
│   ├── app/                     # rotas, shell (navegação lateral, cabeçalho, menu do usuário), fronteira de erro
│   ├── auth/                    # oidc-client-ts (UserManager com armazenamento em memória), /callback, RequireAdmin
│   ├── api/                     # cliente fetch (Bearer; 401 → renova/relogin; envelope de erro), esquemas zod,
│   │                            # hooks TanStack Query
│   ├── features/{assistants,mcp,usage,observability,access}/
│   ├── ui/                      # primitivas sobre Radix; tokens.css exportado do Penpot
│   └── i18n/pt-BR.ts
├── tests/                       # Vitest + Testing Library + MSW
├── e2e/                         # Playwright + axe; serve_platform.py sobe platform() do core em memória
└── deploy/nginx.conf.template
```

## Stack

React 19, React Router 7, TanStack Query 5, react-hook-form + zod, Radix (primitivas acessíveis), Vite. CSS por
variáveis (tokens do Penpot); Tailwind v4 ou CSS modules, decidido no plano. Gráficos: biblioteca escolhida com a skill
`dataviz` (Recharts ou visx). Sem geração de cliente por OpenAPI: as rotas da 008 leem JSON cru e o documento OpenAPI
não tem corpos; os esquemas zod espelham o contrato `specs/008-core-http-api/contracts/admin-api.md`, e os testes de
ponta a ponta pegam divergências.

## Autenticação

- Cliente público `console` da 012, código + PKCE, audiência `axon-admin` (ADR-031).
- Tokens só em memória; ao recarregar a página, `signinRedirect` reaproveita a sessão do provedor e volta sem token
  guardado no navegador. Renovação silenciosa com o token de renovação rotativo.
- `GET /admin/v1/me` com 404 → página "Sua conta não tem acesso à console"; 401 → renova ou refaz o login.
- Sair: `end_session` do provedor.

## Telas

| Rota | Conteúdo |
|---|---|
| `/uso` (inicial) | Período 7/30/90, KPIs, barras empilhadas por dia (modelo ou Assistant), tabela, "sem preço" |
| `/uso/precos` | Tabela de preços com vigência |
| `/assistentes` | Lista com estado e marcas (sobreposto, inativa, travado) |
| `/assistentes/:nome` | Abas "Modelos" e "MCP": YAML · sobreposição · efetivo; "Testar modelo"; "Descartar sobreposição"; estado travado |
| `/servidores-mcp` | Servidores globais; os do arquivo somente leitura; saúde e tools |
| `/observabilidade` | Langfuse: endereço, chaves (só escrita), envio, captura de conteúdo com aviso, testar conexão, estado |
| `/acesso` | Google (liga/desliga, endereço de retorno), usuários, grupos |

Slugs em português também evitam colisão com os prefixos da plataforma repassados pelo servidor estático.

## Instalação

Estágio `console-build` no `axon-deploy/Dockerfile` (`node:24-bookworm-slim`, `npm ci && npm run build`) e estágio
`console` (`nginx-unprivileged`, sistema de arquivos somente leitura). O nginx:

- serve a SPA com fallback para `index.html`; cache imutável para os arquivos com hash, `no-cache` no `index.html`;
- repassa ao core, sem reescrever, `/v1/`, `/private/v1/`, `/admin/v1/`, `/oauth2/` e `/.well-known/` — assim o
  emissor e os endereços são os mesmos com ou sem console, e não há CORS;
- CSP `default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'`; HSTS sob HTTPS.

Com console, `AXON_PUBLIC_URL` é a origem da console.

## Fluxo de design

1. Penpot (`high_level_overview` do MCP): tokens (cor, tipo, espaço, raio) nos temas claro e escuro, componentes, as
   sete telas, a página de login da 012 e os estados (vazio, carregando, erro, travado, indisponível, "Definido na instalação", acesso negado).
2. Direção: `impeccable:impeccable` como skill principal (UI de produto, dashboards, formulários, estados);
   `taste-skill:minimalist-skill` para a direção visual (a v2 da taste-skill exclui dashboards e telas de app); `dataviz`
   para os gráficos.
3. Crítica pela impeccable; aprovação do mantenedor antes de implementar.
4. Exportar `tokens.css`; implementar; auditoria e polimento pela impeccable sobre capturas do Playwright.

## Testes

- Vitest + Testing Library + MSW para componentes e hooks; `tsc --noEmit`; ESLint.
- Playwright: o `webServer` sobe (1) `uv run python e2e/serve_platform.py` — `platform(profile="memory", overrides=…)`
  com provider de modelo programado, Google simulado e admin inicial — e (2) `vite preview` com as mesmas regras de
  repasse do nginx. Cenários: login por senha, Google simulado, sobreposição de modelos e de MCP, dashboard depois de
  conversas semeadas, Langfuse, contas. `@axe-core/playwright` (WCAG 2.2 AA) e capturas de referência.
- O MCP do Playwright serve aos ciclos interativos de crítica e polimento.
- CI: `.github/workflows/console.yml` (Node pelo `.nvmrc`, uv com Python 3.14, Chromium).

## Portas e adapters **[ADR-012]**

A console não é módulo do núcleo e não declara portas do core. Por dentro, a mesma separação vale em escala de
aplicação web:

| Porta | Tipo | Adapters | Teste |
|---|---|---|---|
| Cliente da API de administração (`src/api/`) | saída | `fetch` contra `/admin/v1` | MSW nos testes de unidade; plataforma real em memória no e2e |
| Sessão OIDC (`src/auth/`) | saída | `oidc-client-ts` contra a 012 | provedor real em memória no e2e; sessão falsa nos testes de unidade |
| Telas (`src/features/`) | entrada | React | Testing Library + Playwright |

Regra: componentes de tela não chamam `fetch` nem o cliente OIDC diretamente; só os hooks de `src/api/` e de
`src/auth/`.

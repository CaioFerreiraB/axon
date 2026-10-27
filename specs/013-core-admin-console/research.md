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

---

# Passada de 2026-10-20: identidade Axon ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md), [ADR-038](../../docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md), [ADR-039](../../docs/adr/ADR-039-hover-do-botao-primario-no-escuro.md); US8)

Decisões pré-aprovadas pelos ADRs e pelo `DESIGN.md` ("Brand" e tokens), mais a do mantenedor de 2026-10-20 sobre o hover
escuro (ADR-039); o que segue é como elas chegam à console, sem re-pesquisa. Os R anteriores ficam como foram executados
(ADR-037, item 6).

## R15 — Os arquivos da marca na console

**Decision**: cópias de `brand-kit/svg/{axon-symbol,axon-symbol-light,axon-lockup-light,axon-lockup-dark,favicon}.svg` em
`axon-ai/console/src/brand/`, importadas pelo Vite (com `assetsInlineLimit: 0`, saem em `/assets/` com hash, no cache
imutável e na CSP que o nginx já tem); o favicon entra no `index.html` (`<link rel="icon" type="image/svg+xml"
href="/src/brand/favicon.svg">`, que o Vite reescreve). O wordmark sozinho — o `DESIGN.md` pede, na barra lateral, o
símbolo de 32px ao lado do wordmark de 12px, uma composição que o lockup, com a proporção fixa de 1,85×, não dá — é
recortado do lockup aprovado: `brand-kit/svg/axon-wordmark-light.svg` (`#111827`) e `axon-wordmark-dark.svg` (branco),
com o mesmo `<path>` do lockup, sem a translação, e o `viewBox` `252.38 132.47 252.12 62.78`, que enquadra a altura de x
de 58,3 (de 135 a 193,3) e as curvas do "a", do "o" e do "n". Entram no README do `brand-kit` como "recorte do lockup,
mesmo traço". Um teste do Vitest confere que cada arquivo da console é igual ao do `brand-kit`.

**Rationale** (ADR-038, item 6): os vetores são do `brand-kit`; o recorte não redesenha nada. Imagens, em vez de SVG
embutido, evitam ids repetidos de degradê e máscara entre instâncias (ADR-038, Consequências).

**Alternatives considered**: o lockup inteiro na barra lateral (símbolo de 23px com o wordmark de 12px, fora do
`DESIGN.md`); wordmark como texto na Mona Sans (o `DESIGN.md` diz que o wordmark não depende de fonte); `public/` do Vite
(sem hash, fora do cache imutável do nginx).

## R16 — A versão do símbolo segue o tema escolhido

**Decision**: um componente `src/app/brand/Mark.tsx` renderiza as duas versões (`<img>` clara e escura) de cada arquivo, e
o CSS mostra uma delas pelos mesmos seletores do `tokens.css` (`:root[data-theme="dark"]` e `@media (prefers-color-scheme:
dark) { :root:not([data-theme="light"]) }`). A versão "para fundo claro" (`-light`) aparece no claro; a "para fundo
escuro", no escuro. A imagem decorativa tem `alt=""`; a que é a marca no lugar principal tem `alt="Axon"`.

**Rationale**: a console troca o tema pela escolha da pessoa (`data-theme`, FR-019), e `<picture>` com
`prefers-color-scheme` (a solução da 012, que não tem a escolha) seguiria só o sistema. O CSS troca na hora, sem
recarregar.

**Alternatives considered**: escolher a versão em JavaScript pelo tema resolvido (um hook a mais que observa o sistema);
um só SVG com `currentColor` (perde o degradê, que é parte da marca).

## R17 — A barra lateral, o trilho e o acesso negado

**Decision**: `Sidebar` lê `me.instance` (o esquema `meSchema` ganha `custom: z.boolean()`); com `me` ainda carregando,
`{ name: "Axon", logo_url: null, custom: false }`.

- **sem marca própria**: símbolo de 32px (`alt=""`), ao lado da coluna com o wordmark (altura de x de 12px, ou seja 13px de
  altura, `alt="Axon"`) e "Console". Sem atribuição.
- **com marca própria**: o que já existe (logotipo ou inicial de 24px e o nome) e "Console"; no fim do rodapé, depois da
  pessoa, a atribuição: símbolo de 16px (`alt=""`) e "com Axon" em caption terciário.
- **trilho** (abaixo de 1100px): o texto da marca já fica só para leitor de tela; o símbolo (ou o logotipo/inicial)
  continua; a atribuição fica só com o símbolo, e "com Axon" vai para o leitor de tela.

`AccessDenied` mostra o lockup (32px de altura, `alt="Axon"`), sempre: sem o grupo de administração, o `me` responde 404, e
a console não sabe a marca da instalação. O componente `Brand` antigo (a inicial) fica só para a marca da instalação.

**Rationale** (ADR-038, itens 1 e 2; `DESIGN.md`, "Brand").

**Alternatives considered**: ler a marca da instalação pela descoberta OIDC no acesso negado (a descoberta não traz marca,
e a 012 não a publica fora das páginas).

## R18 — Título da aba, favicon e cor da barra do navegador

**Decision**: `ui/Page.tsx` ganha o contexto `PageTitleSuffix` (padrão "Axon"); o `PageHeader`, quando o título é texto,
põe `document.title = "<título> · <sufixo>"`; o `Shell` fornece o sufixo com `me.instance.name`. `AccessDenied` usa
"Sem acesso · Axon"; o `index.html`, `<title>Axon</title>` até a primeira tela. `theme-color` do escuro passa a `#0b0f19`.

**Rationale** (ADR-038, item 3: favicon sempre Axon): o título com o nome da instalação segue as páginas da 012
("<página> · <nome>"), para o login e a console dizerem o mesmo nome; sem nome próprio, dá "Tela · Axon", o do plano do
renome.

**Alternatives considered**: "Tela · Axon" sempre (a console diria um nome e o login, outro).

## R19 — Tokens e o hover escuro

**Decision**: `src/ui/tokens.css` com os valores do `DESIGN.md` (os mesmos neutros que a 012 passou a usar, R22 dela) nos
três blocos (claro, `data-theme="dark"`, sistema escuro), e `--acao-hover` do escuro `#1d4ed8` (ADR-039); o comentário do
topo diz "neutros frios da marca Axon". O mesmo `--acao-hover` escuro em `identity.css` (012), e o par "texto sobre o
hover" entra no teste de contraste da 012 e num teste novo do Vitest que lê os blocos do `tokens.css` e confere os pares
de texto em AA nos dois temas, inclusive o hover.

**Rationale** (ADR-038, item 4; ADR-039).

**Alternatives considered**: nenhuma (decidido pelo mantenedor).

## R20 — O pacote

**Decision**: `"name": "@axon/console"` no `package.json`; `npm install --package-lock-only` atualiza o lock. Nada mais
muda de nome: `console.theme` e o cliente `console` ficam (ADR-037, item 5).

**Rationale** (ADR-037, item 2).

**Alternatives considered**: nenhuma.

## R21 — Verificação

**Decision**: Vitest — a barra lateral sem e com marca própria (o MSW com `custom` falso e verdadeiro), o acesso negado
com o lockup, o título da aba, a igualdade dos SVG com o `brand-kit` e o contraste dos tokens; a fixture do MSW passa a
`{ name: "Axon", logo_url: null, custom: false }`. E2E com axe nos dois temas e na largura de tablet (os projetos que já
existem), mais um caso que confere o título e o favicon. Capturas da barra lateral sem e com marca, claro e escuro, pelo
Playwright do MCP. O Penpot não estava conectado em 2026-10-20; a comparação fica para quando estiver.

**Rationale**: SC-005 e SC-008.

**Alternatives considered**: nenhuma.

---

# Passada de 2026-10-21: chaves de API e permissões dos Assistants (US9, US10; [ADR-040](../../docs/adr/ADR-040-rotacao-de-chaves-e-acesso-sobreponivel.md))

Decisões pré-aprovadas: ADR-029 (a console só apresenta), ADR-031, ADR-040, o contrato `admin-api.md` da 008 (US11 dela:
rotação, `rotated_at`, `PUT …/auth`, `yaml.auth`/`effective.auth`, 409 `key_revoked`) e as clarificações de 2026-10-21.

## R22 — Rotas e lugares

- **Decision**: aba "Chaves de API" em `/acesso/chaves` (`features/access/KeysTab.tsx`), com "Criar chave" no
  cabeçalho da tela Acesso quando a aba está aberta (`?criar=1`, como `?cadastrar=1`); aba "Permissões" em
  `/assistentes/:nome/permissoes` (`features/assistants/PermissionsTab.tsx`), entre MCP e Histórico.
- **Rationale**: clarificações 1 e 2 de 2026-10-21; o padrão das abas que já existem.
- **Alternatives considered**: item próprio na barra lateral (rejeitado na clarificação).

## R23 — A chave em claro uma vez

- **Decision**: `useCreateKey` e `useRotateKey` (`src/api/hooks/apiKeys.ts`) como as escritas de conta com
  `keepResult: false` (`gcTime: 0`): o resultado vive só no estado do diálogo (`IssuedKeyDialog`), que ao fechar chama
  `reset()` da mutação e limpa o estado; a lista é **invalidada** (relida, sem `key`), nunca escrita com o resultado. O
  esquema da resposta da emissão e da rotação é `issuedKeySchema = apiKeySchema.extend({ key })`, usado só nessas duas
  escritas. O diálogo é o segundo modal da console, pela mesma razão do R7 (foco protegido para um segredo mostrado uma
  vez): campo somente leitura com a chave, "Copiar", o aviso de que não aparece de novo e "Concluir". Nenhum `console.*`
  no código da console: a regra `no-console` do ESLint passa a valer em `src/`.
- **Rationale**: FR-025 e SC-009; o padrão da senha temporária (R7).
- **Alternatives considered**: mostrar a chave numa linha da tabela (fica no DOM e na cópia da tela); guardar até o
  admin confirmar que copiou (retém o segredo).

## R24 — Revogar e rotacionar com confirmação na linha

- **Decision**: cada linha ativa tem "Rotacionar" e "Revogar"; a confirmação aparece na própria linha (o padrão do
  `DiscardButton`: texto curto, "Cancelar" com foco, botão de perigo). Rotação confirmada abre o mesmo diálogo da
  criação, com o aviso de que a chave anterior já não vale. 409 `key_revoked` mostra o motivo num aviso e relê a lista.
  Ordem: ativas antes das revogadas; dentro de cada grupo, por sistema e rótulo.
- **Rationale**: FR-026, FR-027; a console não usa `confirm()`.
- **Alternatives considered**: confirmação em modal (o modal fica reservado a segredo, R7).

## R25 — A aba "Permissões"

- **Decision**: rascunho `{ schemes: Set<"oidc" | "api_key">, allow: string[] }` a partir de `effective.auth`; um
  `Toggle` por esquema ("Login", "Chave de API"); a lista de entradas, cada uma com rótulo legível (sistema, grupo,
  pessoa, "Qualquer pessoa autenticada") e "Remover"; "Adicionar" é um `TextInput` com `<datalist>` (o padrão da escolha
  de modelo da `ModelsTab`) com as sugestões `svc:<nome>` dos subjects das chaves **ativas** e `group:<nome>` dos grupos,
  aceitando `user:<nome>` digitado; a **forma** é conferida antes de entrar na lista (`*`, `user:…`, `svc:…` ou
  `group:…`, sem espaço). `*` é um `Checkbox` à parte, só em Assistant público, com nota; num privado, não aparece e um
  texto diz por quê. Marcas, sem bloquear: "sem correspondência" para `svc:` fora das chaves ativas e `group:` fora dos
  grupos (`user:` não é conferido: a lista de contas é paginada); "não entra com os esquemas ligados" para `svc:` com
  "Chave de API" desligada. "Salvar" fica desabilitado, com o motivo, com os dois esquemas desligados ou sem entradas.
  Travada, inativa, conflito, descarte e rodapé usam `editorParts` como Modelos e MCP.
- **Rationale**: FR-028 a FR-030 e as clarificações 3 e 4; a forma no cliente é o que o R7 já permite, a regra continua
  na 003 (que recusa o mesmo, com `param`).
- **Alternatives considered**: um combobox ARIA próprio (mais código e mais risco de acessibilidade que o `<datalist>`
  que a console já usa); conferir `user:` contra todas as contas (paginaria a API inteira).

## R26 — Esquemas e as telas que mostram seções

- **Decision**: `SECTIONS = ["models", "mcp", "auth"]`; `authSelectionSchema = { schemes: ("oidc" | "api_key")[],
  allow: string[] }`; `yaml`/`effective` ganham `auth`; o `payload` das sobreposições e do histórico aceita o de `auth`
  (com `isAuthPayload`); `apiKeySchema` ganha `rotated_at`. `HistoryTab`, `overrideMeta` e os selos da lista de Assistants
  passam a nomear a seção "Permissões" e a resumir `auth` (esquemas e quantidade de entradas).
- **Rationale**: FR-031; o esquema `zod` de hoje recusaria a visão de um Assistant com sobreposição de `auth` (o
  `payload` não casa nem com modelos nem com MCP) — a tela inteira cairia em "contrato".
- **Alternatives considered**: tornar o `payload` desconhecido opaco (esconderia divergência de contrato, R6).

## R27 — Testes

- **Decision**: Vitest + MSW: `tests/access/keys.test.tsx` (criar, diálogo uma vez, nada no cache depois de fechar —
  `queryClient` sem a chave —, lista com rotação e revogada, confirmação de revogar e rotacionar, 409 `key_revoked`, erro
  de campo do nome), `tests/assistants/permissions.test.tsx` (travada, edição, sugestões, `*` só em público, marcas,
  salvar desabilitado, conflito, descarte), `tests/api/schemas.test.ts` (auth e `rotated_at`); fixtures e handlers novos
  em `tests/msw/`. Playwright: `e2e/keys.spec.ts` (criar, copiar, fechar, rotacionar e revogar contra a plataforma em
  memória; a chave nova autentica e a antiga não, conferido pela API) e `e2e/permissions.spec.ts` (adicionar um sistema
  e salvar; o efetivo na visão); `e2e/a11y.spec.ts` com `/acesso/chaves`, o diálogo aberto e
  `/assistentes/<nome>/permissoes`; `e2e/serve_platform.py` com um Assistant `overrides: [auth]`.
- **Rationale**: SC-009, SC-010.
- **Alternatives considered**: —

## R28 — `vision` na aba Modelos ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md), item 10; FR-032)

**Decision**: em `api/schemas.ts`, o papel é `string | {model, vision?}` (`roleValue`), com os auxiliares
`refOfRole` e `sees`; o resto da console lê o modelo por `refOfRole` (lista de Assistants, resumo, histórico). A aba
Modelos guarda `vision` no rascunho, conta a mudança dele como alteração, manda `{model, vision: true}` no PUT e mostra
o selo "Visão" no efetivo. Vitest com MSW (`tests/assistants/models.test.tsx`) e um e2e que prova o efeito na plataforma:
a pergunta com imagem a `geral` é 400 `vision_unsupported` antes e 200 depois de marcar e salvar.

**Rationale**: a forma do YAML na API (008 R60) só muda para quem usa imagem; normalizar no esquema deixaria a console
sem saber o que gravar de volta.

**Alternatives considered**: um controle de `vision` fora da tabela de papéis (separa o atributo do papel); converter
para uma estrutura própria na leitura (cada tela leria um formato diferente do da API).

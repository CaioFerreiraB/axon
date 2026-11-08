# ADR-060 — A console no celular e instalável (PWA)

- **Status:** Aceita · 2026-11-08
- **Specs afetadas:** [013-core-admin-console](../../specs/013-core-admin-console/spec.md) (US13: layout de celular,
  barra inferior, tabelas em lista, folhas, manifest, ícones e service worker; contratos `serving.md` e `screens.md`)
- **Origem:** pedido do mantenedor (2026-11-08). No celular, a console aparece como "um desktop pequeno": trilho de
  ícones, tabelas que rolam de lado, diálogos centrados e alvos de 32px. O mantenedor quer usá-la no celular e
  instalá-la como app, em janela própria, sem a barra do navegador. Desenho aprovado no Penpot ("axon mockup", página
  "Console — celular").

## Contexto

A 013 assumia desktop e tablet ("celular não é alvo", Assumptions). Abaixo de 1100px, a barra lateral vira um trilho
de 64px, e abaixo de 1024px o respiro cai para 24px. Nada além disso muda de forma. Em 390×844, cinco das sete telas
principais rolam na horizontal (a página de Assistentes chega a 745px), e a faixa de números sobrepõe os valores.

A console é uma SPA estática servida pelo nginx na mesma origem da plataforma (contrato `serving.md`). O login é o
cliente público `console` da 012, com código + PKCE, e os tokens ficam só em memória (FR-002). A CSP é
`default-src 'self'`, sem script nem estilo inline.

## Decisão

1. **O celular é alvo.** Abaixo de **640px**, a console tem layout próprio. Entre 640 e 1100px fica o trilho de hoje, e
   acima disso nada muda. O ponto de quebra é o mesmo das páginas da 012, onde a partir de 640px o login vira cartão.
2. **Navegação de app.** No celular, a barra lateral some. No lugar dela entram:
   - um **cabeçalho de app** no topo (marca compacta e o título da tela; numa tela de detalhe, o "voltar" substitui a
     marca);
   - uma **barra inferior** com Uso, Assistentes, MCP, Acesso e **Mais**. "Mais" abre uma folha com Meio ambiente,
     Observabilidade, "Instalar app" (só quando o navegador oferece a instalação), o tema, a pessoa e "Sair".

   Os itens vêm da mesma lista `NAV` da barra lateral.
3. **As primitivas mudam, não as telas.**
   - A `Table` vira lista de linhas: a primeira célula é o título, e as demais saem como pares rótulo/valor, com o
     rótulo tirado do cabeçalho da própria tabela.
   - O `Dialog` vira folha ancorada embaixo.
   - `TabNav` e `Segmented` rolam de lado.
   - Botões e campos têm alvo de 44px, e o campo usa 16px (sem o zoom do iOS).
   - As telas só ajustam o que é delas: a faixa de números em 2 colunas, o gráfico e os formulários numa coluna.
4. **PWA instalável.**
   - **Manifest** `/manifest.webmanifest`: `display: standalone`, `start_url: /uso`, `scope: /`, `id: /`, nome "Axon
     Console", nome curto "Axon", e ícones PNG de 192 e 512 (`any`) e de 512 (`maskable`). Os ícones são gerados do
     símbolo do `brand-kit/svg/`.
   - **Marca no manifest:** o manifest é estático e igual em toda instalação, porque a marca da instalação (ADR-038)
     só se conhece depois do login. Por isso o ícone do app é sempre o símbolo Axon, como o favicon.
   - **iOS:** `apple-touch-icon`, `apple-mobile-web-app-capable` e `viewport-fit=cover`, com as áreas seguras
     respeitadas.
   - **Cor da barra de status:** `theme-color` acompanha o tema escolhido na console, não só o do sistema.
5. **O service worker guarda só a casca.**
   - **Origem e versão:** o `sw.js` é gerado no build, com a lista dos arquivos do bundle, e o cache se chama
     `axon-console-<impressão digital da lista>`. A ativação apaga os caches anteriores.
   - **Navegação:** vai sempre pela rede, para o HTML sempre apontar para os assets do deploy atual. Sem rede, a resposta
     é `offline.html`: uma página estática, sem script, com "Sem conexão" e "Tentar de novo". Nunca é o `index.html` do
     cache, porque a sessão OIDC fica só em memória e, sem rede, o app tentaria um login que não completa.
   - **Assets:** `/assets/` e `/icons/` saem do cache primeiro, porque têm hash e são imutáveis.
   - **O que nunca passa pelo service worker:** os prefixos do core (`/v1/`, `/private/v1/`, `/admin/v1/`, `/oauth2/`,
     `/.well-known/`, `/static/`). Também não passam requisição que não seja GET nem requisição de outra origem.
     Nenhuma resposta da API e nenhum token entra no cache.
   - **Atualização:** a versão nova do service worker entra na próxima abertura, sem `skipWaiting`.
6. **A sessão não muda.** Os tokens continuam só em memória. Quando o sistema descarta o app e ele reabre, a console
   refaz o redirecionamento OIDC, que a sessão da 012 (cookie `axon_session`) resolve sem pedir senha.
7. **O nginx da console** serve `manifest.webmanifest` como `application/manifest+json`, e `sw.js` e
   `offline.html` com `no-cache`. A CSP não muda, porque `default-src 'self'` já cobre `manifest-src` e `worker-src`.

## Alternativas rejeitadas

- **Gaveta lateral (☰) no lugar da barra inferior.** Fica mais perto do desktop, mas tira a navegação do alcance do
  polegar e soma um toque a cada troca de seção. O mantenedor escolheu a barra inferior.
- **Só o manifest, sem service worker.** É instalável e sem barra, mas sem rede o app abre a página de erro do
  navegador, o que quebra a sensação de app. O service worker que guarda só a casca custa pouco e não toca dados.
- **`vite-plugin-pwa` (Workbox).** É uma dependência grande para um service worker de cerca de 50 linhas. O plugin
  local no `vite.config.ts` gera a lista e o nome do cache sem nada novo no `package.json`.
- **Tabela com rolagem horizontal no celular.** É o comportamento de hoje, justamente o "desktop pequeno". A lista de
  linhas mostra todos os valores sem rolar de lado.
- **Guardar o token de renovação para reabrir sem redirecionar.** Mudaria a FR-002 (tokens só em memória) e a
  superfície de ataque da console. Fica fora deste ADR.
- **Nome e ícone da instalação no manifest.** Exigiriam um manifest dinâmico servido pelo core, antes do login, com a
  marca da instalação. É possível num ADR futuro. Hoje a marca da instalação aparece dentro do app.

## Consequências

- A 013 ganha a US13 e as FR-046 a FR-053. A suposição "celular não é alvo" sai das Assumptions, e o `DESIGN.md` ganha
  a seção "Abaixo de 640px" e os componentes barra inferior, folha e lista de linhas.
- Os e2e ganham os projetos `celular` e `celular-escuro` (axe, teclado, nenhuma rolagem horizontal) e uma suíte de PWA
  (manifest, ícones, registro do service worker, "Sem conexão"). Os outros projetos bloqueiam o service worker, para o
  cache não mascarar os testes.
- O login pelo Google sai do escopo do app (accounts.google.com) e volta. No Android isso passa por uma aba
  personalizada, e no iOS pela própria janela, com uma barra mínima. O fluxo não muda.
- O `axon-deploy` não muda: a imagem `axon-console` já serve o `dist/`, e o nginx dela é o de `deploy/`.

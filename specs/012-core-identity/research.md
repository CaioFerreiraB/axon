# Research — 012 Identity

Insumos: [spec.md](spec.md) (com as clarificações de 2026-10-13), [design.md](design.md), ADR-030, ADR-031, ADR-033,
ADR-012, ADR-015, ADR-020, a constituição 1.3.0 e o `PRODUCT.md` da raiz. Decisões do `design.md` e dos ADRs entram como
pré-aprovadas; o que segue resolve o que eles deixaram para o plano.

## R1 — Protocolo próprio sobre `pyjwt[crypto]`, sem servidor de biblioteca

- **Decision**: o subconjunto do OIDC (FR-004) é implementado no próprio módulo: as regras em `domain/` (validação do
  pedido de autorização, PKCE S256, troca de código, rotação de renovação, montagem de claims, decisão de logout) e a
  assinatura em `adapters/signing.py` com `pyjwt[crypto]`, já dependência do core (003). O authlib entra só como
  dependência de **desenvolvimento**, como cliente (RP) da suíte de protocolo.
- **Rationale**: o subconjunto é pequeno e fechado (sem implícito, sem registro dinâmico, sem consentimento —
  ADR-030); as regras ficam puras e testáveis sem HTTP (princípio XIII); o servidor do authlib é desenhado em torno de
  ganchos de Flask/Django, e para cinco endpoints a cola pesaria mais que o protocolo. Usar um RP de terceiros na suíte
  prova a interoperabilidade que a implementação própria poderia esconder.
- **Alternatives considered**: servidor do authlib (cola com FastAPI e modelos próprios, mais superfície); um IdP
  externo leve (rejeitado no ADR-030); `python-jose` (sem vantagem sobre o `pyjwt`, já presente).

## R2 — Hash de senha: argon2id com `argon2-cffi`

- **Decision**: `argon2-cffi>=25.1,<26` em `adapters/passwords.py`, perfil RFC 9106 "baixa memória" (t=3, m=64 MiB,
  p=4), re-hash no login quando os parâmetros mudam (`check_needs_rehash`), verificação em `asyncio.to_thread`. Usuário
  inexistente passa por um hash fictício calculado uma vez no início (FR-003, SC-005).
- **Rationale**: o `argon2-cffi-bindings` 26.1.0 publica wheels `cp310-abi3` para `manylinux` aarch64 e x86_64 — servem
  ao Python 3.14 do workspace e ao hardware alvo (ARM64); argon2id é a recomendação atual para senhas. 64 MiB por login
  cabem no host de 12 GB com o bloqueio de força bruta limitando a concorrência.
- **Alternatives considered**: `hashlib.scrypt` da biblioteca padrão (o fallback do design; desnecessário com as
  wheels); bcrypt (limite de 72 bytes, contra o teto de 128 caracteres da FR-002).
- **Medição (T067, 2026-10-14)**: verificação com o perfil de produção em **36 ms** (mediana de 7) numa máquina de
  desenvolvimento x86_64 de 16 núcleos. O hardware alvo (ARM64, 2 OCPU) não estava disponível: a meta de < 250 ms fica
  para conferir na passada da 002, na imagem.

## R3 — Páginas HTML sem motor de templates

- **Decision**: as páginas (login, troca de senha, "Minha conta", erro) são strings HTML em
  `adapters/pages.py`, montadas por uma função que **escapa toda substituição por padrão** (`html.escape`) e só aceita
  trechos já seguros marcados explicitamente. CSS num arquivo estático servido pelo próprio router, com cache longo e
  nome com hash. Nenhum script. Os tokens visuais são os da console (013), nos temas claro e escuro por
  `prefers-color-scheme`.
- **Rationale**: quatro páginas pequenas não justificam `jinja2`, que o FastAPI não traz; escape por padrão fecha o XSS
  que um template sem autoescape abriria; sem script, a CSP fica `script-src 'none'`.
- **Alternatives considered**: `jinja2` com autoescape (dependência nova para quatro páginas); renderizar a página na
  SPA da console (a página precisa existir sem console — ADR-030).
- **Na implementação**: sem script, o botão "mostrar senha" do desenho não existe nas páginas do provedor; a fonte é a
  pilha do sistema com "Mona Sans" em primeiro lugar (a fonte não é empacotada no core, e a CSP não tem `font-src`).

## R4 — Formulários sem `python-multipart`

- **Decision**: o router lê `application/x-www-form-urlencoded` direto do corpo (`await request.body()` +
  `urllib.parse.parse_qs`, teto de 16 KiB), recusando outro tipo de conteúdo com 415.
- **Rationale**: o `Form` do FastAPI exige `python-multipart`, que não está no lock; os formulários do provedor têm
  três a cinco campos de texto, sem arquivo.
- **Alternatives considered**: `python-multipart` (dependência para um caso que a biblioteca padrão resolve).

## R5 — Sessão do provedor e CSRF

- **Decision**: cookie de sessão opaco (32 bytes, guardado como hash no `GrantStore`), `HttpOnly`, `SameSite=Lax`,
  `Path=/`, sem `Domain`, só `Max-Age` (30 dias, clarificação de 2026-10-13); nome `__Host-aic_session` com `Secure`
  quando `AI_CORE_COOKIE_SECURE` (padrão: ligado se `AI_CORE_PUBLIC_URL` é `https`), e `aic_session` sem `Secure` em
  desenvolvimento sobre `http` — o prefixo `__Host-` exige `Secure`, `Path=/` e nenhum `Domain`, senão o navegador
  descarta o cookie (achado C2 do `/speckit-analyze`); id trocado a cada login. CSRF por **token
  sincronizador** guardado no pedido de autorização pendente (login, troca de senha) ou na sessão ("Minha conta"),
  conferido em tempo constante, mais conferência de `Origin` quando o cabeçalho vem. A CSP das páginas tem
  `form-action 'self'` **mais as origens dos endereços de retorno** dos clientes do `identity.yaml`: o Chrome aplica
  `form-action` também ao redirecionamento que segue o POST do login, e só `'self'` bloquearia a volta ao cliente
  (achado C1). O Google não entra na diretiva: o início do fluxo com ele é um link (GET), não um formulário.
- **Rationale**: `SameSite=Lax` sozinho não protege o POST do login vindo de subdomínio irmão; o sincronizador cobre
  isso sem estado no navegador. `Max-Age` em vez de `Expires` porque o relógio fixo do perfil `test` tornaria o cookie
  vencido.
- **Alternatives considered**: double-submit cookie (mais frágil sob subdomínios); JWT como cookie de sessão (revogação
  exigiria lista de bloqueio).

## R6 — Tokens e prazos

- **Decision**: acesso RS256 de 10 min com `iss`, `aud`, `sub` (id estável da conta), `preferred_username`, `groups`,
  `azp`, `scope`, `iat`, `exp`, `kid` no cabeçalho; identidade com `nonce`, `auth_time`, `amr`, `email`,
  `email_verified`, `name`. Código de 60 s, uso único. Renovação opaca de 32 bytes; sessão absoluta de 30 dias
  (clarificação de 2026-10-13); rotação a cada uso para cliente público, com detecção de reuso que revoga a família
  (FR-006); sem rotação para cliente confidencial. Tolerância de relógio: a da 003 (60 s).
- **Rationale**: o ADR-030 fixa RS256 e o TTL de 10 min; o `JwksOidcVerifier` da 003 aceita RS256; o Open WebUI renova
  em paralelo (cliente confidencial), e a rotação ali causaria corridas.
- **Alternatives considered**: ES256 (menor, mas RS256 é o obrigatório do OIDC e o que todo RP aceita); TTL de acesso
  maior (alongaria o acesso de quem é desativado — SC-004).

## R7 — Chaves de assinatura

- **Decision**: RSA-2048 gerada com `cryptography` em `adapters/signing.py`; a privada é guardada no `SigningKeyStore`
  cifrada pela porta `SecretCipher` (AES-GCM, subchave HKDF-SHA256 de `AI_CORE_MASTER_KEY` com `info="ai-core/identity/v1"`,
  nonce de 12 bytes por gravação — ADR-033). Estados `active` → `retiring` → `retired`; o JWKS publica `active` e
  `retiring`; uma chave sai de `retiring` quando passou o TTL do acesso + a tolerância desde a rotação. `kid` = 16
  hex aleatórios. Rotação forçada (`--force`): retira todas as chaves, gera uma nova e revoga todas as sessões.
- **Rationale**: sobrevive a restart sem segredo em claro no banco; a rotação normal não invalida tokens vigentes
  (SC-007).
- **Alternatives considered**: chave privada vinda da instalação (mais um segredo para o operador gerir; a geração no
  primeiro boot é o caminho que o ADR-030 escolheu).

## R8 — Descoberta com backchannel dinâmico

- **Decision**: `issuer`, `authorization_endpoint` e `end_session_endpoint` sempre de `AI_CORE_PUBLIC_URL`;
  `token_endpoint`, `userinfo_endpoint`, `jwks_uri` e `revocation_endpoint` a partir da base pela qual o pedido de
  descoberta chegou (esquema e `Host`, ou `X-Forwarded-Proto`/`X-Forwarded-Host` só de proxies confiáveis). O `iss` dos
  tokens é sempre o público.
- **Rationale**: o navegador alcança a plataforma pelo endereço público; o Open WebUI, pelo nome do contêiner —
  o mesmo truque do `KC_HOSTNAME_BACKCHANNEL_DYNAMIC` da Fase 7 (002 R37). Um `Host` forjado só muda a resposta de quem o
  forjou; não há cache compartilhado da descoberta.
- **Alternatives considered**: dois emissores (um por rede) — quebraria a verificação da 003, que confia num único
  emissor (ADR-030).

## R9 — Login com Google

- **Decision**: cliente OIDC do Google em `adapters/google.py` sobre `httpx` (descoberta em
  `https://accounts.google.com/.well-known/openid-configuration`, cache de 1 h; troca de código com segredo; `id_token`
  verificado com `pyjwt` contra o JWKS do Google, `aud` = client id, `iss` ∈ {`https://accounts.google.com`,
  `accounts.google.com`}, `nonce`). PKCE S256 e `state` também no fluxo com o Google. Regras puras em
  `domain/google.py` (FR-008): `email_verified` verdadeiro; domínio aceito, quando a instalação o define (`hd` e sufixo do
  e-mail); conta ativa com o e-mail normalizado; vínculo pelo `sub` do Google no primeiro sucesso; `sub` diferente do
  vinculado é recusado. Nunca cria conta.
- **Rationale**: o RP do Google é o lado cliente do mesmo protocolo; `httpx` e `pyjwt` já estão no core; a porta
  `UpstreamOidc` permite o provedor simulado nas suítes.
- **Alternatives considered**: biblioteca de cliente do Google (dependência pesada para três chamadas).

## R10 — Contas e nomes

- **Decision**: `Account.id` = UUID estável (o `sub`); `username` imutável no padrão do design (sem `@`); e-mail
  normalizado (`strip().lower()`), único; login aceita usuário ou e-mail, decidido pela presença de `@` (clarificação de
  2026-10-13). Grupos no mesmo padrão; o grupo de administração vem da 011 e é protegido (FR-011). Senha temporária
  gerada: 20 caracteres de um alfabeto sem ambíguos, em grupos de 4 com hífen (≈ 100 bits), devolvida uma vez.
- **Rationale**: o subject `user:<username>` da Fase 7 continua (003 lê `preferred_username`); o UUID deixa o `sub`
  estável e opaco; a senha gerada em grupos é ditável e forte.
- **Alternatives considered**: senha temporária por lista de palavras (exigiria embutir uma lista; o desenho da
  console mostra um exemplo assim, que muda para o formato em grupos na implementação).

## R11 — Bloqueio de força bruta

- **Decision**: porta `LoginAttempts` em memória (processo único), janelas deslizantes por usuário normalizado e por
  origem: 5 falhas em 15 min bloqueiam 15 min (FR-013). A origem é o IP do socket, ou o primeiro IP de
  `X-Forwarded-For` não confiável quando o par vem de `AI_CORE_TRUSTED_PROXIES`. A troca de senha em "Minha conta" conta
  para o mesmo contador. Bloqueio responde a mesma mensagem genérica, com o mesmo tempo (hash fictício).
- **Rationale**: o mesmo modelo de processo único da 003 (contadores de taxa); sem dependência de infraestrutura.
- **Alternatives considered**: contadores em Postgres (sem caso de uso enquanto há um processo).

## R12 — Persistência

- **Decision**: schema `identity` (ADR-015), migrações `001_accounts.sql` (contas, grupos, membros, vínculo Google),
  `002_grants.sql` (pedidos pendentes, códigos, sessões, renovação), `003_signing_keys.sql`, `004_settings.sql`, no
  padrão do `migrate()` dos demais módulos (trava consultiva, `schema_version`). Expurgo periódico de pedidos, códigos,
  sessões e renovação vencidos — função do serviço, agendada pela 011. Segredos guardados só como hash (sessão,
  renovação, código) ou cifrados (chave privada).
- **Rationale**: padrão já provado em `assistants`, `http`, `mcp` e `capabilities`.
- **Alternatives considered**: tabelas de sessão em memória mesmo no `persistent` (sessões de 30 dias não podem morrer
  num restart).

## R13 — Seams expostos

- **Decision**: três seams em `api.py` (contrato em [contracts/identity-api.md](contracts/identity-api.md)):
  `AccountAdmin` (contas e grupos, com o ator em toda operação), `LoginSettings` (Google ligado e origem) e
  `PublicKeySet` (`jwks() -> Mapping`). O protocolo HTTP é o adapter primário `adapters/http.py`, exportado como uma
  função `router(service, settings)` que a 011 inclui no app.
- **Rationale**: a 008 só traduz HTTP para `AccountAdmin`/`LoginSettings` (ADR-031); a 011 injeta o `jwks()` no
  verificador da 003 sem chamada de rede (FR-017); o protocolo fica dentro do módulo (ADR-030).
- **Alternatives considered**: a 008 servir os endpoints do protocolo (a 008 aprenderia OIDC, contra o ADR-030).

## R14 — Linha de comando e admin inicial

- **Decision**: `ai-core users create <nome> --email … [--name …] [--group …]… [--password-stdin]` (sem a opção, pede a
  senha sem eco com `getpass`; a senha da CLI é a definitiva da pessoa, não temporária), `users list`, `users disable|enable
  <nome>`, `users password <nome>` (gera temporária), `users groups <nome> --set …`, `groups create <grupo>`, `groups list` (acrescentados na implementação: a instalação
cria o grupo antes de cadastrar quem entra nele), e `ai-core identity keys rotate
  [--force]`, em `adapters/cli.py`, registrados pela 011. Admin inicial por `AI_CORE_BOOTSTRAP_ADMIN_USERNAME`,
  `_EMAIL` e `_PASSWORD_FILE` (arquivo, nunca a senha em variável), só com zero contas (FR-018).
- **Rationale**: o operador precisa do primeiro admin antes de existir console; segredo em arquivo segue o padrão de
  segredos do Docker.
- **Alternatives considered**: senha do admin inicial em variável de ambiente (vaza em `docker inspect`).

## R15 — Eventos de segurança

- **Decision**: logger `ai_core.identity` (constante `LOGGER` do `service.py`) em `INFO` com eventos estruturados
  (`login.ok`, `login.failed`, `login.locked`, `google.refused`,
  `account.created|updated|disabled|enabled|password_reset`, `keys.rotated`), com usuário (quando existe), cliente,
  motivo curto e ator; nunca senha, código, token, cookie ou segredo (FR-020, FR-021). Não entram no Trace Sink da
  009: não são execuções.
- **Rationale**: o trace é por requisição de execução; segurança vai para o log do processo, que o operador já coleta.
- **Alternatives considered**: tabela de auditoria (sem caso de uso declarado; o `updated_by` da conta cobre a FR-010).

## R16 — Testes

- **Decision**: `tests/identity/` com `unit/` (domínio: PKCE, pedido de autorização, rotação e reuso, claims, bloqueio,
  Google, nomes, senha), `contract/` (os três seams; cada porta contra memória e real — Postgres com
  `AI_CORE_TEST_POSTGRES_DSN`, `argon2`, `cryptography`), `integration/` (suíte de protocolo com o authlib como RP sobre o
  app em processo via transporte ASGI do `httpx`; casos adversariais da SC-002; Google simulado pela porta
  `UpstreamOidc`; varredura de segredos nos logs). Hypothesis para nomes e entradas do formulário.
- **Rationale**: o padrão das demais specs; o RP real prova a interoperabilidade.
- **Alternatives considered**: suíte de conformidade da OpenID Foundation em Docker (útil antes de produção; fica como
  verificação manual opcional, não no CI).

## R17 — Escopo desta passada

- **Decision**: US1–US7 da 012 inteiras. O encaixe é das passadas das consumidoras, nesta mesma fase: a 003
  (`JwksSource` em processo, audiência por superfície, admin por grupo — US9), a 011 (etapa `identity`, portas,
  configuração, CLI — US6), a 008 (rotas de `AccountAdmin`/`LoginSettings` — US9) e a 002 (instalação — US7). Esta
  passada não toca `assistants/`, `http/` nem `bootstrap/`.
- **Rationale**: uma passada por módulo (princípio II); a suíte de protocolo roda com o router montado num app de teste,
  sem a 011.
- **Alternatives considered**: implementar o encaixe aqui (violaria a fronteira).

## R18 — `Referrer-Policy: same-origin` nas páginas (2026-10-14, achado do e2e da console)

- **Decision**: as páginas e redirecionamentos da 012 mandam `Referrer-Policy: same-origin`, não `no-referrer`. O
  `origin_ok` continua recusando `Origin` diferente da origem pública ou da de chegada — inclusive `null`.
- **Rationale**: pela especificação do Fetch, com `no-referrer` o navegador serializa a origem de um POST de navegação
  como `null`, mesmo de mesma origem; o Chromium faz exatamente isso, e o login pelo formulário era recusado ("Não foi
  possível conferir o formulário"). A prova da 9.1 não pegou porque o `check-webui.py` usa `urllib`, que não manda
  `Origin`. Com `same-origin`, o `Origin` volta correto e nenhum referenciador sai para outro site.
- **Alternatives considered**: aceitar `Origin: null` e confiar só no token sincronizador (enfraquece a defesa em
  profundidade contra formulários de outros sites).

## R19 — Mona Sans servida pela própria página (2026-10-14, achado do e2e da console)

- **Decision**: os quatro pesos da Mona Sans (latino, woff2, SIL OFL 1.1 em `assets/fonts/OFL.txt`) vão no pacote da
  012 e saem por `/oauth2/assets/mona-sans-<peso>.woff2`; o CSS os declara com `@font-face` por URL relativa, e a CSP
  das páginas ganha `font-src 'self'`.
- **Rationale**: o CSS do desenho aprovado declarava a Mona Sans sem servi-la, e as páginas caíam na fonte do sistema;
  servir da própria origem mantém a CSP sem terceiros e o visual igual ao da console.
- **Alternatives considered**: fonte do sistema (diverge do desenho); Google Fonts (terceiro, privacidade, CSP).

---

# Passada de 2026-10-20: identidade Axon ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md), [ADR-038](../../docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md); US8)

Decisões pré-aprovadas pelos ADRs e pelo `DESIGN.md` (seção "Brand" e tokens, remapeados em 2026-10-20 com o desenho
aprovado no Penpot); o que segue é como elas chegam às páginas e aos identificadores do provedor, sem re-pesquisa. Os R
anteriores ficam como foram executados (ADR-037, item 6).

## R20 — A marca nas páginas

**Decision**: `pages.Brand` ganha `custom: bool` (o `http.py` o calcula como `name != DEFAULT_NAME or has_logo`, a mesma
regra do `instance.custom` da 008), e `DEFAULT_NAME = "Axon"`. `_brand(brand)`:

- **sem marca própria** (`custom` falso): o lockup no lugar principal —
  `<span class="brand brand-axon"><picture><source media="(prefers-color-scheme: dark)"
  srcset="/oauth2/assets/axon-lockup-dark.svg"><img class="lockup" src="/oauth2/assets/axon-lockup-light.svg" alt="Axon"
  width="106" height="32"></picture></span>`. Com 32px de altura, o símbolo mede 28px e a altura de x do wordmark, 14px
  (`DESIGN.md`, "Brand"; `viewBox` 435 × 132). Nenhuma atribuição.
- **com marca própria**: o que já existe (logotipo ou a inicial em quadrado, e o nome) no lugar principal, e no fim do
  cartão a atribuição `<p class="attribution"><picture><source media="(prefers-color-scheme: dark)"
  srcset="/oauth2/assets/axon-symbol.svg"><img src="/oauth2/assets/axon-symbol-light.svg" alt="" width="16"
  height="16"></picture><span>com Axon</span></p>` — o símbolo é decorativo, e o texto diz a marca.

O `<head>` de toda página ganha `<link rel="icon" type="image/svg+xml" href="/oauth2/assets/favicon.svg">`. O título
continua `<página> · <nome>`. A atribuição entra pelo `_document`, depois do corpo, para valer em todas as páginas.

**Rationale** (ADR-038, itens 1 a 3): o lockup substitui a inicial em quadrado só quando o lugar principal é do Axon; a
marca da organização continua em primeiro plano quando existe. `<picture>` com `prefers-color-scheme` troca a versão do
símbolo pelo tema sem script, que a CSP proíbe (`script-src 'none'`), e cabe em `img-src 'self'`. Imagens externas, em
vez de SVG embutido, evitam ids repetidos de degradê e máscara entre o lockup e a atribuição (ADR-038, Consequências).

**Alternatives considered**: SVG embutido no HTML com `currentColor` (perde o degradê, que é parte da marca); um só
arquivo com `@media` interno no SVG (funciona como `<img>`, mas o `brand-kit` já tem as duas versões aprovadas, e o
`<picture>` não exige editar o vetor); manter a inicial em quadrado como marca padrão (o ADR-038 a substitui pelo lockup).

## R21 — Os assets da marca

**Decision**: cópias exatas de `brand-kit/svg/{axon-lockup-light,axon-lockup-dark,axon-symbol,axon-symbol-light,favicon}.svg`
em `axon_ai/identity/adapters/assets/brand/`, carregadas na construção do router como as fontes e servidas em
`GET /oauth2/assets/<nome>.svg` com `image/svg+xml`, `Cache-Control: public, max-age=604800` e a CSP de SVG que o logotipo
da instalação já usa (`default-src 'none'; style-src 'unsafe-inline'`). Um teste confere que cada cópia é idêntica ao
arquivo do `brand-kit` (o `brand-kit` é a fonte; o pacote, a distribuição).

**Rationale** (ADR-038, item 6: "os arquivos ficam em `brand-kit/svg/` e entram nos assets da console e da 012"): a
distribuição Python não lê fora do pacote, e o teste de igualdade impede que as cópias se desviem.

**Alternatives considered**: link simbólico (não sobrevive à distribuição); gerar os SVG na construção (o vetor é
desenho aprovado, não código).

## R22 — Os tokens de cor

**Decision**: em `assets/identity.css`, os valores do `DESIGN.md` nos nomes de token que a página já usa:

| Token | Claro | Escuro |
|---|---|---|
| `--fundo-base` | `#ffffff` | `#0b0f19` |
| `--fundo-sutil` | `#f8fafc` | `#111724` |
| `--fundo-realce` | `#f1f5f9` | `#1a2130` |
| `--borda-base` | `#e5e7eb` | `#242b3a` |
| `--borda-forte` | `#d1d5db` | `#353d4f` |
| `--texto-primario` | `#111827` | `#f1f3f7` |
| `--texto-secundario` | `#556070` | `#a3abbb` |
| `--texto-terciario` | `#666d7c` | `#8c94a6` |
| `--acao-hover` | `#1d4ed8` | `#3882f6` |
| `--acao-sutil` | `#eff4ff` | `#14223f` |

Azul de ação, texto de ação, estados e foco não mudam. O comentário do topo passa a "neutros frios da marca Axon". Um
teste lê os dois blocos de tokens do CSS e confere o contraste AA dos pares de texto usados (primário, secundário e
terciário sobre fundo base e sutil; texto de ação sobre base; branco sobre o azul de ação; ok e erro sobre os próprios
fundos; foco sobre base e sutil), medidos em 2026-10-20 entre 4,76:1 e 17,7:1.

**Rationale** (ADR-038, item 4): os neutros passam do zinco à família fria da marca, com o mesmo azul de ação, e os
valores são iguais aos da console (`tokens.css`, na passada da 013). **Pendência conhecida, registrada pelo mantenedor
para a passada da 013**: o hover do botão primário no escuro (`#3882f6`, o `axon-blue` que o ADR-038 põe ali) dá 3,69:1
com texto branco, abaixo de 4,5:1. Já era assim antes (`#3b82f6`, 3,68:1). Fica como está aqui, para os dois CSS
continuarem iguais; a decisão sai na 013 e vale para os dois, e o teste de contraste não inclui esse par até lá.

**Alternatives considered**: resolver o hover agora só nas páginas (os dois CSS divergiriam, contra o ADR-038).

## R23 — Cookie e realm

**Decision**: `IdentityHttpSettings.cookie_name` → `"__Host-axon_session"` (seguro) ou `"axon_session"`; o desafio do
endpoint de token → `'Basic realm="axon"'`. O cookie antigo não é lido: o nome procurado é só o novo.

**Rationale** (ADR-037, item 2; corte seco).

**Alternatives considered**: ler os dois nomes por uma janela (sem usuário a preservar).

## R24 — Rótulos da subchave e do CSRF

**Decision**: `cipher.INFO = b"axon-ai/identity/v1"` e `digest._CSRF_CONTEXT = "axon-ai/identity/csrf:"`. A mensagem de
`IdentityStartError` quando a chave não abre passa a "a chave de assinatura não abre com AXON_MASTER_KEY (chave mestra
trocada, ou selada antes do renome — ADR-037); restaure a chave mestra ou rode `axon identity keys rotate --force`
(encerra todas as sessões)". Nenhuma migração.

**Rationale** (ADR-037, itens 2 e 3; ADR-033): a rotação forçada da CLI não abre a chave antiga (não passa pelo
`start()`), então ela recupera o ambiente; a mensagem diz as duas causas possíveis para o operador não procurar uma chave
mestra que não mudou (princípio VII).

**Alternatives considered**: migração que abre com o rótulo antigo e sela com o novo (mantém o rótulo antigo no código);
apagar as chaves no boot (encerraria sessões sem pedido do operador).

## R25 — Consumidores

**Decision**: `IdentityHttpSettings.display_name` usa o `DEFAULT_NAME` novo (a 011 já passa `"Axon"` por
`AXON_DISPLAY_NAME`). Testes: `test_pages.py` (título, lockup, atribuição, favicon), `test_login_uniform.py`,
`test_google.py` e `test_protocol.py` (cookie), `tests/bootstrap/integration/test_platform_identity.py` (cookie) e os de
cifra e CSRF. O e2e da console (`console/e2e/`) entra pelas páginas com seletores de campo e botão, sem depender da marca
nem do cookie — roda para provar. Documentos vivos: `contracts/pages.md`, `contracts/oidc.md`, `contracts/ports.md`,
`design.md`, `data-model.md`, `quickstart.md`.

**Rationale** (ADR-037, item 7).

**Alternatives considered**: nenhuma.

## R26 — Verificação visual

**Decision**: além das suítes, capturas do login com e sem marca da instalação, em 390 e 1440 px, nos temas claro e
escuro, pelo Playwright do MCP (no `serve` do perfil `memory` com identidade), e o favicon a 16px; o contraste AA pelo
teste da R22. A comparação com o Penpot fica para quando o arquivo estiver conectado nesta sessão (não estava em
2026-10-20); o `DESIGN.md` registra o desenho aprovado.

**Rationale**: o plano do renome pede capturas comparadas ao desenho; a parte que não depende do Penpot roda aqui.

**Alternatives considered**: teste de regressão visual automatizado (sem linha de base aprovada para as páginas novas).

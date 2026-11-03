---

description: "Task list for 012 — Provedor de identidade da plataforma, Fase 9"
---

# Tasks: Provedor de identidade da plataforma

**Input**: Design documents from `/specs/012-core-identity/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos, antes do código (TDD). SC-002, SC-003 e SC-005 são enunciados adversariais que só se demonstram
por teste, e a governança exige a suíte de conformidade de cada seam exposto e de cada porta secundária (memória ×
adapter real).

**Organization**: **US1–US7** (Fase 9 do roadmap). **Não** entram: nada em `ai_core/assistants/`, `ai_core/http/` nem
`ai_core/bootstrap/` — o `JwksSource` e a audiência por superfície na 003, as rotas de administração na 008, a etapa
`identity`, as portas, a configuração e a CLI na 011 e a instalação na 002 são das passadas delas
([research.md](research.md) R17).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1–US7)

## Path Conventions

- Os nomes de arquivo de teste são únicos no workspace (o pytest roda sem `__init__.py` nos diretórios): por isso
  `test_settings_precedence.py`, `test_signing_keys.py`, `test_identity_cli.py`, `test_identity_token_generator.py` e
  `test_google_rules.py`, no lugar dos nomes curtos que já existiam em outros módulos ou na própria 012

- Caminhos relativos a `ai-core/packages/core/`: código em `src/ai_core/identity/` (abreviado `identity/`), testes em
  `tests/identity/{unit,contract,integration}/` (abreviado `tests/identity/`)
- Comandos a partir de `ai-core/`, com `XDG_DATA_HOME=$HOME/.local/share`; Postgres por `AI_CORE_TEST_POSTGRES_DSN`

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Criar o esqueleto: `src/ai_core/identity/__init__.py` (docstring: spec 012 — a plataforma é o provedor OIDC,
  ADR-030; seams em `api.py`; protocolo e páginas em `adapters/http.py`), `identity/domain/__init__.py`,
  `identity/adapters/__init__.py`, `identity/adapters/sql/`, `identity/adapters/assets/` e
  `tests/identity/{unit,contract,integration}/`
- [X] T002 Acrescentar `argon2-cffi>=25.1,<26` a `dependencies` de `pyproject.toml` (pacote core), com comentário citando a
  spec 012 e R2 (wheels `abi3` aarch64; confinado a `adapters/`); `uv sync`; conferir no `uv.lock` o
  `argon2-cffi-bindings` com wheel `cp310-abi3` para aarch64
- [X] T003 [P] Em `ai-core/pyproject.toml`: `authlib>=1.8,<2` no grupo de desenvolvimento (só testes, R1) e
  `packages/core/tests/identity` em `[tool.pytest.ini_options] pythonpath`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: superfície pública, portas, adapters em memória e reais, kit de teste, chaves de assinatura e fronteiras

**⚠️ CRITICAL**: nenhuma user story começa antes de T004–T020

- [X] T004 Implementar `identity/api.py` conforme [data-model.md](data-model.md) e
  [contracts/identity-api.md](contracts/identity-api.md), só com a stdlib:
  - vocabulário `USERNAME_PATTERN = r"^[a-z0-9][a-z0-9._-]{0,63}$"` (o mesmo para grupo), `PASSWORD_MIN = 12`,
    `PASSWORD_MAX = 128`, `NAME_MAX = 120`, `ClientType = Literal["confidential", "public"]`,
    `AuthMethod = Literal["pwd", "google"]`, `SettingSource = Literal["installation", "runtime", "default"]`;
  - value objects congelados (`frozen=True, slots=True, kw_only=True`) `Account`, `AccountDraft`, `AccountPatch`,
    `IssuedPassword`, `Group`, `LoginSettingsView`, `Page[T]`, validados na construção;
  - erros `IdentityError` → `AccountNotFound`, `GroupNotFound`, `Conflict(field)`, `InvalidField(field, reason)`,
    `ProtectedGroup(reason)`, `GoogleNotConfigured`, `InstallationDefined(field)`;
  - os `Protocol` `AccountAdmin`, `LoginSettings` e `PublicKeySet` com as assinaturas do contrato
- [X] T005 Implementar `identity/ports.py` com as 13 portas de [contracts/ports.md](contracts/ports.md) e os registros
  internos `AccountRecord`, `PendingAuthorization`, `AuthorizationCode`, `Session`, `RefreshToken`, `SigningKey`,
  `IdentitySettings`, `Client`, `GoogleIdentity`, `BootstrapAdmin` ([data-model.md](data-model.md))
- [X] T006 [P] Testes de `tests/identity/unit/test_names.py` (Hypothesis): usuário e grupo no padrão, sem `@`; e-mail
  normalizado `strip().lower()`; senha de 12 a 128 caracteres contados como código Unicode; identificador de login decide
  usuário × e-mail pela presença de `@`
- [X] T007 [P] Implementar `identity/domain/names.py` para fazer T006 passar
- [X] T008 [P] Testes de `tests/identity/unit/test_settings_precedence.py` e implementação de `identity/domain/settings.py`:
  precedência instalação > runtime > padrão com a origem por campo (ADR-033); padrão do Google = ligado se configurado
- [X] T009 Implementar `identity/adapters/memory.py`: adapters em memória de todas as portas — `PasswordHasher` rápido e
  determinístico, `TokenGenerator` sequencial, `UpstreamOidc` simulado e programável (`GoogleIdentity` por código),
  `Clock` fixo e ajustável
- [X] T010 Criar `tests/identity/identity_testkit.py` e `tests/identity/conftest.py`: fábricas de conta e cliente
  (`open-webui` confidencial, `console` público), relógio fixo, Google simulado, `IdentityService` montado com memória,
  fixture `postgres_pool` (pula sem `AI_CORE_TEST_POSTGRES_DSN`) e um app FastAPI de teste com `router(service, settings)`
- [X] T011 [P] Suítes de conformidade parametrizadas (memória × Postgres) em `tests/identity/contract/`:
  `test_account_store.py` (unicidade de nome e e-mail sem diferenciar maiúsculas, inclusive com conta desativada;
  `replace` com versão desatualizada → `Conflict`; cascata ao apagar grupo), `test_grant_store.py` (código de uso único
  sob duas trocas concorrentes; rotação atômica; reuso revoga a família; `revoke_for_account`, `revoke_except`; `purge`),
  `test_signing_key_store.py`, `test_settings_store.py` (versão)
- [X] T012 Implementar `identity/adapters/postgres_schema.py` (`migrate(pool, *, now)`, schema `identity`, trava
  consultiva, `schema_version` — padrão de `assistants/adapters/postgres_schema.py`) e `adapters/sql/001_accounts.sql`,
  `002_grants.sql`, `003_signing_keys.sql`, `004_settings.sql` com as tabelas de [data-model.md](data-model.md)
- [X] T013 Implementar `identity/adapters/postgres.py` (`PostgresAccountStore`, `PostgresGrantStore`,
  `PostgresSigningKeyStore`, `PostgresIdentitySettingsStore`) para fazer T011 passar contra o Postgres; `consume` do código
  e `rotate` da renovação com `UPDATE … WHERE … RETURNING` atômico
- [X] T014 [P] `tests/identity/contract/test_cipher.py` e `identity/adapters/cipher.py`: AES-GCM com subchave
  HKDF-SHA256 (`info="ai-core/identity/v1"`) da chave mestra de 32 bytes, nonce de 12 bytes por gravação; ida e volta;
  chave errada falha sem vazar o texto
- [X] T015 [P] `tests/identity/contract/test_signer.py` e `identity/adapters/signing.py`: geração RSA-2048 (`kid` = 16
  hex), assinatura RS256 com `kid` no cabeçalho, verificação contra um JWKS; recusa `alg=none` e HS256
- [X] T016 [P] `tests/identity/contract/test_password_hasher.py` e `identity/adapters/passwords.py`: argon2id (t=3,
  m=64 MiB, p=4), `needs_rehash`, `dummy_verify` com custo igual ao real; o adapter de memória passa na mesma suíte
- [X] T017 [P] `tests/identity/contract/test_client_source.py` e `identity/adapters/clients_yaml.py` +
  `identity/domain/clients.py`: o formato de [contracts/identity-yaml.md](contracts/identity-yaml.md) — `secret`
  obrigatório em `confidential` e proibido em `public`, referência `[a-z0-9_]{1,64}`, URIs absolutas, `http` só para
  `localhost`, `127.0.0.1` ou nome sem ponto; erro nomeia o campo; cliente confidencial cuja variável de segredo falta
  fica indisponível (o boot segue, ADR-020): o `token` responde `invalid_client` e o log nomeia a referência, nunca um
  valor
- [X] T018 [P] `tests/identity/contract/test_identity_secrets.py` e `identity/adapters/secrets_env.py`:
  `AI_CORE_IDENTITY_SECRET_<REF>`, `AI_CORE_GOOGLE_CLIENT_ID|CLIENT_SECRET|HOSTED_DOMAIN`, `AI_CORE_GOOGLE_LOGIN`,
  `AI_CORE_BOOTSTRAP_ADMIN_USERNAME|EMAIL|PASSWORD_FILE`; nenhum nome arbitrário (ADR-020)
- [X] T019 `tests/identity/unit/test_signing_keys.py` e `identity/domain/keys.py` (ciclo `active` → `retiring` → `retired`;
  `retiring` sai depois do TTL do acesso + 60 s); em `identity/service.py`, o esqueleto do `IdentityService` (construtor
  com as portas e um `IdentityConfig` — `public_url`, `admin_group`, `display_name`, `logo`, `cookie_secure`,
  `trusted_proxies`, `access_ttl=600`, `session_ttl=30 dias`) e `start()`, que garante uma chave `active` — a privada
  gerada pelo `TokenSigner` e **selada pelo `SecretCipher` antes de chegar ao `SigningKeyStore`** (FR-016, ADR-033) — e
  carrega o JWKS em memória
- [X] T020 Contratos de import-linter em `ai-core/pyproject.toml` (os 7 de "Fronteiras verificadas" do
  [plan.md](plan.md)); a 012 nos contratos existentes de "framework HTTP só nos adapters" e "nenhum módulo importa a
  composition root"; `uv run lint-imports` verde

**Checkpoint**: portas e adapters prontos e conformes; nenhum endpoint ainda

---

## Phase 3: User Story 1 — Pessoa entra no chat com usuário e senha (Priority: P1) 🎯 MVP

**Goal**: um cliente confidencial faz o fluxo de código e recebe tokens com `preferred_username` e `groups`

**Independent Test**: com duas contas em grupos diferentes, o RP authlib faz login por senha e os tokens trazem os
grupos certos; usuário inexistente, senha errada e conta desativada recebem a mesma resposta

### Tests for User Story 1

- [X] T021 [P] [US1] `tests/identity/unit/test_authorize.py`: cliente desconhecido e `redirect_uri` divergente →
  "não redirecionar"; `response_type` diferente de `code`; `scope` sem `openid`; `nonce` obrigatório; `prompt=none` sem
  sessão → `login_required`
- [X] T022 [P] [US1] `tests/identity/unit/test_tokens.py`: claims de acesso (`iss`, `aud` do cliente, `sub`,
  `preferred_username`, `groups`, `azp`, `scope`, `iat`, `exp` = `iat` + 600) e de identidade (`nonce`, `auth_time`,
  `amr`, `email`, `email_verified`, `name`, `aud` = `client_id`)
- [X] T023 [P] [US1] `tests/identity/integration/test_protocol.py` (parte 1): descoberta com backchannel dinâmico
  (`issuer` público; `token_endpoint` pela base do pedido; `X-Forwarded-*` só de proxy confiável); login por usuário e por
  e-mail; código → tokens por `client_secret_basic` e `client_secret_post`; token de identidade validado pelo authlib
  (iss, aud, nonce, kid); `userinfo`; código reusado → `invalid_grant`
- [X] T024 [P] [US1] `tests/identity/integration/test_login_uniform.py`: inexistente, senha errada e desativada →
  mesmo status (`401`), mesmo corpo e tempos na mesma ordem de grandeza (SC-005); formulário sem `csrf` ou com `csrf`
  errado → recusado; pedido vencido (10 min) → "O link de login expirou", sem redirecionar; cookie de sessão
  `__Host-aic_session` com `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, sem `Domain` e só `Max-Age` (e `aic_session`
  sem `Secure` com `AI_CORE_COOKIE_SECURE=false`)
- [X] T025 [P] [US1] `tests/identity/integration/test_pages.py`: a página de login tem `lang="pt-BR"`, rótulos ligados,
  `autocomplete` certos, o nome da instalação (`AI_CORE_DISPLAY_NAME`) e, sem ele, "Agentic"; o logotipo em
  `/oauth2/assets/logo` quando `AI_CORE_LOGO_FILE` existe (e `404` sem ele); cabeçalhos CSP com `form-action` contendo
  `'self'` e as origens dos `redirect_uris` dos clientes, `nosniff`, `no-referrer`, `no-store`; nenhum `<script>`;
  substituições escapadas (nome com `<`)

### Implementation for User Story 1

- [X] T026 [P] [US1] `identity/domain/authorize.py` e `identity/domain/tokens.py` para T021–T022
- [X] T027 [US1] Em `identity/service.py`: `discovery(base)`, `begin_authorization(params)` (grava `PendingAuthorization`
  com CSRF), `login(request_id, identifier, password, csrf, origin)` (hash fictício para inexistente; conta desativada
  igual a senha errada; re-hash quando preciso; cria sessão de 30 dias e código de 60 s), `exchange_code(...)`,
  `userinfo(token)`; `last_login_at` atualizado
- [X] T028 [P] [US1] `identity/adapters/pages.py` (função de montagem com escape por padrão; páginas de login, erro e
  "você saiu"; nome e logotipo da instalação — FR-023) e `identity/adapters/assets/identity.css` com os tokens do desenho
  aprovado (página "Login e conta" do Penpot): Mona Sans, raio 6/8, temas claro e escuro por `prefers-color-scheme`,
  celular primeiro, foco visível
- [X] T029 [US1] `identity/adapters/http.py`: `router(service, settings)` com `GET /.well-known/openid-configuration`,
  `GET /oauth2/authorize`, `POST /oauth2/login`, `POST /oauth2/token`, `GET /oauth2/userinfo`, `GET /oauth2/jwks`,
  `GET /oauth2/assets/identity.<hash>.css`, `GET /oauth2/assets/logo`; CSP com `form-action` montada no boot a partir
  das origens dos `redirect_uris`; formulário `x-www-form-urlencoded` lido do corpo com teto de 16 KiB (outro
  tipo → 415, R4); cookie de sessão (R5); cabeçalhos de [contracts/oidc.md](contracts/oidc.md); erros RFC 6749
- [X] T030 [US1] Rodar T021–T025 até verde

**Checkpoint**: o Open WebUI (simulado pelo authlib) entra com senha e recebe os grupos

---

## Phase 4: User Story 2 — Admin inicial, contas, grupos e "Minha conta" (Priority: P1)

**Goal**: o operador cria o primeiro admin; admins gerem contas e grupos; senha temporária obrigatória; a pessoa troca a
própria senha

**Independent Test**: sem contas, o admin inicial é criado; ele cadastra outra pessoa, que entra, troca a senha
temporária e recebe o grupo

### Tests for User Story 2

- [X] T031 [P] [US2] `tests/identity/contract/test_account_admin.py`: cadastro (nome e e-mail livres entre todas as
  contas, inclusive desativadas — US2 cen. 4), senha temporária só em `create`/`reset_password`, `google_only` sem senha,
  `update` com versão desatualizada → `Conflict("version")`, troca de e-mail mantém o vínculo Google, grupo de admin
  protegido (apagar; tirar ou desativar o último admin ativo → `ProtectedGroup`), `set_members`, `delete_group` remove as
  associações, `updated_by` gravado
- [X] T032 [P] [US2] `tests/identity/integration/test_bootstrap.py`: variáveis de admin inicial com zero contas → admin
  no grupo de administração com a senha do arquivo; com contas → ignoradas, com aviso no log; arquivo de senha ausente →
  erro que nomeia a variável
- [X] T033 [P] [US2] `tests/identity/integration/test_password_pages.py`: login com senha temporária leva à troca antes
  de qualquer código; erros junto ao campo (tamanho, confirmação, igual à temporária); "Minha conta" exige sessão, troca a
  senha com a atual, encerra as outras sessões e mantém a atual; senha atual errada conta para o bloqueio; conta só
  Google não mostra o formulário
- [X] T034 [P] [US2] `tests/identity/integration/test_identity_cli.py`: `users create` com `--password-stdin` e sem (entrada sem
  eco simulada), `users list`, `disable|enable`, `password` (mostra a temporária uma vez), `groups --set`

### Implementation for User Story 2

- [X] T035 [P] [US2] `identity/domain/accounts.py`: regras de cadastro e de proteção do grupo de administração; geração da
  senha temporária no `TokenGenerator` (20 caracteres de alfabeto sem ambíguos, grupos de 4 com hífen — R10), com a
  conformidade da porta em `tests/identity/contract/test_identity_token_generator.py` (32 bytes de token, UUID, formato da senha;
  o sequencial de memória na mesma suíte)
- [X] T036 [US2] Em `identity/service.py`, o seam `AccountAdmin` completo e `bootstrap_admin()` (só com zero contas);
  `reset_password` e `disable` revogam as sessões da conta
- [X] T037 [US2] Em `identity/adapters/http.py` e `pages.py`: `POST /oauth2/password` (troca obrigatória),
  `GET|POST /oauth2/account` ("Minha conta", CSRF da sessão), conforme [contracts/pages.md](contracts/pages.md)
- [X] T038 [US2] `identity/adapters/cli.py`: `users_create_command`, `users_list_command`, `users_disable_command`,
  `users_enable_command`, `users_password_command`, `users_groups_command` (sem parser próprio; a 011 os registra, como
  em `assistants/adapters/cli.py`); senha por `--password-stdin` ou `getpass`
- [X] T039 [US2] Rodar T031–T034 até verde

**Checkpoint**: a instalação nova tem quem administra; as pessoas trocam a própria senha

---

## Phase 5: User Story 3 — A console entra com audiência própria (Priority: P1)

**Goal**: cliente público com PKCE S256 e audiência `ai-core-admin`; logout encerra a sessão

**Independent Test**: sem PKCE é recusado; com PKCE, o token da console tem `aud = ai-core-admin` e o do Open WebUI,
`ai-core`; o logout revoga a renovação da sessão

### Tests for User Story 3

- [X] T040 [P] [US3] `tests/identity/unit/test_pkce.py` e `tests/identity/unit/test_refresh.py`: S256 (vetores da RFC
  7636); cliente público sem desafio → `invalid_request`; rotação a cada uso para público; reuso de token rotacionado
  revoga a família; confidencial não rotaciona
- [X] T041 [P] [US3] `tests/identity/integration/test_protocol.py` (parte 2): fluxo público com PKCE pelo authlib;
  audiências por cliente; renovação com rotação e com reuso; `POST /oauth2/revoke`; `GET /oauth2/logout` com
  `id_token_hint` e `post_logout_redirect_uri` exato (inválido → página "Você saiu", sem redirecionar)

### Implementation for User Story 3

- [X] T042 [P] [US3] `identity/domain/pkce.py` e `identity/domain/refresh.py` para T040
- [X] T043 [US3] Em `identity/service.py` e `adapters/http.py`: PKCE no `authorize`/`token`, `refresh_token` com
  rotação e detecção de reuso, `revoke`, `logout`
- [X] T044 [US3] Rodar T040–T041 até verde

**Checkpoint**: a console pode entrar sem segredo no navegador e sem aceitar token do chat

---

## Phase 6: User Story 4 — Login com Google só para cadastrados (Priority: P2)

**Goal**: o Google entra só para contas ativas com o e-mail verificado; liga e desliga em runtime

**Independent Test**: com o Google simulado, só o e-mail cadastrado e verificado recebe token; nenhuma conta é criada

### Tests for User Story 4

- [X] T045 [P] [US4] `tests/identity/unit/test_google_rules.py`: `email_verified` falso → recusa; domínio fora do aceito →
  recusa; e-mail sem conta ativa → "conta Google não cadastrada"; primeiro sucesso vincula o `sub`; `sub` diferente do
  vinculado → recusa
- [X] T046 [P] [US4] `tests/identity/contract/test_login_settings.py`: precedência; `AI_CORE_GOOGLE_LOGIN` definido →
  `InstallationDefined`; sem cliente Google → `GoogleNotConfigured`; versão
- [X] T047 [P] [US4] `tests/identity/contract/test_upstream_oidc.py`: o adapter real (`adapters/google.py`) contra um
  servidor OIDC falso local (descoberta, troca de código, `id_token` assinado por chave de teste) e o simulado de memória
  na mesma suíte; `iss`, `aud`, `nonce`, PKCE
- [X] T048 [P] [US4] `tests/identity/integration/test_google.py`: botão só com o Google ligado e configurado;
  `/oauth2/google/start` recusado sem configuração; fluxo completo com o simulado; SC-003: nenhuma conta criada em nenhum
  cenário

### Implementation for User Story 4

- [X] T049 [P] [US4] `identity/domain/google.py` para T045
- [X] T050 [P] [US4] `identity/adapters/google.py`: `UpstreamOidc` sobre `httpx` e `pyjwt` (R9)
- [X] T051 [US4] Em `identity/service.py`: o seam `LoginSettings` e `google_start`/`google_callback`; em
  `adapters/http.py`: `GET /oauth2/google/start` e `GET /oauth2/google/callback`; em `pages.py`: o botão e as mensagens
  de recusa de [contracts/pages.md](contracts/pages.md)
- [X] T052 [US4] Rodar T045–T048 até verde

---

## Phase 7: User Story 5 — Tentativas repetidas são contidas (Priority: P2)

**Goal**: 5 falhas em 15 min bloqueiam por 15 min, por usuário e por origem, sem revelar existência

**Independent Test**: depois de 5 falhas, a sexta com a senha certa é recusada com a mensagem genérica; igual para
usuário inexistente

### Tests for User Story 5

- [X] T053 [P] [US5] `tests/identity/unit/test_attempts.py`: janela deslizante com relógio fixo; chaves por usuário
  normalizado e por origem; liberação depois de 15 min; e a conformidade da porta `LoginAttempts` em
  `tests/identity/contract/test_login_attempts.py` (`blocked`, `fail`, `reset`) contra o adapter de memória — o único,
  processo único (R11)
- [X] T054 [P] [US5] Casos de bloqueio em `tests/identity/integration/test_login_uniform.py`: sexta tentativa recusada
  com a senha certa; inexistente com as mesmas respostas; `X-Forwarded-For` ignorado sem proxy confiável e usado com ele

### Implementation for User Story 5

- [X] T055 [US5] `identity/domain/attempts.py` e o uso da porta `LoginAttempts` no `login` e na troca de senha de "Minha
  conta" em `identity/service.py`; origem pelo socket ou pelo `X-Forwarded-For` de `trusted_proxies` em
  `adapters/http.py`
- [X] T056 [US5] Rodar T053–T054 até verde

---

## Phase 8: User Story 6 — Desativar alguém corta o acesso (Priority: P2)

**Goal**: conta desativada não entra, não renova e perde as sessões; reativada volta com os grupos atuais

**Independent Test**: com sessão aberta, desativar → a renovação seguinte é recusada e o login também

### Tests for User Story 6

- [X] T057 [P] [US6] `tests/identity/integration/test_disable.py`: desativação revoga sessões e renovação; `userinfo`
  com token ainda válido → `401`; `authorize` com o cookie antigo mostra o login; reativação → login normal com grupos
  atuais; mudança de grupo vale no próximo token

### Implementation for User Story 6

- [X] T058 [US6] Conferir conta ativa em `refresh_token`, `userinfo` e no uso da sessão em `identity/service.py`
- [X] T059 [US6] Rodar T057 até verde

---

## Phase 9: User Story 7 — Chave de assinatura trocada sem derrubar ninguém (Priority: P3)

**Goal**: rotação normal mantém tokens vigentes; rotação forçada encerra todas as sessões

**Independent Test**: token emitido antes da rotação continua válido; novo token sai com outro `kid`

### Tests for User Story 7

- [X] T060 [P] [US7] `tests/identity/contract/test_public_key_set.py`: `jwks()` com `active` + `retiring`; rotação
  normal publica as duas; `retiring` sai depois do prazo; rotação forçada troca tudo e revoga as sessões (SC-007); o
  `SigningKeyStore` nunca recebe a chave privada em claro (só o selo do `SecretCipher`)

### Implementation for User Story 7

- [X] T061 [US7] `rotate_keys(force)` e `PublicKeySet.jwks()` em `identity/service.py`; `identity_keys_rotate_command`
  em `identity/adapters/cli.py`
- [X] T062 [US7] Rodar T060 até verde

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T063 [P] `tests/identity/integration/test_no_secrets_in_logs.py`: captura o logger `ai_core.identity` ao longo de todos os
  fluxos e procura senhas, códigos, tokens, cookies, segredo de cliente e chave privada (FR-020); eventos de segurança
  presentes com usuário e motivo (FR-021, R15)
- [X] T064 Eventos de segurança estruturados no logger `ai_core.identity` em `identity/service.py` (`login.ok`, `login.failed`,
  `login.locked`, `google.refused`, `account.*`, `keys.rotated`)
- [X] T065 [P] `purge(now)` no `IdentityService` (pedidos, códigos, sessões e renovação vencidos; chaves `retiring`
  vencidas) com teste em `tests/identity/contract/test_grant_store.py`; o agendamento é da 011
- [X] T066 [P] Atualizar `specs/README.md` (status da 012) e `CLAUDE.md` (o módulo de identidade existe; o encaixe vem
  nas passadas da 003, 008, 011 e 002)
- [X] T067 Rodar o [quickstart.md](quickstart.md) inteiro: `uv run pytest`, `mypy`, `ruff check packages`,
  `lint-imports`, e as portas contra o Postgres com `AI_CORE_TEST_POSTGRES_DSN`; medir uma verificação de senha com o
  argon2id real (meta do plano: < 250 ms no hardware alvo) e anotar o valor no `research.md` R2

---

## Dependencies & Execution Order

- Setup (T001–T003) → Foundational (T004–T020) → US1 (T021–T030) → US2, US3 em qualquer ordem → US4, US5, US6 → US7 →
  Polish
- US2 usa o login da US1 (troca de senha obrigatória no fluxo); US3 usa o `token` da US1; US5 e US6 alteram o `login` e
  o `refresh` da US1/US3; US4 é independente depois da US1; US7 é independente depois do Foundational (T019)

## Parallel Example: Foundational

```text
T006 + T008 + T011 + T014 + T015 + T016 + T017 + T018   # arquivos diferentes, sem dependência entre si
```

## Parallel Example: User Story 1

```text
T021 + T022 + T023 + T024 + T025   # testes primeiro
T026 + T028                        # domínio e páginas em paralelo; T027 e T029 em seguida
```

## Implementation Strategy

1. **MVP**: Setup + Foundational + US1 — o login por senha de um cliente confidencial; é o que tira o Keycloak do
   caminho do Open WebUI.
2. US2 e US3 completam o P1: quem administra e a console.
3. US4–US6: Google, força bruta e desativação.
4. US7 e Polish.
5. O encaixe (003 US9, 008 US9, 011 US6, 002 US7) vem nas passadas das consumidoras, nesta fase.

---

## Passada de 2026-10-20: identidade Axon — US8 ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md), [ADR-038](../../docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md); research R20–R26)

**Goal**: páginas com o lockup Axon ou a marca da instalação com "com Axon", favicon do símbolo, tokens do `DESIGN.md` em
AA; cookie `axon_session`, realm `axon`, rótulos `axon-ai/identity/…`; suítes, e2e e capturas.

**Independent Test**: [quickstart.md, "Fase 9, incremento 9.5"](quickstart.md).

### Setup

- [X] T068 [US8] Copiar `brand-kit/svg/{axon-lockup-light,axon-lockup-dark,axon-symbol,axon-symbol-light,favicon}.svg` para
  `axon-ai/packages/core/src/axon_ai/identity/adapters/assets/brand/` (R21); a marca `us8` em `axon-ai/pyproject.toml`
  ganha `; 012 US8 — identidade Axon (marca das páginas, cookie, realm e rótulos)`

### Tests (antes das T072–T076)

- [X] T069 [P] [US8] `axon-ai/packages/core/tests/identity/integration/test_pages.py` (R20, R21, marca `us8`): sem marca
  própria, o login, a troca de senha, "Minha conta", o erro e a saída têm o `<picture>` do lockup (`axon-lockup-dark.svg`
  na `<source>` escura, `axon-lockup-light.svg` no `<img alt="Axon">`), nenhum `class="attribution"` e o título
  `Entrar · Axon` (cen. 1); com `display_name="Instituto Exemplo"`, o nome no lugar principal, sem lockup, e a atribuição
  com `com Axon` e o símbolo `alt=""` (cen. 2); com logotipo e o nome padrão, a atribuição também; toda página tem
  `<link rel="icon" type="image/svg+xml" href="/oauth2/assets/favicon.svg">` (cen. 3); os testes existentes do título e da
  marca passam ao padrão novo
- [X] T070 [P] [US8] Assets e contraste (R21, R22, marca `us8`): `GET /oauth2/assets/<nome>.svg` para os cinco nomes →
  200, `image/svg+xml`, a CSP de SVG e o corpo igual ao arquivo de `brand-kit/svg/` (caminho a partir da raiz do
  repositório); nome desconhecido → 404; e `axon-ai/packages/core/tests/identity/unit/test_page_contrast.py`, que lê os
  dois blocos de tokens de `assets/identity.css` e confere ≥ 4,5:1 para primário, secundário e terciário sobre
  `--fundo-base` e `--fundo-sutil`, `--acao-texto` sobre `--fundo-base`, `--texto-sobre-acao` sobre `--acao-base`,
  `--ok-texto` sobre `--ok-fundo`, `--erro-texto` sobre `--erro-fundo` e `--foco` sobre os dois fundos (cen. 4)
- [X] T071 [P] [US8] Nomes com comportamento (R23, R24, marca `us8`): o cookie (`__Host-axon_session`/`axon_session`) em
  `tests/identity/integration/test_login_uniform.py`, `test_google.py`, `test_protocol.py` e
  `tests/bootstrap/integration/test_platform_identity.py`; um pedido com só `aic_session` não tem sessão (cen. 5); o realm
  `Basic realm="axon"` no 401 do token (cen. 6); `INFO == b"axon-ai/identity/v1"` e o CSRF com o contexto novo; uma chave
  selada com `AesGcmCipher(MASTER_KEY, info=b"ai-core/identity/v1")` faz `start()` levantar `IdentityStartError` com
  `rotate --force` e "antes do renome", e `rotate_keys(force=True)` devolve a identidade (cen. 7). Rodar T069–T071 e ver
  falhar

### Implementation

- [X] T072 [US8] `axon-ai/packages/core/src/axon_ai/identity/adapters/pages.py` (R20): `DEFAULT_NAME = "Axon"`,
  `Brand.custom`, `_brand` com o lockup ou a marca da instalação, `_attribution`, o `<link rel="icon">` e a atribuição no
  `_document`; docstrings
- [X] T073 [US8] `axon-ai/packages/core/src/axon_ai/identity/adapters/http.py` (R20, R21, R23): `custom` no `Brand`; os SVG
  de `assets/brand/` carregados e servidos com `image/svg+xml`, `max-age=604800` e a CSP de SVG; `cookie_name` novo;
  `Basic realm="axon"`
- [X] T074 [US8] `axon-ai/packages/core/src/axon_ai/identity/adapters/assets/identity.css` (R20, R22): os tokens da tabela
  do R22, o comentário do topo, `.lockup` (altura 32px, largura automática) e `.attribution` (caption terciário, símbolo de
  16px, centrado, com respiro do cartão)
- [X] T075 [US8] `axon-ai/packages/core/src/axon_ai/identity/adapters/cipher.py` e `domain/digest.py` (R24): rótulo e
  contexto novos, e a docstring do cipher; `axon-ai/packages/core/src/axon_ai/identity/service.py`: a mensagem da chave que
  não abre
- [X] T076 [US8] `axon-ai/packages/core/tests/identity/contract/test_cipher.py`: a subchave de outro módulo continua a da 009
  (`axon-ai/observability/v1`); conferir que o teste da identidade usa o rótulo novo

### Integration e verificação

- [X] T077 [US8] Suítes (a partir de `axon-ai/`): `uv run pytest && uv run mypy && uv run ruff check packages && uv run
  ruff format --check packages && uv run lint-imports`, com e sem `AXON_TEST_POSTGRES_DSN`; a console (`npm test` e
  `npm run e2e`, que entra pelas páginas)
- [X] T078 [US8] Verificação visual (R26): `serve` no `memory` com identidade, capturas do login sem e com marca da
  instalação em 390 e 1440 px, claro e escuro, e do favicon, pelo Playwright do MCP; guardar no scratchpad e descrever no
  relatório
- [X] T079 [US8] Resíduos (SC-008): `git grep -nE 'aic_session|realm="ai-core"|ai-core/identity/|"Agentic"'` fora do
  histórico só nos testes e textos do corte seco (e no que é da 013: a Sidebar e o AccessDenied da console); nenhuma
  palavra `agentic` removida (`--word-diff`)
- [X] T080 [P] [US8] `specs/README.md` (linha da 012 com a US8) e `docs/roadmap.md` (andamento do 9.5: 012 feita)

### Dependencies (US8)

T068 → T069 ∥ T070 ∥ T071 (veem falhar) → T072 → T073 → T074 → T075 → T076 → T077 → T078 → T079; T080 em paralelo com a
T077.

### Notas da execução (US8)

- O teste de contraste achou um par que **já reprovava** com os tokens anteriores: o terciário sobre o fundo sutil no
  claro (`#74747c` sobre `#fafafa`); com os tokens da marca, 4,96:1. O hover escuro fica fora do teste (pendência da
  013, R22).
- `Safe("\n") + _ATTRIBUTION` daria `str` comum, que o `join` escaparia: a atribuição entra como `Safe("\n" + …)`.
- O Penpot não estava conectado nesta sessão; a verificação visual seguiu o `DESIGN.md` (R26). Capturas (390 e 1440 px,
  claro e escuro, sem e com marca da instalação) no scratchpad da sessão, `capturas-012/`; a pasta `.playwright-mcp/` que
  o Playwright criou no repositório foi apagada.
- O "Agentic" que sobra no código é da console (`Sidebar.tsx`, `AccessDenied.tsx`, a fixture do MSW), da passada da 013.
- Suítes: workspace 3208 passed, 168 skipped; com `AXON_TEST_POSTGRES_DSN`, 3365 passed, 11 skipped; mypy sem erro; ruff
  limpo; import-linter 69 kept; console 67 testes e e2e 39 passed, 4 skipped.

---

## Correção de 2026-10-28: a CSP com as origens dos clientes no perfil `persistent` (research R27)

- [X] T081 `_Http.csp` calculada por página a partir de `service.clients`; teste de regressão em
  `tests/identity/integration/test_pages.py`. Verificado no dev: o login por senha pelo Open WebUI volta ao cliente.

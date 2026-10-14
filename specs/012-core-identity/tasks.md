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

- Caminhos relativos a `ai-core/packages/core/`: código em `src/ai_core/identity/` (abreviado `identity/`), testes em
  `tests/identity/{unit,contract,integration}/` (abreviado `tests/identity/`)
- Comandos a partir de `ai-core/`, com `XDG_DATA_HOME=$HOME/.local/share`; Postgres por `AI_CORE_TEST_POSTGRES_DSN`

---

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Criar o esqueleto: `src/ai_core/identity/__init__.py` (docstring: spec 012 — a plataforma é o provedor OIDC,
  ADR-030; seams em `api.py`; protocolo e páginas em `adapters/http.py`), `identity/domain/__init__.py`,
  `identity/adapters/__init__.py`, `identity/adapters/sql/`, `identity/adapters/assets/` e
  `tests/identity/{unit,contract,integration}/`
- [ ] T002 Acrescentar `argon2-cffi>=25.1,<26` a `dependencies` de `pyproject.toml` (pacote core), com comentário citando a
  spec 012 e R2 (wheels `abi3` aarch64; confinado a `adapters/`); `uv sync`; conferir no `uv.lock` o
  `argon2-cffi-bindings` com wheel `cp310-abi3` para aarch64
- [ ] T003 [P] Em `ai-core/pyproject.toml`: `authlib>=1.8,<2` no grupo de desenvolvimento (só testes, R1) e
  `packages/core/tests/identity` em `[tool.pytest.ini_options] pythonpath`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: superfície pública, portas, adapters em memória e reais, kit de teste, chaves de assinatura e fronteiras

**⚠️ CRITICAL**: nenhuma user story começa antes de T004–T020

- [ ] T004 Implementar `identity/api.py` conforme [data-model.md](data-model.md) e
  [contracts/identity-api.md](contracts/identity-api.md), só com a stdlib:
  - vocabulário `USERNAME_PATTERN = r"^[a-z0-9][a-z0-9._-]{0,63}$"` (o mesmo para grupo), `PASSWORD_MIN = 12`,
    `PASSWORD_MAX = 128`, `NAME_MAX = 120`, `ClientType = Literal["confidential", "public"]`,
    `AuthMethod = Literal["pwd", "google"]`, `SettingSource = Literal["installation", "runtime", "default"]`;
  - value objects congelados (`frozen=True, slots=True, kw_only=True`) `Account`, `AccountDraft`, `AccountPatch`,
    `IssuedPassword`, `Group`, `LoginSettingsView`, `Page[T]`, validados na construção;
  - erros `IdentityError` → `AccountNotFound`, `GroupNotFound`, `Conflict(field)`, `InvalidField(field, reason)`,
    `ProtectedGroup(reason)`, `GoogleNotConfigured`, `InstallationDefined(field)`;
  - os `Protocol` `AccountAdmin`, `LoginSettings` e `PublicKeySet` com as assinaturas do contrato
- [ ] T005 Implementar `identity/ports.py` com as 13 portas de [contracts/ports.md](contracts/ports.md) e os registros
  internos `AccountRecord`, `PendingAuthorization`, `AuthorizationCode`, `Session`, `RefreshToken`, `SigningKey`,
  `IdentitySettings`, `Client`, `GoogleIdentity`, `BootstrapAdmin` ([data-model.md](data-model.md))
- [ ] T006 [P] Testes de `tests/identity/unit/test_names.py` (Hypothesis): usuário e grupo no padrão, sem `@`; e-mail
  normalizado `strip().lower()`; senha de 12 a 128 caracteres contados como código Unicode; identificador de login decide
  usuário × e-mail pela presença de `@`
- [ ] T007 [P] Implementar `identity/domain/names.py` para fazer T006 passar
- [ ] T008 [P] Testes de `tests/identity/unit/test_settings.py` e implementação de `identity/domain/settings.py`:
  precedência instalação > runtime > padrão com a origem por campo (ADR-033); padrão do Google = ligado se configurado
- [ ] T009 Implementar `identity/adapters/memory.py`: adapters em memória de todas as portas — `PasswordHasher` rápido e
  determinístico, `TokenGenerator` sequencial, `UpstreamOidc` simulado e programável (`GoogleIdentity` por código),
  `Clock` fixo e ajustável
- [ ] T010 Criar `tests/identity/identity_testkit.py` e `tests/identity/conftest.py`: fábricas de conta e cliente
  (`open-webui` confidencial, `console` público), relógio fixo, Google simulado, `IdentityService` montado com memória,
  fixture `postgres_pool` (pula sem `AI_CORE_TEST_POSTGRES_DSN`) e um app FastAPI de teste com `router(service, settings)`
- [ ] T011 [P] Suítes de conformidade parametrizadas (memória × Postgres) em `tests/identity/contract/`:
  `test_account_store.py` (unicidade de nome e e-mail sem diferenciar maiúsculas, inclusive com conta desativada;
  `replace` com versão desatualizada → `Conflict`; cascata ao apagar grupo), `test_grant_store.py` (código de uso único
  sob duas trocas concorrentes; rotação atômica; reuso revoga a família; `revoke_for_account`, `revoke_except`; `purge`),
  `test_signing_key_store.py`, `test_settings_store.py` (versão)
- [ ] T012 Implementar `identity/adapters/postgres_schema.py` (`migrate(pool, *, now)`, schema `identity`, trava
  consultiva, `schema_version` — padrão de `assistants/adapters/postgres_schema.py`) e `adapters/sql/001_accounts.sql`,
  `002_grants.sql`, `003_signing_keys.sql`, `004_settings.sql` com as tabelas de [data-model.md](data-model.md)
- [ ] T013 Implementar `identity/adapters/postgres.py` (`PostgresAccountStore`, `PostgresGrantStore`,
  `PostgresSigningKeyStore`, `PostgresIdentitySettingsStore`) para fazer T011 passar contra o Postgres; `consume` do código
  e `rotate` da renovação com `UPDATE … WHERE … RETURNING` atômico
- [ ] T014 [P] `tests/identity/contract/test_cipher.py` e `identity/adapters/cipher.py`: AES-GCM com subchave
  HKDF-SHA256 (`info="ai-core/identity/v1"`) da chave mestra de 32 bytes, nonce de 12 bytes por gravação; ida e volta;
  chave errada falha sem vazar o texto
- [ ] T015 [P] `tests/identity/contract/test_signer.py` e `identity/adapters/signing.py`: geração RSA-2048 (`kid` = 16
  hex), assinatura RS256 com `kid` no cabeçalho, verificação contra um JWKS; recusa `alg=none` e HS256
- [ ] T016 [P] `tests/identity/contract/test_password_hasher.py` e `identity/adapters/passwords.py`: argon2id (t=3,
  m=64 MiB, p=4), `needs_rehash`, `dummy_verify` com custo igual ao real; o adapter de memória passa na mesma suíte
- [ ] T017 [P] `tests/identity/contract/test_client_source.py` e `identity/adapters/clients_yaml.py` +
  `identity/domain/clients.py`: o formato de [contracts/identity-yaml.md](contracts/identity-yaml.md) — `secret`
  obrigatório em `confidential` e proibido em `public`, referência `[a-z0-9_]{1,64}`, URIs absolutas, `http` só para
  `localhost`, `127.0.0.1` ou nome sem ponto; erro nomeia o campo; cliente confidencial cuja variável de segredo falta
  fica indisponível (o boot segue, ADR-020): o `token` responde `invalid_client` e o log nomeia a referência, nunca um
  valor
- [ ] T018 [P] `tests/identity/contract/test_identity_secrets.py` e `identity/adapters/secrets_env.py`:
  `AI_CORE_IDENTITY_SECRET_<REF>`, `AI_CORE_GOOGLE_CLIENT_ID|CLIENT_SECRET|HOSTED_DOMAIN`, `AI_CORE_GOOGLE_LOGIN`,
  `AI_CORE_BOOTSTRAP_ADMIN_USERNAME|EMAIL|PASSWORD_FILE`; nenhum nome arbitrário (ADR-020)
- [ ] T019 `tests/identity/unit/test_keys.py` e `identity/domain/keys.py` (ciclo `active` → `retiring` → `retired`;
  `retiring` sai depois do TTL do acesso + 60 s); em `identity/service.py`, o esqueleto do `IdentityService` (construtor
  com as portas e um `IdentityConfig` — `public_url`, `admin_group`, `display_name`, `logo`, `cookie_secure`,
  `trusted_proxies`, `access_ttl=600`, `session_ttl=30 dias`) e `start()`, que garante uma chave `active` — a privada
  gerada pelo `TokenSigner` e **selada pelo `SecretCipher` antes de chegar ao `SigningKeyStore`** (FR-016, ADR-033) — e
  carrega o JWKS em memória
- [ ] T020 Contratos de import-linter em `ai-core/pyproject.toml` (os 7 de "Fronteiras verificadas" do
  [plan.md](plan.md)); a 012 nos contratos existentes de "framework HTTP só nos adapters" e "nenhum módulo importa a
  composition root"; `uv run lint-imports` verde

**Checkpoint**: portas e adapters prontos e conformes; nenhum endpoint ainda

---

## Phase 3: User Story 1 — Pessoa entra no chat com usuário e senha (Priority: P1) 🎯 MVP

**Goal**: um cliente confidencial faz o fluxo de código e recebe tokens com `preferred_username` e `groups`

**Independent Test**: com duas contas em grupos diferentes, o RP authlib faz login por senha e os tokens trazem os
grupos certos; usuário inexistente, senha errada e conta desativada recebem a mesma resposta

### Tests for User Story 1

- [ ] T021 [P] [US1] `tests/identity/unit/test_authorize.py`: cliente desconhecido e `redirect_uri` divergente →
  "não redirecionar"; `response_type` diferente de `code`; `scope` sem `openid`; `nonce` obrigatório; `prompt=none` sem
  sessão → `login_required`
- [ ] T022 [P] [US1] `tests/identity/unit/test_tokens.py`: claims de acesso (`iss`, `aud` do cliente, `sub`,
  `preferred_username`, `groups`, `azp`, `scope`, `iat`, `exp` = `iat` + 600) e de identidade (`nonce`, `auth_time`,
  `amr`, `email`, `email_verified`, `name`, `aud` = `client_id`)
- [ ] T023 [P] [US1] `tests/identity/integration/test_protocol.py` (parte 1): descoberta com backchannel dinâmico
  (`issuer` público; `token_endpoint` pela base do pedido; `X-Forwarded-*` só de proxy confiável); login por usuário e por
  e-mail; código → tokens por `client_secret_basic` e `client_secret_post`; token de identidade validado pelo authlib
  (iss, aud, nonce, kid); `userinfo`; código reusado → `invalid_grant`
- [ ] T024 [P] [US1] `tests/identity/integration/test_login_uniform.py`: inexistente, senha errada e desativada →
  mesmo status (`401`), mesmo corpo e tempos na mesma ordem de grandeza (SC-005); formulário sem `csrf` ou com `csrf`
  errado → recusado; pedido vencido (10 min) → "O link de login expirou", sem redirecionar; cookie de sessão
  `__Host-aic_session` com `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/`, sem `Domain` e só `Max-Age` (e `aic_session`
  sem `Secure` com `AI_CORE_COOKIE_SECURE=false`)
- [ ] T025 [P] [US1] `tests/identity/integration/test_pages.py`: a página de login tem `lang="pt-BR"`, rótulos ligados,
  `autocomplete` certos, o nome da instalação (`AI_CORE_DISPLAY_NAME`) e, sem ele, "Agentic"; o logotipo em
  `/oauth2/assets/logo` quando `AI_CORE_LOGO_FILE` existe (e `404` sem ele); cabeçalhos CSP com `form-action` contendo
  `'self'` e as origens dos `redirect_uris` dos clientes, `nosniff`, `no-referrer`, `no-store`; nenhum `<script>`;
  substituições escapadas (nome com `<`)

### Implementation for User Story 1

- [ ] T026 [P] [US1] `identity/domain/authorize.py` e `identity/domain/tokens.py` para T021–T022
- [ ] T027 [US1] Em `identity/service.py`: `discovery(base)`, `begin_authorization(params)` (grava `PendingAuthorization`
  com CSRF), `login(request_id, identifier, password, csrf, origin)` (hash fictício para inexistente; conta desativada
  igual a senha errada; re-hash quando preciso; cria sessão de 30 dias e código de 60 s), `exchange_code(...)`,
  `userinfo(token)`; `last_login_at` atualizado
- [ ] T028 [P] [US1] `identity/adapters/pages.py` (função de montagem com escape por padrão; páginas de login, erro e
  "você saiu"; nome e logotipo da instalação — FR-023) e `identity/adapters/assets/identity.css` com os tokens do desenho
  aprovado (página "Login e conta" do Penpot): Mona Sans, raio 6/8, temas claro e escuro por `prefers-color-scheme`,
  celular primeiro, foco visível
- [ ] T029 [US1] `identity/adapters/http.py`: `router(service, settings)` com `GET /.well-known/openid-configuration`,
  `GET /oauth2/authorize`, `POST /oauth2/login`, `POST /oauth2/token`, `GET /oauth2/userinfo`, `GET /oauth2/jwks`,
  `GET /oauth2/assets/identity.<hash>.css`, `GET /oauth2/assets/logo`; CSP com `form-action` montada no boot a partir
  das origens dos `redirect_uris`; formulário `x-www-form-urlencoded` lido do corpo com teto de 16 KiB (outro
  tipo → 415, R4); cookie de sessão (R5); cabeçalhos de [contracts/oidc.md](contracts/oidc.md); erros RFC 6749
- [ ] T030 [US1] Rodar T021–T025 até verde

**Checkpoint**: o Open WebUI (simulado pelo authlib) entra com senha e recebe os grupos

---

## Phase 4: User Story 2 — Admin inicial, contas, grupos e "Minha conta" (Priority: P1)

**Goal**: o operador cria o primeiro admin; admins gerem contas e grupos; senha temporária obrigatória; a pessoa troca a
própria senha

**Independent Test**: sem contas, o admin inicial é criado; ele cadastra outra pessoa, que entra, troca a senha
temporária e recebe o grupo

### Tests for User Story 2

- [ ] T031 [P] [US2] `tests/identity/contract/test_account_admin.py`: cadastro (nome e e-mail livres entre todas as
  contas, inclusive desativadas — US2 cen. 4), senha temporária só em `create`/`reset_password`, `google_only` sem senha,
  `update` com versão desatualizada → `Conflict("version")`, troca de e-mail mantém o vínculo Google, grupo de admin
  protegido (apagar; tirar ou desativar o último admin ativo → `ProtectedGroup`), `set_members`, `delete_group` remove as
  associações, `updated_by` gravado
- [ ] T032 [P] [US2] `tests/identity/integration/test_bootstrap.py`: variáveis de admin inicial com zero contas → admin
  no grupo de administração com a senha do arquivo; com contas → ignoradas, com aviso no log; arquivo de senha ausente →
  erro que nomeia a variável
- [ ] T033 [P] [US2] `tests/identity/integration/test_password_pages.py`: login com senha temporária leva à troca antes
  de qualquer código; erros junto ao campo (tamanho, confirmação, igual à temporária); "Minha conta" exige sessão, troca a
  senha com a atual, encerra as outras sessões e mantém a atual; senha atual errada conta para o bloqueio; conta só
  Google não mostra o formulário
- [ ] T034 [P] [US2] `tests/identity/integration/test_cli.py`: `users create` com `--password-stdin` e sem (entrada sem
  eco simulada), `users list`, `disable|enable`, `password` (mostra a temporária uma vez), `groups --set`

### Implementation for User Story 2

- [ ] T035 [P] [US2] `identity/domain/accounts.py`: regras de cadastro e de proteção do grupo de administração; geração da
  senha temporária no `TokenGenerator` (20 caracteres de alfabeto sem ambíguos, grupos de 4 com hífen — R10), com a
  conformidade da porta em `tests/identity/contract/test_token_generator.py` (32 bytes de token, UUID, formato da senha;
  o sequencial de memória na mesma suíte)
- [ ] T036 [US2] Em `identity/service.py`, o seam `AccountAdmin` completo e `bootstrap_admin()` (só com zero contas);
  `reset_password` e `disable` revogam as sessões da conta
- [ ] T037 [US2] Em `identity/adapters/http.py` e `pages.py`: `POST /oauth2/password` (troca obrigatória),
  `GET|POST /oauth2/account` ("Minha conta", CSRF da sessão), conforme [contracts/pages.md](contracts/pages.md)
- [ ] T038 [US2] `identity/adapters/cli.py`: `users_create_command`, `users_list_command`, `users_disable_command`,
  `users_enable_command`, `users_password_command`, `users_groups_command` (sem parser próprio; a 011 os registra, como
  em `assistants/adapters/cli.py`); senha por `--password-stdin` ou `getpass`
- [ ] T039 [US2] Rodar T031–T034 até verde

**Checkpoint**: a instalação nova tem quem administra; as pessoas trocam a própria senha

---

## Phase 5: User Story 3 — A console entra com audiência própria (Priority: P1)

**Goal**: cliente público com PKCE S256 e audiência `ai-core-admin`; logout encerra a sessão

**Independent Test**: sem PKCE é recusado; com PKCE, o token da console tem `aud = ai-core-admin` e o do Open WebUI,
`ai-core`; o logout revoga a renovação da sessão

### Tests for User Story 3

- [ ] T040 [P] [US3] `tests/identity/unit/test_pkce.py` e `tests/identity/unit/test_refresh.py`: S256 (vetores da RFC
  7636); cliente público sem desafio → `invalid_request`; rotação a cada uso para público; reuso de token rotacionado
  revoga a família; confidencial não rotaciona
- [ ] T041 [P] [US3] `tests/identity/integration/test_protocol.py` (parte 2): fluxo público com PKCE pelo authlib;
  audiências por cliente; renovação com rotação e com reuso; `POST /oauth2/revoke`; `GET /oauth2/logout` com
  `id_token_hint` e `post_logout_redirect_uri` exato (inválido → página "Você saiu", sem redirecionar)

### Implementation for User Story 3

- [ ] T042 [P] [US3] `identity/domain/pkce.py` e `identity/domain/refresh.py` para T040
- [ ] T043 [US3] Em `identity/service.py` e `adapters/http.py`: PKCE no `authorize`/`token`, `refresh_token` com
  rotação e detecção de reuso, `revoke`, `logout`
- [ ] T044 [US3] Rodar T040–T041 até verde

**Checkpoint**: a console pode entrar sem segredo no navegador e sem aceitar token do chat

---

## Phase 6: User Story 4 — Login com Google só para cadastrados (Priority: P2)

**Goal**: o Google entra só para contas ativas com o e-mail verificado; liga e desliga em runtime

**Independent Test**: com o Google simulado, só o e-mail cadastrado e verificado recebe token; nenhuma conta é criada

### Tests for User Story 4

- [ ] T045 [P] [US4] `tests/identity/unit/test_google.py`: `email_verified` falso → recusa; domínio fora do aceito →
  recusa; e-mail sem conta ativa → "conta Google não cadastrada"; primeiro sucesso vincula o `sub`; `sub` diferente do
  vinculado → recusa
- [ ] T046 [P] [US4] `tests/identity/contract/test_login_settings.py`: precedência; `AI_CORE_GOOGLE_LOGIN` definido →
  `InstallationDefined`; sem cliente Google → `GoogleNotConfigured`; versão
- [ ] T047 [P] [US4] `tests/identity/contract/test_upstream_oidc.py`: o adapter real (`adapters/google.py`) contra um
  servidor OIDC falso local (descoberta, troca de código, `id_token` assinado por chave de teste) e o simulado de memória
  na mesma suíte; `iss`, `aud`, `nonce`, PKCE
- [ ] T048 [P] [US4] `tests/identity/integration/test_google.py`: botão só com o Google ligado e configurado;
  `/oauth2/google/start` recusado sem configuração; fluxo completo com o simulado; SC-003: nenhuma conta criada em nenhum
  cenário

### Implementation for User Story 4

- [ ] T049 [P] [US4] `identity/domain/google.py` para T045
- [ ] T050 [P] [US4] `identity/adapters/google.py`: `UpstreamOidc` sobre `httpx` e `pyjwt` (R9)
- [ ] T051 [US4] Em `identity/service.py`: o seam `LoginSettings` e `google_start`/`google_callback`; em
  `adapters/http.py`: `GET /oauth2/google/start` e `GET /oauth2/google/callback`; em `pages.py`: o botão e as mensagens
  de recusa de [contracts/pages.md](contracts/pages.md)
- [ ] T052 [US4] Rodar T045–T048 até verde

---

## Phase 7: User Story 5 — Tentativas repetidas são contidas (Priority: P2)

**Goal**: 5 falhas em 15 min bloqueiam por 15 min, por usuário e por origem, sem revelar existência

**Independent Test**: depois de 5 falhas, a sexta com a senha certa é recusada com a mensagem genérica; igual para
usuário inexistente

### Tests for User Story 5

- [ ] T053 [P] [US5] `tests/identity/unit/test_attempts.py`: janela deslizante com relógio fixo; chaves por usuário
  normalizado e por origem; liberação depois de 15 min; e a conformidade da porta `LoginAttempts` em
  `tests/identity/contract/test_login_attempts.py` (`blocked`, `fail`, `reset`) contra o adapter de memória — o único,
  processo único (R11)
- [ ] T054 [P] [US5] Casos de bloqueio em `tests/identity/integration/test_login_uniform.py`: sexta tentativa recusada
  com a senha certa; inexistente com as mesmas respostas; `X-Forwarded-For` ignorado sem proxy confiável e usado com ele

### Implementation for User Story 5

- [ ] T055 [US5] `identity/domain/attempts.py` e o uso da porta `LoginAttempts` no `login` e na troca de senha de "Minha
  conta" em `identity/service.py`; origem pelo socket ou pelo `X-Forwarded-For` de `trusted_proxies` em
  `adapters/http.py`
- [ ] T056 [US5] Rodar T053–T054 até verde

---

## Phase 8: User Story 6 — Desativar alguém corta o acesso (Priority: P2)

**Goal**: conta desativada não entra, não renova e perde as sessões; reativada volta com os grupos atuais

**Independent Test**: com sessão aberta, desativar → a renovação seguinte é recusada e o login também

### Tests for User Story 6

- [ ] T057 [P] [US6] `tests/identity/integration/test_disable.py`: desativação revoga sessões e renovação; `userinfo`
  com token ainda válido → `401`; `authorize` com o cookie antigo mostra o login; reativação → login normal com grupos
  atuais; mudança de grupo vale no próximo token

### Implementation for User Story 6

- [ ] T058 [US6] Conferir conta ativa em `refresh_token`, `userinfo` e no uso da sessão em `identity/service.py`
- [ ] T059 [US6] Rodar T057 até verde

---

## Phase 9: User Story 7 — Chave de assinatura trocada sem derrubar ninguém (Priority: P3)

**Goal**: rotação normal mantém tokens vigentes; rotação forçada encerra todas as sessões

**Independent Test**: token emitido antes da rotação continua válido; novo token sai com outro `kid`

### Tests for User Story 7

- [ ] T060 [P] [US7] `tests/identity/contract/test_public_key_set.py`: `jwks()` com `active` + `retiring`; rotação
  normal publica as duas; `retiring` sai depois do prazo; rotação forçada troca tudo e revoga as sessões (SC-007); o
  `SigningKeyStore` nunca recebe a chave privada em claro (só o selo do `SecretCipher`)

### Implementation for User Story 7

- [ ] T061 [US7] `rotate_keys(force)` e `PublicKeySet.jwks()` em `identity/service.py`; `identity_keys_rotate_command`
  em `identity/adapters/cli.py`
- [ ] T062 [US7] Rodar T060 até verde

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T063 [P] `tests/identity/integration/test_no_secrets_in_logs.py`: captura o logger `identity` ao longo de todos os
  fluxos e procura senhas, códigos, tokens, cookies, segredo de cliente e chave privada (FR-020); eventos de segurança
  presentes com usuário e motivo (FR-021, R15)
- [ ] T064 Eventos de segurança estruturados no logger `identity` em `identity/service.py` (`login.ok`, `login.failed`,
  `login.locked`, `google.refused`, `account.*`, `keys.rotated`)
- [ ] T065 [P] `purge(now)` no `IdentityService` (pedidos, códigos, sessões e renovação vencidos; chaves `retiring`
  vencidas) com teste em `tests/identity/contract/test_grant_store.py`; o agendamento é da 011
- [ ] T066 [P] Atualizar `specs/README.md` (status da 012) e `CLAUDE.md` (o módulo de identidade existe; o encaixe vem
  nas passadas da 003, 008, 011 e 002)
- [ ] T067 Rodar o [quickstart.md](quickstart.md) inteiro: `uv run pytest`, `mypy`, `ruff check packages`,
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

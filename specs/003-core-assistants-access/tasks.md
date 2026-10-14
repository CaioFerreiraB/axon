---

description: "Task list for 003 — Assistants, identidade e autorização, Fases 2 e 3"
---

# Tasks: Assistants, identidade e autorização

**Input**: Design documents from `/specs/003-core-assistants-access/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos. SC-001, SC-002 e SC-005 são enunciados adversariais que só se demonstram por teste, e a
governança exige a suíte de conformidade de cada seam exposto e de cada porta secundária (memória × adapter real).

**Organization**: **US1–US7** (Fase 2 do roadmap), mais a validação de referências (FR-011) que a etapa de boot e o
`assistants validate` da 011 consomem ([research.md](research.md) R14) — para Assistants de sistema na US1 e de usuário
na US6. **Não** entram: nada em `ai_core/http/` nem em `ai_core/bootstrap/` (a troca na plataforma é das passadas da
008 e da 011, R2); registro dos subcomandos na raiz `ai-core` (011 US4); perfis e pool Postgres da composition root
(011 US2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1–US7)
- Todo caminho é relativo à raiz do repositório

## Path Conventions

- Código: `ai-core/packages/core/src/ai_core/assistants/` (abreviado `assistants/` abaixo)
- Testes: `ai-core/packages/core/tests/assistants/{unit,contract,integration}/` (abreviado `tests/assistants/`)
- Comandos a partir de `ai-core/`, com `XDG_DATA_HOME=$HOME/.local/share`

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Criar o esqueleto do módulo: `ai-core/packages/core/src/ai_core/assistants/__init__.py` (docstring: spec
  003, a fronteira de isolamento; seams em `api.py`; autenticação mora aqui, não em `ai_core/auth/`, ADR-012),
  `assistants/domain/__init__.py`, `assistants/adapters/__init__.py`, `assistants/adapters/sql/` e os diretórios
  `ai-core/packages/core/tests/assistants/{unit,contract,integration}/`
- [X] T002 Acrescentar a `dependencies` de `ai-core/packages/core/pyproject.toml`, cada uma com comentário citando a
  spec 003 e a pesquisa: `pyjwt[crypto]>=2.10,<3` (R6), `httpx>=0.28,<1` (R6, R17), `psycopg[binary]>=3.2,<4` e
  `psycopg-pool>=3.2,<4` (R8, ADR-015); rodar `XDG_DATA_HOME=$HOME/.local/share uv sync` e conferir que `uv.lock` foi
  atualizado
- [X] T003 [P] Em `ai-core/pyproject.toml`, acrescentar `packages/core/tests/assistants` a
  `[tool.pytest.ini_options] pythonpath` e `ai_core` já coberto em `known-first-party` (conferir)
- [X] T004 [P] Em `.github/workflows/core.yml`, job `test`: acrescentar `services: postgres` (imagem `postgres:17`,
  `POSTGRES_PASSWORD`, porta 5432, health check `pg_isready`) e a variável `AI_CORE_TEST_POSTGRES_DSN` apontando para
  ele, com comentário citando o princípio XIII e o ADR-015 (a conformidade contra o adapter real roda em todo PR)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: a superfície pública, as portas, os adapters em memória, o kit de teste e as fronteiras de import

**⚠️ CRITICAL**: nenhuma user story começa antes de T005–T009

- [X] T005 Implementar `assistants/api.py` conforme [data-model.md](data-model.md) e
  [contracts/assistants-api.md](contracts/assistants-api.md), importando **só** a stdlib e os `api.py` de 002
  (`Composition`), 005 (`FLOW_CHAT`) e 006 (`ModelPolicy`, `ModelRef`, `ModelRole` — só value objects, [ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md)):
  - vocabulário: `Surface`, `Scheme`, `SCHEME_OF_SURFACE` (`public → oidc`, `private → api_key`), `USER_PREFIX = "~"`,
    `DEFAULT_RPM = 60`, `WIDENING_FIELDS` = `packs`, `mcp`, `mcp_servers`, `collections`, `provider`, `flow`,
    `limits`, `allowed_tools`, `write_tools`, `tools`, `functions`, `tool_choice`, `function_call`;
  - value objects congelados (`frozen=True, slots=True, kw_only=True`): `Principal` (`subject` com prefixo `user:` ou
    `svc:`, `scheme`, `groups: frozenset[str]`), `Limits` (`rpm` ≥ 1; `max_iterations` e `max_context_tokens`
    `int | None`, ≥ 1 quando presentes), `ExecutionGrant` (campos da tabela do data-model + propriedade `packs` =
    `composition.packs`), `AssistantSummary`, `UserAssistantDraft` (`description` "até 500 caracteres"; `name` na
    gramática `[a-z0-9][a-z0-9._-]{0,63}`, aceito com ou sem `~`), `UserAssistant`, `AssistantStatus`,
    `ValidationReport` (`ok`), `ApiKeyInfo` (`key_id` de 16 caracteres hexadecimais), `IssuedApiKey`;
    cada `__post_init__` rejeita valor fora da regra com `ValueError` que nomeia o campo;
  - os quatro `Protocol`: `Authenticator`, `GrantResolver`, `AssistantDirectory`, `ApiKeyAdmin`, com as assinaturas
    exatas do contrato;
  - erros: `NotFound(LookupError)`, `AssistantNotFound(NotFound)`, `AssistantUnavailable` (`reasons`),
    `RequestRejected(ValueError)` (`field`), `PolicyViolation(RequestRejected)`,
    `NoApplicablePolicy(RequestRejected)`, `Conflict`, `RateLimited` (`retry_after: float`), `AssistantsConfigError`
- [X] T006 Implementar os tipos internos e as portas: em `assistants/domain/definitions.py`, só os tipos
  `AccessRule`, `AssistantDefinition` (com `problems: tuple[str, ...]`), `UserAssistantPolicy` e `AssistantsConfig`
  (`assistants`, `policies`, `admin_group`); em `assistants/domain/keys.py`, o tipo `ApiKeyRecord` (`ApiKeyInfo` +
  `key_hash: bytes`); em `assistants/domain/rate.py`, o tipo `RateDecision` (`allowed`, `retry_after: timedelta | None`);
  em `assistants/domain/access.py`, o tipo `OidcClaims` (`subject_claim="sub"`, `groups_claim="groups"`,
  `leeway=timedelta(seconds=60)`); e `assistants/ports.py` com as nove portas e o tipo `StoredUserAssistant`, nas
  assinaturas exatas de [contracts/ports.md](contracts/ports.md). Nenhum arquivo importa biblioteca de infraestrutura
- [X] T007 [P] Implementar os adapters em memória e de teste em `assistants/adapters/memory.py`:
  `InMemoryAssistantConfigSource`, `InMemoryUserAssistantStore`, `InMemoryApiKeyStore` (com `seed(record)` para as
  suítes e para a 011), `StaticOidcVerifier` (token → claims), `DisabledOidcVerifier` (sempre `None`),
  `SequentialTokenGenerator` (determinístico), `InMemoryMcpDirectory` (globais + por dono) e
  `InMemoryCollectionCatalog`; e os vazios da fase em `assistants/adapters/catalogs.py` (`EmptyMcpDirectory`,
  `EmptyCollectionCatalog`)
- [X] T008 [P] Criar o kit de teste: `tests/assistants/assistants_testkit.py` com construtores de configuração
  (mapeamentos de Assistant e de política válidos por default, sobrescrevíveis por campo), Principals prontos
  (`user:ana` OIDC, `user:caio` chave, membro de `group:chefia`), `FakePackRegistry` que cumpre o `PackRegistry` da
  002 (entradas com status e `preferred_flow`, `compose` que levanta `CompositionError` para pack indisponível),
  `MutableClock` com `advance(...)`, chaves RSA e EC geradas com `cryptography`, emissão de JWT assinado e um
  `httpx.MockTransport` que serve documento de descoberta e JWKS; e `tests/assistants/conftest.py` com a fixture
  `pg_pool` — `AsyncConnectionPool` a partir de `AI_CORE_TEST_POSTGRES_DSN`, `DROP SCHEMA assistants CASCADE` antes
  de cada teste, `pytest.skip` com motivo explícito quando a variável não existe — e a fixture parametrizada que
  entrega cada porta de armazenamento nas versões memória e Postgres
- [X] T009 Acrescentar a `ai-core/pyproject.toml` os contratos de import-linter de [plan.md](plan.md) ("Fronteiras
  verificadas"): `api.py` da 003 não importa o resto do módulo; `domain/` não importa portas, service nem adapters;
  `service.py` não importa adapters; o núcleo (`api`, `domain`, `ports`, `service`) não importa `yaml`, `jwt`,
  `cryptography`, `httpx`, `psycopg`, `psycopg_pool`; a 003 só vê internals de outros módulos pelo `api.py` (e nada de
  `ai_core.http` nem `ai_core.bootstrap`); nenhum outro módulo importa `assistants.domain`, `.ports`, `.service` ou
  `.adapters`; o Model Router (`ai_core.llm`) não importa `ai_core.assistants` (ADR-016). Acrescentar `ai_core.assistants` à origem dos contratos existentes "o framework HTTP só existe nos
  adapters da API", "o framework de grafo só existe no adapter do motor", "nenhum módulo do core importa a API" e
  "nenhum módulo importa a composition root". Rodar `uv run lint-imports` até tudo aparecer como `KEPT`

**Checkpoint**: superfície pública, portas e adapters em memória prontos — as user stories podem começar

---

## Phase 3: User Story 1 - Operador define Assistants de sistema (Priority: P1) 🎯 MVP

**Goal**: o `assistants.yaml` vira definições; cada Assistant resolve num grant com exatamente o que declara; o
relatório de validação diz, por Assistant, o que está disponível e por quê.

**Independent Test**: `uv run pytest packages/core/tests/assistants -k us1` — dois Assistants (um público com um pack,
outro privado com pack + MCP) resolvem para grants diferentes e completos.

### Tests for User Story 1 ⚠️

- [X] T010 [P] [US1] `tests/assistants/unit/test_assistants_yaml.py`, testes com `us1` no nome: o exemplo completo de
  [contracts/assistants-yaml.md](contracts/assistants-yaml.md) carrega sem problemas; cada erro de arquivo (YAML
  inválido, raiz que não é mapeamento, chave de topo desconhecida, política malformada) levanta
  `AssistantsConfigError` nomeando o caminho do campo; cada erro de Assistant da lista do contrato vira `problems`
  **só** naquele Assistant — inclusive nome com `~`, `*` em privado, `write_tools` em público, `models.allow` vazia,
  modelo declarado fora da allowlist e composição sem flow —; o arquivo da Fase 1 (com `allow` na raiz e sem `auth`)
  produz a mensagem literal "`allow` saiu da raiz do Assistant: a allowlist de modelos vive em `models.allow`, e quem
  pode usar o Assistant, em `auth.allow`"
- [X] T011 [P] [US1] `tests/assistants/contract/test_config_source.py`: `YamlAssistantConfigSource` e
  `InMemoryAssistantConfigSource` produzem o mesmo `AssistantsConfig` para a mesma configuração; arquivo ausente é
  erro que nomeia o caminho; variável não definida é tratada pela composition root (fora desta suíte)
- [X] T012 [P] [US1] `tests/assistants/contract/test_grant_resolver.py`, testes com `us1` no nome (Principal
  autorizado por `*`): `mcp: []` → `mcp_aliases` vazio (cen. 1); dois packs → `composition.packs` na ordem declarada
  (cen. 2); um pack sem flow → `preferred_flow` do pack, ou `chat` se ele não preferir nenhum (cen. 3); dois packs sem
  flow → `AssistantUnavailable` (cen. 4); pack em erro → `AssistantUnavailable` com o motivo, e os demais resolvem;
  o grant tem os quatro atributos que o `ExecutionGrant` da 005 lê (`assistant`, `flow`, `composition`, `models`), com
  os tipos certos — a conformidade estática fica em T017, porque o mypy não cobre a pasta de testes
- [X] T013 [P] [US1] `tests/assistants/contract/test_validation.py`, testes com `us1` no nome: `validate()` devolve um
  `AssistantStatus` por Assistant de sistema, ordenado por nome; referência a flow inexistente, pack em erro, MCP fora
  de `McpDirectory.aliases(owner=None)` e coleção fora do catálogo aparecem como motivos que nomeiam campo e
  referência; com os catálogos vazios da fase, qualquer `mcp` ou `collections` não vazio deixa o Assistant
  indisponível (clarificação 3); `ok` é falso se algum estiver indisponível

### Implementation for User Story 1

- [X] T014 [US1] Implementar em `assistants/domain/definitions.py` a leitura pura de um mapeamento já carregado para
  `AssistantsConfig`, conforme [contracts/assistants-yaml.md](contracts/assistants-yaml.md): chaves de topo
  `assistants`, `user_assistants.policies`, `api_keys.admin_group`; para cada Assistant, as regras da tabela (nome
  `[a-z0-9][a-z0-9._-]{0,63}` e sem `~`; `visibility` ∈ {`public`, `private`}; `auth.schemes` não vazio ⊆ {`oidc`,
  `api_key`}; `auth.allow` não vazio com seletores `*`, `user:…`, `svc:…`, `group:…`; `description` "até 500
  caracteres"; `models.<papel>` em texto `provider/modelo` por `ModelRef.parse`; `models.allow` obrigatória e não
  vazia; `limits.rpm` default `DEFAULT_RPM`; inteiros ≥ 1) acumulando `problems` em vez de levantar; para políticas,
  as regras da tabela de política levantando `AssistantsConfigError`, porque política malformada para o boot
- [X] T015 [US1] Implementar `assistants/adapters/assistants_yaml.py`: `YamlAssistantConfigSource(path)` lê o arquivo
  com `yaml.safe_load`, traduz erro de leitura e de YAML em `AssistantsConfigError` com o caminho, e delega a
  interpretação a `domain/definitions.py`
- [X] T016 [US1] Implementar `assistants/domain/resolution.py` — decomposição do id (`<assistant>` e o resto, no
  primeiro `/`), regra do flow (declarado; um pack → `preferred_flow` ou `FLOW_CHAT`; dois ou mais sem flow →
  motivo) e montagem do `ExecutionGrant` a partir de `AssistantDefinition`, `Composition` e `Principal` — e
  `assistants/domain/validation.py` — referências de uma definição (flow ∈ nomes do motor, packs compostos, MCP ⊆
  aliases, coleções ⊆ catálogo, `problems` de carga) → `AssistantStatus`
- [X] T017 [US1] Implementar em `assistants/service.py` a classe `AssistantsService(config, packs, flows, users, mcp,
  collections, rate, clock)` — `flows` chega como `frozenset[str]`, injetado pela composition root — com
  `validate() -> ValidationReport` para os Assistants de sistema e `resolve(*, model, principal)` com os passos 1, 2
  (sistema), 5 e 8 de [research.md](research.md) R4: nome desconhecido → `AssistantNotFound("assistant '<nome>' não
  existe ou não é visível")`; indisponível → `AssistantUnavailable(reasons)`. Os passos 3, 4, 6 e 7 entram nas US3,
  US6, US4 e US7. Acrescentar ao mesmo arquivo uma função privada `_engine_grant(grant: ExecutionGrant) ->
  ai_core.graph.api.ExecutionGrant` que só devolve o argumento: é ela que faz o `uv run mypy` recusar qualquer
  divergência entre o grant desta spec e o `Protocol` da 005 (R1)
- [X] T018 [US1] Implementar em `assistants/adapters/cli.py` o comando `assistants validate` conforme
  [contracts/cli.md](contracts/cli.md): função `validate_command(service, out) -> int` que imprime uma linha por
  Assistant (nome, origem, estado, motivos), o resumo "N de M Assistants indisponível" e devolve 0 (todos
  disponíveis), 1 (algum indisponível); e `validate_config_error(error, err) -> int` que imprime a mensagem de
  `AssistantsConfigError` e devolve 2. Sem `argparse` aqui: o registro é da 011 (US4)

**Checkpoint**: Assistants de sistema carregam, validam e resolvem — sem ACL ainda

---

## Phase 4: User Story 2 - Principal autenticado por uma de duas superfícies (Priority: P1)

**Goal**: token OIDC na superfície pública e chave de API na privada produzem Principals; o resto é recusado; o
operador emite, lista e revoga chaves, e a revogação vale na requisição seguinte.

**Independent Test**: `uv run pytest packages/core/tests/assistants/contract/test_authenticator.py
packages/core/tests/assistants/contract/test_oidc_verifier.py packages/core/tests/assistants/contract/test_key_admin.py`.

### Tests for User Story 2 ⚠️

- [X] T019 [P] [US2] `tests/assistants/unit/test_keys.py` e `tests/assistants/unit/test_access.py` (parte de claims):
  formato `aic_<key_id>_<segredo>` com `key_id` de 16 caracteres hexadecimais; `parse` recusa prefixo errado, partes
  faltando e `key_id` fora do formato; hash é SHA-256 da chave inteira; comparação via `hmac.compare_digest`; claims →
  `Principal(subject="user:<sub>", scheme="oidc", groups=…)` com claims de subject e grupos configuráveis; grupos em
  lista de textos, texto único ou ausentes; `exp` no passado, `nbf` no futuro e `iat` no futuro além da tolerância de
  60 s → recusa, com `MutableClock`
- [X] T020 [P] [US2] `tests/assistants/contract/test_oidc_verifier.py`: `StaticOidcVerifier` e `JwksOidcVerifier`
  (chaves RSA e EC da suíte, JWKS pelo `httpx.MockTransport`, descoberta por `<emissor>/.well-known/openid-configuration`
  e por URL explícita): token bom → claims; assinatura trocada, `iss` errado, `aud` errado, `alg: none`, HS256 assinado
  com a chave pública e `kid` desconhecido → `None`; rotação de chave dispara nova busca do JWKS, e duas buscas não
  acontecem em menos que o intervalo mínimo; `DisabledOidcVerifier` recusa tudo
- [X] T021 [P] [US2] `tests/assistants/contract/test_api_key_store.py`, parametrizado memória × Postgres: `add` e `get`
  por `key_id`; o registro guarda hash, nunca a chave; `revoke` é idempotente e preserva o primeiro `revoked_at`;
  `revoke` de inexistente → `None`; `list` inclui revogadas. E `tests/assistants/contract/test_token_generator.py`:
  tamanho e alfabeto de `token_hex`/`token_urlsafe` em `SecretsTokenGenerator`; `SequentialTokenGenerator`
  determinístico
- [X] T022 [P] [US2] `tests/assistants/contract/test_authenticator.py`, com os dois verificadores OIDC e os dois
  armazenamentos de chave: a tabela do `Authenticator` em [contracts/assistants-api.md](contracts/assistants-api.md) —
  cen. 1 e 2; credencial ausente, malformada, expirada, adulterada ou revogada → `None` sem levantar (cen. 3 e 4); token
  na superfície privada e chave na pública → `None`; superfície desconhecida → `None`
- [X] T023 [P] [US2] `tests/assistants/contract/test_key_admin.py`: `issue` por ator do `admin_group` devolve
  `IssuedApiKey` cuja `plaintext` autentica; `keys()` não expõe chave nem hash; `revoke` faz a chamada seguinte ser
  recusada sem reconstruir o serviço (cen. 4); ator fora do grupo, ou `admin_group` ausente na configuração →
  `NotFound` nas três operações (cen. 5); `subject` sem `user:`/`svc:` → `RequestRejected(field="subject")`;
  `revoke` de `key_id` inexistente → `NotFound`

### Implementation for User Story 2

- [X] T024 [P] [US2] Implementar `assistants/domain/keys.py` (formato, `parse`, `hash_key`, `matches` com
  `hmac.compare_digest`) e, em `assistants/domain/access.py`, `principal_from_claims(claims, now, config)` com a
  conferência de `exp` (obrigatória), `nbf` e `iat` contra o relógio e a tolerância, e `is_admin(principal,
  admin_group)`
- [X] T025 [P] [US2] Implementar `assistants/adapters/tokens.py` (`SecretsTokenGenerator` sobre `secrets`) e
  `assistants/adapters/oidc.py`: `JwksOidcVerifier(issuer, audience, client, clock, jwks_url=None,
  algorithms=("RS256", "ES256"), cache_ttl=timedelta(minutes=10), min_refresh_interval=timedelta(seconds=60))` com
  PyJWT — `options` exigindo `exp` e `sub`, conferindo `iss` e `aud`, **sem** conferir `exp`/`nbf`/`iat` (são do
  domínio, R6) —, lista fechada de algoritmos, recusa de `none` e HMAC, JWKS por httpx com cache, nova busca em `kid`
  desconhecido limitada pelo intervalo mínimo, e qualquer falha de rede ou de decodificação devolvendo `None`
- [X] T026 [US2] Implementar a persistência de chaves: `assistants/adapters/sql/001_api_keys.sql` (schema
  `assistants`, tabela `schema_version`, tabela `api_keys` com `key_id text PRIMARY KEY`, `key_hash bytea NOT NULL`,
  `subject text NOT NULL`, `groups text[] NOT NULL DEFAULT '{}'`, `label text`, `created_at timestamptz NOT NULL`,
  `revoked_at timestamptz`); `assistants/adapters/postgres_schema.py` com `migrate(pool)` — aplica os arquivos de
  `sql/` em ordem numérica, cada um numa transação, sob `pg_advisory_xact_lock`, registrando a versão; falha nomeia o
  arquivo (ADR-015) —; e `assistants/adapters/api_keys_postgres.py` com `PostgresApiKeyStore(pool)`, timestamps sempre
  recebidos como parâmetro, nunca `now()` no SQL
- [X] T027 [US2] Implementar em `assistants/service.py` a classe `AccessService(keys, oidc, tokens, clock, claims,
  admin_group)`: `authenticate` (superfície pública → OIDC + `principal_from_claims`; privada → `parse` + `get` +
  `matches` + não revogada; qualquer outra coisa → `None`; nunca levanta) e o `ApiKeyAdmin` (`issue` gera `key_id`
  com `token_hex(8)` e segredo com `token_urlsafe(32)`, guarda só o hash e devolve `IssuedApiKey`; `keys`; `revoke`),
  com `NotFound` para ator fora do `admin_group`; mais os métodos `issue_as_operator`, `keys_as_operator` e
  `revoke_as_operator`, sem checagem de grupo, para a CLI
- [X] T028 [US2] Acrescentar a `assistants/adapters/cli.py` os comandos `keys create`, `keys list` e `keys revoke`
  conforme [contracts/cli.md](contracts/cli.md): a chave em claro sozinha na última linha da saída e em nenhum outro
  lugar; `keys revoke` de inexistente sai com 1; aviso quando o armazenamento não é persistente (parâmetro
  `persistent: bool` recebido de quem registra o comando)

**Checkpoint**: as duas superfícies autenticam; chaves são emitidas e revogadas sem restart

---

## Phase 5: User Story 3 - Autorização por Assistant sem vazar existência (Priority: P1)

**Goal**: a ACL de cada Assistant é aplicada antes de qualquer outra verificação, e quem não pode recebe exatamente o
mesmo que receberia por um Assistant inexistente.

**Independent Test**: `uv run pytest packages/core/tests/assistants/contract/test_adversarial.py -k not_found`.

### Tests for User Story 3 ⚠️

- [X] T029 [P] [US3] `tests/assistants/unit/test_access.py` (parte de ACL): `AccessRule.permits` — esquema fora de
  `schemes` recusa; `*` aceita qualquer Principal de esquema aceito; `user:x` e `svc:x` casam só o subject exato;
  `group:g` casa quem tem `g` em `groups`; lista sem nenhum casamento recusa
- [X] T030 [P] [US3] `tests/assistants/contract/test_adversarial.py`, testes com `not_found` no nome: privado que só
  aceita `api_key` e `user:caio`, pedido por Principal OIDC → `AssistantNotFound` (cen. 1); `user:caio` por chave →
  grant (cen. 2); público com `*` → grant para qualquer esquema aceito (cen. 3); inexistente e privado não autorizado
  levantam o **mesmo** tipo com a **mesma** mensagem; privado **indisponível** pedido por não autorizado também é
  `AssistantNotFound` (ACL antes de disponibilidade); a razão entre as medianas de 200 resoluções de cada caso fica
  abaixo de 10

### Implementation for User Story 3

- [X] T031 [US3] Implementar `AccessRule.permits(principal)` em `assistants/domain/access.py` e acrescentar o passo 3
  (ACL) a `AssistantsService.resolve` em `assistants/service.py`, **antes** da disponibilidade, levantando o mesmo
  `AssistantNotFound` do passo 2 pelo mesmo caminho de código

**Checkpoint**: 404, nunca 403 — SC-001 verificado

---

## Phase 6: User Story 4 - A requisição só restringe, nunca amplia (Priority: P1)

**Goal**: o único canal de restrição é o id de modelo; modelo fora da allowlist é recusado na resolução; nada da
requisição entra no grant além do modelo de geração permitido.

**Independent Test**: `uv run pytest packages/core/tests/assistants/contract/test_adversarial.py
packages/core/tests/assistants/contract/test_allowlist_parity.py`.

**Fora desta passada**: o cenário 2 (`packs` ou `mcp_servers` no corpo) e a parte "corpo da requisição" da SC-005
são verificados na passada da 008, que recusa `WIDENING_FIELDS` antes de pedir o grant ([research.md](research.md)
R13). Aqui, T034 garante o conteúdo da lista.

### Tests for User Story 4 ⚠️

- [X] T032 [P] [US4] `tests/assistants/unit/test_resolution.py`: gramática do id de [research.md](research.md) R5 —
  `geral` (sem restrição), `geral/qwen3:8b` (provider do `generation` declarado), `geral/ollama/qwen3:8b`,
  `generic/openrouter/qwen/qwen3-8b` (provider `openrouter`, modelo `qwen/qwen3-8b`), `geral/` (parte vazia →
  `RequestRejected(field="model")`); o modelo pedido substitui só `generation`, e os demais papéis ficam intactos
- [X] T033 [P] [US4] `tests/assistants/contract/test_allowlist_parity.py`: tabela de pares (referência, padrões) —
  curingas, tag do Ollama, modelos com `/`, maiúsculas — em que a regra de allowlist da resolução e
  `ai_core.llm.domain.policy.is_allowed` (importada só pela suíte) dão a mesma resposta, excluída a allowlist vazia,
  que a 003 nunca produz
- [X] T034 [P] [US4] Em `tests/assistants/contract/test_adversarial.py`: allowlist `ollama/*` e pedido `openai/...` →
  `RequestRejected(field="model")` (cen. 1, SC-005); pedido `ollama/<outro>` → grant com esse modelo em `generation`
  (cen. 3); com hypothesis, gerar Assistants (packs, MCPs, coleções, tools, papéis, allowlist) e ids de modelo
  arbitrários e conferir que todo grant produzido tem `mcp_aliases`, `collections`, `allowed_tools`, `write_tools` e
  `composition.packs` contidos no declarado e `models` só com papéis declarados, com `generation` casando a allowlist
  (SC-002); público nunca carrega `write_tools`; `WIDENING_FIELDS` contém exatamente a lista do data-model

### Implementation for User Story 4

- [X] T035 [US4] Implementar em `assistants/domain/resolution.py` a seleção de modelo (`ModelSelection`: parte com
  `/` → `ModelRef.parse`; sem `/` → provider do `generation` declarado) e a checagem de allowlist com `fnmatchcase`
  sobre `provider/modelo`; e acrescentar o passo 6 a `AssistantsService.resolve` em `assistants/service.py`, depois da
  disponibilidade e antes de montar o grant, levantando `RequestRejected(field="model", "modelo não permitido: <ref>;
  allowlist: <padrões>")`

**Checkpoint**: a requisição só restringe — SC-002 e SC-005 verificados na resolução

---

## Phase 7: User Story 5 - Descoberta filtrada (Priority: P2)

**Goal**: a listagem de um Principal é exatamente o conjunto de Assistants que ele resolve.

**Independent Test**: `uv run pytest packages/core/tests/assistants/contract/test_directory.py -k discover`.

### Tests for User Story 5 ⚠️

- [X] T036 [P] [US5] `tests/assistants/contract/test_directory.py`, testes com `discover` no nome: Principal público
  vê só os públicos que aceitam seu esquema (cen. 1); privado com `group:chefia` aparece para um membro do grupo e para
  mais ninguém (cen. 2); indisponível não aparece; para cada Principal do kit, o conjunto de nomes de `discover` é
  igual ao conjunto de nomes que `resolve` aceita sem `NotFound` nem `AssistantUnavailable`; cada
  `AssistantSummary` traz `generation` e `allow` declarados

### Implementation for User Story 5

- [X] T037 [US5] Implementar `AssistantsService.discover(principal)` em `assistants/service.py` reutilizando a mesma
  função de ACL e de disponibilidade da resolução (nenhuma regra duplicada), ordenado por nome

**Checkpoint**: descoberta e resolução não divergem

---

## Phase 8: User Story 6 - Usuário cria Assistants próprios (Priority: P2)

**Goal**: usuários criam, editam e removem Assistants `~nome`, dentro da política do seu grupo, visíveis e resolvíveis
só por eles, persistidos e disponíveis sem restart.

**Independent Test**: `uv run pytest packages/core/tests/assistants/contract/test_directory.py
packages/core/tests/assistants/contract/test_user_assistant_store.py`.

### Tests for User Story 6 ⚠️

- [X] T038 [P] [US6] `tests/assistants/unit/test_policies.py`: primeira política que casa, na ordem declarada; `*`
  casa todos; sem política aplicável → nenhuma; conformidade do rascunho — packs, flows e coleções fora da política,
  papel fora de `models.allow`, limite acima do teto e `write_tools` com a política em `false` → `PolicyViolation`
  nomeando o campo (`packs`, `flow`, `collections`, `models.<papel>`, `limits.rpm`, `write_tools`); limite ausente
  assume o teto; allowlist do Assistant de usuário = `models.allow` da política
- [X] T039 [P] [US6] `tests/assistants/contract/test_user_assistant_store.py`, parametrizado memória × Postgres:
  unicidade (dono, nome) com `insert` duplicado → `False`; mesmo nome com donos diferentes coexiste; `get` e `list`
  isolados por dono; `replace` e `delete` de inexistente → `False`; `all` lista todos; ida e volta do rascunho sem
  perda (inclusive `ModelRef` e limites ausentes). E `tests/assistants/contract/test_catalogs.py`: vazios devolvem
  conjunto vazio; `InMemoryMcpDirectory` separa globais de `owner=None` e os do dono
- [X] T040 [P] [US6] Em `tests/assistants/contract/test_directory.py`: `create` dentro da política → `UserAssistant`
  com nome `~meu-rag`, resolvível pelo dono na chamada seguinte (cen. 1, SC-003); outro usuário recebe
  `AssistantNotFound` para o mesmo `~meu-rag` e resolve o próprio `~meu-rag` (cen. 4); MCP de outro usuário →
  `PolicyViolation(field="mcp")` com a mesma mensagem de MCP inexistente (cen. 2); modelo `openai/...` ou `rpm: 50`
  fora da política → `PolicyViolation` nomeando o campo (cen. 5); sem política → `NoApplicablePolicy` (cen. 6); nome
  repetido do mesmo dono → `Conflict`; `get`/`update`/`delete` de nome alheio → `AssistantNotFound`; dono que sai do
  grupo (novo `Principal` sem o grupo) vê o Assistant em `mine` como indisponível, com motivo, e recebe
  `AssistantUnavailable` ao resolver; `discover` passa a incluir os `~` disponíveis do próprio Principal; com
  Postgres, um serviço novo sobre o mesmo pool continua resolvendo o Assistant (cen. 3)
- [X] T041 [P] [US6] Em `tests/assistants/contract/test_validation.py`: `validate()` inclui os Assistants de usuário
  de `UserAssistantStore.all()` com referências conferidas (pack, flow, MCP do dono, coleção) e o dono no relatório,
  sem conferir política (R14)

### Implementation for User Story 6

- [X] T042 [P] [US6] Implementar `assistants/domain/policies.py`: `applicable_policy(policies, principal)` (primeira
  que casa) e `conform(draft, policy, mcp_aliases, collections) -> AssistantDefinition` com as regras da tabela
  `UserAssistantDraft` de [data-model.md](data-model.md) — privado, os dois esquemas, `allow` só o dono, allowlist da
  política, limite ausente = teto —, levantando `PolicyViolation(field)`; a mensagem para MCP fora dos aliases é
  "MCP '<alias>' não existe ou não é visível", a mesma para inexistente e alheio
- [X] T043 [US6] Implementar a persistência: `assistants/adapters/sql/002_user_assistants.sql` (tabela
  `user_assistants` com `owner text NOT NULL`, `name text NOT NULL` sem o `~`, `definition jsonb NOT NULL` com
  `"format": 1`, `created_at`/`updated_at timestamptz NOT NULL`, `PRIMARY KEY (owner, name)`) e
  `assistants/adapters/assistants_postgres.py` com `PostgresUserAssistantStore(pool)` serializando o rascunho em JSON
  (papéis como `provider/modelo`) e reconstruindo-o na leitura
- [X] T044 [US6] Implementar em `assistants/service.py` o `AssistantDirectory` de `AssistantsService` (`mine`, `get`,
  `create`, `update`, `delete`; "a última escrita vence") e estender `resolve`: nome com `~` busca (dono =
  `principal.subject`, nome) — inexistente e alheio pelo mesmo caminho, `AssistantNotFound` —, passo 4 (política
  aplicável **agora** + `conform`; violação → `AssistantUnavailable` nomeando o campo) e disponibilidade; estender
  `discover` com os `~` disponíveis do próprio Principal e `validate()` com os Assistants de usuário

**Checkpoint**: Assistants de usuário existem, isolados por dono, sob a política do operador

---

## Phase 9: User Story 7 - Orçamento por Principal e Assistant (Priority: P2)

**Goal**: cada par (Principal, Assistant) tem no máximo `rpm` execuções concedidas em qualquer janela de 60 s; o
excedente recebe `RateLimited` com o tempo de espera; iterações e tokens viajam no grant.

**Independent Test**: `uv run pytest packages/core/tests/assistants -k rate`.

### Tests for User Story 7 ⚠️

- [X] T045 [P] [US7] `tests/assistants/unit/test_rate.py` e `tests/assistants/contract/test_rate_counter_store.py`:
  janela deslizante — `limit` concessões na janela, a seguinte recusada com `retry_after` = instante mais antigo + 60 s
  − agora; concessão volta quando o mais antigo sai da janela; pares independentes; `acquire` recusado não registra
  instante
- [X] T046 [P] [US7] Em `tests/assistants/contract/test_grant_resolver.py`, testes com `rate` no nome: com `rpm: 20` e
  `MutableClock`, a 21ª resolução do par levanta `RateLimited` com `retry_after` exato e outro Principal resolve
  (cen. 1); avançado o relógio, o par volta a resolver; pedido recusado por ACL, indisponibilidade ou modelo não
  consome cota; sem `limits.rpm`, vale 60; `limits` do grant carrega `max_iterations` e `max_context_tokens`
  declarados

### Implementation for User Story 7

- [X] T047 [P] [US7] Implementar `assistants/domain/rate.py` (`sliding_window(instants, now, limit, window) ->
  (RateDecision, instants_restantes)`) e `assistants/adapters/rate_memory.py` (`InMemoryRateCounterStore`, com
  `acquire` atômico por par, aplicando a regra do domínio)
- [X] T048 [US7] Acrescentar o passo 7 a `AssistantsService.resolve` em `assistants/service.py` — `acquire` com a
  chave (`principal.subject`, nome do Assistant), `limit` = `limits.rpm`, janela de 60 s, instante do `Clock` — como
  último passo antes de montar o grant, levantando `RateLimited(retry_after=<segundos>)`

**Checkpoint**: as sete user stories da fase estão verificadas

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T049 `tests/assistants/integration/test_cli.py`: `validate_command` com todos disponíveis (0), com um
  indisponível (1, motivo impresso) e com `AssistantsConfigError` (2); `keys create` seguido de `authenticate` com a
  chave impressa na última linha; `keys list` sem chave nem hash; `keys revoke` seguido de recusa; aviso de
  armazenamento não persistente
- [X] T050 `tests/assistants/integration/test_postgres_migrations.py` (pulado sem `AI_CORE_TEST_POSTGRES_DSN`):
  `migrate` num banco vazio cria o schema `assistants` e registra as versões 1 e 2; rodar de novo não reaplica; duas
  chamadas concorrentes terminam com o schema íntegro (trava consultiva); nenhuma tabela é criada fora do schema
  `assistants`
- [X] T051 Rodar a verificação completa de [quickstart.md](quickstart.md) — `uv run pytest`, `uv run mypy`,
  `uv run ruff check packages`, `uv run ruff format --check packages/core`, `uv run lint-imports` — e os cenários 1–8,
  com e sem `AI_CORE_TEST_POSTGRES_DSN` (Postgres local por `docker run`), corrigindo divergências entre o resultado e
  o "Esperado"
- [X] T052 [P] Atualizar a seção "Código" de `CLAUDE.md` (o módulo `ai_core/assistants/` existe, spec 003, Fase 2:
  US1–US7 — autenticação OIDC e por chave, resolução de grant com 404-não-403, políticas de Assistant de usuário,
  orçamento, validação e comandos `assistants validate`/`keys`, Postgres por psycopg com schema próprio; a troca na
  plataforma chega com as passadas da 008 e da 011) e a linha da 003 em `specs/README.md` com o status "Fase 2
  implementada (US1–US7), aguardando encaixe pela 008 e 011"

---

## Fase 3 (2026-10-02): passada de encaixe — regras de referência novas (research R18–R23)

Caminhos relativos a `ai-core/packages/core/`. Testes primeiro; marca `us8` na validação de Assistants de sistema e
`us6` na criação e atualização de Assistants de usuário. Toques declarados na 005 e na 011, sob o
[ADR-019](../../docs/adr/ADR-019-papeis-por-flow-no-seam-execution-engine.md).

## Phase 11: Foundational da Fase 3 — papéis por flow no seam da 005 (ADR-019)

**⚠️ CRITICAL**: a regra de papéis da 003 depende deste dado

- [X] T053 [P] Toque declarado na 005: estender `tests/graph/contract/test_flow_registry.py` — motor sem `capabilities`:
  `flow_roles() == {"chat": ("generation",)}`; com `FakeCapabilities`: `{"chat": ("generation",), "agentic":
  ("controller", "generation")}`; as chaves de `flow_roles()` são sempre as de `flows()`; flow sem regra (o
  `experimental` do `SpyRuntime`) → `()`. Marca `us2`
- [X] T054 Toque declarado na 005: `src/ai_core/graph/api.py` — `flow_roles(self) -> Mapping[str, tuple[ModelRole,
  ...]]` no `Protocol` `ExecutionEngine`, com docstring citando ADR-019 (importa `ModelRole` de `ai_core.llm.api`);
  `src/ai_core/graph/service.py` — `flow_roles()` = `{name: required_roles(name) for name in self.flows()}`;
  `specs/005-core-execution-engine/contracts/execution-engine.md` — o método na superfície e a regra "papéis de
  `flow_roles()` == papéis que `run` confere"; a linha do seam Execution Engine em `specs/README.md` cita os papéis por
  flow como dado consumido pela 003 (depende de T053)
- [X] T055 [P] Em `ai-core/pyproject.toml`, a marca `us8: 003 US8 — validação de Assistants` na lista `markers`, e a
  descrição de `us6` passa a citar também "003 US6 — Assistants de usuário"

**Checkpoint**: o motor publica os papéis por flow

---

## Phase 12: User Story 8 — validação com as regras novas (Priority: P3 — Fase 3)

**Goal**: Assistant de sistema com papel exigido ausente, entrada morta de tool ou colisão alias × pack fica
indisponível com o motivo (US8 cen. 2–4).

**Independent Test**: `uv run pytest packages/core/tests/assistants -m us8`.

### Tests for User Story 8 ⚠️

- [X] T056 [P] [US8] Criar `tests/assistants/unit/test_assistants_reference_rules.py`, com as mensagens **exatas** de
  [contracts/assistants-yaml.md](contracts/assistants-yaml.md), "Fase 3": `role_reasons` — `agentic` sem
  `controller` → um motivo; com `controller` → nenhum; flow sem entrada no mapeamento ou `flow_roles=None` → nenhum;
  flow `None` → nenhum; `tool_reasons` — `calculate` (sem namespace), `outro.x` (fora dos packs e MCPs), `generic.nao_existe`
  (pack não oferece) → um motivo cada, com o campo (`allowed_tools` ou `write_tools`); `generic.calculate` com o pack
  oferecendo `calculate`, `generic.buscar` com o retriever `buscar`, `financeiro.qualquer` com `financeiro` em `mcp` e
  `demo.files.read` (namespace = antes do **primeiro** `.`) → nenhum; `" generic.calculate"` (espaço no início) e
  `Generic.calculate` (caixa) → "não é pack nem MCP deste Assistant", como no gateway da 004; pack sem capacidades (em erro) → nenhum motivo de
  tool; `allowed_tools=None` → nenhum; `collision_reasons` — `packs=[generic]` + `mcp=[generic]` → um motivo; sem
  colisão → nenhum
- [X] T057 [P] [US8] Estender `tests/assistants/contract/test_validation.py`: com `flow_roles` = `{"chat":
  ("generation",), "agentic": ("controller", "generation")}` e o pack `generic` oferecendo `calculate`, um Assistant
  `agentic` sem `controller`, um com `allowed_tools: [calculate]`, um com `write_tools: [outro.x]` (privado), um com
  `packs: [generic]` + `mcp: [generic]` (com `generic` no diretório MCP falso) → indisponíveis com o motivo e os demais
  disponíveis (US8 cen. 2–4); o exemplo completo do contrato (`interno`, com `financeiro` no diretório MCP falso e o pack
  `generic`) → disponível; Assistant que herda `agentic` do pack `rag` (flow efetivo) sem `controller` → indisponível

### Implementation for User Story 8

- [X] T058 [US8] Em `src/ai_core/assistants/domain/validation.py` (R19–R21): `role_reasons(definition, *, flow,
  flow_roles)`, `tool_reasons(definition, *, pack_tools: Mapping[str, frozenset[str]])` e `collision_reasons(definition)`,
  puras; `reference_reasons` ganha `flow_roles: Mapping[str, Sequence[ModelRole]] | None = None` e `pack_tools:
  Mapping[str, frozenset[str]] | None = None` e acrescenta os motivos das três (faz T056 passar)
- [X] T059 [US8] Em `src/ai_core/assistants/service.py` (R19, R22): `AssistantsService(..., flow_roles=None)`;
  `_pack_tools(packs)` = por pack com capacidades, os nomes de `capabilities.tools` e de `capabilities.retrievers`;
  `_availability` passa `flow_roles` e `pack_tools` a `reference_reasons`; em `tests/assistants/assistants_testkit.py`,
  `pack_entry(..., tools=(), retrievers=())` e `assistants_service(..., flow_roles=None)` (depende de T058; faz T057
  passar)

**Checkpoint**: `assistants validate` acusa as três regras

---

## Phase 13: User Story 6 — criação e atualização de Assistants de usuário (Priority: P2 — Fase 3)

**Goal**: o rascunho de usuário que violaria uma regra nova é recusado na criação e na atualização, nomeando o campo
(R22).

**Independent Test**: `uv run pytest packages/core/tests/assistants -m us6 -k regra`.

- [X] T060 [P] [US6] Estender `tests/assistants/contract/test_directory.py` (testes com `regra` no nome): com a política
  `*` permitindo `generic` e os flows `chat` e `agentic`, `create` de rascunho `agentic` sem `controller` →
  `RequestRejected` com `field == "models"`; `allowed_tools=("calculate",)` → `field == "allowed_tools"`;
  `write_tools=("outro.x",)` numa política com `write_tools: true` → `field == "write_tools"`; `mcp=("generic",)` com o
  pack `generic` → `field == "mcp"`; e o mesmo para `update` de um Assistant existente; um rascunho válido continua
  criado
- [X] T061 [US6] Em `src/ai_core/assistants/service.py`, `_conform` aplica `role_reasons`, `tool_reasons` e
  `collision_reasons` à definição conformada e, se houver motivo, levanta `RequestRejected(<primeiro motivo>,
  field=<campo do motivo>)` — o campo é o prefixo do motivo antes de `:` (depende de T059; faz T060 passar)

---

## Phase 14: Polish da Fase 3

- [X] T062 Toque declarado na 011: `src/ai_core/bootstrap/wiring.py` — `assistants_service` passa
  `flow_roles=parts["engine"].flow_roles()`; teste em `tests/bootstrap/contract/test_boot_sequence.py` (marca `us8`): um
  Assistant `agentic` sem `controller` no `assistants.yaml` → a etapa `assistants` degrada nomeando o papel, e uma
  requisição a ele pela API responde 424 com o motivo (antes, 400 do motor); e, em
  `tests/bootstrap/bootstrap_testkit.py`, o `perdido` e o `pesquisador` continuam declarando `controller`
- [X] T063 Rodar a seção "Fase 3" de [quickstart.md](quickstart.md) (inclusive `ai-core assistants validate` pela
  plataforma de verdade, esperando código 1 e o motivo do papel)
- [X] T064 [P] Atualizar a seção "Código" de `CLAUDE.md` (a 003 valida papéis por flow, entradas de tool com namespace e
  colisão alias × pack; o motor publica `flow_roles()`, ADR-019) e a linha da 003 em `specs/README.md`
- [X] T065 Verificação completa a partir de `ai-core/`: `uv run pytest` (com e sem `AI_CORE_TEST_POSTGRES_DSN`),
  `uv run mypy`, `uv run ruff check packages`, `uv run lint-imports`

---

## Ajuste de 2026-10-13 — JWKS com chave que não é de assinatura (achado da passada da Fase 7 na 002)

Na prova com o Keycloak de verdade (002 research R40), todo access token era recusado: o JWKS do Keycloak traz, ao lado
das chaves de assinatura, uma de cifragem (`use: enc`, `RSA-OAEP`) que o `jwt.PyJWK` não carrega; a exceção abortava a
atualização inteira e nenhuma chave ficava em cache (research R24). Nenhum seam muda.

- [X] T066 [P] Em `tests/assistants/contract/test_oidc_verifier.py` (com `JwksServer(extra=...)` no
  `assistants_testkit`): um JWKS com a chave de cifragem do Keycloak e uma entrada malformada ainda verifica o token
  assinado pela chave de assinatura; um token assinado com a chave publicada como `use: enc` é recusado
- [X] T067 Em `src/ai_core/assistants/adapters/oidc.py` (`JwksOidcVerifier._refresh`): só entram entradas de assinatura
  (`use` ausente ou `sig`), e uma entrada que o PyJWT não carrega é ignorada sozinha; erro de rede ou de formato do
  documento continua descartando a atualização (faz T066 passar)

---

## Fase 9 (2026-10-14): superfície de administração e sobreposições

**Escopo**: US9 e US10 ([research.md](research.md) R25–R32). Caminhos relativos a `ai-core/packages/core/`. Nada em
`ai_core/http/` nem `ai_core/bootstrap/` (passadas da 008 e da 011).

## Phase 15: User Story 9 — Administração por grupo, com token da plataforma ou chave (Priority: P2)

**Independent Test**: token da console de admin e chave de admin passam na superfície `admin`; token do chat é não
autenticado ali; não admin é 404 (pela 008, depois)

### Tests for User Story 9

- [X] T068 [P] [US9] `tests/assistants/contract/test_surfaces.py` (marca `us9`): `authenticate` nas três superfícies —
  `public` só OIDC com audiência `ai-core`; `private` só chave; `admin` chave (prefixo `aic_`) ou OIDC com audiência
  `ai-core-admin`; audiência trocada → `None`; `is_admin` por grupo com OIDC e com chave; `SCHEME_OF_SURFACE` antigo
  ainda devolve o esquema das duas superfícies antigas
- [X] T069 [P] [US9] `tests/assistants/contract/test_oidc_verifier.py`: `JwksOidcVerifier` com `HttpJwksSource` (os casos
  atuais, inclusive R24) e com `CallableJwksSource` (chaves de um gerador de teste); audiência conferida por chamada

### Implementation for User Story 9

- [X] T070 [US9] `assistants/api.py`: `ADMIN_SURFACE`, `Surface` com `admin`, `SCHEMES_OF_SURFACE` e o
  `SCHEME_OF_SURFACE` derivado e depreciado (docstring citando o ADR-031)
- [X] T071 [US9] `assistants/ports.py` (`OidcVerifier.verify(token, *, audience)`), `assistants/adapters/oidc.py`
  (`JwksSource`, `HttpJwksSource` com o cache atual, `CallableJwksSource`; `JwksOidcVerifier(issuer, source, clock,
  algorithms)`), `assistants/adapters/memory.py` (`StaticOidcVerifier` com audiência)
- [X] T072 [US9] `assistants/domain/access.py` (`is_admin` só pelo grupo) e `assistants/service.py` (`AccessService` com
  `OidcAudiences`, despacho por formato na superfície `admin`)
- [X] T073 [US9] Rodar T068–T069 e a suíte inteira da 003 até verde (os testes atuais de superfície continuam válidos)

## Phase 16: User Story 10 — Operador libera sobreposições de Assistants de sistema (Priority: P2)

**Independent Test**: com `overrides: [models]`, sobrepor `generation` muda o grant da resolução seguinte; tirar a flag
ou mudar a seção no YAML deixa a sobreposição inativa e o YAML volta a valer

### Tests for User Story 10

- [X] T074 [P] [US10] `tests/assistants/unit/test_overrides.py`: impressão digital estável e insensível à ordem dos
  aliases; estados `active`/`inactive` com os dois motivos; efetiva de `models`; efetiva de `mcp` mantendo as entradas
  de pack e, com `allowed_tools` ausente no YAML, enumerando as tools dos packs mais as de MCP escolhidas
- [X] T075 [P] [US10] `tests/assistants/unit/test_assistants_yaml.py` (acréscimo): `overrides` lido; valor desconhecido
  vira problema do Assistant
- [X] T076 [P] [US10] `tests/assistants/contract/test_override_store.py` (memória × Postgres): `put` com versão; versão
  desatualizada → `Conflict`; `delete`; histórico na mesma transação
- [X] T077 [P] [US10] `tests/assistants/contract/test_system_assistant_admin.py` (marca `us10`, adversarial — SC-006):
  os cenários 1–8 da US10; não admin → `NotFound`; Assistant de usuário → `NotFound`; `declared_models()` com os
  efetivos; a sobreposição vale na resolução seguinte sem recriar o serviço

### Implementation for User Story 10

- [X] T078 [US10] `assistants/api.py`: `OverrideSection`, `ModelsOverride`, `McpOverride`, `OverrideView`,
  `SystemAssistantView`, `OverrideHistoryEntry`, `SystemAssistantAdmin` ([data-model.md](data-model.md), Fase 9)
- [X] T079 [US10] `assistants/domain/definitions.py` (`overrides` no `AssistantDefinition` e no `read_config`) e
  `assistants/domain/overrides.py` (novo) para T074–T075
- [X] T080 [US10] `assistants/ports.py` (`SystemOverrideStore`), `assistants/adapters/memory.py`
  (`InMemorySystemOverrideStore`), `assistants/adapters/sql/003_system_overrides.sql` e
  `assistants/adapters/overrides_postgres.py` para T076
- [X] T081 [US10] `assistants/service.py`: `AssistantsService` recebe `overrides: SystemOverrideStore`; definição
  efetiva em `_find`, `discover` e `validate` com cache invalidado na gravação (TTL de 5 s); o seam
  `SystemAssistantAdmin` com as validações da FR-020 e a FR-012; `declared_models()`
- [X] T082 [US10] Rodar T074–T077 até verde; `assistants validate` (CLI) passa a listar as sobreposições inativas e
  inválidas com o motivo

## Phase 17: Polish da Fase 9

- [X] T083 [P] Marcas `us9` e `us10` em `ai-core/pyproject.toml`; docstrings de `api.py` citando ADR-031 e ADR-032
- [X] T084 [P] `specs/README.md` (status da 003 na Fase 9) e `contracts/assistants-yaml.md` revisado contra o código
- [X] T085 Rodar `uv run pytest`, `mypy`, `ruff check packages`, `lint-imports` e as portas contra o Postgres com
  `AI_CORE_TEST_POSTGRES_DSN`

## Dependencies & Execution Order

**Fase 3**: T053 → T054 (toque na 005); T055 em paralelo. US8: T056 ∥ T057, depois T058 → T059. US6: T060, depois
T061 (depois de T059, mesmo `service.py`). Polish: T062 depois de T054 e T059; T063 e T065 por último; T064 em
paralelo.

### Phase Dependencies

As user stories são **independentes em teste** — cada uma tem suíte e critério próprios —, mas **sequenciais em
arquivo**: há um só `service.py`, e várias stories estendem a mesma resolução. Testes, `domain/` e `adapters/` de
stories diferentes podem andar juntos; `service.py` e `cli.py`, nunca.

- **Setup (Phase 1)**: T001 → T002; T003 e T004 em paralelo
- **Foundational (Phase 2)**: T005 → T006 → (T007 ∥ T008); T009 depois de T005–T007
- **US1 (Phase 3)**: depende da Foundational; T010–T013 em paralelo; T014 → T015; T016 → T017 → T018
- **US2 (Phase 4)**: T019–T026 podem começar logo após a Foundational, em paralelo com a US1 (T026 usa a fixture
  Postgres de T008); T027 espera T017 e T024–T026 (mesmo `service.py`); T028 espera T027 e T018 (mesmo `cli.py`)
- **US3 (Phase 5)**: T029 depois de T019 (mesmo `unit/test_access.py`); T031 depois de T027 (`service.py`) e de T024
  (`domain/access.py`)
- **US4 (Phase 6)**: T032 e T033 a qualquer momento após a Foundational; T034 depois de T030 (mesmo
  `test_adversarial.py`); T035 depois de T016 (`domain/resolution.py`) e de T031 (`service.py`)
- **US5 (Phase 7)**: T036 a qualquer momento após T017; T037 depois de T035
- **US6 (Phase 8)**: T038, T039, T042 e T043 a qualquer momento após a Foundational; T040 depois de T036 (mesmo
  `test_directory.py`); T041 depois de T013 (mesmo `test_validation.py`); T044 depois de T037, T042 e T043
- **US7 (Phase 9)**: T045 e T047 a qualquer momento após a Foundational; T046 depois de T012 (mesmo
  `test_grant_resolver.py`); T048 depois de T044 e T047
- **Polish (Phase 10)**: T049 depois de T028; T050 depois de T043; T051 depois de tudo; T052 em paralelo com T051

### Mesmo arquivo, em sequência

- `assistants/service.py`: T017 → T027 → T031 → T035 → T037 → T044 → T048
- `assistants/adapters/cli.py`: T018 → T028
- `assistants/domain/access.py`: T006 → T024 → T031; `assistants/domain/resolution.py`: T016 → T035
- `tests/assistants/unit/test_access.py`: T019 → T029
- `tests/assistants/contract/test_grant_resolver.py`: T012 → T046; `test_adversarial.py`: T030 → T034;
  `test_directory.py`: T036 → T040; `test_validation.py`: T013 → T041

### Parallel Opportunities

- Setup: T003 ∥ T004. Foundational: T007 ∥ T008
- Os testes de cada story ([P]) são escritos antes da implementação dela; os que não dividem arquivo com outra story
  podem ser escritos todos juntos
- `domain/` e `adapters/` de stories diferentes em paralelo com a US1: T024, T025, T026 (US2), T042, T043 (US6), T047
  (US7)
- T052 em paralelo com T051

---

## Parallel Example: User Story 2

```bash
# Testes primeiro, juntos:
Task: "T019 unit/test_keys.py e unit/test_access.py (claims)"
Task: "T020 contract/test_oidc_verifier.py"
Task: "T021 contract/test_api_key_store.py e test_token_generator.py"
Task: "T022 contract/test_authenticator.py"
Task: "T023 contract/test_key_admin.py"

# Depois, domínio e adapters sem dependência entre si:
Task: "T024 domain/keys.py e domain/access.py (claims)"
Task: "T025 adapters/tokens.py e adapters/oidc.py"
```

---

## Implementation Strategy

### MVP (US1 → US4, as P1)

1. Phase 1 e 2: esqueleto, dependências, CI com Postgres, superfície pública, portas, adapters em memória, fronteiras
2. Phase 3 (US1): Assistants de sistema resolvem e validam
3. Phase 4 (US2): as duas superfícies autenticam, chaves com hash
4. Phases 5 e 6 (US3, US4): ACL com 404 idêntico e restrição por id de modelo
5. **PARE e VALIDE**: cenários 1–4 do quickstart — é a fronteira de isolamento completa para Assistants de sistema

### Incremental (P2)

6. US5: descoberta
7. US6: Assistants de usuário com política, Postgres
8. US7: orçamento
9. Phase 10: CLI, migrações, quickstart completo, documentação

### Depois desta passada

- **008 (Fase 2)**: consome os seams daqui e aposenta as portas próprias de autenticação e grant; ganha o endpoint de
  administração de chaves (FR a acrescentar na spec dela) e aplica `WIDENING_FIELDS` no corpo — é o que fecha o
  cenário 2 da US4 e a SC-005 para o corpo da requisição. Corrige também o cenário US2.1 dela, que contradiz a FR-008
  daqui (um privado aparece para quem o `allow` nomeia).
- **011 (Fase 2)**: constrói `AccessService` e `AssistantsService` nos perfis, chama `migrate(pool, now=…)`, acrescenta a
  etapa de validação de Assistants, registra `assistants validate` e `keys` e remove `bootstrap/grants.py` — é essa etapa que fecha a SC-004
  ("antes de servir tráfego").

---

## Notes

- [P] = arquivos diferentes, sem dependência pendente; [USn] liga a tarefa à user story para rastreabilidade
- Testes de cada story são escritos antes e falham antes da implementação
- Postgres: sem `AI_CORE_TEST_POSTGRES_DSN`, os casos do adapter real são pulados com motivo; na CI eles rodam sempre
- Nenhuma tarefa toca `ai_core/http/` nem `ai_core/bootstrap/` (research R2)

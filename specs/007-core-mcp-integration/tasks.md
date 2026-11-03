---

description: "Task list for 007 — Registry e cliente MCP, Fase 3"
---

# Tasks: Registry e cliente MCP

**Input**: Design documents from `/specs/007-core-mcp-integration/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos, antes do código (TDD). SC-001, SC-002 e SC-004 são enunciados adversariais que só se demonstram
por teste, e a governança exige a suíte de conformidade de cada seam exposto e de cada porta secundária (memória ×
adapter real).

**Organization**: **US1–US6** (Fase 3 do roadmap). **Não** entram: nada em `ai_core/assistants/`, `ai_core/http/` nem
`ai_core/bootstrap/` — a troca do catálogo vazio da 003, as rotas da 008 e os perfis, o arquivo do operador e a etapa de
boot da 011 são das passadas delas ([research.md](research.md) R1).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1–US6)

## Path Conventions

- Caminhos relativos a `ai-core/packages/core/`: código em `src/ai_core/mcp/` (abreviado `mcp/` abaixo), testes em
  `tests/mcp/{unit,contract,integration}/` (abreviado `tests/mcp/`)
- Comandos a partir de `ai-core/`, com `XDG_DATA_HOME=$HOME/.local/share`; Postgres por `AI_CORE_TEST_POSTGRES_DSN`

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Criar o esqueleto do módulo: `src/ai_core/mcp/__init__.py` (docstring: spec 007 — registry por alias e
  cliente restrito ao grant; seams em `api.py`; `stdio` só pelo arquivo do operador, ADR-003),
  `mcp/domain/__init__.py`, `mcp/adapters/__init__.py`, `mcp/adapters/sql/` e os diretórios
  `tests/mcp/{unit,contract,integration,servers}/`
- [X] T002 Acrescentar `mcp>=2.2,<3` a `dependencies` de `pyproject.toml` (do pacote core), com comentário citando a
  spec 007 e a pesquisa (R6: SDK oficial, traz `httpx2`/`httpcore2`, confinado a `adapters/`); rodar `uv sync`, conferir
  `uv.lock` e que `uv run python -c "import mcp, httpx2, httpcore2"` funciona no Python 3.14 do workspace
- [X] T003 [P] Em `ai-core/pyproject.toml`, acrescentar `packages/core/tests/mcp` a `[tool.pytest.ini_options]
  pythonpath`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: a superfície pública, as portas, os adapters em memória, o kit de teste e as fronteiras de import

**⚠️ CRITICAL**: nenhuma user story começa antes de T004–T008

- [X] T004 Implementar `mcp/api.py` conforme [data-model.md](data-model.md) e [contracts/mcp-api.md](contracts/mcp-api.md),
  importando **só** a stdlib, o contrato 001 (`ToolSpec`, `ToolResult`, `JSONValue`) e `ai_core.assistants.api`
  (`Principal`, `ExecutionGrant`, `NotFound`, `RequestRejected`, `Conflict`):
  - vocabulário: `Scope` (`global`, `user`), `Transport` (`http`, `sse`, `stdio`), `AuthType` (`none`, `bearer`),
    `Origin` (`file`, `registry`), `USER_PREFIX = "~"`, `ALIAS_PATTERN` = `[a-z0-9][a-z0-9_-]{0,31}`,
    `CREDENTIAL_REF_PATTERN` = `[a-z0-9][a-z0-9_]{0,63}`, `DESCRIPTION_MAX = 500`;
  - value objects congelados (`frozen=True, slots=True, kw_only=True`): `SecurityPolicy` (`timeout_ms` "1 000–120 000;
    padrão 30 000", `max_response_bytes` "1 024–1 048 576; padrão 65 536", `allowed_tools` "obrigatória, não vazia,
    nomes exatos, sem repetição", `write_tools` "⊆ `allowed_tools`; padrão vazio"), `McpServerDraft` (campos da tabela
    do data-model), `McpServer` (visão publicada, com `origin`, `read_only`, `available`, `reason`, sem valor de
    segredo), `McpSummary` (`alias`, `scope`, `description`), `ServerHealth` (`alias`, `ok`, `detail`, `tools`,
    `missing`), `Discovery` (`tools: tuple[ToolSpec, ...]`, `unavailable: Mapping[str, str]` imutável); o
    `__post_init__` de `SecurityPolicy` recusa valor fora da faixa com `McpRejected` nomeando `policy.<campo>`;
  - os `Protocol`: `McpRegistry`, `McpCatalog`, `McpClients`, `RestrictedMcpClient`, nas assinaturas exatas do contrato;
  - erros: `McpNotFound(NotFound)` com mensagem fixa `"MCP não encontrado"`, `McpRejected(RequestRejected)` (`field`),
    `McpConflict(Conflict)`, `UnknownServer(LookupError)`, `McpConfigError(ValueError)`
- [X] T005 Implementar `mcp/ports.py` nas assinaturas exatas de [contracts/ports.md](contracts/ports.md): as sete portas
  (`McpServerStore`, `McpConfigSource`, `McpTransport`, `DnsResolver`, `SecretResolver`, `DiscoveryCache`, `Clock`) e os
  tipos internos `StoredServer` (`owner: str | None`, `draft`, `created_at`, `updated_at`), `McpConfig` (`entries`,
  `internal_hosts: frozenset[str]`, `allowed_hosts: frozenset[str] | None`), `ConfigEntry` (`alias`, a definição validada ou `problem: str`, e para `stdio`
  `command`, `args`, `env`, `secrets`), `RemoteTool` (`name`, `description`, `input_schema`), `RemotePart` (texto ou
  marcador de tipo), `RemoteResult` (`parts`, `structured`, `is_error`), `Target` (escopo, transporte, endpoint ou
  comando/args/ambiente, cabeçalhos — segredo já resolvido, `repr` sem cabeçalhos nem ambiente), `OperationLimits`
  (`timeout: float`, `max_bytes: int`), `CacheKey`, `CachedDiscovery` (`tools` ou `failure`) e a exceção
  `TransportFailure(reason)`. Nenhum import de biblioteca de infraestrutura
- [X] T006 [P] Implementar os adapters em memória em `mcp/adapters/memory.py`, na distribuição (o perfil `test` da 011 os
  usa): `InMemoryServerStore`, `InMemoryConfigSource` (configuração pronta), `ScriptedMcpTransport` (servidores
  programados por endpoint ou comando: tools, resultados por tool, falha, atraso; guarda os `Target` recebidos em
  `calls` para as suítes conferirem cabeçalhos), `FixedDnsResolver` (nome → IPs; IP literal → ele mesmo),
  `InMemorySecretResolver` (ref → valor) e `InMemoryDiscoveryCache` (dicionário + `Clock`)
- [X] T007 [P] Criar o kit de teste: `tests/mcp/mcp_testkit.py` com construtores de `SecurityPolicy` e `McpServerDraft`
  válidos por default (global `http` e de usuário `https`, sobrescrevíveis por campo), Principals (`user:ana`,
  `user:bia`), construtores de `ExecutionGrant` da 003 para Assistant de sistema e de usuário (`~meu`, dono `user:ana`)
  com `mcp_aliases` dados, um `MutableClock` com `advance(...)`, e a montagem de `McpService` com adapters em memória;
  `tests/mcp/servers/demo.py` — um `MCPServer` do SDK com as tools `ecoar` (devolve o texto), `quem` (devolve o
  cabeçalho `Authorization` recebido), `grande` (texto de N bytes), `lento` (dorme N s), `falha` (resultado de erro),
  `estruturado` (`structured_content`) e `t01`…`t50`, exposto por `streamable_http_app()`, `sse_app()` e
  `run_stdio_async()` (executável como `python -m` para o `stdio`); e `tests/mcp/conftest.py` com a fixture `pg_pool`
  (`AsyncConnectionPool` de `AI_CORE_TEST_POSTGRES_DSN`, `DROP SCHEMA mcp CASCADE` antes de cada teste, `pytest.skip`
  com motivo explícito sem a variável), a fixture parametrizada `server_store` (memória × Postgres) e a fixture
  `demo_http` (o servidor demo servido por uvicorn em `127.0.0.1` numa porta livre, numa thread, durante o teste)
- [X] T008 Acrescentar a `ai-core/pyproject.toml` os contratos de import-linter de [plan.md](plan.md) ("Fronteiras
  verificadas"): `api.py` da 007 não importa o resto do módulo; `domain/` não importa portas, service nem adapters;
  `service.py` não importa adapters; o núcleo (`api`, `domain`, `ports`, `service`) não importa `mcp`, `mcp_types`,
  `httpx2`, `httpcore2`, `anyio`, `yaml`, `psycopg`, `psycopg_pool`; a 007 só vê outros módulos pelo `api.py` (só
  `ai_core.assistants.api`; nada de `ai_core.http` nem `ai_core.bootstrap`); nenhum outro módulo importa `mcp.domain`,
  `.ports`, `.service` ou `.adapters` (só a composition root); `mcp` e `mcp_types` não aparecem fora de
  `ai_core.mcp.adapters` (`httpx2`/`httpcore2` são também a pilha do SDK do provider da 006). Acrescentar `ai_core.mcp` à origem de "nenhum módulo do core importa a API" e "nenhum
  módulo importa a composition root". Rodar `uv run lint-imports` até tudo aparecer como `KEPT`

**Checkpoint**: superfície pública, portas e adapters em memória prontos — as user stories podem começar

---

## Phase 3: User Story 1 - Operador registra um MCP global sem código nem restart (Priority: P1) 🎯 MVP

**Goal**: globais pela API (`http`/`sse`) e pelo arquivo do operador (inclusive `stdio`); o catálogo de aliases da 003;
a descoberta de tools com cache por TTL; a saúde por servidor.

**Independent Test**: `uv run pytest packages/core/tests/mcp -k us1` — um MCP registrado com o serviço montado aparece
na descoberta seguinte, sem recriar nada; desabilitado, some de `aliases`.

### Tests for User Story 1 ⚠️

> Escrever primeiro e ver falhar antes da implementação

- [X] T009 [P] [US1] `tests/mcp/unit/test_servers.py`: a tabela de [research.md](research.md) R11 para globais e para
  entradas do arquivo — alias fora da gramática ou com `~`, endpoint sem host, com usuário/senha ou fragmento, `stdio`
  sem `command` ou com `endpoint`/`auth`, `http` com `command`, `bearer` sem referência, referência fora da gramática,
  `none` com referência, `description` acima de 500, política fora das faixas, `allowed_tools` vazia ou repetida,
  `write_tools` fora de `allowed_tools` — cada recusa nomeando o campo
- [X] T010 [P] [US1] `tests/mcp/contract/test_mcp_config_source.py` ([contracts/mcp-yaml.md](contracts/mcp-yaml.md)),
  contra `InMemoryConfigSource` e o adapter YAML: o exemplo do contrato carrega; YAML inválido, raiz que não é
  mapeamento, chave de topo desconhecida, `servers`/`network` que não é mapeamento e `internal_hosts` que não é lista
  de textos levantam `McpConfigError` nomeando o caminho; entrada com erro vira entrada indisponível com o motivo e as
  outras carregam; `internal_hosts` e `allowed_hosts` normalizados em minúsculas; `allowed_hosts` ausente vira `None`,
  vazia ou com padrão fora de nome, `*.domínio` ou IP literal levanta `McpConfigError`
- [X] T011 [P] [US1] `tests/mcp/contract/test_registry.py` (parte global, `-k us1`): `create_global`/`get_global`/
  `update_global`/`delete_global` e `globals` (arquivo + armazenamento, por alias); `stdio` pela API recusado com
  `field="transport"` em `create` e `update` (US1 cen. 3, FR-013); entrada do arquivo com `origin="file"` e
  `read_only=True`, e `update`/`delete` nela levantam `McpConflict`; `create_global` com alias do arquivo levanta
  `McpConflict`; registro armazenado cujo alias o arquivo passa a declarar aparece `available=False` com o motivo
  (sombreado); `check` lista as tools anunciadas e as da allowlist que faltam, e ignora o cache
- [X] T012 [P] [US1] `tests/mcp/contract/test_catalog.py`: `aliases(owner=None)` devolve só globais habilitados e
  disponíveis — desabilitado sai (US1 cen. 2), sombreado sai, entrada do arquivo com erro sai; e um teste tipado que
  atribui o `McpService` a uma variável anotada com `ai_core.assistants.ports.McpDirectory` (mypy confere a forma) —
  único import de internal da 003, só na suíte, de propósito: uma cópia local da porta poderia divergir da real
- [X] T013 [P] [US1] `tests/mcp/contract/test_discovery.py`: servidor criado depois de montado o serviço aparece no
  `discover` seguinte (US1 cen. 1, SC-003); só as tools da allowlist, com nome local, `kind="mcp"`, `mutates` pela
  `write_tools`, sem handler (FR-007); tool da allowlist não anunciada não aparece; segunda descoberta dentro do TTL
  não toca o transporte; depois do TTL, toca; `update_global` (inclusive mudar a allowlist) vale na descoberta seguinte;
  servidor com falha entra em `unavailable` com o motivo e os demais atendem; falha fica 30 s em cache negativo;
  `discover_tools` devolve só as tools
- [X] T014 [P] [US1] `tests/mcp/contract/test_transport.py` (parte `stdio`), parametrizada sobre `ScriptedMcpTransport`
  e `transport_stdio` com o servidor demo: `list_tools` devolve as tools anunciadas; `call_tool` de `ecoar` e de
  `estruturado`; `falha` volta com `is_error`; `lento` além do prazo e comando inexistente viram `TransportFailure`
  com motivo; `env` literal chega ao processo filho

### Implementation for User Story 1

- [X] T015 [US1] Implementar `mcp/domain/servers.py`: validação do rascunho e da entrada do arquivo pela tabela de R11
  (global nesta história), gramática do alias, normalização da política, e a conversão rascunho → `McpServer`
- [X] T016 [US1] Implementar `mcp/domain/visibility.py` (parte global): fusão arquivo + armazenamento por alias, com o
  arquivo prevalecendo e o registro armazenado marcado como sombreado; conjunto de aliases globais referenciáveis
  (habilitados e disponíveis)
- [X] T017 [US1] Implementar `mcp/domain/tools.py`: tools remotas → `ToolSpec` filtradas pela allowlist, com
  `mutates` de `write_tools`, `kind="mcp"`, descrição do servidor ou o próprio nome quando vazia; e a lista de faltantes
  para a saúde
- [X] T018 [P] [US1] Implementar `mcp/adapters/config_yaml.py` (`YamlMcpConfigSource`), lendo `mcp.yaml` com
  `yaml.safe_load` e validando cada entrada com `domain/servers.py`
- [X] T019 [P] [US1] Implementar `mcp/adapters/transport_stdio.py` (`StdioMcpTransport`): `stdio_client` do SDK com
  comando, argumentos e ambiente da entrada, sem shell, uma sessão por operação (`initialize` + operação) sob
  `anyio.fail_after(limits.timeout)`; tools do SDK → `RemoteTool`, resultado → `RemoteResult`; toda falha vira
  `TransportFailure` com motivo, sem o ambiente do filho na mensagem
- [X] T020 [US1] Implementar `mcp/service.py` (`McpService`), parte global: construtor com `store`, `config`,
  `transports` (por tipo), `secrets`, `cache`, `clock`, `discovery_ttl: timedelta = 300 s` e
  `failure_ttl: timedelta = 30 s`; CRUD global com as recusas de T011; `aliases(owner=None)`; `check` (R14); e o
  caminho de descoberta — cache por `(escopo, dono, alias, versão)` com a versão de R8, lista bruta guardada, filtro de
  `domain/tools.py` aplicado na leitura — usado por um `client_for` provisório que aceita os globais do grant (o
  cliente restrito completo é da US3)

**Checkpoint**: um operador registra MCP global pela API ou pelo arquivo, e ele aparece na execução seguinte

---

## Phase 4: User Story 2 - Credencial por referência, resolvida no servidor (Priority: P1)

**Goal**: o registry guarda só a referência; o segredo é lido de `AI_CORE_MCP_SECRET_<REF>` na hora da operação e nunca
aparece em armazenamento, log, trace, exceção ou valor devolvido.

**Independent Test**: `AI_CORE_TEST_POSTGRES_DSN=… uv run pytest packages/core/tests/mcp -k us2`.

### Tests for User Story 2 ⚠️

- [X] T021 [P] [US2] `tests/mcp/contract/test_secrets.py`, contra `InMemorySecretResolver` e `secrets_env`: referência
  presente devolve o valor; ausente devolve `None`; fora de `[a-z0-9][a-z0-9_]{0,63}` devolve `None`;
  `AI_CORE_DATABASE_URL`, `PATH` e `AI_CORE_DEV_API_KEY` não são alcançáveis por referência nenhuma
- [X] T022 [P] [US2] `tests/mcp/contract/test_store.py`, sobre a fixture `server_store` (memória × Postgres): `insert`
  duplicado devolve `False` sem alterar; `replace`/`delete` de inexistente devolvem `False`; `list(None)` só globais,
  `list("user:ana")` só de Ana; `all` traz todos; o rascunho volta igual (política inclusive)
- [X] T023 [P] [US2] `tests/mcp/contract/test_credentials.py`: com `bearer`, o `Target` recebido pelo
  `ScriptedMcpTransport` traz `Authorization: Bearer <segredo>` (US2 cen. 2); `stdio` com `secrets` recebe a variável
  no ambiente; referência sem valor faz descoberta, chamada e saúde falharem com "credencial '<ref>' não configurada";
  nenhum `McpServer`, `ServerHealth`, `Discovery`, `ToolResult`, mensagem de exceção ou `repr(Target)` contém o valor
- [X] T024 [P] [US2] `tests/mcp/integration/test_secret_scan.py` (SC-001): com o store Postgres, criar globais com
  `bearer`, descobrir e chamar; depois, despejar todas as linhas do schema `mcp` e os logs capturados (`caplog` em
  `DEBUG`, inclusive dos loggers do SDK e de `httpx2`) e conferir que nenhum valor de segredo aparece — só a
  referência (US2 cen. 1)

### Implementation for User Story 2

- [X] T025 [P] [US2] Implementar `mcp/adapters/secrets_env.py` (`EnvSecretResolver`, prefixo fixo
  `AI_CORE_MCP_SECRET_`, nome em maiúsculas; ambiente injetável para as suítes)
- [X] T026 [P] [US2] Implementar `mcp/adapters/sql/001_servers.sql` (schema `mcp`, tabela `servers` com dono nulo para
  global, alias, transporte, endpoint, descrição, `auth_type`, `credential_ref`, `enabled`, `user_access`, política
  em `jsonb`, `created_at`, `updated_at`; índices únicos parciais — `(alias) WHERE owner IS NULL` e `(owner, alias)
  WHERE owner IS NOT NULL`), `mcp/adapters/postgres_schema.py` (`migrate(pool, *, now)` sob trava consultiva, versão
  em `mcp.schema_version`, `MigrationError` nomeando módulo e arquivo — o mesmo desenho da 003 e da 008, ADR-015) e
  `mcp/adapters/registry_postgres.py` (`PostgresServerStore`; o rascunho serializado com `format: 1`; datas como
  parâmetro, nunca `now()` no SQL)
- [X] T027 [US2] Em `mcp/service.py`, montar o `Target` de cada operação resolvendo a referência pelo `SecretResolver`
  só no momento da operação (`bearer` → cabeçalho `Authorization`; `stdio` → `secrets` no ambiente do filho);
  referência sem valor vira falha nomeando a referência; garantir que nenhuma mensagem de falha repassada inclua
  cabeçalho ou ambiente

**Checkpoint**: chamadas autenticadas funcionam e nenhum segredo sai do momento da operação

---

## Phase 5: User Story 3 - Cliente restrito a aliases autorizados (Priority: P1)

**Goal**: o cliente entregue a uma execução conhece só os aliases do grant e confere de novo a visibilidade; executa
tools devolvendo `ToolResult` não confiável.

**Independent Test**: `uv run pytest packages/core/tests/mcp -k us3` — alias fora do grant responde "servidor
desconhecido" sem tocar no transporte.

### Tests for User Story 3 ⚠️

- [X] T028 [P] [US3] `tests/mcp/contract/test_restricted_client.py`: grant com `mcp_aliases={"financeiro"}` — `discover`
  e `execute` de `drive` levantam `UnknownServer("servidor desconhecido: drive")` sem chamada ao transporte (US3 cen.
  1); alias do grant desabilitado ou removido depois de `client_for` também; Assistant de sistema não alcança alias
  `~`; `execute` de tool da allowlist devolve `ToolResult(untrusted=True)` com o texto (ou o `structured_content`, se não houver texto);
  tool fora da allowlist devolve `ToolResult(error=...)` sem tocar no servidor; resultado de erro do servidor, prazo
  esgotado e falha de transporte viram `ToolResult(error=...)`, nunca exceção; o `RestrictedMcpClient` passa por
  variável anotada com o `MCPClient` do contrato 001 (mypy)
- [X] T029 [P] [US3] `tests/mcp/unit/test_results.py`: `RemoteResult` → `ToolResult` — textos concatenados com
  marcador para partes não textuais, e `structured` só quando não há texto; `is_error` vira `error`; `untrusted` sempre
  verdadeiro

### Implementation for User Story 3

- [X] T030 [US3] Implementar `mcp/domain/results.py` (mapeamento de T029; o corte por tamanho entra na US5)
- [X] T031 [US3] Em `mcp/service.py`, substituir o `client_for` provisório pelo `RestrictedMcpClient` completo: aliases
  e dono congelados do grant; a cada `discover`/`execute`, conferir que o alias está no grant **e** continua visível
  para a origem do grant (R9) — senão `UnknownServer`; `execute` com a allowlist, o `Target` da US2 e o mapeamento de
  T030; `discover_tools` como projeção de `discover`

**Checkpoint**: elo 4 da cadeia de enforcement fechado — a 004 já pode consumir o cliente

---

## Phase 6: User Story 4 - Usuário registra MCPs próprios (Priority: P2)

**Goal**: MCPs de escopo `user` com prefixo `~`, visíveis e utilizáveis só pelo dono, sempre `https`, sem autenticação
e sem `stdio`; globais liberados a usuários.

**Independent Test**: `uv run pytest packages/core/tests/mcp -k us4` — A registra um MCP; B não o lista nem o
referencia.

### Tests for User Story 4 ⚠️

- [X] T032 [P] [US4] `tests/mcp/unit/test_servers.py` (parte de usuário): alias sem `~`; `stdio` (US4 cen. 2); `http`
  em vez de `https`; `auth_type` diferente de `none`, `credential_ref` presente ou usuário/senha na URL (US4 cen. 3);
  `user_access` presente — cada recusa nomeando o campo; e global com alias começando por `~` recusado (US4 cen. 5)
- [X] T033 [P] [US4] `tests/mcp/contract/test_isolation.py` (SC-004): `mine` de B não contém nada de A (US4 cen. 1);
  `get_mine`/`update_mine`/`delete_mine` de B sobre o `~drive` de A levantam `McpNotFound` com a mesma mensagem de
  alias inexistente; o cliente de um Assistant de B com `~drive` no grant levanta `UnknownServer`; `~drive` de A e
  global `drive` coexistem (US4 cen. 5)
- [X] T034 [P] [US4] `tests/mcp/contract/test_registry.py` e `test_catalog.py` (parte de usuário, `-k us4`): CRUD de
  `mine`; `available(principal)` devolve os `~` do Principal e os globais habilitados com `user_access`, só com alias,
  escopo e descrição; `aliases(owner="user:ana")` = `~` habilitados de Ana + globais habilitados com `user_access`;
  global sem `user_access` fora (US4 cen. 4); desligar `user_access` tira o global do conjunto e do cliente do Assistant
  de usuário na execução seguinte

### Implementation for User Story 4

- [X] T035 [US4] Estender `mcp/domain/servers.py` (regras de usuário de R11 e FR-014/FR-015) e
  `mcp/domain/visibility.py` (o que cada dono enxerga e pode referenciar; origem do grant pelo prefixo `~` do Assistant)
- [X] T036 [US4] Em `mcp/service.py`: `mine`, `get_mine`, `create_mine`, `update_mine`, `delete_mine` sempre no escopo
  de `principal.subject`, com `McpNotFound` de mensagem fixa para alheio e inexistente; `available`;
  `aliases(owner=X)`; e o cliente restrito para grants de Assistant de usuário (dono = `subject` do Principal do grant)

**Checkpoint**: usuário pluga o próprio MCP remoto sem tocar no processo do core

---

## Phase 7: User Story 5 - Política por servidor (Priority: P2)

**Goal**: prazo por operação e teto de tamanho aplicados de verdade, com corte visível; de 50 tools anunciadas, só as da
allowlist.

**Independent Test**: `uv run pytest packages/core/tests/mcp -k us5`.

### Tests for User Story 5 ⚠️

- [X] T037 [P] [US5] `tests/mcp/contract/test_policy.py`: servidor programado com `t01`…`t50` e allowlist de 3 — a
  descoberta devolve só as 3, com a marca de escrita das que estão em `write_tools` (US5 cen. 1); tool anunciada depois
  fora da allowlist continua ausente; operação mais lenta que `timeout_ms` volta como falha/`ToolResult(error=...)` em
  não mais que o prazo + 10%; resultado maior que `max_response_bytes` volta cortado, com a marca de corte no texto e
  `truncated=True`
- [X] T038 [P] [US5] `tests/mcp/unit/test_results.py` (parte de corte): corte em fronteira de caractere UTF-8, marca
  visível ao final, `structured` grande serializado e cortado como texto, resultado no limite exato não é cortado

### Implementation for User Story 5

- [X] T039 [US5] Em `mcp/domain/results.py`, o corte por `max_response_bytes` com marca; em `mcp/service.py`, repassar
  a cada operação `OperationLimits(timeout=timeout_ms/1000, max_bytes=max_response_bytes + 1 MiB)`, **sem** prazo
  próprio — o prazo é regra da porta e cada transporte o aplica (T019, T046, `ScriptedMcpTransport`); o teto de bytes
  vale só em `http`/`sse` (T046), não no `stdio` ([research.md](research.md) R6)

**Checkpoint**: nenhum servidor expõe mais que a allowlist, demora mais que o prazo ou entrega mais que o teto

---

## Phase 8: User Story 6 - Proteções de rede (Priority: P2)

**Goal**: a decisão de rede pura, aplicada a cada conexão do transporte `http`/`sse` com a conexão fixada no IP
validado; hosts internos do operador só para globais.

**Independent Test**: `uv run pytest packages/core/tests/mcp -k "us6 or ssrf"` — 100% dos vetores de
[contracts/network-policy.md](contracts/network-policy.md) bloqueados.

### Tests for User Story 6 ⚠️

- [X] T040 [P] [US6] `tests/mcp/unit/test_network.py`: a tabela de vetores de
  [contracts/network-policy.md](contracts/network-policy.md) contra `admit` — todos bloqueados para `scope="user"` e
  para global fora de `internal_hosts`, com o motivo nomeando a classe; as exceções (host interno para global
  permitido, para usuário bloqueado; público permitido nos dois escopos); resposta mista bloqueada; a allowlist de
  hosts de destino (US6 cen. 5) — `*.empresa.example` casa `mcp.empresa.example` e não `empresa.example` nem
  `outro.example`, vale para global e usuário, IP literal casa só ele mesmo, host interno de global passa antes dela, e
  `None` não restringe; e a propriedade com
  hypothesis: todo IPv4/IPv6 com `is_global` falso é bloqueado para usuário
- [X] T041 [P] [US6] `tests/mcp/contract/test_dns.py`, contra `FixedDnsResolver` e `dns_system`: IP literal devolve ele
  mesmo; `localhost` resolve para loopback; nome inexistente (`.invalid`) devolve vazio, não exceção
- [X] T042 [P] [US6] `tests/mcp/contract/test_transport.py` (parte `http`/`sse`): parametrizar também sobre
  `transport_http` com o servidor demo em `127.0.0.1` (fixture `demo_http`), alcançado como global com `127.0.0.1` em
  `internal_hosts` — `list_tools`, `call_tool`, `falha`, `lento`, teto de bytes com `grande`; `quem` recebe o
  `Authorization` do `Target` (US2 cen. 2 no transporte real); e, sem a exceção, a mesma operação falha com o motivo
  da política (US6 cen. 3, lado do usuário); e `tests/mcp/contract/test_guarded_backend.py`: o backend de rede com
  conector falso — duas conexões ao mesmo nome, a primeira resolvendo para IP público (o conector recebe o **IP**, não o
  nome) e a segunda para privada (bloqueada antes de o conector ser chamado: rebinding); `allowed_hosts` aplicada a cada
  conexão
- [X] T043 [P] [US6] `tests/mcp/integration/test_ssrf.py` (SC-002): pelo transporte `http` real, com `FixedDnsResolver`
  mapeando nomes de teste — nome que resolve para privada (US6 cen. 1), resposta mista, IPv4 mapeado, decimal e octal,
  `localhost` e `*.localhost`, metadados por global sem exceção (US6 cen. 4), host público fora de `allowed_hosts`
  (US6 cen. 5), redirecionamento `302` do servidor demo para
  `http://127.0.0.1/` e para um nome que resolve para privada (US6 cen. 2) — 100% bloqueados antes de qualquer byte da
  operação chegar ao destino bloqueado; `trust_env` desligado mesmo com `HTTPS_PROXY` no ambiente

### Implementation for User Story 6

- [X] T044 [US6] Implementar `mcp/domain/network.py`: `admit(host, addresses, *, scope, internal_hosts, allowed_hosts) ->
  Admission` na ordem do contrato, com normalização de IPv4 mapeado, 6to4 e Teredo e o critério `is_global`
- [X] T045 [P] [US6] Implementar `mcp/adapters/dns_system.py` (`SystemDnsResolver`, `getaddrinfo` assíncrono do laço,
  IPs deduplicados na ordem devolvida; falha de resolução → vazio)
- [X] T046 [US6] Implementar `mcp/adapters/transport_http.py` (`HttpMcpTransport`): backend de rede do `httpcore2` que,
  em `connect_tcp`, resolve pelo `DnsResolver`, chama `admit` com o escopo do `Target`, os `internal_hosts` e os
  `allowed_hosts` do operador e conecta no IP devolvido (o TLS segue verificando o nome do host), com o conector TCP
  subjacente injetável (padrão `anyio.connect_tcp`) para `test_guarded_backend.py`; `httpx2.AsyncClient` sobre esse pool,
  com `trust_env=False`, cabeçalhos do `Target` e o teto de bytes de `OperationLimits`; `streamable_http_client` para
  `http` e `sse_client` (com fábrica de cliente) para `sse`; uma sessão por operação sob `anyio.fail_after`; recusa da
  política e toda falha viram `TransportFailure` com motivo, sem cabeçalhos na mensagem

**Checkpoint**: SSRF fechado no IP resolvido, a cada conexão

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T047 Rodar o [quickstart.md](quickstart.md) e a verificação completa a partir de `ai-core/`: `uv run pytest` com e
  sem `AI_CORE_TEST_POSTGRES_DSN`, `uv run mypy`, `uv run ruff check packages`, `uv run lint-imports`; corrigir o que
  falhar
- [X] T048 [P] Atualizar `specs/README.md` (linha da 007: "Fase 3 implementada (US1–US6); encaixe pela 003, 008 e 011
  nas passadas delas"; conferir a linha do seam **MCP Registry + cliente MCP restrito**) e `CLAUDE.md` ("Código": o
  módulo `ai_core/mcp/`, o SDK em `adapters/`, `stdio` só pelo arquivo do operador, segredos em
  `AI_CORE_MCP_SECRET_<REF>`, e o que falta ligar nas passadas de 003, 008 e 011)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 → T002; T003 em paralelo
- **Foundational (Phase 2)**: depende do Setup; T004 → T005; T006 e T007 em paralelo depois de T005; T008 por último
- **US1 (Phase 3)**: depende do Foundational. Testes T009–T014 em paralelo; T015 → T016 → T017; T018 e T019 em
  paralelo com T016–T017; T020 por último
- **US2 (Phase 4)**: depende da US1 (o serviço monta o `Target`). T021–T024 em paralelo; T025 e T026 em paralelo; T027
  por último
- **US3 (Phase 5)**: depende da US2 (o `Target` com credencial). T028 e T029 em paralelo; T030 → T031
- **US4 (Phase 6)**: depende da US3 (o cliente restrito). T032–T034 em paralelo; T035 → T036
- **US5 (Phase 7)**: depende da US3 (`execute`). Independente da US4. T037 e T038 em paralelo; T039
- **US6 (Phase 8)**: depende do Foundational e da US1 (contrato do transporte); independente de US4 e US5. T040–T043 em
  paralelo; T044 → T046; T045 em paralelo com T044. T042 e T043 rodam contra o transporte real só depois de T046
- **Polish (Phase 9)**: depois de todas

### User Story Dependencies

```text
Foundational ─▶ US1 ─▶ US2 ─▶ US3 ─┬─▶ US4
                  │                 └─▶ US5
                  └────────────────────▶ US6
```

### Within Each User Story

- Testes primeiro, falhando; depois domínio, adapters e serviço
- `mcp/service.py` é tocado por T020, T027, T031, T036 e T039 — sequenciais

### Parallel Opportunities

- Foundational: T006 ∥ T007
- US1: T009–T014; depois T018 ∥ T019 com o domínio
- US2: T021–T024; T025 ∥ T026
- US4 ∥ US5 depois da US3; US6 em paralelo com US2–US5 (arquivos próprios: `domain/network.py`, `dns_system.py`,
  `transport_http.py`)

---

## Parallel Example: User Story 1

```bash
# Testes da US1, juntos:
Task: "unit/test_servers.py (T009)"
Task: "contract/test_mcp_config_source.py (T010)"
Task: "contract/test_registry.py, parte global (T011)"
Task: "contract/test_catalog.py (T012)"
Task: "contract/test_discovery.py (T013)"
Task: "contract/test_transport.py, parte stdio (T014)"
```

---

## Implementation Strategy

### MVP (US1)

1. Phase 1 e 2: esqueleto, SDK, superfície pública, portas, adapters em memória e fronteiras
2. Phase 3: globais pela API e pelo arquivo, catálogo para a 003, descoberta com cache, `stdio`
3. **PARE e VALIDE**: `-k us1` — MCP novo aparece sem restart; desabilitado some do catálogo

### Incremental

1. US2 + US3 (P1): credenciais e cliente restrito — com elas, a 004 pode começar o plano dela
2. US4 e US5 (P2): usuário e política
3. US6 (P2): transporte HTTP com a política de rede — **antes** de qualquer encaixe na plataforma em execução, porque é
   ela que torna `http`/`sse` seguros
4. Polish

### Depois desta passada

- **011**: perfis com os adapters desta spec, `AI_CORE_MCP_FILE`, `AI_CORE_MCP_DISCOVERY_TTL`, `migrate` do schema
  `mcp`, etapa `mcp_registry` antes de `assistants`, e o serviço no lugar do `McpDirectory` vazio — e, de ponta a ponta, US1
  cen. 2 (MCP desabilitado deixa o Assistant indisponível) e US4 cen. 4 (Assistant de usuário com global não liberado é
  recusado), que dependem da 003 montada com este catálogo
- **008**: CRUD de MCPs em `/v1` e `/private/v1` e saúde por servidor
- **004**: catálogo e execução de tools com o cliente restrito

---

## Passada de 2026-10-22: imagens no resultado ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md); research R17)

**Goal**: a parte de imagem de um resultado MCP chega à 004 como `ToolResult.attachments`; tipo fora da lista ou acima
do teto vira a marca de omissão com motivo.

**Independent Test**: `tests/mcp/unit/test_results.py` e o transporte real contra o servidor MCP do SDK devolvendo
texto e PNG.

- [X] T049 `RemotePart.mime`/`data`; `_part` do adapter do SDK decodifica `ImageContent` (R17)
- [X] T050 `results.to_tool_result` com `max_attachment_bytes`: anexo na ordem e sem repetição; marca com motivo
  para tipo, tamanho e base64 inválido; o corte de texto não conta os anexos
- [X] T051 `McpService(max_attachment_bytes=)`, `DEFAULT_MAX_ATTACHMENT_BYTES` em `api.py`; teto do transporte com
  a folga de quatro anexos
- [X] T052 [P] Testes: unidade do resultado (PNG aceito, SVG e acima do teto recusados com motivo, inválido, repetição,
  texto cortado sem perder o anexo) e contrato do transporte HTTP real com uma tool que devolve PNG


## Incremento ADR-055

- [X] D01 Contratos e testes de delegação/isolamento antes do código.
- [X] D02 Implementar os seams confidenciais e falha fechada deste módulo.
- [X] D03 Validar regressões, types, lint e atualizar documentação operacional.

Validação ADR-055: suítes MCP/gateway/motor/HTTP com Postgres temporário; testes novos de isolamento, API e canal confidencial; mypy, Ruff e 69 contratos import-linter aprovados. Testes de transporte e destinos estáticos preservados.

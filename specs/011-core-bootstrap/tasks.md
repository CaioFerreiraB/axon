---

description: "Task list for 011 — bootstrap e composition root, Fases 1, 2 e 3"
---

# Tasks: Bootstrap e composition root — boot, perfis e plataforma em memória

**Input**: Design documents from `/specs/011-core-bootstrap/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos. A ordem de boot e as políticas de falha são requisito observável (FR-002, FR-003) e só se
demonstram por teste; SC-002, SC-003 e SC-004 são critérios desta fase.

**Organization**: **US1**, **US2 no perfil em memória** e **US3** (Fase 1 do roadmap), mais o `ai-core serve` que a
US1 exige para existir ([research.md](research.md) R5, R9). **Não** entram: subcomandos contribuídos por módulo (US4,
Fase 2), saúde agregada (US5, Fase 2) e perfil persistente — nem `health.py`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1, US2, US3)
- Todo caminho é relativo à raiz do repositório

## Path Conventions

- Código: `ai-core/packages/core/src/ai_core/bootstrap/`
- Testes: `ai-core/packages/core/tests/bootstrap/{unit,contract,integration}/`
- Configuração: `ai-core/packages/core/pyproject.toml` (dependência e ponto de entrada) e `ai-core/pyproject.toml`

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Criar `ai-core/packages/core/src/ai_core/bootstrap/__init__.py` com a docstring que declara a exceção do
  princípio XIII: esta é a única spec autorizada a importar `service.py` e `adapters/` de outros módulos
- [X] T002 Acrescentar `uvicorn>=0.53,<1` a `dependencies` e `[project.scripts] ai-core =
  "ai_core.bootstrap.cli:main"` em `ai-core/packages/core/pyproject.toml`; rodar
  `XDG_DATA_HOME=$HOME/.local/share uv sync` e conferir que o comando `ai-core` existe no ambiente
- [X] T003 Em `ai-core/pyproject.toml`, acrescentar `packages/core/tests/bootstrap` a
  `[tool.pytest.ini_options] pythonpath`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: as regras puras que o resto usa — configuração, perfis e a sequência

**⚠️ CRITICAL**: T004–T006 precedem a montagem da plataforma

- [X] T004 [US2] Implementar `ai-core/packages/core/src/ai_core/bootstrap/ports.py` e `settings.py` conforme
  [contracts/configuration.md](contracts/configuration.md): porta `ConfigSource` (`load() -> Settings`); `Settings`
  congelada com `profile`, `packs_file`, `assistants_file`, `ollama_base_url`, `trace_dir`, `host`, `port`,
  `shutdown_grace_seconds`, validando perfil desconhecido, porta fora de 1–65535 e prazo negativo com erro que nomeia
  o campo; adapters `EnvConfigSource` (variáveis `AI_CORE_*`, com os defaults da tabela) e `InMemoryConfigSource`
- [X] T005 [US2] Implementar `ai-core/packages/core/src/ai_core/bootstrap/profiles.py` conforme
  [contracts/profiles.md](contracts/profiles.md): a lista de portas exigidas como **dado** (`clock`, `trace`,
  `providers`, `pack_source`, `authenticator`, `request_ids`); `Profile` com uma fábrica por porta; `validate` que
  recusa perfil incompleto nomeando a porta; e os perfis `memory` (relógio do sistema, JSONL ou memória conforme
  `trace_dir`, provider do Ollama, entry points, autenticador anônimo, identificadores aleatórios) e `test` (relógio
  fixo, trace em memória, provider simulado, entry points, anônimo, identificadores sequenciais). Um **único** objeto
  de relógio atende as três portas de tempo (FR-008)
- [X] T006 [US1] Implementar `ai-core/packages/core/src/ai_core/bootstrap/lifecycle.py` conforme
  [contracts/boot-sequence.md](contracts/boot-sequence.md): `Stage` (nome, ação, `critical`), `StageOutcome`
  (`ok`/`degraded`/`failed` + motivo), `BootReport` (etapas na ordem, `ok`, `degraded`), o executor que roda a lista
  respeitando a política de cada etapa, o registro de recursos a liberar e o encerramento em **ordem inversa** —
  inclusive quando uma etapa crítica falha no meio. O executor **não** menciona nenhum módulo

---

## Phase 3: User Story 1 - Ordem de boot com falha fechada (Priority: P1) 🎯 MVP

**Goal**: o boot segue a ordem declarada, cada etapa falha conforme sua política, e o operador lê no relatório o que
falhou e por quê.

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/contract` passa com etapas de teste, sem plataforma.

### Tests for User Story 1 ⚠️

- [X] T007 [P] [US1] `ai-core/packages/core/tests/bootstrap/contract/test_boot_sequence.py`: os sete itens de
  [contracts/boot-sequence.md](contracts/boot-sequence.md), com etapas de teste — ordem, interrupção em etapa
  crítica, continuidade em etapa degradável, relatório nomeando etapa e motivo, encerramento inverso, desfazimento
  inverso quando etapa crítica falha, e uma etapa nova rodando sem mudança no executor
- [X] T008 [P] [US1] `ai-core/packages/core/tests/bootstrap/unit/test_settings.py`: os itens 1 e 2 de
  [contracts/configuration.md](contracts/configuration.md) — defaults, e recusa de perfil desconhecido, porta fora da
  faixa e prazo negativo, cada um nomeando a variável

### Implementation for User Story 1

- [X] T009 [US1] `ai-core/packages/core/src/ai_core/bootstrap/grants.py`: leitura do `assistants.yaml` conforme
  [contracts/configuration.md](contracts/configuration.md) e `ConfiguredGrants`, que cumpre a porta `GrantResolver`
  da 008 — resolve `<assistant>[/<modelo>]`, compõe os packs pelo Pack Registry, monta a `ModelPolicy` da 006 e
  levanta `AssistantNotFound` para Assistant desconhecido ou cujo pack está indisponível
- [X] T010 [US1] `ai-core/packages/core/src/ai_core/bootstrap/wiring.py`: `platform(profile=…, config=…)` montando,
  nas cinco etapas da fase, `PackRuntime` (002), `TraceService` (009), `ModelRoutingService` (006), `ExecutionService`
  (005) e a aplicação HTTP (008), e devolvendo a `Platform` congelada com `settings`, `profile`, `packs`, `trace`,
  `engine`, `app`, `report` e `aclose()`. É o único lugar do projeto que importa `service.py` e `adapters/` de outros
  módulos
- [X] T011 [US1] `ai-core/packages/core/src/ai_core/bootstrap/cli.py`: raiz `ai-core` com o subcomando `serve` —
  monta a plataforma, imprime o relatório de boot, serve a app com o servidor ASGI e encerra no sinal de parada,
  respeitando o prazo configurado. Sai com código não zero quando o boot falha. O servidor entra por parâmetro
  (default: o real), para que a suíte exercite o comando sem abrir porta. **O relatório DEVE avisar, em destaque,
  quando a autenticação em uso é anônima** — o perfil `memory` é o que mais parece produção, e subir sem autenticação
  achando que está protegido é o erro caro que este aviso evita
- [X] T011b [P] [US1] `ai-core/packages/core/tests/bootstrap/contract/test_cli_serve.py`: o comando monta a
  plataforma e chama o servidor injetado com a app e o endereço configurados; imprime o relatório com as cinco
  etapas; **imprime o aviso de autenticação anônima**; sai com código não zero — e **sem** chamar o servidor — quando
  a configuração é inválida; e `--help` lista o subcomando

---

## Phase 4: User Story 2 - Perfil de adapters por fase (Priority: P1)

**Goal**: o operador escolhe o perfil por configuração; perfil incompleto é recusado antes do boot; trocar de perfil
não muda módulo nenhum.

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/unit/test_profiles.py`.

- [X] T012 [P] [US2] `ai-core/packages/core/tests/bootstrap/unit/test_profiles.py`: os seis itens de
  [contracts/profiles.md](contracts/profiles.md) — cobertura das portas nos dois perfis, recusa de perfil incompleto
  nomeando a porta, recusa de perfil desconhecido, o **mesmo** objeto de relógio em motor, API e trace, provider
  simulado e trace de memória no `test`, e a escolha entre JSONL e memória no `memory` conforme `trace_dir`
- [X] T013 [P] [US2] `ai-core/packages/core/tests/bootstrap/unit/test_grants.py`: os itens 3 a 9 de
  [contracts/configuration.md](contracts/configuration.md) — YAML válido, recusas nomeando o campo, `flow` inexistente,
  id com e sem a parte do modelo, Assistant desconhecido e Assistant com pack indisponível

---

## Phase 5: User Story 3 - Plataforma inteira em memória (Priority: P1)

**Goal**: uma chamada monta a plataforma completa, sem rede e sem serviço externo, e uma conversa acontece por HTTP.

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/integration`.

- [X] T014 [P] [US3] `ai-core/packages/core/tests/bootstrap/integration/test_platform_test_profile.py`:
  `platform(profile="test")` devolve a plataforma montada com o `ai-generic` carregado; uma conversa completa
  acontece por HTTP, com e sem streaming; o trace da requisição tem começo, chamada de modelo, validação e fim; o
  relógio fixo torna `created` e a data de referência verificáveis; e nenhum adapter que fale com rede é instanciado
- [X] T015 [P] [US3] `ai-core/packages/core/tests/bootstrap/integration/test_boot_degradado.py` (nome com
  `degradado`, que o [quickstart.md](quickstart.md) usa no filtro): com um pack em erro na configuração, o boot
  conclui, a etapa `packs` aparece degradada com o pack nomeado, e um Assistant que não depende dele atende
  normalmente (SC-004)
- [X] T016 [US3] Rodar `uv run pytest packages/core/tests/bootstrap` até T007, T008 e T012–T015 passarem, e
  `uv run mypy` e `uv run ruff check packages` limpos

**Checkpoint**: a Fase 1 do roadmap está completa — a conversa ponta a ponta existe, montada por configuração

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T017 Acrescentar a `ai-core/pyproject.toml` os contratos de import-linter de [research.md](research.md) R11 —
  nenhum módulo do core importa `ai_core.bootstrap`, e cada módulo continua proibido de importar `service.py` e
  `adapters/` dos outros — e rodar `uv run lint-imports` até todos aparecerem como `KEPT`
- [X] T018 [P] Registrar em [research.md](research.md) R7 por que as suítes de 005 e 008 **não** passam a usar o
  perfil `test`: fariam os testes desses módulos dependerem da composition root, inversão que o próprio design evita
  ("a 008 não importa a 011") e que enfraqueceria o isolamento protegido pelo SC-001 da 005. A montagem manual lá é
  deliberada; o perfil serve a esta spec e às suítes de packs externos
- [X] T019 Executar as seções de [quickstart.md](quickstart.md) (verificação completa e cenários 1–4) e corrigir
  divergências entre o resultado e o "Esperado"
- [X] T020 [P] Atualizar a seção "Código" de `CLAUDE.md` (o módulo `ai_core/bootstrap/` existe, com boot por etapas
  declaradas, perfis `memory` e `test`, resolvedor de grant a partir de `assistants.yaml` e o comando `ai-core
  serve`; saúde agregada e subcomandos de módulo continuam para a Fase 2), a linha da 011 em `specs/README.md`
  (status "Fase 1 implementada (US1, US2 memória, US3)") e a linha da Fase 1 em `docs/roadmap.md`, que passa a estar
  concluída

---

## Fase 2 (2026-09-30): US2 (persistente), US4 (CLI), US5 (saúde) e autenticação real (FR-015)

Decisões em [plan.md](plan.md) ("Fase 2") e [research.md](research.md) R11–R20. Caminhos relativos a
`ai-core/packages/core/`; `bootstrap/` = `src/ai_core/bootstrap/`.

## Phase 7: Foundational da Fase 2 — configuração e perfis

- [X] T021 [P] Estender `tests/bootstrap/unit/test_settings.py` (contracts/configuration.md, "Fase 2"): cada variável
  nova com default; `persistent` sem `AI_CORE_DATABASE_URL`, `AI_CORE_OIDC_ISSUER` sem `AI_CORE_OIDC_AUDIENCE`,
  `AI_CORE_DEV_API_KEY` fora do formato `aic_<16 hex>_<segredo>` e `AI_CORE_DEV_API_KEY` no `persistent` recusados
  nomeando a variável — e nenhuma mensagem nem `repr(Settings)` contém o valor de um segredo
- [X] T022 Implementar em `bootstrap/settings.py` as variáveis de R18, o perfil `persistent`, as validações do T021 e
  `repr` sem segredos
- [X] T023 [P] Estender `tests/bootstrap/unit/test_profiles.py` (contracts/profiles.md, "Fase 2"): os três perfis
  atendem as portas exigidas; as fábricas do `persistent` constroem o pool **fechado** e os adapters Postgres sem
  conectar; o `test` não instancia nada que fale com rede; as credenciais exportadas (`TEST_SUBJECT`,
  `TEST_OIDC_TOKEN`, `TEST_API_KEY`, `TEST_ADMIN_GROUP`) autenticam pelos adapters do perfil
- [X] T024 Implementar em `bootstrap/profiles.py` a lista nova de portas exigidas, fábricas que recebem a configuração e
  as partes já construídas, os três perfis da tabela de contracts/profiles.md, as credenciais do perfil `test` (claims
  válidas no instante do relógio fixo) e a fábrica `conversation_ids` (R19); remover `ANONYMOUS_WARNING` e
  `anonymous_auth`

## Phase 8: User Story 2 — perfil persistente e autenticação real (Priority: P1)

**Independent Test**: `AI_CORE_TEST_POSTGRES_DSN=… uv run pytest packages/core/tests/bootstrap -k persistent`.

- [X] T025 [P] [US2] Criar `tests/bootstrap/integration/test_persistent_profile.py` (pulado sem
  `AI_CORE_TEST_POSTGRES_DSN`): o boot migra `assistants` e `http` e conclui; uma chave emitida por `AccessService`
  sobre o Postgres autentica numa plataforma **nova** sobre o mesmo banco; uma conversa aberta numa plataforma continua
  noutra; um Assistant de usuário criado sobrevive; com a URL apontando para uma porta fechada, o boot falha na etapa
  `adapters` nomeando `database` e o adapter, e nem o relatório nem a mensagem contêm a URL (US2 cen. 2) — usando
  `httpx.AsyncClient` com o ciclo de vida da app no laço do teste
- [X] T026 [P] [US2] Atualizar as suítes de `tests/bootstrap/` para a autenticação real: `test_platform_test_profile.py`
  e `test_boot_degradado.py` mandam `Authorization` com as credenciais exportadas; sem credencial é 401 (US2 cen. 5);
  `test_cli_serve.py` troca o aviso de anônimo pelo aviso de "sem chave de desenvolvimento nem OIDC" no `memory`
- [X] T027 [US2] Implementar em `bootstrap/wiring.py`: os armazenamentos e o verificador OIDC vindos do perfil;
  `AccessService` com eles e o `admin_group` do `assistants.yaml`; a chave de desenvolvimento semeada no `memory`;
  na etapa `adapters` do `persistent`, conferência de conexão e `migrate` de `assistants` e `http` num pool temporário
  (falha nomeia porta e adapter, sem a URL); o ciclo de vida da app — abrir o pool de serviço, agendar
  `ConversationService.expire` a cada `AI_CORE_CONVERSATION_EXPIRY_INTERVAL` segundos, cancelar e fechar no fim — e
  `conversation_retention` dos dias configurados; `Platform` com `assistants`, `access`, `routing` e `conversations`;
  e em `src/ai_core/http/adapters/app.py` o parâmetro opcional `lifespan` de `create_app` (toque declarado na 008, R14)
- [X] T028 [US2] Atualizar `bootstrap/cli.py` (`serve`): avisar em destaque quando o `memory` sobe sem chave de
  desenvolvimento nem OIDC; nenhum segredo em saída

## Phase 9: User Story 5 — saúde agregada (Priority: P2)

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/unit/test_health.py`.

- [X] T029 [P] [US5] Criar `tests/bootstrap/unit/test_health.py` (contracts/health.md) com checagens falsas: provider
  fora do ar → `degraded` nomeando o modelo e os demais saudáveis (US5 cen. 1); tudo bem → `ok` (cen. 2); banco fora →
  `down` (cen. 3); checagem que passa de 3 s vira item não saudável; segunda consulta em 15 s não repete checagens; e
  atualizar `tests/http/contract/test_private_routes.py` — 503 só em `down`, 200 em `degraded`
- [X] T030 [US5] Implementar `bootstrap/health.py` (`PlatformHealth`: itens `database`, `boot:*`, `pack:*`,
  `assistant:*`, `model:*`, timeout de 3 s por item, cache de 15 s) e, na 008 (toque declarado),
  `HealthItem.critical`, `HealthReport.status` (`ok`/`degraded`/`down`) em `src/ai_core/http/domain/records.py`, o JSON
  com `critical` em `domain/private.py` e a rota de saúde em `adapters/private.py` respondendo 503 só em `down`

## Phase 10: User Story 4 — linha de comando única (Priority: P2)

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/contract/test_cli_commands.py`.

- [X] T031 [P] [US4] Criar `tests/bootstrap/contract/test_cli_commands.py` (contracts/cli.md): `--help` lista todos os
  subcomandos (US4 cen. 1); `packs check` com pack incompatível sai com 1 e com `packs.yaml` malformado com 2;
  `assistants validate` com Assistant inválido sai com 1 e com `assistants.yaml` malformado com 2 (US4 cen. 2 e
  Independent Test); `keys create` imprime a chave e avisa que o perfil não é persistente; `health` sai com 0/1/2;
  nenhum subcomando além de `serve` chama o servidor injetado
- [X] T032 [US4] Implementar em `bootstrap/cli.py` a raiz com a lista de registro dos subcomandos (R17), chamando as
  funções de `ai_core.packs.adapters.cli`, `ai_core.assistants.adapters.cli` e `bootstrap/health.py`; `packs` monta só
  configuração, adapters e packs; `keys` abre e fecha o armazenamento no próprio laço

## Phase 11: Polish da Fase 2

- [X] T033 Rodar a seção "Fase 2" do [quickstart.md](quickstart.md) e a verificação completa (`uv run pytest` com e sem
  `AI_CORE_TEST_POSTGRES_DSN`, `uv run mypy`, `uv run ruff check packages`, `uv run lint-imports`), incluindo o roteiro
  manual com `ai-core keys create` e `ai-core serve` no `persistent`
- [X] T034 [P] Atualizar `CLAUDE.md` ("Código"), a linha da 011 em `specs/README.md` e `docs/roadmap.md` (a Fase 2 fica
  concluída: 003 US1–US7, 002 US4, 008 US2–US5 e US7, 011 US2, US4, US5)

---

## Fase 3 (2026-10-02): registry MCP, gateway de tools e `agentic` (research R21–R33)

Encaixe da 007, da 004 e do `agentic` da 005 nos três perfis, com as três clarificações de 2026-10-02. Caminhos
relativos a `ai-core/packages/core/`. Testes primeiro em cada bloco; marcas `us1`–`us5` pela história. Fora: rotas
HTTP de MCP e `finish_reason` por gravidade (008), papel `controller` na validação (003).

## Phase 12: Foundational da Fase 3 — configuração e perfis

**⚠️ CRITICAL**: nenhuma story da Fase 3 antes desta fase

- [X] T035 [P] Estender `tests/bootstrap/unit/test_settings.py` (contracts/configuration.md, "Fase 3"): defaults
  `mcp_file=None`, `mcp_discovery_ttl=300.0`, `tool_timeout_ms=30000`, `tool_max_response_bytes=16384`; o
  `EnvConfigSource` lê `AI_CORE_MCP_FILE`, `AI_CORE_MCP_DISCOVERY_TTL`, `AI_CORE_TOOL_TIMEOUT_MS` e
  `AI_CORE_TOOL_MAX_RESPONSE_BYTES`; recusa com `ConfigurationError` **nomeando a variável** para TTL `≤ 0`, prazo fora
  de "1 000–300 000" e tamanho fora de "1 024–1 048 576"; com `AI_CORE_MCP_SECRET_X=segredo-x` no ambiente, o texto
  `segredo-x` não aparece em `repr(Settings)`
- [X] T036 Implementar em `src/ai_core/bootstrap/settings.py` os quatro campos e as validações do T035 (constantes
  `DEFAULT_MCP_DISCOVERY_TTL = 300.0`, `DEFAULT_TOOL_TIMEOUT_MS = 30_000`, `DEFAULT_TOOL_MAX_RESPONSE_BYTES = 16_384`),
  e a leitura no `EnvConfigSource` (depende de T035)
- [X] T037 [P] Estender `tests/bootstrap/unit/test_profiles.py` (contracts/profiles.md, "Fase 3"): `REQUIRED_PORTS`
  termina com `mcp_store`, `mcp_dns`, `mcp_transports`, `mcp_secrets`, `mcp_cache`, `audit`; `STORAGE_PORTS` contém `mcp_store` e
  `audit`; nos três perfis, com `parts` contendo `settings`, `clock`, `database` e `mcp_config`, cada porta nova é
  construída com o adapter da tabela de R22 (`memory`: transportes `{"http", "sse"}`; `persistent`: `{"http", "sse",
  "stdio"}`, armazenamento e auditoria Postgres sobre o pool; `test`: `{"http", "sse", "stdio"}` com o **mesmo**
  `ScriptedMcpTransport` sem servidores); o provider `ollama` do perfil `test` devolve `{"action": "answer"}` em
  `chat(..., stream=False)` e continua fazendo streaming de `"Bras"`, `"ília"`
- [X] T038 Implementar em `src/ai_core/bootstrap/profiles.py` as seis portas nos três perfis (R22): `mcp_dns`
  (`SystemDnsResolver` no `memory`/`persistent`, `FixedDnsResolver` vazio no `test`); transportes HTTP com
  `parts["mcp_dns"]` e os `internal_hosts`/`allowed_hosts` de `parts["mcp_config"].network`, `stdio` só no
  `persistent`; `EnvSecretResolver` no `memory`/`persistent` e `InMemorySecretResolver` no `test`;
  `InMemoryDiscoveryCache(parts["clock"])`; `PostgresServerStore`/`PostgresAuditLog` sobre `parts["database"]`; o
  `ScriptedProvider` do `test` com `content='{"action": "answer"}'` (depende de T036, T037)

**Checkpoint**: configuração e perfis da Fase 3 prontos

---

## Phase 13: User Story 1 — boot com registry MCP e gateway de tools (Priority: P1)

**Goal**: a sequência ganha `mcp_registry`; o motor recebe o gateway e oferece `agentic`; a 003 valida contra o
registry real.

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/contract/test_boot_sequence.py -m us1` — itens
13–18 de contracts/boot-sequence.md.

### Tests for User Story 1 ⚠️

- [X] T039 [P] [US1] Estender `tests/bootstrap/contract/test_boot_sequence.py` com os itens 13–18 de
  [contracts/boot-sequence.md](contracts/boot-sequence.md): etapas na ordem `configuration, adapters, packs,
  mcp_registry, engine, assistants, api`; `AI_CORE_MCP_FILE` com YAML malformado → boot para em `configuration`
  nomeando o arquivo; entrada com problema (ex.: sem `policy.allowed_tools`) → `mcp_registry` degradada nomeando o
  alias, boot concluído; `engine.flows() == {"chat", "agentic"}` nos perfis `memory` e `test`; com
  `logging.getLogger().setLevel(DEBUG)` antes do boot, `logging.getLogger("mcp.client.streamable_http")
  .getEffectiveLevel() == INFO` depois (restaurar a raiz no fim); Assistant que declara alias MCP inexistente fica
  indisponível no relatório da etapa `assistants`, e um que declara alias do `mcp.yaml` fica disponível; servidor global
  com `auth.credential: falta` sem `AI_CORE_MCP_SECRET_FALTA` → `mcp_registry` degradada nomeando o alias e a referência,
  e, com `AI_CORE_MCP_SECRET_OUTRA=segredo-outra` no ambiente, `segredo-outra` não aparece no relatório de boot (FR-009)

### Implementation for User Story 1

- [X] T040 [US1] Em `src/ai_core/bootstrap/wiring.py` (R23–R26, R30): `STAGE_MCP = "mcp_registry"`; a etapa
  `configuration` guarda `parts["mcp_config"]` (`YamlMcpConfigSource(settings.mcp_file)` ou `McpConfig()`); a etapa
  nova `_mcp_registry` (crítica, entre `packs` e `engine`) monta `parts["mcp"] = mcp_service(parts,
  store=parts["mcp_store"])`, fixa `logging.getLogger("mcp").setLevel(logging.INFO)` e degrada com `"; "`.join de
  `"mcp '<alias>': <problema>"` das entradas com `problem` e de `"mcp '<alias>': credencial '<ref>' ausente
  (AI_CORE_MCP_SECRET_<REF>)"` para cada referência que `parts["mcp_secrets"].resolve(ref)` não resolve —
  `credential_ref` de `globals()` (na sessão de armazenamento) e os `secrets` das entradas `stdio` do arquivo, sem
  nunca imprimir valor; `mcp_service(parts, *, store)` monta o `McpService` com
  `config=parts["mcp_config"]`, `transports=parts["mcp_transports"]`, `secrets`, `cache`, `clock` e
  `discovery_ttl=timedelta(seconds=settings.mcp_discovery_ttl)`; `capabilities_service(parts, *, audit, mcp)` monta o
  `CapabilityService` com `pack_tools=parts["packs"]`, o trace, o relógio e `GatewayLimits(timeout_ms=…,
  max_response_bytes=…)`; a etapa `engine` guarda `parts["capabilities"]` e passa `capabilities=` ao
  `ExecutionService`; `assistants_service(parts, *, users, mcp)` usa o `mcp` dado no lugar do `EmptyMcpDirectory`
  (servidor: `parts["mcp"]`; `_validate` e `platform_health`: `mcp_service(parts, store=session["mcp_store"])`);
  `_migrate` acrescenta `mcp_schema.migrate` e `capabilities_schema.migrate` depois de `http`; `Platform` ganha `mcp` e
  `capabilities`; docstring do módulo com a ordem nova (depende de T038)
- [X] T041 [US1] Em `src/ai_core/bootstrap/cli.py`: `_validate` (assistants validate) passa o `mcp` da sessão a
  `assistants_service`, e o `STAGE_MCP` entra nos imports onde for preciso (depende de T040)

**Checkpoint**: `ai-core serve` sobe com registry e gateway; `agentic` aparece nos flows

---

## Phase 14: User Story 2 — perfil persistente com `mcp` e `capabilities` (Priority: P1)

**Goal**: no `persistent`, registry e auditoria em Postgres, migrados no boot.

**Independent Test**: `AI_CORE_TEST_POSTGRES_DSN=… uv run pytest packages/core/tests/bootstrap/integration/
test_persistent_profile.py -m us2`.

- [X] T042 [P] [US2] Estender `tests/bootstrap/integration/test_persistent_profile.py` (pulado sem
  `AI_CORE_TEST_POSTGRES_DSN`): o boot cria os schemas `mcp` e `capabilities` (consulta a `information_schema`);
  `engine.flows()` tem `agentic`; um servidor criado por `platform.mcp.create_global(...)` dentro do ciclo de vida da
  app (`TestClient` aberto) aparece num **segundo** boot, lido pela sessão de armazenamento (`async with
  storage(parts) as session: await mcp_service(parts, store=session["mcp_store"]).globals()`, R13); um Assistant do `assistants.yaml` que declara esse alias fica
  disponível na validação do segundo boot (depende de T040)

---

## Phase 15: User Story 3 — trocas de porta e `agentic` + MCP ponta a ponta (Priority: P1)

**Goal**: a suíte programa controller e servidores MCP na montagem; uma conversa `agentic` com tool de MCP atravessa a
API sem rede (US3 cen. 3, clarificação 2).

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/integration/test_platform_agentic_mcp.py`.

### Tests for User Story 3 ⚠️

- [X] T043 [P] [US3] Criar `tests/bootstrap/unit/test_profile_overrides.py` (contracts/profiles.md, "Trocas de
  porta"): `platform(profile="test", overrides={"request_ids": fixo})` usa o adapter dado; uma troca de `clock` é a
  que as fábricas seguintes recebem (`parts["clock"]` é o relógio dado e a data de referência de uma execução é a dele); porta desconhecida → boot falha em `adapters` com `ConfigurationError` nomeando
  a porta; `database`, `api_keys`, `user_assistants`, `conversations`, `mcp_store` ou `audit` → idem
- [X] T044 [P] [US3] Criar `tests/bootstrap/integration/test_platform_agentic_mcp.py` (US3 cen. 3), sem rede: em
  `tmp_path`, `assistants.yaml` com um Assistant `pesquisador` (`flow: agentic`, `packs: [generic]`, `mcp: [demo]` —
  o campo de aliases MCP do formato da 003 —, `models` com `generation: ollama/qwen3:1.7b` e `controller:
  ctrl/controlador`, `allow: ["ollama/*", "ctrl/*"]`) e `mcp.yaml` com `demo` (`transport: http`, `endpoint:
  https://demo.test/mcp`, `policy.allowed_tools: [eco]`); `platform(profile="test", config=…, overrides={"providers":
  {"ollama": ScriptedProvider(deltas=("Pronto.",)), "ctrl": ScriptedController([tool_action("demo.eco",
  texto="olá"), ANSWER])} — `ScriptedController`, `tool_action` e `ANSWER` importados de `graph_testkit`, como as
  suítes da 008 já fazem, "mcp_transports": {"http": t, "sse": t, "stdio": t}})` com `t =
  ScriptedMcpTransport({"https://demo.test/mcp": ScriptedServer(tools=(RemoteTool eco,))})`; `POST
  /v1/chat/completions` com `Bearer TEST_OIDC_TOKEN` e `model: "pesquisador"` → 200, conteúdo `"Pronto."`,
  `finish_reason: "stop"`; `t.calls` tem `call_tool:eco`; o trace da requisição (`platform.trace`) tem
  `controller_decision` e `tool_call`; sem trocas, o mesmo Assistant (com `controller: ollama/qwen3:1.7b`) responde
  200 com o controller simulado respondendo direto

### Implementation for User Story 3

- [X] T045 [US3] Em `src/ai_core/bootstrap/wiring.py` (R31): `platform(..., overrides: Mapping[str, Any] | None =
  None)`; a etapa de adapters recusa nome fora de `REQUIRED_PORTS`, `database` e `STORAGE_PORTS` com
  `ConfigurationError` nomeando a porta, e constrói o perfil com o valor trocado no lugar da fábrica (as fábricas
  seguintes enxergam a troca) — pela `Profile.build_all(settings, parts, overrides=…)` em `profiles.py` (depende de
  T040)

**Checkpoint**: a conversa `agentic` + MCP ponta a ponta passa no perfil `test`, sem rede

---

## Phase 16: User Story 5 — saúde com servidores MCP (Priority: P2)

**Goal**: um item não crítico por servidor MCP global (clarificação 1).

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/unit/test_health.py -m us5`.

- [X] T046 [P] [US5] Estender `tests/bootstrap/unit/test_health.py` (contracts/health.md, "Fase 3") com um registry
  falso (`globals()` e `check(alias)`): servidor fora do ar → `degraded`, item `mcp:<alias>` com `critical=False` e o
  motivo; servidor que não anuncia uma tool da allowlist → item não saudável nomeando a tool; `globals()` que levanta →
  item `mcp` não saudável e não crítico; `check` que passa do prazo → item com "sem resposta em 3 s"; segunda consulta
  dentro de 15 s não chama `check`; sem registry (`mcp=None`), nenhum item de MCP
- [X] T047 [US5] Em `src/ai_core/bootstrap/health.py`: `PlatformHealth(..., mcp: McpRegistry | None = None)` e os itens
  de R28 em paralelo com os demais; `wiring.platform_health` passa o `mcp_service` da sessão; docstring com os itens
  novos (depende de T046 e T040)

---

## Phase 17: User Story 4 — `ai-core audit` (Priority: P2)

**Goal**: o operador lista as escritas auditadas pela 004.

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/contract/test_cli_commands.py -m us4`.

- [X] T048 [P] [US4] Estender `tests/bootstrap/contract/test_cli_commands.py` (contracts/cli.md, "Fase 3"): `--help`
  lista `audit`; `audit --since ontem` → código 2; `audit` no perfil `test` → 0 e nenhuma linha de registro; e, em
  `tests/bootstrap/integration/test_persistent_profile.py` (com Postgres), um registro aberto e fechado pelo
  `PostgresAuditLog` aparece em `ai-core audit` sem o resultado, e com `--results` com ele
- [X] T049 [US4] Em `src/ai_core/bootstrap/cli.py` (R29): `Command(path=("audit",), …)` com os argumentos do contrato da
  004; sobe com `until=STAGE_ENGINE` (o gateway precisa do Trace Sink, que nasce em `engine`), abre a sessão de armazenamento, monta `capabilities_service(parts,
  audit=session["audit"], mcp=mcp_service(parts, store=session["mcp_store"]))` e chama `audit_command` da 004; boot
  que falha → 1 (depende de T048 e T040)

---

## Phase 18: Polish da Fase 3

- [X] T050 Rodar a seção "Fase 3" do [quickstart.md](quickstart.md) e corrigir divergências entre o resultado e o
  "Esperado"; e, em `tests/bootstrap/contract/test_cli_serve.py`, conferir que pelo caminho do `serve` (servidor
  falso de `main(argv)`) o nível efetivo de `mcp.*` continua `INFO` depois de o servidor configurar o logging
- [X] T051 [P] Atualizar a linha da 011 em `specs/README.md` (Fase 3 implementada: registry MCP, gateway, `agentic`,
  `audit`), a seção "Código" de `CLAUDE.md` (o que estava "Falta ligar" na 007, na 004 e na 005 passa a ligado pela 011;
  `Platform.mcp` para a 008; trocas de porta) e a nota "Depois desta fase" deste arquivo
- [X] T052 Verificação completa a partir de `ai-core/`: `uv run pytest`, `uv run mypy`, `uv run ruff check packages`,
  `uv run lint-imports`, e a suíte com `AI_CORE_TEST_POSTGRES_DSN`

---

## Fase 9 (2026-10-14): encaixe da identidade, da administração e dos destinos (research R36–R44)

**Escopo**: US6. Caminhos relativos a `ai-core/packages/core/`. Depende das passadas da Fase 9 da 012, 003, 009 (+006)
e 008.

## Phase 19: User Story 6 — A plataforma sobe com identidade, administração e destinos do trace (Priority: P2)

> **Andamento (2026-10-14)**: incremento 9.1 — a **identidade** (variáveis e validações da R36 que são da 012, as
> sete portas `identity_*`, a etapa crítica `identity` com o `JwksOidcVerifier` sobre o JWKS em processo, o router da
> 012 no app, o item `identity` na saúde, o expurgo, a carga das chaves no ciclo de vida e os comandos `users …` e
> `identity keys rotate`). Incremento 9.2 — o **resto da US6**: o grupo `AI_CORE_LANGFUSE_*` (tudo ou nada, host
> validado), `AI_CORE_USAGE_TIMEZONE` e `AI_CORE_USAGE_RETENTION_DAYS`; as portas `system_overrides`, `usage_store`,
> `price_store`, `destination_settings` (armazenamento) e `langfuse_transport` (simulado no `test`) nos três perfis
> (`bootstrap/observability.py`); a migração `observability`; o `TraceService` com o uso e o Langfuse e a captura lida
> do `DestinationService`; a origem do processo (`platform(origin=…)`, `evaluation` no `ai-core eval run`, que grava o
> lote na sessão própria); uma chave mestra por processo para a 012 e a 009 (`shared_master_key`); as tarefas
> `usage.flush` (2 s) e `usage.purge` (diária), os ajustes dos destinos lidos quando o pool de serviço abre e o último
> lote gravado antes de fechar; a saúde com os modelos efetivos e os itens `trace:usage` e `trace:langfuse`; e a
> superfície `/admin/v1` (`admin_seams`, `instance`). A CLI da R42 é a do incremento 9.1
> (`contract/test_cli_identity.py`).

### Tests for User Story 6

- [X] T053 [P] [US6] `tests/bootstrap/unit/test_settings_phase9.py`: as variáveis e os padrões de
  [contracts/configuration.md](contracts/configuration.md) (Fase 9); cada erro que para o boot nomeia a variável e
  nunca mostra o valor da chave mestra
- [X] T054 [P] [US6] `tests/bootstrap/unit/test_profiles_phase9.py`: as portas novas em `REQUIRED_PORTS` e
  `STORAGE_PORTS` nos três perfis; `test` sem identidade continua aceitando `TEST_OIDC_TOKEN`; com identidade, semeia
  `TEST_ADMIN_USERNAME`
- [X] T055 [P] [US6] `tests/bootstrap/integration/test_boot_phase9.py`: cenários 1–5 da US6 (chave mestra ausente no
  `persistent`; emissor duplo; admin inicial uma vez; Langfuse fora do ar não impede o boot e aparece na saúde; suíte de
  pack com o perfil `test`)
- [X] T056 [P] [US6] `tests/bootstrap/integration/test_platform_identity_admin.py` (R43, SC-007)
- [X] T057 [P] [US6] `tests/bootstrap/contract/test_cli_identity.py` (incremento 9.1): `ai-core users …` e `ai-core identity keys rotate`
  com a identidade ligada e desligada

### Implementation for User Story 6

- [X] T058 [US6] `bootstrap/settings.py`: as variáveis e validações de R36
- [X] T059 [US6] `bootstrap/profiles.py`: as fábricas das portas novas nos três perfis (R38) e o `test` de R39
- [X] T060 [US6] `bootstrap/wiring.py`: migrações de `identity` e `observability`; etapa `identity` (R37);
  `AccessService` com `OidcAudiences` e o `CallableJwksSource`; `AssistantsService` com o `SystemOverrideStore`;
  `TraceService` com os destinos e a origem do processo (R40); `create_app` com `admin_seams`, `instance` e o router da
  012; tarefas periódicas e o `aclose()` que esvazia os destinos
- [X] T061 [US6] `bootstrap/health.py` (R41) e `bootstrap/cli.py` (R42)
- [X] T062 [US6] Rodar T053–T057 e a suíte inteira do core até verde, com o Postgres de teste

## Phase 20: Polish da Fase 9

- [X] T063 [P] `CLAUDE.md` e `specs/README.md`: a Fase 9 no core (identidade, administração, sobreposições, uso e
  Langfuse) e o que falta (console 013, instalação 002)
- [ ] T064 Verificação completa (`pytest`, `mypy`, `ruff`, `lint-imports`, Postgres) e, **com aprovação do
  mantenedor**, release `0.6.0` (tag `v0.6.0`) antes da passada da 002 (R44)

## Dependencies & Execution Order

### Phase Dependencies

**Fase 3**: T035 → T036; T037 → T038 (depois de T036) — bloqueiam as stories. US1: T039 → T040 → T041. Depois de
T040: US2 (T042), US3 (T043 ∥ T044 → T045), US5 (T046 → T047) e US4 (T048 → T049, depois de T041, mesmo `cli.py`).
Polish por último (T051 em paralelo).

**Fase 2**: T021 → T022; T023 → T024 (depois de T022) — bloqueiam as stories. US2: T025 ∥ T026, depois T027 → T028;
US5: T029 → T030 (depois de T027, que monta a plataforma com `routing` e `access`); US4: T031 → T032 (depois de T028 e
T030, mesmo `cli.py`). Polish por último.


- **Setup (Phase 1)**: T001 e T002 primeiro; T003 em paralelo
- **Foundational (Phase 2)**: T004 → T005; T006 em paralelo com os dois
- **US1 (Phase 3)**: depende de Setup + Foundational; T009 → T010 → T011
- **US2 (Phase 4)** e **US3 (Phase 5)**: dependem de T010
- **Polish (Phase 6)**: T017 depois de T010; T019 depois de T016; T018 e T020 em paralelo

### Parallel Opportunities

- T007 e T008 em paralelo; T012 e T013 em paralelo; T014 e T015 em paralelo
- T018 e T020 em paralelo com qualquer tarefa concluída

---

## Implementation Strategy

### MVP (US1, US2 e US3 — o escopo desta fase)

1. Phase 1 e 2: esqueleto, dependência, configuração, perfis e sequência
2. Phase 3: grant, montagem e comando
3. Phases 4 e 5: perfis e plataforma completa
4. **PARE e VALIDE**: quickstart — inclusive subir `ai-core serve` com Ollama de verdade e conversar por `curl`
5. Phase 6: fronteiras de import, limpeza das suítes, documentação

### Depois desta fase

- Fase 2: a 003 assume `assistants.yaml` e fornece autenticador e resolvedor reais; entram os subcomandos de módulo
  (US4), a saúde agregada (US5) e o perfil persistente
- Fase 3 (Phases 12–18 acima): etapa de registry MCP (007) e gateway (004) entram na lista, sem mudar a sequência;
  a porta de checkpoint (005) ficou adiada até haver retomada
- Depois da Fase 3 da 011: rotas de MCP e `finish_reason` por gravidade (008); papel `controller` na validação (003)

---

## Passada de 2026-10-20: identidade Axon — US7 ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md), [ADR-038](../../docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md); research R46–R53)

**Goal**: distribuição `axon-ai` 0.7.0rc1, workspace `axon-ai/`, import `axon_ai` em todos os módulos, comando `axon`
com `--version`, prefixo `AXON_` com a recusa de `AI_CORE_*`, nome padrão "Axon", pool `axon`; CI e console verdes.

**Independent Test**: [quickstart.md, "Fase 9, incremento 9.5"](quickstart.md) — `axon --version`, `serve` com
`AXON_*`, recusa com `AI_CORE_PROFILE`, `import ai_core` falha; suítes do workspace e da console verdes.

> A T064 acima (release `0.6.0`) não será executada: a linha 0.6.0 terminou no rc6 com o nome antigo, e o próximo
> release é `v0.7.0-rc1`, depois da passada da 013 (ADR-037, item 4).

### Setup (renome mecânico — bloqueia o resto)

- [X] T065 [US7] Linha de base antes do renome: `git grep -cw agentic -- . ':!ai-scouting' ':!agentic-deploy'` (contagem
  a preservar, R47) e a lista dos literais `"ai-core"` em `ai-core/packages/core/src` (R47: só `prog`, a versão e o pool
  são da 011)
- [X] T066 [US7] `git mv ai-core axon-ai` e `git mv axon-ai/packages/core/src/ai_core axon-ai/packages/core/src/axon_ai`
  (R46); apagar `__pycache__` e `.venv` velhos do workspace movido se o `uv` reclamar
- [X] T067 [US7] Aplicar o script do R47 (`rename011.py` no scratchpad) a: `axon-ai/**` (arquivos de texto versionados,
  menos `uv.lock`, `package-lock.json`, `node_modules/`, `*/CHANGELOG.md`), `.github/workflows/*.yml`, os documentos vivos
  das specs 001–010, 012 e 013 (`spec.md`, `design.md`, `data-model.md`, `quickstart.md`, `contracts/**`),
  `specs/README.md`, `PRODUCT.md` e `.impeccable/surfaces/ai-core-console.md` — nunca `research.md`, `plan.md`,
  `tasks.md`, `checklists/`, `docs/`, `specs/1xx-*`, `CLAUDE.md`, `.specify/`, submódulos nem os documentos da 011 (já
  escritos nesta passada)
- [X] T068 [US7] À mão (R46, R47): `axon-ai/packages/core/pyproject.toml` com `name = "axon-ai"`, `version = "0.7.0rc1"`,
  `description = "Runtime genérico da plataforma Axon (monolito modular; specs 002–009, 011, 012)."` e o script `axon`;
  `axon-ai/pyproject.toml` (comentário da raiz e contratos do import-linter com `axon_ai`);
  `axon-ai/packages/core/src/axon_ai/__init__.py` ("axon-ai: runtime genérico da plataforma Axon, …"); `uv lock` em
  `axon-ai/`
- [X] T069 [US7] Revisar os resíduos: `git grep -nE "ai_core|ai-core|AI_CORE" -- . ':!ai-scouting' ':!agentic-deploy'`
  fora dos caminhos de histórico — cada um tem de ser protegido do R47 (de outra passada) ou da recusa; e `git grep -n
  "axon_ai\.packs\|audiência.*axon\|axon-ai:8000\|axon-ai-admin"` sem ocorrência indevida; contagem do `agentic` igual à
  da T065

### Tests (antes de T073–T075)

- [X] T070 [P] [US7] `axon-ai/packages/core/tests/bootstrap/unit/test_settings_legacy.py` (R53): `EnvConfigSource` com
  `AI_CORE_PROFILE`; com `AI_CORE_FOO` (desconhecida) → linha `AI_CORE_FOO → AXON_FOO`; com `AI_CORE_PROFILE=""`
  (vazia); com `AI_CORE_PROFILE` e `AXON_PROFILE` juntas; com duas antigas, linhas em ordem; nenhum valor na mensagem;
  `AI_COREX`, `MY_AI_CORE_URL` e `AI_SCOUTING_INDEX` aceitas (US7 cen. 3, 4; casos de borda)
- [X] T071 [P] [US7] `axon-ai/packages/core/tests/bootstrap/contract/test_cli_commands.py` (R53): `main(["--version"])`
  imprime `axon-ai <importlib.metadata.version("axon-ai")>` e sai com 0 (`SystemExit`) sem ler configuração; um
  subcomando (`health`) com `AI_CORE_PROFILE` no ambiente sai com 1 e a linha `AI_CORE_PROFILE → AXON_PROFILE`; a ajuda
  começa com `usage: axon`; sem metadados (`importlib.metadata.version` simulado levantando
  `PackageNotFoundError`), `axon-ai desconhecida` (US7 cen. 1, 3, 7; caso de borda)
- [X] T072 [P] [US7] `axon-ai/packages/core/tests/bootstrap/unit/test_core_old_name_absent.py` (o nome `test_no_old_name.py` colide com o
  teste da 001 na coleta do pytest):
  `importlib.util.find_spec("ai_core") is None` (FR-022); nome padrão "Axon" em
  `tests/bootstrap/unit/test_settings_phase9.py` e no `me` de `tests/bootstrap/integration/test_platform_identity_admin.py`
  (US7 cen. 5); o pool do `persistent` criado (fechado) com `name == "axon"` em
  `tests/bootstrap/unit/test_profiles.py` (FR-027)

### Implementation

- [X] T073 [US7] `axon-ai/packages/core/src/axon_ai/bootstrap/settings.py` (R48, R50): `PREFIX = "AXON_"` (vem da
  T067), `LEGACY_PREFIX: Final = "AI_CORE_"`, a recusa no início de `EnvConfigSource.load()` com a mensagem do
  contracts/configuration.md, `DEFAULT_DISPLAY_NAME = "Axon"`; mensagem da `AXON_DEV_API_KEY` citando `axon keys`
- [X] T074 [US7] `axon-ai/packages/core/src/axon_ai/bootstrap/cli.py` (R49): `prog="axon"`, `description="Axon — linha
  de comando do operador"`, `--version` com `axon-ai {_core_version()}`, `_core_version()` lendo `"axon-ai"`; ajuda do
  `--profile` com `AXON_PROFILE`
- [X] T075 [US7] `axon-ai/packages/core/src/axon_ai/bootstrap/profiles.py` (R50): `name="axon"` no pool

### Integration e verificação

- [X] T076 [US7] CI e console (R52): conferir `.github/workflows/*.yml` (filtros `axon-ai/**`, `working-directory`,
  `AXON_TEST_POSTGRES_DSN`, `uv run axon …`) e `axon-ai/console/` (`AXON_UPSTREAM` no `vite.config.ts`,
  `playwright.config.ts`, `e2e/serve_nginx.sh` e `deploy/nginx.conf.template`; imports do `e2e/serve_platform.py`)
- [X] T077 [US7] Suítes (a partir de `axon-ai/`): `uv sync && uv run pytest && uv run mypy && uv run ruff check packages
  && uv run lint-imports`; `uv run python packages/contracts/tools/check_clean_env.py`; contratos em Python 3.12;
  conformidade Postgres com `AXON_TEST_POSTGRES_DSN`; `axon-generic` (ainda `ai-generic`) em ambiente limpo; a console
  (`npm ci && npm run typecheck && npm run lint && npm test`) e o e2e (`npm run e2e`)
- [X] T078 [US7] Quickstart da US7 à mão: `axon --version`, `serve` + saúde, recusa com `AI_CORE_PROFILE`, `import
  ai_core` ausente
- [X] T079 [P] [US7] `specs/README.md` (linha da 011 com a US7, diagrama `axon-ai`) e `docs/roadmap.md` (andamento do
  9.5: 011 feita)

### Dependencies (US7)

T065 → T066 → T067 → T068 → T069 (bloqueiam o resto). Testes T070 ∥ T071 ∥ T072, depois T073 → T074 → T075 (T074
depende do `settings` da T073 para a recusa). T076 depois de T069. T077 depois de tudo; T078 depois de T077; T079 em
paralelo com T077.

### Notas da execução (US7)

- A substituição alcançou os testes do corte seco da 001, que usam de propósito `ai-core-contracts`
  (`tests/unit/test_distribution_check.py`, `tests/boundary/test_no_old_name.py`); foram restaurados como estavam.
- Também corrigidos à mão: o grupo `ai_core.packs` no `entry_points.txt` sintético do `packs_testkit.py` e nos exemplos
  de `entry_points(group=…)` da 002 e da 010; os nomes da instalação na 002 (`contracts/installation.md` inteiro, o
  serviço `ai-core` do compose, `/opt/ai-core`, a imagem de exemplo), que mudam na passada dela; o `contracts.yml`, cuja
  linha de base é uma tag com a pasta `ai-core/` (procura `axon-ai/`, depois `ai-core/`).
- `ruff format` e Prettier redistribuíram uma linha em `observability/service.py` e duas na console (nomes mais curtos).

---

## Correção de 2026-10-21: `axon health` e a identidade (FR-012; research R34)

- [X] T080 [US6] `axon-ai/packages/core/tests/bootstrap/integration/test_platform_identity.py`: no `persistent` com a
  identidade, contra o Postgres, a saúde com a identidade da plataforma dá `identity` em falha (o defeito) e, com
  `session_identity`, `identity` ok e `status` diferente de `down`. Visto falhar antes da correção (`session_identity`
  inexistente)
- [X] T081 [US6] `axon-ai/packages/core/src/axon_ai/bootstrap/wiring.py`: `platform_health(…, identity=None)` e
  `session_identity(parts, session)`; `bootstrap/cli.py` (`_check`): a saúde de `axon health` com
  `session_identity`. Suítes: workspace 3290 passed, 193 skipped; com `AXON_TEST_POSTGRES_DSN`, 3472 passed, 11 skipped;
  mypy, ruff e import-linter (69 kept) limpos

---

## Passada de 2026-10-21: o pack prepara os próprios dados (FR-028; [ADR-041](../../docs/adr/ADR-041-o-pack-prepara-os-proprios-dados-no-build.md); research R54)

- [X] T082 Testes primeiro: `AXON_PACKS_DATA_DIR` em `tests/bootstrap/unit/` (lido como `Path`; ausente ou vazio →
  `None`); em `tests/bootstrap/contract/test_cli_commands.py`, `packs prepare` com um pack em memória: 0 e o diretório
  criado; 2 com `packs.yaml` malformado; `axon --help` com o subcomando; o boot carrega o pack com `data_dir =
  <raiz>/<nome>` e não chama `prepare`
- [X] T083 `settings.py`: `packs_data_dir`; `wiring.py`: `LocalPackDataDirs` em `pack_runtime`; `bootstrap/cli.py`:
  `packs prepare` na lista de registro (R54)
- [X] T084 [P] Documentos vivos: `contracts/configuration.md` e `contracts/cli.md` (feito nesta passada), `CLAUDE.md`


---

## Passada de 2026-10-22: tetos das imagens ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md); research R56)

- [X] T085 `Settings` com as quatro variáveis e faixas; ligação ao `McpService` e ao `create_app`;
  `contracts/configuration.md` (R56)
- [X] T086 [P] Testes: `test_settings_phase9.py` (padrões, leitura, faixas) e a prova ponta a ponta
  `test_platform_images.py` (tool MCP com PNG → imagem na resposta → turno seguinte com `view_image` → imagem no
  provider simulado)

---

## Passada de 2026-10-28: o endereço dos scripts dos gráficos ([ADR-052](../../docs/adr/ADR-052-graficos-na-conversa.md); research R57)

**Goal**: a plataforma montada sabe de onde o navegador carrega o ECharts, e uma conversa `agentic` com MCP e
`generic.chart` chega ao Open WebUI como gráfico.

**Independent Test**: `tests/bootstrap/unit/test_settings_charts.py` e
`tests/bootstrap/integration/test_platform_charts.py`.

- [X] T087 `AXON_CHARTS_SCRIPT_BASE_URL` em `Settings` (validação com o nome da variável), `charts_base_url` com o
  `AXON_PUBLIC_URL` de reserva, ligação ao `create_app`; `contracts/configuration.md` (R57)
- [X] T088 Item informativo `charts` na saúde agregada
- [X] T089 [P] Testes: leitura, reserva, precedência e recusa da variável; a prova ponta a ponta sem rede

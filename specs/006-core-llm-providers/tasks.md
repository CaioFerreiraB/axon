---

description: "Task list for 006 — providers de LLM e modelo por papel, Fase 1"
---

# Tasks: Providers de LLM e modelo por papel

**Input**: Design documents from `/specs/006-core-llm-providers/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos. A constituição exige suíte de conformidade para cada seam exposto e para cada porta secundária
(princípio XIII); FR-003 (allowlist), FR-008 (uma emissão por chamada), FR-009 (saúde) e FR-010 (timeouts) só se
demonstram por teste.

**Organization**: só a **User Story 1** (Fase 1 do roadmap), mais FR-003, FR-009 e FR-010, que nascem com o seam
([research.md](research.md) R9, R8, R5 e R14). US2–US6 (papéis múltiplos com providers remotos, rejeição de roteamento
automático, restrição de formato no controller, tempo até o primeiro token) são Fase 3: **nada** de `adapters/openai.py`,
`adapters/openrouter.py` nem `ports.SecretResolver` nesta fase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1)
- Todo caminho é relativo à raiz do repositório

## Path Conventions

- Código: `ai-core/packages/core/src/ai_core/llm/`
- Testes: `ai-core/packages/core/tests/llm/{unit,contract,integration}/`
- Configuração: `ai-core/packages/core/pyproject.toml` (dependência) e `ai-core/pyproject.toml` (import-linter, pytest)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: o módulo existe no layout do ADR-012 e a dependência nova entra no workspace

- [X] T001 Criar o esqueleto em `ai-core/packages/core/src/ai_core/llm/`: `__init__.py` (docstring: consumidores
  importam `ai_core.llm.api`), `domain/__init__.py` e `adapters/__init__.py`. Nenhum arquivo de provider remoto —
  OpenAI e OpenRouter são Fase 3
- [X] T002 Acrescentar `openai>=3.15,<4` a `dependencies` em `ai-core/packages/core/pyproject.toml` e rodar
  `XDG_DATA_HOME=$HOME/.local/share uv sync` a partir de `ai-core/`, conferindo que `openai` e `httpx2` aparecem no
  ambiente ([research.md](research.md) R4)
- [X] T003 Em `ai-core/pyproject.toml`, acrescentar `packages/core/tests/llm` a `[tool.pytest.ini_options] pythonpath`
  (mesmo padrão de `tests/packs` e `tests/observability`, para o testkit do módulo)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `api.py` (tipos que todo o resto usa), portas, regras puras e as fábricas de teste

**⚠️ CRITICAL**: T004 precede tudo; nenhuma implementação de serviço ou adapter começa antes de T004–T006

- [X] T004 Implementar `ai-core/packages/core/src/ai_core/llm/api.py` conforme
  [contracts/model-router.md](contracts/model-router.md) e as tabelas de [data-model.md](data-model.md):
  `type ModelRole = Literal["controller", "generation", "rerank"]`; `ModelRef`
  (`frozen=True, slots=True, kw_only=True`; `provider: str` não vazio e **sem** `/`, `model: str` não vazio, podendo
  conter `/` e `:`; `parse(text)` dividindo no **primeiro** `/` e levantando `ValueError` para texto sem `/` ou com
  lado vazio; `__str__` devolvendo `"provider/model"`); `ModelPolicy` (`roles: Mapping[ModelRole, ModelRef]` com pelo
  menos um papel, guardado como `MappingProxyType`; `allow: tuple[str, ...]`, vazio = nenhuma restrição declarada;
  `__post_init__` rejeita papel fora do vocabulário e política sem papel); `ModelHealth` (`role`, `ref`,
  `available: bool`, `detail: str | None`); Protocols `BoundModel` (`role`, `ref`, `async complete(...)`,
  `stream(...)`), `ModelRouter` (`for_role`) e `ModelRouting` (`for_execution`, `async check`); e os erros
  `ModelRoutingError(RuntimeError)`, `RoleNotConfigured`, `ModelNotAllowed`, `UnknownProvider` e `ModelCallFailed`
  (com atributos `provider`, `model`, `reason`). Importa só stdlib e `ai_core_contracts` — **não** importa o resto do
  próprio módulo
- [X] T005 [P] Implementar `ai-core/packages/core/src/ai_core/llm/ports.py` conforme
  [contracts/ports.md](contracts/ports.md): `ProbeResult` (`available: bool`, `detail: str | None`),
  `ModelProvider(LLMProvider, Protocol)` com `name: str` e `async probe(model: str) -> ProbeResult`, e
  `Clock(Protocol)` com `monotonic() -> float`. Nenhuma outra porta — `SecretResolver` é Fase 3 (R8)
- [X] T006 [P] Implementar `ai-core/packages/core/src/ai_core/llm/domain/policy.py`, puro e sem I/O:
  `resolve(policy, role) -> ModelRef` levantando `RoleNotConfigured` com o papel pedido e os configurados;
  `is_allowed(ref, patterns) -> bool` por `fnmatch` sobre `"provider/model"`, com lista vazia devolvendo `True`; e
  `ensure_allowed(ref, patterns)` levantando `ModelNotAllowed` com a referência e os padrões ([research.md](research.md)
  R9, R12)
- [X] T007 Criar `ai-core/packages/core/tests/llm/conftest.py` e
  `ai-core/packages/core/tests/llm/llm_testkit.py` (padrão de `tests/observability/trace_testkit.py`): políticas de
  exemplo (um papel, vários papéis, allowlist restritiva e vazia), um `TraceSink` de memória que acumula eventos e as
  fábricas de transporte HTTP falso — resposta única, corpo SSE de streaming com dois pedaços mais um final com
  `usage`, resposta de erro de status, conexão recusada e stream que para de entregar pedaços (R10). O relógio
  programado **não** fica aqui: é adapter (`ScriptedClock`, T015)

**Checkpoint**: tipos, portas, regras puras e fábricas prontos — a US1 pode começar

---

## Phase 3: User Story 1 - Geração local em streaming (Priority: P1) 🎯 MVP

**Goal**: o motor pede o papel `generation` ao roteador e recebe um cliente do provider local que gera em streaming;
falha de provider vira erro explícito que nomeia provider e modelo; cada chamada deixa rastro no trace.

**Independent Test**: `uv run pytest packages/core/tests/llm` a partir de `ai-core/` passa sem rede; com
`OLLAMA_BASE_URL` definida, a integração gera tokens incrementais de um modelo real.

### Tests for User Story 1 ⚠️

> Escrever primeiro e confirmar que falham antes de implementar.

- [X] T008 [P] [US1] `ai-core/packages/core/tests/llm/unit/test_llm_api.py`: construção e validação dos value objects
  de T004 — `ModelRef.parse("ollama/qwen3:1.7b")` e `parse("openrouter/qwen/qwen3-8b")` (modelo com `/` preservado),
  texto sem `/` levanta `ValueError`, `str(ref)` volta ao texto original, `ModelPolicy` sem papel e com papel
  desconhecido levanta, e os erros carregam `provider`, `model` e `reason`
- [X] T009 [P] [US1] `ai-core/packages/core/tests/llm/unit/test_llm_policy.py`: `resolve` devolve a referência do papel
  e levanta `RoleNotConfigured` nomeando os papéis configurados; `is_allowed` com `"ollama/*"`, `"openrouter/qwen/*"`,
  lista vazia (deixa passar) e caso negativo; `ensure_allowed` levanta `ModelNotAllowed` com referência e padrões
- [X] T010 [P] [US1] `ai-core/packages/core/tests/llm/contract/test_model_provider_port.py`: a conformidade da porta
  descrita em [contracts/ports.md](contracts/ports.md), parametrizada por `ScriptedProvider` e por `OllamaProvider` com
  transporte falso — resposta única, streaming com dois pedaços e `finish_reason` só no último, `usage` presente e
  ausente sem invenção de número, `tools` e `response_format` repassados sem alteração de forma, provider inalcançável,
  erro de status, inatividade e as três respostas de `probe`
- [X] T011 [P] [US1] `ai-core/packages/core/tests/llm/contract/test_clock_port.py`: leituras nunca diminuem no
  `MonotonicClock`; a diferença entre duas leituras do relógio programado é exatamente a programada
- [X] T012 [P] [US1] `ai-core/packages/core/tests/llm/contract/test_model_router_seam.py`: os nove itens da suíte de
  conformidade de [contracts/model-router.md](contracts/model-router.md), com os nomes de teste que o
  [quickstart.md](quickstart.md) usa nos filtros (`streaming`, `indisponivel`, `saude`) — resolução, papel ausente,
  allowlist, provider desconhecido (os três sem nenhum I/O), streaming incremental, `complete`, provider fora do ar com
  provider e modelo na mensagem, uma emissão de `ModelCall` por chamada (sucesso e falha) e `check` com um
  `ModelHealth` por papel. Acrescentar o caso de SC-001: o mesmo cenário rodado com duas `ModelPolicy` que diferem só
  no modelo produz chamadas ao modelo declarado em cada uma, sem nenhuma outra mudança
- [X] T013 [P] [US1] `ai-core/packages/core/tests/llm/unit/test_instrumentation.py`: o `ModelCall` emitido carrega
  `request_id` de `for_execution`, papel, provider, modelo, `duration_ms` vindo do relógio programado, tokens do
  `usage` (e `None` quando ausente) e `finish_reason`; falha emite com `finish_reason="error"`; streaming emite **uma
  vez** ao encerrar o iterador, inclusive quando quem consome abandona no meio; resolução que falha antes da rede não
  emite nada
- [X] T014 [P] [US1] `ai-core/packages/core/tests/llm/integration/test_ollama_real.py`, marcado e pulado sem
  `OLLAMA_BASE_URL`: streaming incremental de um modelo real, `probe` confirmando o modelo presente e negando um
  inexistente, e erro explícito com o serviço fora do ar

### Implementation for User Story 1

- [X] T015 [P] [US1] `ai-core/packages/core/src/ai_core/llm/adapters/clock.py`: `MonotonicClock` cumprindo a porta
  `Clock` com `time.monotonic()` e `ScriptedClock`, que devolve valores programados e repete o último quando a
  sequência acaba — é o adapter em memória que o princípio XIII exige e o relógio do perfil de teste da 011 (US3
  cenário 2), por isso fica em `adapters/` e não no testkit
- [X] T016 [P] [US1] `ai-core/packages/core/src/ai_core/llm/adapters/fake.py`: `ScriptedProvider` cumprindo
  `ModelProvider` com respostas, sequências de pedaços, `usage` e falhas programados, `name` configurável e registro das
  chamadas recebidas (é o adapter em memória da porta e o provider do perfil de teste da 011 — R11)
- [X] T017 [US1] `ai-core/packages/core/src/ai_core/llm/adapters/openai_compat.py`: provider sobre qualquer endpoint
  compatível com OpenAI, conforme [contracts/ollama-adapter.md](contracts/ollama-adapter.md) — cliente `AsyncOpenAI`
  com `base_url`, sentinela de credencial, `max_retries=0` e timeout `connect=connect_seconds` (default 5 s) /
  `read=idle_seconds` (default 120 s), **sem teto total**; `chat` com os dois `@overload` do contrato 001; tradução de
  `ChatMessage`/`ChatTool` sem enviar chave ausente como `None`; streaming com `stream_options={"include_usage": True}`,
  `finish_reason` e `usage` só no último pedaço, e fechamento do iterador inclusive em abandono; `probe` listando os
  modelos; e o mapeamento de erro da tabela do contrato para `ModelCallFailed`, com corpo truncado em 500 caracteres e
  provider e modelo no início da mensagem (FR-010, R5, R6)
- [X] T018 [US1] `ai-core/packages/core/src/ai_core/llm/adapters/ollama.py`: `OllamaProvider` sobre T017, com
  `name="ollama"`, `base_url` default `http://localhost:11434/v1` e a sentinela de credencial que o Ollama ignora
- [X] T019 [US1] `ai-core/packages/core/src/ai_core/llm/service.py`: `TracedModel` (implementa `BoundModel`; mede pela
  porta `Clock`, chama o provider e emite exatamente um `ModelCall` ao fim de `complete()` e ao encerrar o iterador de
  `stream()`, com `finish_reason="error"` em falha — R7), `ExecutionRouter` (implementa `ModelRouter`; usa
  `domain/policy.py` para resolver o papel e aplicar a allowlist, e levanta `UnknownProvider` antes de qualquer rede) e
  `ModelRoutingService` (implementa `ModelRouting`; recebe `providers: Mapping[str, ModelProvider]`, `trace: TraceSink`
  e `clock: Clock`; `for_execution` sem I/O; `check` sondando um provider por papel configurado, sem levantar por
  indisponibilidade — R8). Não importa `adapters/`
- [X] T020 [US1] Rodar `uv run pytest packages/core/tests/llm` a partir de `ai-core/` até T008–T013 passarem (T014
  pulado sem `OLLAMA_BASE_URL`), e `uv run mypy` e `uv run ruff check packages` limpos

**Checkpoint**: a US1 está completa e testável sozinha — a 005 e a 011 já podem consumir o seam

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T021 Acrescentar a `ai-core/pyproject.toml` os contratos de import-linter de [research.md](research.md) R13 —
  `ai_core.llm.api` não importa `domain`/`ports`/`service`/`adapters`; `ai_core.llm.domain` não importa
  `ports`/`service`/`adapters`; `ai_core.llm.service` não importa `adapters`; `ai_core.llm.api`/`domain`/`ports`/
  `service` não importam `openai` nem `httpx2`; `ai_core.llm` não importa `ai_core.packs`; e `ai_core.observability`
  passa a ter `ai_core.llm` entre os módulos proibidos — e rodar `uv run lint-imports` até todos aparecerem como `KEPT`
- [X] T022 Executar as seções de [quickstart.md](quickstart.md) (pré-requisitos, verificação completa, cenários 1–3 e
  saúde) e corrigir divergências entre o resultado e o "Esperado"
- [X] T023 [P] Atualizar a seção "Código" de `CLAUDE.md` (o módulo `ai_core/llm/` existe, com o seam Model Router, o
  adapter do Ollama pela camada compatível e o provider simulado; OpenAI e OpenRouter continuam para a Fase 3) e a
  linha da 006 em `specs/README.md` (status "Fase 1 implementada (US1)")

---

## Fase 3 (2026-10-02): US2–US5 — providers remotos, roteamento automático e saída estruturada (research R15–R26)

Caminhos relativos a `ai-core/packages/core/`, salvo quando começam com `specs/` ou `ai-core/`. Testes primeiro, falhando
antes do código; marcas `us2` (papéis em providers diferentes), `us3` (providers externos, roteamento automático e
credencial — FR-011 entra aqui), `us4` (saída estruturada no controller) e `us5` (allowlist). Toque declarado na 011:
`bootstrap/profiles.py`, seus testes e `specs/011-core-bootstrap/contracts/profiles.md`. Nenhum seam muda.

## Phase 5: Setup da Fase 3

- [X] T024 Em `ai-core/pyproject.toml`, acrescentar a descrição da 006 às marcas existentes, sem criar marca nova:
  `us2` += "; 006 US2 — modelo por papel", `us3` += "; 006 US3 — providers externos e roteamento automático",
  `us4` += "; 006 US4 — saída estruturada no controller", `us5` += "; 006 US5 — allowlist de modelo"

---

## Phase 6: Foundational da Fase 3 — porta `SecretResolver` (FR-011, R21)

**⚠️ Bloqueia a US3** (os providers remotos e a porta `llm_secrets` da 011 dependem dela). US2 e US5 não dependem.

- [X] T025 [P] Criar `tests/llm/contract/test_secret_resolver_port.py` (marca `us3`), parametrizado por
  `EnvSecretResolver(environ={...})` e `InMemorySecretResolver({...})`, com os quatro casos de
  [contracts/ports.md](contracts/ports.md) "Fase 3": nome presente → valor exato; ausente → `None`; valor `""` ou
  `"   "` → `None`; nome vazio → `None`, sem levantar
- [X] T026 Acrescentar a `src/ai_core/llm/ports.py` o `Protocol` `SecretResolver` com
  `def resolve(self, name: str) -> str | None` — docstring: "Valor da credencial pelo nome, ou None quando ausente ou
  vazia. Nunca levanta." (R21)
- [X] T027 Criar `src/ai_core/llm/adapters/secrets.py` com `EnvSecretResolver(environ: Mapping[str, str] | None = None)`
  (default `os.environ`; lê exatamente a variável com o nome pedido) e `InMemorySecretResolver(values: Mapping[str, str]
  | None = None)`; nos dois, valor ausente, vazio ou só espaços → `None`, e nome vazio → `None` (depende de T026; T025
  passa)

**Checkpoint**: a porta existe com dois adapters e conformidade verde

---

## Phase 7: User Story 2 — Modelo por papel (Priority: P1 — prova da Fase 3)

**Goal**: provar que cada papel resolve para o seu provider, com o trace separado por papel (R24). Nenhum código novo.

**Independent Test**: `uv run pytest packages/core/tests -m us2 -k "papeis or providers_por_papel"`.

- [X] T028 [P] [US2] Em `tests/llm/contract/test_model_router_seam.py`, `test_papeis_em_providers_diferentes` (marca
  `us2`): política com `controller: openrouter/qwen/qwen3-8b`, `generation: ollama/qwen3:1.7b` e
  `allow=("ollama/*", "openrouter/*")`; dois `ScriptedProvider` (`name="openrouter"` com `content='{"action":
  "answer"}'`, e `name="ollama"`); `for_role("controller").ref.provider == "openrouter"` e
  `for_role("generation").ref.provider == "ollama"`; `complete` do controller **com** um `response_format`
  `{"type": "json_schema", "json_schema": {"name": "acao", "schema": {"type": "object"}}}` (continua verde depois da guarda
  da US4) e `stream` da geração; o trace tem dois `ModelCall`, `(controller, openrouter)` e `(generation, ollama)`, e
  cada provider recebeu exatamente uma chamada
- [X] T029 [P] [US2] Criar `tests/bootstrap/integration/test_providers_por_papel.py` (marca `us2`): YAML a partir de
  `AGENTIC_ASSISTANTS_YAML` (bootstrap_testkit) com o bloco `pesquisador` sem `mcp: [demo]`, `controller:
  openrouter/qwen/qwen3-8b` e `allow: ["ollama/*", "openrouter/*"]` (substituição como `CONTROLLER_PROGRAMADO` em
  `test_platform_agentic_mcp.py`); `platform(config=MemoryConfig(settings), overrides={"providers": {"ollama":
  ScriptedProvider(name="ollama", deltas=("Pronto.",)), "openrouter": ScriptedProvider(name="openrouter",
  content='{"action": "answer"}')}})`; `POST /v1/chat/completions` com `model="pesquisador"` e `OIDC` → 200; nos registros
  `model_call` do trace da requisição, o de papel `controller` tem provider `openrouter` e o de `generation`, `ollama`
  (teste `test_providers_por_papel_no_trace`)

**Checkpoint**: US2 provada no seam e ponta a ponta

---

## Phase 8: User Story 3 — Providers externos, roteamento automático e credencial (Priority: P2)

**Goal**: OpenAI e OpenRouter como providers (R20), recusa de roteamento automático no `ModelRef` (R16) e o remoto sem
credencial registrado e explícito (FR-011, R21), ligados nos perfis da 011 (R23).

**Independent Test**: `uv run pytest packages/core/tests -m us3 -k "automatico or credencial or remot"`.

### Testes da US3 (escrever primeiro; devem falhar)

- [X] T030 [P] [US3] Em `tests/llm/unit/test_llm_api.py` (marca `us3`), `test_roteamento_automatico_recusado`
  parametrizado — `ModelRef.parse` de `openrouter/auto`, `openrouter/AUTO`, `openrouter/auto:free`,
  `openrouter/openrouter/auto`, `openrouter/OpenRouter/Auto`, `openrouter/openrouter/qualquer` e
  `ModelRef(provider="openrouter", model="auto")` levantam `ValueError` cuja mensagem contém "roteamento automático" e
  "modelo explícito" —, e `test_roteamento_automatico_nao_atinge_modelo_explicito` — `openrouter/qwen/qwen3-8b`,
  `openrouter/qwen/qwen3-8b:free`, `…:nitro`, `…:floor`, `ollama/auto` e `openai/gpt-4o-mini` são aceitos
- [X] T031 [US3] Em `tests/llm/llm_testkit.py`: atributo `name = "ollama"` em `ScriptedCase` e `OllamaCase`; constantes
  `SECRET = "sk-teste-0123456789"` e `REMOTE_BASE_URL = "http://remoto.test/v1"`; `OpenAICase` e `OpenRouterCase` (ids
  `"openai"`/`"openrouter"`, `name` igual), com a mesma interface de `OllamaCase` (`ok`, `failing`, `sent_model`,
  `sent_tool_names`, `sent_response_format`, `call_count`, `transport`), construindo o provider com
  `secrets=InMemorySecretResolver({<credencial>: SECRET})`, `base_url=REMOTE_BASE_URL` e o `RecordingTransport`; e
  `PORT_CASES = (*PROVIDER_CASES, OpenAICase, OpenRouterCase)`. Em `tests/llm/contract/test_model_provider_port.py`, a
  fixture `case` passa a usar `PORT_CASES`, e as asserções com `"ollama"` fixo passam a usar `case.name` (os casos
  `failing` dos remotos produzem `ModelCallFailed` com o próprio nome)
- [X] T032 [US3] Criar `tests/llm/contract/test_remote_providers.py` (marca `us3`; depende de T031), com o transporte
  falso do testkit e um teste por linha de [contracts/remote-adapters.md](contracts/remote-adapters.md):
  `test_sem_credencial_chat_falha_antes_da_rede` (sem e com streaming: `ModelCallFailed` com `reason` contendo
  `"sem credencial: defina AI_CORE_OPENAI_API_KEY"` — e `…OPENROUTER…` no outro — e `transport.requests == []`);
  `test_credencial_em_branco_conta_como_ausente` (`"   "`); `test_sem_credencial_probe_relata_a_falta`;
  `test_credencial_vai_no_cabecalho` (`Authorization: Bearer <SECRET>`); `test_url_base_default` (sem `base_url`, a
  requisição vai a `api.openai.com` em `/v1/chat/completions` e a `openrouter.ai` em `/api/v1/chat/completions`);
  `test_chave_nunca_aparece_no_motivo` (401 cujo corpo contém `SECRET` → `reason` com `***` e sem `SECRET`; idem na
  `probe`); `test_probe_openrouter_aceita_base_da_variante` (lista com `qwen/qwen3-8b` → `qwen/qwen3-8b:nitro`
  disponível; `qwen/qwen3-8b:free` listado → disponível; `outro/x:nitro` → indisponível);
  `test_probe_trunca_a_lista_de_disponiveis` (25 ids, modelo ausente → `detail` com os 20 primeiros e `"(+5)"`)
- [X] T033 [P] [US3] Em `tests/llm/contract/test_model_router_seam.py`, `test_saude_de_remoto_sem_credencial`
  (marca `us3`): `ModelRoutingService` com `OpenAIProvider(secrets=InMemorySecretResolver())` e política
  `generation: openai/gpt-4o-mini` → `check` devolve um `ModelHealth` com `available=False` e `detail` contendo
  `AI_CORE_OPENAI_API_KEY`, sem levantar; e a chamada `complete` levanta `ModelCallFailed` e emite um `ModelCall` com
  `finish_reason="error"`
- [X] T034 [P] [US3] Em `tests/bootstrap/unit/test_profiles.py` (toque na 011): o teste que constrói `providers` do
  `memory` passa `parts={"llm_secrets": InMemorySecretResolver()}` (o da 006); novos — `REQUIRED_PORTS` tem
  `llm_secrets` antes de `providers`; `memory` e `persistent` constroem `providers` com as chaves
  `{"ollama", "openai", "openrouter"}` (`OpenAIProvider`, `OpenRouterProvider`); `llm_secrets` do `memory` é o
  `EnvSecretResolver` da 006; `test` mantém só `"ollama"` (`ScriptedProvider`) e `llm_secrets` em memória;
  `llm_secrets` pode ser trocada por `overrides` (não está em `NOT_OVERRIDABLE`)
- [X] T035 [P] [US3] Criar `tests/bootstrap/integration/test_providers_remotos.py` (marca `us3`), no perfil `test`:
  `test_assistant_com_roteamento_automatico_fica_indisponivel` (Assistant `agentic` com `controller: openrouter/auto` →
  `POST /v1/chat/completions` → 424, `code: "assistant_unavailable"`, e algum item de `error.reasons` contendo
  `models.controller` e "roteamento automático");
  `test_modelo_automatico_pedido_na_requisicao_e_recusado` (Assistant com `allow: ["ollama/*", "openrouter/*"]` e
  `model="<assistant>/openrouter/openrouter/auto"` → 400 com `param: "model"`);
  `test_remoto_sem_credencial_na_saude_e_na_conversa` (`overrides={"providers": {"ollama": ScriptedProvider(...),
  "openai": OpenAIProvider(secrets=InMemorySecretResolver(), http_client=<transporte do testkit>)}}`, Assistant `chat`
  com `generation: openai/gpt-4o-mini` e `allow: ["openai/*"]`: `GET /private/v1/health` com `TEST_API_KEY` traz o item
  `model:openai/gpt-4o-mini` indisponível com "sem credencial: defina AI_CORE_OPENAI_API_KEY"; a conversa sem streaming
  → 502 com o motivo; o transporte não recebeu requisição)

### Implementação da US3

- [X] T036 [US3] Em `src/ai_core/llm/api.py` (R16): constante `AUTO_ROUTING_PROVIDER: Final = "openrouter"` e, em
  `ModelRef.__post_init__`, `base = self.model.strip().casefold().partition(":")[0]`; com
  `provider == AUTO_ROUTING_PROVIDER` e `base == "auto"` ou `base.startswith("openrouter/")`, levantar
  `ValueError(f"'{self.provider}/{self.model}' é roteamento automático, que escolhe o modelo sozinho: declare um modelo
  explícito (autor/modelo)")`; docstring de `ModelCallFailed` passa a citar as falhas antes da rede (controller sem
  esquema, remoto sem credencial) além das de rede (T030 passa)
- [X] T037 [US3] Em `src/ai_core/llm/adapters/openai_compat.py` (R22): `LISTED_LIMIT: Final = 20` e a lista de
  disponíveis do `detail` da `probe` com os 20 primeiros ids ordenados e `" (+N)"` quando houver mais; método
  `_has_model(self, model: str, ids: Sequence[str]) -> bool` (default `model in ids`) usado pela `probe`, para o
  OpenRouter sobrescrever; o Ollama não muda para listas curtas (suíte da Fase 1 verde)
- [X] T038 [US3] Criar `src/ai_core/llm/adapters/remote.py` (R20, R21): `RemoteProvider(OpenAICompatProvider)` com
  `__init__(self, *, name, base_url, credential: str, secrets: SecretResolver, connect_seconds=5.0, idle_seconds=120.0,
  http_client=None)`; resolve `secrets.resolve(credential)` uma vez; sem valor, passa à base uma sentinela fixa (o SDK
  nunca lê `OPENAI_API_KEY`) e guarda o motivo `f"sem credencial: defina {credential}"`; `chat` (sem e com streaming)
  levanta `ModelCallFailed(provider=name, model=model, reason=<motivo>)` antes de qualquer requisição; `probe` devolve
  `ProbeResult(available=False, detail=<motivo>)` sem rede; `_reason` troca o valor da chave por `***` (depende de T027,
  T037)
- [X] T039 [P] [US3] Criar `src/ai_core/llm/adapters/openai.py`: `OpenAIProvider(RemoteProvider)` com `NAME = "openai"`,
  `DEFAULT_BASE_URL = "https://api.openai.com/v1"`, `CREDENTIAL = "AI_CORE_OPENAI_API_KEY"`; construtor
  `(*, secrets, base_url=DEFAULT_BASE_URL, connect_seconds=5.0, idle_seconds=120.0, http_client=None)` (depende de T038)
- [X] T040 [P] [US3] Criar `src/ai_core/llm/adapters/openrouter.py`: `OpenRouterProvider(RemoteProvider)` com
  `NAME = AUTO_ROUTING_PROVIDER` (importado de `ai_core.llm.api`, para a regra do `ModelRef` e o nome do registro nunca
  divergirem — achado A1), `DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"`,
  `CREDENTIAL = "AI_CORE_OPENROUTER_API_KEY"`, mesmo construtor do T039, e `_has_model` que aceita o id ou, com `:` no
  modelo, a base antes do último `:` (R22) (depende de T038; T031–T033 passam)
- [X] T041 [US3] Em `src/ai_core/bootstrap/profiles.py` (toque na 011, R23): `llm_secrets` em `REQUIRED_PORTS` logo antes
  de `providers` (docstring atualizada); `memory` e `persistent` com `llm_secrets` = `EnvSecretResolver()` da 006
  (importado com alias para não colidir com o da 007) e `providers` = fábrica `_providers` que devolve
  `{"ollama": OllamaProvider(base_url=settings.ollama_base_url), "openai": OpenAIProvider(secrets=parts["llm_secrets"]),
  "openrouter": OpenRouterProvider(secrets=parts["llm_secrets"])}`; `test` com `llm_secrets` = `InMemorySecretResolver()`
  da 006 e `providers` inalterado (depende de T039, T040; T034 e T035 passam)
- [X] T042 [P] [US3] Em `specs/011-core-bootstrap/contracts/profiles.md`, acrescentar a seção "Fase 3 (2026-10-02):
  providers remotos da 006" com a linha `llm_secrets` (dono 006; `memory`/`persistent`: ambiente, com as credenciais
  de nome fixo da 006; `test`: memória, vazio) e a linha `providers` em forma genérica (`memory`/`persistent`: "os
  providers da 006 — hoje Ollama, OpenAI e OpenRouter"; `test`: provider simulado), citando a 006 R23 e o ADR-020

**Checkpoint**: `openrouter/auto` recusado em todo caminho; remotos registrados nos perfis; sem credencial, saúde e
conversa explicam a falta sem tocar a rede

---

## Phase 9: User Story 4 — Saída estruturada no controller (Priority: P2)

**Goal**: as três camadas do FR-005 (R17–R19): guarda no roteador, forma rígida no adapter, recusa sem reenvio.

**Independent Test**: `uv run pytest packages/core/tests/llm -m us4`.

### Testes da US4 (escrever primeiro; devem falhar)

- [X] T043 [P] [US4] Criar `tests/llm/unit/test_llm_output.py` (marca `us4`) com a tabela de `constraint_problem` do
  [data-model.md](data-model.md) "Fase 3": `generation` e `rerank` com qualquer formato → `None`; `controller` com
  `{"type": "json_schema", "json_schema": {"name": "acao", "schema": {...}}}` → `None`; `controller` com `None`,
  `{"type": "json_object"}` (o motivo nomeia `json_object`), `json_schema` sem `schema`, `schema` que não é mapeamento
  e `json_schema` que não é mapeamento → motivo contendo `controller` e `json_schema`
- [X] T044 [P] [US4] Em `tests/llm/contract/test_model_router_seam.py` (marca `us4`), casos 11–12 de
  [contracts/model-router.md](contracts/model-router.md) "Fase 3": `test_controller_sem_restricao_e_recusado`
  parametrizado por `None`, `json_object` e `json_schema` sem `schema`, em `complete` e em `stream` — levanta
  `ModelCallFailed` com provider e modelo, o provider não recebe chamada e o trace tem exatamente um `ModelCall` com
  `role="controller"` e `finish_reason="error"`; `test_generation_sem_formato_continua_aceito`
- [X] T045 [P] [US4] Em `tests/llm/contract/test_remote_providers.py` (marca `us4`): `test_strict_forcado`
  parametrizado pelos casos HTTP (`OllamaCase`, `OpenAICase`, `OpenRouterCase`) — com `json_schema` sem `strict` e com
  `"strict": False`, o corpo enviado tem `json_schema.strict is True` e o mapeamento passado continua igual;
  `test_require_parameters_so_com_formato` (OpenRouter: com formato, `body["provider"] == {"require_parameters": True}`;
  sem formato, sem `provider`; OpenAI nunca envia `provider`); `test_recusa_da_restricao_sem_reenvio` (400 com corpo
  "Invalid schema for response_format" na OpenAI e 404 "No endpoints found that can handle the requested parameters" no
  OpenRouter → `ModelCallFailed` com o código e o corpo, e `len(transport.requests) == 1`)
- [X] T046 [P] [US4] Criar `tests/llm/integration/test_remote_real.py` (marca `us4`), pulado sem
  `AI_CORE_OPENROUTER_API_KEY` (e, nos casos `openai`, sem `AI_CORE_OPENAI_API_KEY`): pelo `ModelRoutingService` com
  `OpenRouterProvider(secrets=EnvSecretResolver())` e `MonotonicClock`, o papel `controller` (modelo de
  `OPENROUTER_MODEL`, default `qwen/qwen3-8b`) com o esquema de raiz objeto `{"type": "object", "properties":
  {"action": {"enum": ["answer", "tool"]}}, "required": ["action"], "additionalProperties": false}` devolve conteúdo
  que `json.loads` lê e `jsonschema.validate` aceita (Independent Test da US4); `probe` confirma o modelo e nega
  `inexistente/modelo`; o mesmo com `OpenAIProvider` e `OPENAI_MODEL` (default `gpt-4o-mini`)

### Implementação da US4

- [X] T047 [US4] Criar `src/ai_core/llm/domain/output.py` (R17): `CONSTRAINED_ROLES: Final = frozenset({"controller"})`
  e `constraint_problem(role: ModelRole, response_format: Mapping[str, JSONValue] | None) -> str | None` com as mensagens
  do data-model ("o papel 'controller' exige response_format com esquema (json_schema)…", nomeando o tipo recebido
  quando houver); pura, sem I/O (T043 passa)
- [X] T048 [US4] Em `src/ai_core/llm/service.py`, `TracedModel.complete` e `.stream` aplicam `constraint_problem`
  **dentro** do bloco instrumentado e antes do provider: com motivo, levantam
  `ModelCallFailed(provider=self._ref.provider, model=self._ref.model, reason=<motivo>)` e o `ModelCall` de erro é
  emitido pelo caminho de falha existente (depende de T047; T044 passa e T028 continua verde)
- [X] T049 [US4] Em `src/ai_core/llm/adapters/openai_compat.py`, `_payload`: com `response_format["type"] ==
  "json_schema"` e `json_schema` mapeamento, envia uma cópia com `json_schema["strict"] = True`, sem mutar o recebido
  (R18; `json_object` e outros tipos passam como vieram)
- [X] T050 [US4] Em `src/ai_core/llm/adapters/openrouter.py`, sobrescrever `_payload` para acrescentar
  `extra_body={"provider": {"require_parameters": True}}` quando `response_format is not None` (R18) (depende de T040,
  T049; T045 passa)

**Checkpoint**: nenhuma chamada do controller sai sem esquema; a restrição vai na forma rígida; recusa é erro explícito

---

## Phase 10: User Story 5 — Allowlist de provider e modelo (Priority: P2 — prova da Fase 3)

**Goal**: o cenário literal da US5 no seam (R24). O modelo escolhido na requisição fora da allowlist já é coberto pela
003 (`tests/assistants/contract/test_grant_resolver.py`, `geral/openai/gpt-x`).

**Independent Test**: `uv run pytest packages/core/tests/llm -m us5`.

- [X] T051 [US5] Em `tests/llm/contract/test_model_router_seam.py`, `test_allowlist_us5_literal` (marca `us5`):
  `allow=("ollama/*",)` e `generation: openai/gpt-4o-mini` → `for_role("generation")` levanta `ModelNotAllowed` sem
  tocar provider nem emitir `ModelCall`; com `controller: openai/gpt-4o-mini` e `generation: ollama/qwen3:1.7b`, só o
  `controller` é recusado

---

## Phase 11: Polish da Fase 3

- [X] T052 Verificação completa a partir de `ai-core/`: `uv run pytest` (sem Postgres) e com
  `AI_CORE_TEST_POSTGRES_DSN`, `uv run mypy`, `uv run ruff check packages` e `uv run lint-imports` (todos os contratos
  `KEPT`, nenhum novo — R26); corrigir o que quebrar
- [X] T053 Executar a seção "Fase 3" de [quickstart.md](quickstart.md) (US3, US4, FR-011, US2 e US5; a integração paga
  só com as variáveis) e corrigir divergências entre o resultado e o "Esperado"
- [X] T054 [P] Atualizar `CLAUDE.md` (seção "Código": a 006 tem OpenAI e OpenRouter sobre a camada compatível, a porta
  `SecretResolver` com `AI_CORE_OPENAI_API_KEY`/`AI_CORE_OPENROUTER_API_KEY` e o ADR-020, roteamento automático recusado
  no `ModelRef`, a guarda do controller com `strict`/`require_parameters`, e a pendência da 005 — esquema de raiz objeto
  para OpenAI como controller); em `specs/README.md`, a linha da 006 (status "Fases 1 e 3 implementadas (US1–US5)") e
  a linha do seam **Model Router** na tabela de seams ("…aplicando allowlist e recusando roteamento automático" —
  achado U1); e em `docs/roadmap.md`, junto aos itens da 005, a pendência "esquema de ação de raiz objeto, para OpenAI
  como controller no modo estrito (006 R19)" (achado G1)

### Dependências da Fase 3

- **Setup (T024)** antes dos testes marcados
- **Foundational (T025–T027)** bloqueia a US3; T025 antes de T027
- **US2 (T028–T029)** e **US5 (T051)**: independentes de tudo da Fase 3 (só testes sobre código existente); T028 já
  passa um `response_format` de esquema, para seguir verde depois da US4
- **US3**: testes T030–T035 primeiro (T031 antes de T032); T036 e T037 em qualquer ordem; T038 → T039 ∥ T040 → T041; T042 a qualquer momento
- **US4**: testes T043–T046 primeiro; T047 → T048; T049 → T050 (que também depende de T040, da US3)
- **Polish**: T052 depois de todas as histórias; T053 depois de T052; T054 em paralelo

### Parallel Example: US3

```bash
Task: "unit/test_llm_api.py — roteamento automático (T030)"
Task: "contract/test_remote_providers.py — credencial, chave, sondagem (T032)"
Task: "contract/test_model_router_seam.py — saúde sem credencial (T033)"
Task: "bootstrap/unit/test_profiles.py (T034)"
Task: "bootstrap/integration/test_providers_remotos.py (T035)"
```

### Implementation Strategy (Fase 3)

1. T024–T027: marcas e porta de segredos
2. US2 e US5 (só prova) — verdes de saída, fixam o comportamento antes das mudanças
3. US3: regra do `ModelRef`, remotos, perfis da 011 — **PARE e VALIDE** o Independent Test da US3
4. US4: guarda, `strict`, `require_parameters` — **PARE e VALIDE** o Independent Test da US4
5. Polish: suíte completa, quickstart, documentação

---

## Passada de 2026-10-07: subconjunto estrito da OpenAI (ADR-023; research R27–R31)

Caminhos relativos a `ai-core/packages/core/`. Testes primeiro.

- [X] T055 [P] Criar `tests/llm/unit/test_llm_strict.py` (R27, R28): conversão — raiz `anyOf` embrulhada em `value`;
  opcional → obrigatório e anulável para `type` texto, `type` lista, `enum`, `const` e `anyOf`; `additionalProperties:
  false` acrescentado; `oneOf` → `anyOf`; anotações removidas; `$defs` na nova raiz com `$ref` preservado; o esquema
  recebido não muda —; recusas com o caminho na mensagem — objeto livre, `additionalProperties: true`, `allOf`, `if`,
  `patternProperties`, nó sem tipo —; inversa — desembrulho, `null` introduzido removido, `null` original mantido,
  ramo de `anyOf` escolhido por chaves e `const` (dois ramos de tool), arrays, conteúdo inválido devolvido como veio —;
  e a propriedade: para o esquema de ação da 005 (`action_schema` com uma tool de parâmetro opcional), um valor no
  formato estrito desfeito valida com `jsonschema` contra o esquema original
- [X] T056 [P] Em `tests/llm/contract/test_remote_providers.py`, casos 8–11 de
  [contracts/remote-adapters.md](contracts/remote-adapters.md) (marca `us4`): corpo da OpenAI com raiz objeto e tudo em
  `required`; conteúdo devolvido na forma original; streaming com formato entrega o conteúdo desfeito num pedaço;
  esquema sem equivalente → `ModelCallFailed` com o caminho e `transport.requests == []`; OpenRouter `openai/gpt-x`
  convertido e `z-ai/glm` enviado como veio
- [X] T057 Criar `src/ai_core/llm/domain/strict.py` com `StrictSchemaError`, `StrictPlan` (`wire`, `annotated`,
  `wrapped`), `to_strict` e `from_strict` (T055 passa)
- [X] T058 Em `src/ai_core/llm/adapters/remote.py`, `_needs_strict_subset(model) -> bool` (default `False`) e, em `chat`,
  a conversão do `response_format` de esquema (erro → `ModelCallFailed` antes da rede, `"esquema fora do subconjunto
  estrito da OpenAI: …"`) e a inversa no conteúdo — completo e com streaming; `OpenAIProvider` → `True`;
  `OpenRouterProvider` → modelo começando por `openai/` (T056 passa)
- [X] T059 Verificação a partir de `ai-core/`: `uv run pytest`, `mypy`, `ruff check packages`, `lint-imports`
- [X] T060 Integração paga, uma execução: `tests/bootstrap/integration/test_generic_agentic_real.py -k openrouter`
  (o `agentic` real da 010) com `OPENROUTER_MODEL` num modelo `openai/…` hospedado pela OpenAI; registrar o resultado no
  quickstart
- [X] T061 [P] Documentação: CLAUDE.md (a pendência da 005 sai; a conversão do subconjunto estrito na 006),
  `docs/roadmap.md` (a pendência "esquema de ação de raiz objeto" sai das pendências entre specs) e a seção "Com os
  providers reais" do [quickstart.md](quickstart.md) (a OpenAI como controller)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 e T002 primeiro (o `uv sync` precisa existir antes de qualquer import do SDK); T003 em
  paralelo
- **Foundational (Phase 2)**: T004 antes de tudo; T005 e T006 em paralelo depois dele; T007 depois de T004–T006
- **User Story 1 (Phase 3)**: depende de Setup + Foundational
- **Polish (Phase 4)**: T021 depois de T019; T022 depois de T020; T023 em paralelo

### Within User Story 1

- Testes (T008–T014) antes da implementação e falhando
- T015 e T016 em paralelo; T017 → T018 (o adapter do Ollama é o compatível com defaults); T019 depende de T004–T006 e,
  para rodar os próprios testes, de T015 e T016
- T020 é o portão da fase: nenhuma tarefa da Phase 4 antes dele

### Parallel Opportunities

- T008, T009, T010, T011, T012, T013 e T014 em paralelo (arquivos distintos)
- T015 e T016 em paralelo entre si e com qualquer teste já escrito
- T023 em paralelo com qualquer tarefa da Phase 3 concluída

---

## Parallel Example: User Story 1

```bash
# Testes da US1, juntos:
Task: "unit/test_llm_api.py (T008)"
Task: "unit/test_llm_policy.py (T009)"
Task: "contract/test_model_provider_port.py (T010)"
Task: "contract/test_clock_port.py (T011)"
Task: "contract/test_model_router_seam.py (T012)"
Task: "unit/test_instrumentation.py (T013)"
Task: "integration/test_ollama_real.py (T014)"
```

---

## Implementation Strategy

### MVP (US1, o escopo desta fase)

1. Phase 1 e 2: esqueleto, dependência, `api.py`, portas e regras puras
2. Phase 3: testes primeiro; depois relógio, provider simulado, adapter compatível, Ollama e serviço
3. **PARE e VALIDE**: quickstart, cenários 1–3 — streaming incremental, provider fora do ar e `ModelCall` por chamada
4. Phase 4: fronteiras de import, quickstart completo, documentação

### Depois desta fase

- 005 (mesma fase) recebe `ModelRouting` e gera pelo papel `generation`; 011 monta providers, política e perfil de teste
- Fase 2: a 003 passa a produzir a `ModelPolicy` como parte do grant; a 008 traduz a hierarquia de erro em status HTTP
- Fase 3: `adapters/openai.py` e `adapters/openrouter.py` sobre `openai_compat.py`, porta `SecretResolver`, papéis
  múltiplos (US2), rejeição de roteamento automático (US3), restrição de formato no controller (US4) e `ttft_ms` na 009
  (US6)


---

## Passada de 2026-10-22: imagens na mensagem ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md); research R32)

**Goal**: o seam aceita mensagem com imagem, só para papel com `vision`, e os adapters a entregam no formato da OpenAI.

**Independent Test**: `tests/llm/unit/test_llm_vision.py` e a conformidade da porta com mensagem em partes.

- [X] T062 `ModelMessage` e partes em `api.py`; `image_part`, `has_image`; assinaturas do seam e da porta (R32)
- [X] T063 `ModelPolicy.vision`, `BoundModel.vision`; guarda `vision_problem` e marca `image_marker` em
  `domain/images.py`; `model_exchange` com a marca
- [X] T064 `openai_compat` com partes; `ScriptedProvider.images`
- [X] T065 [P] Testes: guarda nos dois modos (sem chamada ao provider, `ModelCall` de erro), papel com `vision`,
  `model_exchange` com marca, `vision` em papel não declarado, conformidade da porta com partes nos quatro adapters

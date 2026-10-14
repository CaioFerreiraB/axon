---

description: "Task list for 005 — motor de execução: flow chat (Fase 1), agentic (Fase 3) e rag_first (Fase 5)"
---

# Tasks: Motor de execução — flows `chat`, `agentic` e `rag_first`

**Input**: Design documents from `/specs/005-core-execution-engine/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos. A constituição exige suíte de conformidade para cada seam exposto e para cada porta secundária
(princípio XIII); SC-001 (reescrita barata), FR-013 (falha antes de qualquer custo) e o streaming da US1 só se
demonstram por teste.

**Organization**: só a **User Story 1** (Fase 1 do roadmap), mais o registro de nomes de flow da US5, que faz parte do
seam ([research.md](research.md) R11). US2 (`agentic`), US3 (`rag_first`), US6 (rotina de pack), a porta de checkpoint
e o corte por orçamento **não** entram: nada de `gate.py`, `limits.py`, `actions.py`, `budget.py` nem
`ports.CheckpointStore` nesta fase.

**Fase 3 (2026-10-01)**: **US2** — flow `agentic` (Phases 5–7, T027–T056; [research.md](research.md) R14–R33), com os
toques declarados na 009 (`ControllerDecision`, sob o ADR-017) e no import-linter. Continuam fora: US3/`rag_first` e o
portão (Fase 5), US4 no corte de chunks por rank (Fase 5), US6 (P3), a porta de checkpoint (adiada, R30) e o encaixe na
011, 008 e 003 (passadas delas, R33). Caminhos das tarefas da Fase 3 relativos a `ai-core/packages/core/`; testes novos
com `@pytest.mark.us2` (ou `pytestmark`).

**Fase 5 (2026-10-09)**: **US3** — flow `rag_first` com portão de cobertura — e **US4** — validação nele, com o corte
por posição no teto — e o [ADR-026](../../docs/adr/ADR-026-o-modelo-ve-o-identificador-de-cada-trecho.md) (Phases 8–12,
T059–T094; [research.md](research.md) R35–R48). Toques declarados (R35): 002 (`PackHooks.reranker`), 004 (`· id:` na
renderização e `ToolSession.fence_chunks`), 009 (`CoverageGate`, ADR-017) e 011 (`AI_CORE_RAG_*`); a 003 e a 008 não
mudam. Continuam fora: US6 (P3), a porta de checkpoint (R30) e o limiar calibrado (105). Caminhos relativos a
`ai-core/packages/core/`, salvo indicação; testes novos com `pytestmark = pytest.mark.us3` ou `us4`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1)
- Todo caminho é relativo à raiz do repositório

## Path Conventions

- Código: `ai-core/packages/core/src/ai_core/graph/`
- Testes: `ai-core/packages/core/tests/graph/{unit,contract,integration}/`
- Configuração: `ai-core/packages/core/pyproject.toml` (dependência) e `ai-core/pyproject.toml` (import-linter, pytest)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: o módulo existe no layout do ADR-012 e o framework de grafo entra no workspace

- [X] T001 Criar o esqueleto em `ai-core/packages/core/src/ai_core/graph/`: `__init__.py` (docstring: consumidores
  importam `ai_core.graph.api`), `domain/__init__.py`, `adapters/__init__.py` e `adapters/langgraph/__init__.py`
- [X] T002 Acrescentar `langgraph>=1.2,<2` a `dependencies` em `ai-core/packages/core/pyproject.toml` e rodar
  `XDG_DATA_HOME=$HOME/.local/share uv sync` a partir de `ai-core/` ([research.md](research.md) R1)
- [X] T003 Em `ai-core/pyproject.toml`, acrescentar `packages/core/tests/graph` a `[tool.pytest.ini_options]
  pythonpath` (mesmo padrão de `tests/packs`, `tests/observability` e `tests/llm`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `api.py` (tipos que todo o resto usa), a porta, as regras puras e as fábricas de teste

**⚠️ CRITICAL**: T004 precede tudo; nenhuma implementação de serviço, nó ou grafo começa antes de T004–T006

- [X] T004 Implementar `ai-core/packages/core/src/ai_core/graph/api.py` conforme
  [contracts/execution-engine.md](contracts/execution-engine.md) e [data-model.md](data-model.md):
  `ExecutionRequest` (`messages: Sequence[Message]` não vazia, `stream: bool = True`,
  `reference_time: datetime | None` exigindo timezone quando presente); `ExecutionGrant` como `Protocol` com as
  propriedades `assistant`, `flow`, `composition` (002) e `models` (006) — **nada mais** (R3, R4); `TokenEvent`
  (`text`), `ProgressEvent` (`stage` não vazio, `detail: str | None`), `ExecutionIssue` (`stage`, `kind`, `message`,
  os dois primeiros não vazios) e `FinalEvent` (`answer`, `citations: tuple[Citation, ...]`,
  `errors: tuple[ExecutionIssue, ...]`, `flags: frozenset[str]`); `type ExecutionEvent` como união dos três eventos;
  Protocol `ExecutionEngine` (`flows()`, `run()`); erros `ExecutionError(RuntimeError)`,
  `ExecutionRequestInvalid(ExecutionError)` e `UnknownFlow(ExecutionRequestInvalid)`; e a constante
  `FLOW_CHAT = "chat"`. Importa só stdlib, `ai_core_contracts` e os `api.py` de 002 e 006 — **não** importa o resto do
  próprio módulo nem framework nenhum
- [X] T005 [P] Implementar `ai-core/packages/core/src/ai_core/graph/ports.py` conforme
  [contracts/ports.md](contracts/ports.md): `Clock(Protocol)` com `now() -> datetime` (sempre com timezone) e
  `monotonic() -> float`. Nenhuma outra porta — `CheckpointStore` é Fase 3 (R7)
- [X] T006 [P] Implementar `ai-core/packages/core/src/ai_core/graph/domain/`, puro e sem I/O: `request.py` com
  `validate(request, grant, available_flows) -> str` devolvendo a pergunta (última mensagem de papel `user`) e
  levantando `ExecutionRequestInvalid` para requisição sem mensagens, sem mensagem de usuário ou com `reference_time`
  ingênua, e `UnknownFlow` nomeando o flow pedido e os disponíveis; `outcome.py` com
  `final_event(generated, outcome) -> FinalEvent`, aplicando a regra da US1 cenário 3 — resposta e citações do
  validator quando ele as altera, senão as geradas; cada `issue` vira `ExecutionIssue(kind="ValidatorIssue")`; `flags`
  preservadas
- [X] T007 Criar `ai-core/packages/core/tests/graph/conftest.py` e
  `ai-core/packages/core/tests/graph/graph_testkit.py` (padrão de `llm_testkit`): um grant de exemplo que cumpre o
  `Protocol`, um `PackHooks` de teste com prompts, fatias e validators programáveis (inclusive um que altera a
  resposta e outro que levanta), o Model Router real da 006 montado sobre o `ScriptedProvider`, um `TraceSink` de
  memória e o `FixedClock`. A construção do motor fica num **único** helper (`graph_testkit.engine(...)`) — é o único
  ponto do testkit que conhece o adapter, e é o que faz valer a promessa do SC-001 de que as suítes de conformidade
  sobrevivem à troca do grafo

**Checkpoint**: tipos, porta, regras puras e fábricas prontos — a US1 pode começar

---

## Phase 3: User Story 1 - Conversa direta com resposta em streaming (Priority: P1) 🎯 MVP

**Goal**: o motor executa o flow `chat` ponta a ponta — prepara contexto com os packs, gera em streaming pelo papel
`generation` e valida a resposta —, emitindo eventos neutros e deixando rastro no trace.

**Independent Test**: `uv run pytest packages/core/tests/graph` passa sem rede; a integração roda o caminho completo
com o Pack Runtime real e o `ai-generic`.

### Tests for User Story 1 ⚠️

> Escrever primeiro e confirmar que falham antes de implementar.

- [X] T008 [P] [US1] `ai-core/packages/core/tests/graph/unit/test_graph_api.py`: construção e validação dos tipos de
  T004 — requisição sem mensagens levanta, `reference_time` sem timezone levanta, `ProgressEvent` com etapa vazia
  levanta, `FinalEvent` aceita erros e marcações vazios, e a união `ExecutionEvent` cobre os três
- [X] T009 [P] [US1] `ai-core/packages/core/tests/graph/unit/test_graph_request.py`: `validate` devolve a última
  mensagem de papel `user` como pergunta (inclusive com mensagens de sistema e de assistente no meio); levanta
  `ExecutionRequestInvalid` sem mensagens e sem mensagem de usuário; levanta `UnknownFlow` nomeando o flow pedido e os
  disponíveis
- [X] T010 [P] [US1] `ai-core/packages/core/tests/graph/unit/test_graph_outcome.py`: resposta gerada preservada quando
  o validator não a altera; resposta e citações trocadas quando ele as altera; cada `issue` vira um `ExecutionIssue`;
  marcações preservadas; validator com `ok=False` **não** transforma a execução em falha
- [X] T011 [P] [US1] `ai-core/packages/core/tests/graph/contract/test_graph_clock_port.py` (o nome traz o módulo
  porque a 006 já tem um `test_clock_port.py` e o pytest coleta os testes num espaço de nomes só): os quatro itens de
  [contracts/ports.md](contracts/ports.md) — timezone nos dois adapters, `monotonic` não decrescente, data fixa
  repetida e duas execuções com a mesma data de referência
- [X] T012 [P] [US1] `ai-core/packages/core/tests/graph/unit/test_state_view.py`: a projeção `AgentState → TurnView` —
  `question` é a última mensagem de usuário, `reference_time` é a mesma em todas as Turn Views da execução,
  `generation_context` é vazio no `chat`, e as fatias devolvidas por `prepare` chegam a `validate`
- [X] T013 [P] [US1] `ai-core/packages/core/tests/graph/contract/test_execution_engine_seam.py`: os doze itens da
  suíte de [contracts/execution-engine.md](contracts/execution-engine.md), com os nomes que o
  [quickstart.md](quickstart.md) usa nos filtros (`streaming`, `invalida`, `validator`) — ordem dos eventos, tokens
  incrementais com o primeiro antes do fim da geração, resposta final, validator que altera, requisição inválida e
  flow inexistente levantados na chamada sem emitir nada, provider fora do ar e hook de pack que levanta virando
  `FinalEvent` com erro nomeado, `stream=False`, cancelamento no meio, o trace com começo, `ValidationRun` e fim, e a
  asserção de que nenhum módulo de `tests/graph/contract` e `tests/graph/unit` importa `langgraph` (SC-001)
- [X] T014 [P] [US1] `ai-core/packages/core/tests/graph/contract/test_flow_registry.py`: `flows()` devolve
  `{"chat"}`; registrar um flow de teste novo e executá-lo por nome não exige mudança fora do registro (US5 cen. 1)
- [X] T015 [P] [US1] `ai-core/packages/core/tests/graph/integration/test_chat_with_generic_pack.py`: o caminho
  completo com o Pack Runtime real (002) carregando o `ai-generic` (010) pelo entry point e o provider simulado da
  006 — o prompt do pack entra como mensagem de sistema, o validator `non_empty_answer` roda e aparece no trace, e a
  resposta chega em streaming

### Implementation for User Story 1

- [X] T016 [P] [US1] `ai-core/packages/core/src/ai_core/graph/adapters/clock.py`: `SystemClock` (`datetime.now(UTC)` e
  `time.monotonic`) e `FixedClock` (data fixa e leituras programadas, repetindo a última)
- [X] T017 [US1] `ai-core/packages/core/src/ai_core/graph/adapters/langgraph/state.py`: `AgentState` (TypedDict
  `total=False`) com identidade (`request_id`, `assistant`, `flow`, `reference_time`, `question`), `messages`, `packs`
  (fatias), `answer`, `citations`, `flags` e `errors` — estes com reducer de acumulação, porque é o que impede perda
  quando o grafo ganhar loop e ramos (FR-009, SC-005). **Privado**: nenhum outro módulo o importa
- [X] T018 [US1] `ai-core/packages/core/src/ai_core/graph/adapters/langgraph/view.py`: projeção
  `AgentState → TurnView` (contrato 001) conforme a tabela de [contracts/chat-flow.md](contracts/chat-flow.md)
- [X] T019 [US1] `ai-core/packages/core/src/ai_core/graph/adapters/langgraph/nodes.py`: os três nós finos, cada um
  delegando a um seam e escrevendo no canal de stream — `prepare_context` (`PackHooks.prepare`, progresso),
  `generate` (progresso **antes** da primeira chamada, que é o primeiro sinal da SC-004, mais `system_prompts` +
  `for_role("generation").stream`, com um `TokenEvent` por pedaço) e `validate_answer`
  (`PackHooks.validate`, progresso, um `ValidationRun` no trace por validator). Nó não contém regra: decisão é função
  de `domain/`
- [X] T020 [US1] `ai-core/packages/core/src/ai_core/graph/adapters/langgraph/flows.py`: o grafo do `chat`
  (`prepare_context → generate → validate_answer`) compilado, e o registro nome → grafo com `flows()`
- [X] T021 [US1] `ai-core/packages/core/src/ai_core/graph/adapters/langgraph/runtime.py`: consumir
  `astream(stream_mode=["custom", "values"])`, traduzindo `custom` em `TokenEvent`/`ProgressEvent` ao vivo e o último
  `values` em `FinalEvent` via `domain/outcome.py`; qualquer exceção do grafo vira `FinalEvent` com `ExecutionIssue`
  que nomeia etapa e causa (`PackHookError` nomeia o pack, `ModelCallFailed` nomeia provider e modelo), nunca
  propagada (R2, R6); fechar o iterador cancela sem levantar
- [X] T022 [US1] `ai-core/packages/core/src/ai_core/graph/service.py`: `ExecutionService` implementando
  `ExecutionEngine` — `flows()` delega ao registro; `run()` é função comum que valida por `domain/request.py`, fixa
  `reference_time` (da requisição, se houver, senão do relógio), emite `ExecutionStarted`, monta o estado inicial e
  devolve o iterador do runtime, emitindo `ExecutionFinished` ao encerrar e `ExecutionError` em falha (R5, R10). Não
  importa `adapters/`: recebe a fábrica do runtime na construção
- [X] T023 [US1] Rodar `uv run pytest packages/core/tests/graph` a partir de `ai-core/` até T008–T015 passarem, e
  `uv run mypy` e `uv run ruff check packages` limpos

**Checkpoint**: a US1 está completa e testável sozinha — a 008 e a 011 já podem consumir o seam

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T024 Acrescentar a `ai-core/pyproject.toml` os contratos de import-linter de [research.md](research.md) R12 —
  `ai_core.graph.api` não importa o resto do módulo; `ai_core.graph.domain` não importa portas, service nem adapters;
  `ai_core.graph.service` não importa adapters; `ai_core.graph.api`/`domain`/`ports`/`service` não importam
  `langgraph` nem `langchain_core`; e nenhum módulo do core fora de `ai_core.graph.adapters` importa o framework de
  grafo — e rodar `uv run lint-imports` até todos aparecerem como `KEPT`
- [X] T025 Executar as seções de [quickstart.md](quickstart.md) (pré-requisitos, verificação completa, cenários 1–4) e
  corrigir divergências entre o resultado e o "Esperado"
- [X] T026 [P] Atualizar a seção "Código" de `CLAUDE.md` (o módulo `ai_core/graph/` existe, com o seam Execution
  Engine e o flow `chat` em LangGraph; `agentic` e `rag_first` continuam para as Fases 3 e 5) e a linha da 005 em
  `specs/README.md` (status "Fase 1 implementada (US1: flow `chat`)")

---

## Phase 5: Fundação da Fase 3 (Blocking Prerequisites)

**Purpose**: o evento novo da 009 (ADR-017), as mudanças do seam (ADR-018, já escrito no SDD), as regras de requisição por flow e o testkit que o loop usa.
Caminhos relativos a `ai-core/packages/core/`.

**⚠️ CRITICAL**: nenhuma tarefa da US2 antes desta fase

- [X] T027 [P] Toque declarado na 009 (ADR-017, [research.md](research.md) R24). **Teste primeiro**:
  `tests/observability/unit/test_observability_controller_decision.py` — `ControllerDecision(request_id, iteration,
  action, tool=None, reason=None)` aceita `action ∈ {"tool", "answer", "invalid", "limit"}` e recusa outras;
  `request_id` não vazio; `iteration` inteiro `≥ 1`, e `0` **só** com `action="limit"`; `tool` obrigatório (não vazio)
  em `tool` e **ausente** nas outras ações; `reason` obrigatório em `invalid` e em `limit`, e em `limit` só
  `"iterations"` ou `"context"`; ausente em `tool`/`answer`; o registro gravado pelos backends de memória e JSONL tem
  `type == "controller_decision"` e atributos sem campo `None`. Depois: a dataclass em `src/ai_core/observability/api.py`
  (congelada, `kw_only`, `slots`, validação no `__post_init__`, docstring citando ADR-017: nunca argumentos nem saída
  do modelo) e o membro na união `TraceEvent`; o nome em `EXPECTED_NAMES` do teste de nomes públicos da 009; e, na
  documentação da 009: `specs/009-core-observability-evaluation/contracts/trace-api.md` (nome público, campos, e a frase
  "mudar qualquer linha exige ADR" anotada com a exceção do ADR-017), `contracts/record-format.md` (um exemplo de
  `controller_decision`) e `data-model.md` (seções `ToolCall` e `ControllerDecision`, que faltavam)
- [X] T028 [P] `src/ai_core/graph/api.py` (R15, R23, R16; ADR-018). **Teste primeiro** em `tests/graph/unit/test_graph_api.py`:
  `FLOW_AGENTIC == "agentic"`; `ExecutionIssue(stage, kind, message)` tem `severity == "error"` por default, aceita
  `"notice"` e recusa outro valor com `ValueError`; `ExecutionGrant is ai_core.assistants.api.ExecutionGrant`; os nomes
  públicos ganham `FLOW_AGENTIC`. Depois: `FLOW_AGENTIC: Final = "agentic"`; `type IssueSeverity = Literal["error",
  "notice"]` e o campo `severity: IssueSeverity = "error"` em `ExecutionIssue` (validado); remover o `Protocol`
  `ExecutionGrant` e importar/reexportar `ExecutionGrant` de `ai_core.assistants.api`; docstrings do módulo e de
  `run` atualizadas (o grant é o da 003; a ponte do R3 terminou)
- [X] T029 [P] `src/ai_core/graph/domain/request.py` (R16, R25). **Teste primeiro** em
  `tests/graph/unit/test_graph_request.py`: `REQUIRED_ROLES[FLOW_CHAT] == ("generation",)` e
  `REQUIRED_ROLES[FLOW_AGENTIC] == ("controller", "generation")`; `TOOL_FLOWS == frozenset({FLOW_AGENTIC})`;
  `offered(names, *, tools)` devolve os nomes sem os de `TOOL_FLOWS` quando `tools=False`; `required_roles(flow)`
  devolve `()` para flow sem entrada. Depois: as constantes e as duas funções (puras)
- [X] T030 [P] `src/ai_core/graph/domain/outcome.py` (R23). **Teste primeiro** em
  `tests/graph/unit/test_graph_outcome.py`: apontamento de validator sai com `severity="notice"` (o `kind` continua
  `ValidatorIssue`); `succeeded(final)` é `True` com só `notice`s e `False` com qualquer `error`, independentemente do
  `kind`. Depois: `_issues` com `severity="notice"`; `succeeded` por `severity`
- [X] T031 `tests/graph/graph_testkit.py` (R29) (depende de T028): `Grant(**overrides)` passa a ser **função** que
  devolve o `ExecutionGrant` da 003 — `assistant=ASSISTANT`, `principal=Principal(subject="user:test", ...)`,
  `flow="chat"`, `composition=Composition(packs=("generic",))`, `models` com `generation: ollama/qwen3:1.7b` e
  `controller: ctrl/controlador`, `allow=("ollama/*", "ctrl/*")`, `limits=Limits()` —, aceitando os mesmos nomes por
  palavra-chave (a chamada `Grant(assistant=...)` do `tests/http/http_testkit.py` continua valendo); `ScriptedController`
  (`name="ctrl"`, `chat(...)` sem streaming devolve, a cada chamada, o próximo item do roteiro — texto vira
  `{"message": {"role": "assistant", "content": texto}, "finish_reason": "stop"}`, exceção é levantada —, guarda
  `calls` com mensagens e `response_format`, e falha o teste se for chamado além do roteiro; `probe` disponível) e os
  ajudantes `tool_action(name, **arguments)`, `ANSWER`; `FakeSession` (`tools: Mapping[str, CatalogTool]`,
  `unavailable`, `execute(call)` que devolve o `FencedToolResult` programado por nome — texto no formato
  `<tool_result name="…" status="…" truncated="…">…</tool_result>` — e, para nome fora de `tools`, `status="unknown"`
  com "tool inexistente: <nome>"; guarda `calls`); `FakeCapabilities` (`open(grant, context)` guarda `context` e devolve
  a sessão, ou levanta o erro programado, como `CatalogConflict`); `engine(...)` ganha `capabilities=None` e
  `controller: ScriptedController | None`, registrando o controller no `ModelRoutingService` sob `"ctrl"`. Ajustar os
  usos de `Grant(...)` em `tests/graph/` e o `RealGrant` de `tests/graph/integration/test_chat_with_generic_pack.py`
  para o grant da 003; `uv run pytest packages/core/tests/graph packages/core/tests/http` continua verde

**Checkpoint**: seam acrescido, evento da 009 disponível, testkit com controller e gateway simulados

---

## Phase 6: User Story 2 — Loop agêntico com ação estruturada e limite (Priority: P1) — Fase 3

**Goal**: num Assistant `agentic`, o controller emite uma ação estruturada por iteração, o gateway executa, o resultado
cercado volta ao controller e o loop termina por resposta, limite, teto ou falha — sempre com geração e um
`FinalEvent`.

**Independent Test**: `uv run pytest packages/core/tests/graph -m us2` — controller simulado que sempre pede tool, com
limite 3: exatamente 3 chamadas ao controller e 3 execuções, geração e `IterationLimit` (quickstart, Fase 3).

### Tests for User Story 2 ⚠️

> Escrever primeiro e ver falhar. `tests/graph/contract/` e `tests/graph/unit/` (exceto `test_state_view.py`) não
> importam `langgraph` (SC-001).

- [X] T032 [P] [US2] `tests/graph/unit/test_graph_actions.py` (R17, R18): `CONTROLLER_INSTRUCTION` é texto do core, sem
  domínio; `action_schema(tools)` devolve `anyOf` com o ramo `answer` primeiro e um ramo por tool na ordem do
  catálogo — `action` `const "tool"`, `name` `const` com o nome, `arguments` = parâmetros saneados, `required` e
  `additionalProperties: false` em cada ramo; o saneamento remove `pattern` e `patternProperties` em qualquer
  profundidade e troca por `{"type": "object"}` o esquema que tem `$ref` em qualquer ponto, sem alterar o original;
  `response_format(tools) == {"type": "json_schema", "json_schema": {"name": "controller_action", "schema": …}}` sem
  `strict`; `catalog_text(tools)` lista uma linha por tool com nome, descrição e parâmetros em JSON compacto;
  `parse_action`: `None`, `""` e só espaços → `InvalidAction`; texto que não é JSON → "JSON malformado"; raiz lista ou
  número → inválida; `action` ausente ou fora de `tool`/`answer` → inválida; `tool` sem `name`, com `name` vazio ou não
  texto → inválida; `arguments` ausente → `{}`; `arguments` não objeto → inválida; `{"action": "answer"}` →
  `AnswerAction`; nome fora de qualquer catálogo → `ToolAction` (o gateway decide); hypothesis: para texto arbitrário,
  `parse_action` nunca levanta e o `reason` de uma `InvalidAction` está no conjunto fixo de motivos (nunca contém o
  texto recebido)
- [X] T033 [P] [US2] `tests/graph/unit/test_graph_limits.py` (R20): `DEFAULT_MAX_ITERATIONS == 3`;
  `effective_limit(None) == 3` e `effective_limit(5) == 5`; `after_decision(kind, iteration, limit)` reproduz a tabela
  "Limite" de [contracts/agentic-flow.md](contracts/agentic-flow.md) — `tool`/`invalid` com `n < limite` → volta ao
  controller; com `n == limite` → geração com truncamento; `answer` → geração sem truncamento; `failed` → geração;
  hypothesis: para qualquer sequência de decisões e limite de 1 a 6, a simulação pura nunca passa de `limite` chamadas
- [X] T034 [P] [US2] `tests/graph/unit/test_graph_budget.py` (R22): `estimate_tokens(messages)` = soma de
  `ceil(caracteres / 3) + 4` por mensagem, contando conteúdo e, em `tool_calls`, nome e argumentos; `exceeds(messages,
  None)` é sempre `False`; `trim_results(messages, ceiling)` troca o conteúdo das mensagens `tool` **da mais antiga
  para a mais nova** pela marca exata `[resultado omitido: teto de contexto]`, para assim que cabe e devolve as
  mensagens, quantas saíram e se ainda excede (overflow); sem teto, devolve as mensagens intactas; nunca altera
  mensagens que não são `tool`
- [X] T035 [P] [US2] `tests/graph/unit/test_graph_transcript.py` (R19): `controller_messages(...)` = sistema (instrução +
  `catalog_text` + `FENCE_INSTRUCTION` da 004, sem prompts de pack), mensagens da requisição, e a transcrição — por
  tool executada, `assistant` com `content=None` e `tool_calls=[{"id": "call-<n>", "name", "arguments": JSON}]` seguido
  de `tool` com `tool_call_id="call-<n>"` e o texto cercado tal como veio; por ação inválida, um `user` com "A ação
  anterior era inválida: <motivo>. Responda com uma ação válida."; `generation_messages(prompts, messages, transcript)`
  com transcrição vazia == exatamente as mensagens do `chat` (um `system` por prompt de pack + mensagens da
  requisição); com ao menos um resultado, a `FENCE_INSTRUCTION` entra como `system` logo depois dos prompts de pack, e
  a transcrição vem depois das mensagens da requisição (sem os avisos de ação inválida)
- [X] T036 [P] [US2] Estender `tests/graph/unit/test_state_view.py` (R26): com resultados no estado, a Turn View de
  `validate` traz um `ToolResult` (001) por resultado entregue à geração, na ordem — `content` = texto cercado,
  `untrusted=True`, `truncated` e `error` do `FencedToolResult` —, sem os omitidos pelo teto; `retrieved` = chunks de
  todos os resultados de recuperação; `generation_context` = chunks dos que ficaram; `reranked` vazio; a view de
  `prepare` não tem resultados
- [X] T037 [P] [US2] `tests/graph/contract/test_agentic_flow.py`: os itens 13–23 de
  [contracts/execution-engine.md](contracts/execution-engine.md) com `FakeCapabilities`, `ScriptedController` e o
  roteador real — (13) `tool_action("generic.calculate", expression="2+2")` e `ANSWER`: uma execução, o resultado
  cercado na última mensagem `tool` da geração, `FENCE_INSTRUCTION` no sistema da geração, `FinalEvent` sem `error`;
  (14) limite 3 no grant e roteiro só de tools: 3 chamadas ao controller, 3 execuções, `IterationLimit` `notice`; o
  mesmo com `Limits()` (padrão 3); (15) ação malformada conta, gera `InvalidAction` `notice` e a execução segue;
  (16) nome fora do catálogo: o `FencedToolResult` `unknown` volta na transcrição do controller seguinte e conta como
  iteração; (17) `ModelCallFailed` no controller: a geração acontece, registro `ModelCallFailed` `error`, nenhuma nova
  chamada ao controller; (18) sessão sem tools: zero chamadas ao controller; (19) teto: com `max_context_tokens`
  pequeno o loop para antes da chamada que passaria (`ContextLimit`), e na geração os resultados mais antigos saem com
  a marca (`ContextTrimmed` com a contagem), e o número de passos acumulados não muda (a omissão vale só para o que
  vai ao modelo); sem teto, nada sai; (20) a Turn View de `validate` (via `ScriptedHooks`)
  traz os resultados entregues, na ordem; (21) uma `ControllerDecision` por chamada ao controller (+ `limit` com
  `reason`), nenhuma com argumentos; `ToolCall` não é emitido pelo motor; `ExecutionFinished.ok` é `True` com só
  `notice`s; (22) `agentic` sem papel `controller` → `ExecutionRequestInvalid` na chamada de `run`, nomeando o papel,
  sem evento e sem chamada a provider; `ToolContext` recebido pelo `open` tem `request_id`, `reference_time` e os
  `retrieval_filters` das fatias; progresso `load_capabilities`, `controller` (`"iteração <n>"`) e `execute_tool`
  (nome) na ordem; `CatalogConflict` no `open` → `FinalEvent` com `kind="CatalogConflict"`,
  `stage="load_capabilities"`, sem geração; `session.unavailable` → um `McpUnavailable` com `severity="error"` por alias, e a execução segue com o catálogo
  que há; (23) fechar o iterador depois do progresso `execute_tool` não levanta, não há nova chamada ao controller nem
  à tool, e o trace fecha com `ExecutionFinished(reason="cancelled")`
- [X] T038 [P] [US2] `tests/graph/contract/test_agentic_properties.py` (SC-002, SC-005): hypothesis gera roteiros de 1 a
  10 itens (tool válida, tool inexistente, JSON malformado, `answer`, `ModelCallFailed`) e limites de 1 a 6;
  propriedades: chamadas ao controller ≤ limite; execuções ≤ limite; exatamente um `FinalEvent`, o último; todo
  resultado executado aparece na transcrição da geração e na Turn View de `validate`, na ordem; `ControllerDecision`s ==
  chamadas ao controller que não falharam (+1 quando o loop termina por limite). Sem teto declarado
- [X] T039 [P] [US2] Estender `tests/graph/contract/test_flow_registry.py` (R16): sem `capabilities`, `flows() ==
  {"chat"}` e um grant `agentic` levanta `UnknownFlow` na chamada; com `FakeCapabilities`, `flows() == {"chat",
  "agentic"}`
- [X] T040 [P] [US2] `tests/graph/integration/test_agentic_with_generic_pack.py`: `PackRuntime` real carregando o
  `ai-generic` por entry point; `CapabilityService` real (004) com `pack_tools=` o `PackRuntime`, MCP pelo `McpService`
  da 007 em memória sem servidores (o arranjo de `tests/capabilities/integration/test_session_mcp.py`, sem transporte
  de rede), `InMemoryAuditLog`; `ScriptedController` com `tool_action("generic.calculate", expression="2+2")` e
  `ANSWER`; o resultado da tool nativa chega cercado (`<tool_result name="generic.calculate" status="ok"`) à geração; o
  trace tem, em ordem, `ExecutionStarted`, `ModelCall(controller)`, `ControllerDecision(tool)`, `ToolCall`,
  `ModelCall(controller)`, `ControllerDecision(answer)`, `ModelCall(generation)`, `ValidationRun`,
  `ExecutionFinished(ok=True)`

### Implementation for User Story 2

- [X] T041 [P] [US2] `src/ai_core/graph/domain/actions.py` (R17, R18): `CONTROLLER_INSTRUCTION`; `ToolAction(name,
  arguments)`, `AnswerAction`, `InvalidAction(reason)` (dataclasses congeladas); `sanitize(parameters)`;
  `action_schema(tools)`; `response_format(tools)`; `catalog_text(tools)`; `parse_action(content)`. Recebe
  `CatalogTool` da 004; só stdlib e `api.py`s (faz T032 passar)
- [X] T042 [P] [US2] `src/ai_core/graph/domain/limits.py` (R20): `DEFAULT_MAX_ITERATIONS: Final = 3`,
  `effective_limit`, `after_decision` com o resultado `Route(next: Literal["controller", "generate"], truncated: bool)`
  (faz T033 passar)
- [X] T043 [P] [US2] `src/ai_core/graph/domain/budget.py` (R22): `CHARS_PER_TOKEN: Final = 3`,
  `MESSAGE_OVERHEAD: Final = 4`, `OMITTED: Final = "[resultado omitido: teto de contexto]"`, `estimate_tokens`,
  `exceeds`, `trim_results` com resultado `Trimmed(messages, omitted, overflow)` (faz T034 passar)
- [X] T044 [US2] `src/ai_core/graph/domain/transcript.py` (R19) (depende de T041): `Step` (tool executada com
  `ToolCall` e `FencedToolResult`, ou ação inválida com motivo), `controller_messages`, `generation_messages` (faz T035
  passar)
- [X] T045 [US2] `src/ai_core/graph/ports.py`: `ExecutionPlan` ganha `grant: ExecutionGrant`, `capabilities:
  Capabilities | None`, `max_iterations: int | None` e `max_context_tokens: int | None` (os dois `None` no `chat`, R22)
- [X] T046 [US2] `src/ai_core/graph/service.py` (R16, R25) (depende de T029, T045): `capabilities: Capabilities | None
  = None` no construtor; `flows()` = `offered(runtime.names(), tools=capabilities is not None)`; `run()` valida o flow
  contra `flows()`, resolve `for_role` de cada papel de `required_roles(grant.flow)` no roteador da execução e converte
  `ModelRoutingError` em `ExecutionRequestInvalid("papel '<papel>': <motivo>")`, e só no flow de `TOOL_FLOWS` lê
  `effective_limit(grant.limits.max_iterations)` e `grant.limits.max_context_tokens` para o plano
- [X] T047 [US2] `src/ai_core/graph/adapters/langgraph/state.py` e `view.py` (R26, R31): `AgentState` ganha `iteration`,
  `limit`, `ceiling`, `next_action`, e os acumuladores com `operator.add` `steps` e `decisions`; `AgentContext` ganha
  `grant`, `capabilities` e um compartimento mutável para a `ToolSession`; `turn_view` projeta `tool_results`,
  `retrieved` e `generation_context` a partir dos passos entregues à geração (faz T036 passar)
- [X] T048 [US2] `src/ai_core/graph/adapters/langgraph/nodes/` (R31) (depende de T044, T047): mover `nodes.py` para
  `nodes/common.py` (canais `TOKEN`/`PROGRESS`, `prepare_context`, `generate`, `validate_answer`), com `generate`
  montando as mensagens por `generation_messages` e, quando há teto, aplicando `trim_results` e registrando
  `ContextTrimmed`/`ContextOverflow` (`notice`, estágio `generate`); `nodes/__init__.py` só com docstring; ajustar os
  imports de `flows.py` e `runtime.py`
- [X] T049 [US2] `src/ai_core/graph/adapters/langgraph/nodes/agentic.py` (R16, R20–R22, R24, R27, R28) (depende de
  T041–T044, T048): `load_capabilities` (progresso; `ToolContext` com `retrieval_filters` = por pack, o valor de
  `RETRIEVAL_FILTERS_KEY` da fatia quando é mapeamento; abre a sessão e guarda no compartimento; um `McpUnavailable`
  `error` por alias de `unavailable`); `controller` (checa o teto pelas `controller_messages` antes de chamar —
  `ContextLimit` e `ControllerDecision(limit, reason="context")`; progresso `"iteração <n>"`; `complete(...,
  response_format=response_format(tools))`; `ModelCallFailed` → registro `error` + `ExecutionError(stage="controller")`
  no trace e rota para a geração; `parse_action`; `ControllerDecision` com `tool`/`answer`/`invalid`; rota por
  `after_decision`, com `IterationLimit` e `ControllerDecision(limit, reason="iterations")` quando trunca);
  `execute_tool` (progresso com o nome; `session.execute(ToolCall(...))`; acumula o passo; rota por `after_decision`)
- [X] T050 [US2] `src/ai_core/graph/adapters/langgraph/flows.py` (depende de T049): `agentic_graph()` com
  `prepare_context → load_capabilities → (controller | generate)`, `controller ⇄ execute_tool`, `→ generate →
  validate_answer`, arestas condicionais chamando só funções de `domain/` (catálogo vazio → `generate`, R27);
  `compiled_flows()` registra `chat` e `agentic`
- [X] T051 [US2] `src/ai_core/graph/adapters/langgraph/runtime.py` (depende de T050): estado inicial e `AgentContext`
  com os campos do loop vindos do plano; `_issue` mapeia `CatalogConflict` para `stage="load_capabilities"`; o
  `FinalEvent` junta os registros acumulados (com `severity`) e o resultado dos validators
- [X] T052 [US2] Rodar `uv run pytest packages/core/tests/graph` a partir de `ai-core/` até T032–T040 passarem (e os
  testes da Fase 1 continuarem verdes), com `uv run mypy` e `uv run ruff check packages` limpos

**Checkpoint**: a US2 está completa e testável sozinha, com gateway falso e com o real da 004

---

## Phase 7: Polish da Fase 3

- [X] T053 Contratos de import-linter de [research.md](research.md) R32 em `ai-core/pyproject.toml`: `ai_core.graph` não
  importa `ai_core.mcp` (nenhum submódulo, nem o `api.py`); `ai_core.capabilities` e `ai_core.mcp` entram nas fontes do
  contrato "o framework de grafo só existe no adapter do motor"; descrição da marca `us2` passa a citar também
  "005 US2 — flow agentic"; `uv run lint-imports` com todos `KEPT`
- [X] T054 Executar as seções da Fase 3 de [quickstart.md](quickstart.md) e corrigir divergências entre o resultado e o
  "Esperado"
- [X] T055 [P] Documentação: linha da 005 em `specs/README.md` ("Fase 1 implementada (US1: flow `chat`); Fase 3
  implementada (US2: flow `agentic`)"), a menção ao ADR-017 na linha do seam Trace Sink e ao ADR-018 na do seam
  Execution Engine; seção "Código" de
  `CLAUDE.md` (o `agentic` existe, o grant é o da 003, o `ExecutionService` aceita `capabilities` e a 011 o liga na
  passada dela; `ControllerDecision` na 009)
- [X] T056 Verificação completa a partir de `ai-core/`: `uv run pytest`, `uv run mypy`, `uv run ruff check packages`,
  `uv run lint-imports`, e a suíte com `AI_CORE_TEST_POSTGRES_DSN` apontando para o Postgres de teste

---

## Passada de 2026-10-07: validators que filtram o streaming ([ADR-024](../../docs/adr/ADR-024-validators-filtram-o-streaming.md); research R34)

- [X] T057 `nodes/common.py`: `generate` pelo filtro (`open_answer_stream`, `feed`, `finish`, cauda) e
  `validate_answer` com `streamed` e o acréscimo final (`_deliver_rest`); `state.py`: `streamed`
- [X] T058 `graph_testkit`: `ScriptedHooks.open_answer_stream`, `PassThroughFilter`, `DropFilter`; testes
  `tests/graph/contract/test_streaming_filter.py` e `tests/graph/integration/test_streaming_validators.py`

---

---

## Phase 8: Fundação da Fase 5 (Blocking Prerequisites)

**Purpose**: os toques declarados fora da 005 (R35), o seam acrescido, as políticas puras e o testkit que o `rag_first`
usa. Caminhos relativos a `ai-core/packages/core/`.

**⚠️ CRITICAL**: nenhuma tarefa da US3 antes desta fase

- [X] T059 [P] Em `ai-core/pyproject.toml`, acrescentar "005 US3 — flow rag_first" à descrição da marca `us3` e "005
  US4 — validação no rag_first" à da `us4`
- [X] T060 [P] Toque declarado na 004 — renderização com o identificador ([ADR-026](../../docs/adr/ADR-026-o-modelo-ve-o-identificador-de-cada-trecho.md),
  decisão 1). **Teste primeiro** em `tests/capabilities/unit/test_rendering.py`: chunk com seção e página →
  `[Doc — Regra 33, p. 9 · id: doc#r33@p9]` + quebra de linha + texto; sem seção → `[Doc, p. 9 · id: …]`; sem página →
  `[Doc — Regra 33 · id: …]`; sem as duas → `[Doc · id: …]`; o texto do chunk sai igual (decisão 4); sem chunks continua
  "nenhum resultado"; `render_within(chunks, max_bytes) -> Rendered(text, chunks, truncated)` inclui trechos
  **inteiros** enquanto o texto couber em `max_bytes` (UTF-8) e, se nem o primeiro couber inteiro, só ele, cortado no
  texto, com a linha de referência e o `id` intactos; `chunks` = os que entraram, na ordem; `truncated` quando algum
  ficou de fora ou foi cortado (US4 cen. 2: o que o modelo não vê não está no `generation_context`). Depois: `_reference`
  e `render_within` em `src/ai_core/capabilities/domain/rendering.py` (docstring citando o ADR-026: o formato é
  garantia aos packs). Ajustar as asserções do formato antigo em `tests/capabilities/` e
  `tests/graph/` que comparem o texto renderizado; na documentação da 004, tirar de
  `specs/004-core-capability-gateway/contracts/fencing.md` a nota "implementado na passada da 005 Fase 5" e acrescentar
  "recuperação cortada por trecho inteiro; `chunks` = os que entraram"
- [X] T061 Toque declarado na 004 — `ToolSession.fence_chunks(name, chunks) -> FencedToolResult` (ADR-026, decisão 2;
  R41) (depende de T060). **Teste primeiro** em `tests/capabilities/contract/test_session_fence_chunks.py`: com a sessão
  real (`CapabilityService.open`) e uma tool `retrieval` no catálogo, `fence_chunks("<pack>.<tool>", chunks)` devolve
  `kind="retrieval"`, `status="ok"`, `chunks` iguais aos recebidos (mesma ordem), `text` = a cerca de
  `contracts/fencing.md` com os blocos do ADR-026, por `render_within` com `max_response_bytes` (`chunks` = só os que
  entraram; `truncated=True` quando algum ficou de fora); sem chunks, "nenhum resultado"; nome fora do catálogo ou de tool que não é `retrieval` → `ValueError` nomeando a tool;
  **não** executa retriever, **não** emite `ToolCall` (009) e **não** audita — os trechos já passaram pelo gateway na
  recuperação. Depois: o método no `Protocol` `ToolSession` de `src/ai_core/capabilities/api.py` (docstring: o motor
  entrega à geração trechos que já recuperou, no mesmo formato e na mesma cerca) e em `Session`
  (`src/ai_core/capabilities/service.py`, por `render_within` e a cerca de `_finish`). Na mesma tarefa, a recuperação
  executada pelo gateway (`_run`/`_finish`, a que o `agentic` usa) troca o `cut` do texto por `render_within`: caso novo
  em `tests/capabilities/contract/test_session_execute.py` — com `max_response_bytes` pequeno, os `chunks` do resultado
  são só os que aparecem no texto. A linha em `specs/004-core-capability-gateway/contracts/capabilities-api.md`, citando
  que `fence_chunks` é como a 004 cumpre a decisão 2 do ADR-026 (a renderização fica no domínio e é exposta pelo
  `api.py`)
- [X] T062 [P] Toque declarado na 002 — `PackHooks.reranker(composition, pack) -> Reranker | None` (R38; design.md da
  002, Fase 5). **Teste primeiro** em `tests/packs/contract/test_packs_hooks_seam.py`: pack com reranker → o **mesmo**
  objeto coletado na carga (o hook de catálogo não é chamado de novo); pack sem reranker → `None`; pack fora da
  composição → `ValueError` nomeando o pack; a composição é revalidada como nos outros hooks (`CompositionError` para
  composição montada à mão inválida). Depois: o método no `Protocol` `PackHooks` (`src/ai_core/packs/api.py`) e em
  `PackRuntime` (`src/ai_core/packs/service.py`, por `_members`); a assinatura por pack em
  `specs/002-core-pack-runtime/contracts/pack-runtime-api.md` (troca a `reranker(composition)` ilustrativa, citando o
  R38 da 005)
- [X] T063 [P] Toque declarado na 009 — evento `CoverageGate` (ADR-017; R39). **Teste primeiro** em
  `tests/observability/unit/test_observability_coverage_gate.py`: `CoverageGate(request_id, candidates, passages,
  best_score, threshold, covered, route)`; `request_id` não vazio; `candidates` e `passages` inteiros `≥ 0` (não `bool`),
  com `passages ≤ candidates`; `best_score` `None` **se e só se** `passages == 0`; `threshold` `None` ou em `[0, 1]`;
  `route ∈ {"generate", "controller", "fallback"}`, com `covered` **se e só se** `route == "generate"`; o registro dos
  backends de memória e JSONL tem `type == "coverage_gate"` e atributos sem campo `None`. Depois: a dataclass em
  `src/ai_core/observability/api.py` (congelada, `kw_only`, `slots`; docstring: sem texto nem identificador de trecho) e
  o membro na união `TraceEvent`; o nome em `EXPECTED_NAMES` de `tests/observability/unit/test_observability_api.py`; na
  documentação da 009: `contracts/trace-api.md` (nome, campos, ADR-017), `contracts/record-format.md` (um exemplo de
  `coverage_gate`) e `data-model.md`
- [X] T064 [P] `src/ai_core/graph/api.py` (R44; data-model "Fase 5"). **Teste primeiro** em
  `tests/graph/unit/test_graph_api.py`: `FLOW_RAG_FIRST == "rag_first"`; `RagSettings()` tem `candidates == 20`,
  `passages == 5`, `min_score is None`; `candidates < 1`, `passages < 1` e valores `bool` → `ValueError` nomeando o
  campo; `min_score` fora de `[0, 1]` ou NaN → `ValueError`; `0.0` e `1.0` aceitos; os nomes públicos ganham
  `FLOW_RAG_FIRST` e `RagSettings`. Depois: as duas definições (`RagSettings` congelada, `kw_only`, `slots`, docstring
  citando a clarificação 1 de 2026-10-09: sem limiar, só a ausência de resultado escala; a 105 calibra) e o `__all__`
- [X] T065 `src/ai_core/graph/domain/request.py` (R40; FR-007a) (depende de T064). **Teste primeiro** em
  `tests/graph/unit/test_graph_request.py`: `REQUIRED_ROLES[FLOW_RAG_FIRST] == ("generation",)`; `FLOW_RAG_FIRST in
  TOOL_FLOWS`; `optional_roles(FLOW_RAG_FIRST) == ("controller",)` e `()` nos outros flows; `offered(..., tools=False)`
  tira também o `rag_first`. Depois: a entrada em `REQUIRED_ROLES`, `TOOL_FLOWS` e `OPTIONAL_ROLES`/`optional_roles`
- [X] T066 [P] `src/ai_core/graph/domain/gate.py` (R37–R40) — puro: stdlib, contratos e os `api.py` da 004. **Teste
  primeiro** em `tests/graph/unit/test_graph_gate.py`, por tabela: `Passage(pack, tool, chunk)` congelada;
  `retrieval_tools(tools)` → as `CatalogTool` de `kind == "retrieval"`, na ordem do catálogo; `pack_of(name)` → o
  prefixo antes do primeiro `.`; `first(passages, n)` → os `n` primeiros; `accept_reranked(documents, reranked, top_k)`
  → a tupla quando todo item veio de `documents` (mesmo `chunk_id`), sem repetição e com no máximo `top_k`; senão `None`
  com o motivo; `merge(groups, passages)` → um grupo: ele, cortado; vários: ordem estável por `chunk.score`
  decrescente (empate mantém a ordem dos grupos e a posição), cortada em `passages`; `best_score(passages)` → `None` sem
  itens; `is_covered(passages, min_score)` → sem itens `False`, sem limiar `True`, `best ≥ min_score` `True` (igual
  conta); `gate_route(covered, *, escalate)` → `"generate"` coberto, `"controller"` sem cobertura com `escalate`,
  `"fallback"` sem; hypothesis: `merge` nunca devolve mais que `passages`, só itens dos grupos, e preserva a ordem
  relativa de cada grupo. Depois: o módulo
- [X] T067 [P] `src/ai_core/graph/domain/budget.py` — `fit_chunks` (R42). **Teste primeiro** em
  `tests/graph/unit/test_graph_budget.py`: `fit_chunks(items, build, ceiling) -> Fitted(items, dropped, overflow)`;
  sem teto, todos e `dropped == 0`; com teto, tira do **fim** (menor posição) um a um até `not exceeds(build(kept),
  ceiling)`; nunca reordena; se nem sem itens cabe, `items == ()` e `overflow is True`; `build` recebe sempre um prefixo
  da lista. Depois: a função genérica e `Fitted`; o docstring do módulo deixa de anunciar o corte como futuro
- [X] T068 [P] `src/ai_core/graph/domain/transcript.py` (R41, R43). **Teste primeiro** em
  `tests/graph/unit/test_graph_transcript.py`: `ToolStep` aceita `synthetic: bool = False`; um passo sintético entra em
  `generation_messages` exatamente como um passo executado (`assistant` com `tool_calls` + `tool` com o texto cercado,
  `FENCE_INSTRUCTION` no sistema). Depois: o campo, com docstring (o passo que o portão grava; a projeção não soma os
  chunks dele em `retrieved`)
- [X] T069 `tests/graph/graph_testkit.py` (R46) (depende de T061, T062, T064): `chunk(chunk_id, score, *,
  document="Doc", section=None, page=None, text=None)`; `rendered(chunks)` no formato do ADR-026; `ScriptedReranker(*,
  order=None, error=None, extra=None)` (reordena pelos `chunk_id` programados ou inverte; levanta `error`; acrescenta
  `extra` para simular trecho estranho; guarda `calls` com pergunta, documentos e `top_k`); `ScriptedHooks` ganha
  `rerankers: Mapping[str, Reranker]` e `reranker(composition, pack)`; `FakeSession` ganha `failures: Mapping[str,
  tuple[str, str]]` (status `error`/`timeout` e motivo, para a tool de recuperação que falha) e `fence_chunks(name,
  chunks)` (`fenced(name, rendered(chunks))`, guardando `fenced_calls`); `rag(**overrides)` → grant `flow="rag_first"`,
  `composition=Composition(packs=("docs",))`, sem `controller` por default (`models(controller=False)`), com
  `controller=True` para a escalada; `engine(..., rag: RagSettings | None = None)` repassa ao `ExecutionService`; os
  testes de `tests/graph/` continuam verdes

**Checkpoint**: 002, 004 e 009 com os toques declarados e testados; seam e políticas puras do `rag_first` prontos

---

## Phase 9: User Story 3 — `rag_first` com portão de cobertura (Priority: P2) — Fase 5

**Goal**: num Assistant `rag_first`, o motor recupera pelo gateway com os filtros do pack, reordena com o reranker de
cada pack, aplica o portão e gera com **uma** chamada de modelo no caminho coberto; sem cobertura, escala para o loop
(com `controller`) ou gera sem trechos e registra (sem); recuperação que falha encerra com erro, sem gerar.

**Independent Test**: `uv run pytest packages/core/tests/graph -m us3` — retriever e reranker simulados: caminho
coberto com exatamente um `ModelCall` (SC-003); escalada e geração sem trechos conforme o `controller`; `error` sem
geração quando a recuperação falha (quickstart, Fase 5).

### Tests for User Story 3 ⚠️

> Escrever primeiro e ver falhar. `tests/graph/contract/` e `tests/graph/unit/` (exceto `test_state_view.py`) não
> importam `langgraph` (SC-001).

- [X] T070 [P] [US3] `tests/graph/contract/test_rag_first_flow.py` (contracts/rag-first-flow.md; US3 cen. 1–4, SC-003):
  **cen. 1** — pack `docs` com a tool `docs.search` e 8 chunks; a tool é executada uma vez com `{"query": <pergunta>,
  "top_k": 20}`; o reranker recebe os 8 e `top_k=5`; no trace, exatamente um `ModelCall` (papel `generation`) e nenhum do
  `controller` (SC-003); as mensagens da geração têm os prompts do pack, a `FENCE_INSTRUCTION`, a conversa, um
  `assistant` com `tool_calls` (`docs.search`, `{"query": …}`) e um `tool` com os 5 trechos, cada um com `· id:
  <chunk_id>` (ADR-026); `CoverageGate(covered=True, route="generate", candidates=8, passages=5)`; a variante com
  `RagSettings(min_score=0.5)` e melhor score 0,8 também é coberta, com `route="generate"`; progresso na ordem
  `prepare_context`, `retrieve`, `rerank`, `gate`, `generate`, `validate_answer`, com `retrieve` antes de qualquer
  chamada de modelo (R45); `FinalEvent` sem `error`. **cen. 2** — com `controller` e (a) nenhum resultado, (b)
  `RagSettings(min_score=0.9)` e melhor score 0,8: o controller é chamado; suas mensagens não têm nenhum dos trechos
  recusados (transcrição vazia); o limite é o do grant (ou 3); `CoverageGate(covered=False, route="controller")`; sem
  `CoverageInsufficient`. **cen. 3** — idem sem `controller`: uma chamada de geração sem `FENCE_INSTRUCTION` nem
  mensagem `tool`; registro `CoverageInsufficient` (`notice`, estágio `gate`); `route="fallback"`; a execução não falha.
  **cen. 4** — a fatia do pack com `RETRIEVAL_FILTERS_KEY` chega intacta ao `ToolContext` da sessão
  (`FakeCapabilities.opened`), por pack; o motor não lê os filtros
- [X] T071 [P] [US3] `tests/graph/contract/test_rag_first_failures.py` (R37, R38; princípio VII): tool de recuperação
  com status `error` ou `timeout` → `FinalEvent` com `answer == ""` e o registro `RetrievalFailed` (`error`, estágio
  `retrieve`, nomeando a tool e o motivo), um `ExecutionError` no trace, **nenhum** `ModelCall`, nenhum validator,
  nenhum `CoverageGate`, e `ExecutionFinished(ok=False)`; com duas tools, a segunda não é executada depois da falha da
  primeira; reranker que levanta → `RerankFailed` (`notice`, nomeando o pack) e os 5 primeiros na ordem do retriever;
  reranker que devolve trecho que não veio da recuperação, ou mais que `top_k` → idem; pack sem reranker → os 5
  primeiros, sem registro; catálogo sem tool de recuperação → nenhum candidato, sem cobertura (rota pelo `controller`);
  MCP em `unavailable` → `McpUnavailable` (`error`), como no `agentic`; com `controller` e catálogo vazio → `fallback`
- [X] T072 [P] [US3] `tests/graph/contract/test_rag_first_packs.py` (R38, R41): dois packs, cada um com a sua tool de
  recuperação e o seu reranker — cada reranker recebe só os chunks do seu pack; a junção vai pelas cabeças dos grupos
  (maior score primeiro, sem desfazer a ordem de cada reranker) e corta em `passages`; a geração recebe um passo
  sintético por tool com trecho entregue, na ordem em que cada tool aparece na junção, e nenhum passo para o pack sem
  trecho entregue
- [X] T073 [P] [US3] `tests/graph/contract/test_flow_registry.py` (R40, ADR-019): com gateway, `flows() == {"chat",
  "agentic", "rag_first"}` e `flow_roles()["rag_first"] == ("generation",)`; sem gateway, `rag_first` não é oferecido;
  `run` com grant `rag_first` sem `controller` é aceito; com `controller` declarado fora da allowlist →
  `ExecutionRequestInvalid` nomeando o papel, na própria chamada (FR-013)
- [X] T074 [P] [US3] `tests/graph/unit/test_state_view.py` (R43; tabela "Turn View no `rag_first`" do data-model):
  coberto — `retrieved` = todos os candidatos, `reranked` = a junção, `generation_context` e `tool_results` = os do
  passo sintético; `fallback` — `generation_context` e `tool_results` vazios, `retrieved` e `reranked` preenchidos;
  escalado — `retrieved` = candidatos + chunks dos passos do loop, `generation_context` = os do loop entregues; os
  passos sintéticos nunca duplicam chunks em `retrieved`
- [X] T075 [P] [US3] `tests/graph/contract/test_rag_first_properties.py` (hypothesis; SC-003, SC-005): para 0–30 chunks
  com scores arbitrários em `[0, 1]`, `min_score` arbitrário ou `None` e grant sem `controller` — exatamente um
  `FinalEvent`, sempre o último; no máximo uma chamada de geração e nenhuma do controller; `generation_context ⊆
  reranked ⊆ retrieved`; `len(reranked) ≤ passages`; o `CoverageGate` é emitido uma vez e concorda com a rota

### Implementation for User Story 3

- [X] T076 [US3] `src/ai_core/graph/ports.py` e `src/ai_core/graph/service.py` (R40, R44) (depende de T064, T065):
  `ExecutionPlan` ganha `rag: RagSettings | None = None` e `escalate: bool = False`; `ExecutionService(..., rag:
  RagSettings | None = None)` (default `RagSettings()`); no `rag_first`, o plano leva `rag` e `escalate = "controller"
  in grant.models.roles`, e cada papel de `optional_roles(flow)` declarado no grant é resolvido antes do primeiro evento,
  com o mesmo `ExecutionRequestInvalid` do obrigatório (faz T073 passar)
- [X] T077 [US3] `src/ai_core/graph/adapters/langgraph/state.py` e `runtime.py` (R43; data-model "Estado interno")
  (depende de T066, T076): `AgentState` ganha `retrieved: tuple[Passage, ...]` e `reranked: tuple[Passage, ...]`, e a
  rota ganha `"end"`; `AgentContext` ganha `rag` e `escalate`; o estado inicial do runtime com `retrieved=()` e
  `reranked=()`, e o contexto com os campos do plano
- [X] T078 [US3] `src/ai_core/graph/adapters/langgraph/nodes/agentic.py`: extrair de `load_capabilities` a abertura da
  sessão (`ToolContext` com os filtros das fatias, guarda no `ToolSlot`, registros `McpUnavailable`) para uma função
  reaproveitada pelo `retrieve`, sem mudar o comportamento do `agentic` (os testes da US2 continuam verdes)
- [X] T079 [US3] `src/ai_core/graph/adapters/langgraph/nodes/rag.py` (R37–R42, R45) (depende de T061, T062, T063,
  T066–T068, T077, T078): `retrieve` — progresso; abre a sessão; para cada tool de `retrieval_tools`, `execute` com
  `{"query": <pergunta>, "top_k": rag.candidates}`; status ≠ `ok` → `RetrievalFailed` (`error`) + `ExecutionError`
  (009) e rota `"end"`, sem executar as tools seguintes; senão, `retrieved` como `Passage`s na ordem do catálogo e
  progresso com a contagem. `rerank` — progresso; por pack (`pack_of`), `hooks.reranker(composition, pack)`; com
  reranker, `rerank(pergunta, chunks, top_k=rag.passages)` validado por `accept_reranked`; exceção ou recusa →
  `RerankFailed` (`notice`) e `first`; sem reranker, `first`; `reranked = merge(grupos, rag.passages)`. `gate` —
  progresso; `is_covered` com `rag.min_score`; `gate_route(covered, escalate=ctx.escalate and bool(session.tools))`;
  `CoverageGate` no trace; `"generate"` → `fit_chunks(reranked, build, ceiling)`, em que `build` monta
  `generation_messages` com um `ToolStep(synthetic=True)` por tool com trecho entregue (iterações 1…n, chamada
  `<pack>.<tool>` com `{"query": <pergunta>}`, resultado `session.fence_chunks`), `ContextTrimmed` (`notice`, com a
  contagem) quando corta, e os passos no estado; `"fallback"` → `CoverageInsufficient` (`notice`) e rota `generate`;
  `"controller"` → rota `controller` com a transcrição vazia (faz T070–T072 passarem)
- [X] T080 [US3] `src/ai_core/graph/adapters/langgraph/view.py` (R43) (depende de T077): `retrieved` = os chunks de
  `state["retrieved"]` + os dos passos não sintéticos; `reranked` = os de `state["reranked"]`; `generation_context` e
  `tool_results` dos passos entregues, como hoje; docstring com a tabela do `rag_first` (faz T074 passar)
- [X] T081 [US3] `src/ai_core/graph/adapters/langgraph/flows.py` (R36) (depende de T079): `rag_first_graph()` com
  `prepare_context → retrieve → (rerank | END)`, `rerank → gate → (generate | controller)`, `controller ⇄ execute_tool →
  generate → validate_answer → END`, arestas só lendo a rota calculada; `compiled_flows()` registra os três flows
- [X] T082 [US3] Rodar `uv run pytest packages/core/tests/graph` a partir de `ai-core/` até T070–T075 passarem (e as
  suítes das US1 e US2 continuarem verdes), com `uv run mypy` e `uv run ruff check packages` limpos

**Checkpoint**: a US3 está completa e testável sozinha, com gateway e reranker falsos

---

## Phase 10: User Story 4 — Validação determinística no `rag_first` (Priority: P2) — Fase 5

**Goal**: os validators dos packs rodam em sequência com a Turn View do `rag_first`, e o `generation_context` é
exatamente o conjunto de trechos entregue à geração — inclusive depois do corte por posição no teto.

**Independent Test**: `uv run pytest packages/core/tests/graph -m us4` — um validator que confere citação contra o
`generation_context` aprova o id entregue e recusa o cortado pelo teto.

### Tests for User Story 4 ⚠️

- [X] T083 [P] [US4] `tests/graph/contract/test_rag_first_validation.py` (US4 cen. 1–2; R42, R43): **cen. 1** — dois
  validators rodam na ordem da composição e recebem a Turn View com `generation_context` igual aos 5 trechos entregues,
  na ordem, e `retrieved`/`reranked` preenchidos; o filtro de streaming (`open_answer_stream`) recebe a mesma
  `generation_context`; **cen. 2** — com `max_context_tokens` que só comporta 3 dos 5 trechos: saem os 2 de menor
  posição, a mensagem `tool` não contém os ids deles, `generation_context` tem só os 3, e há um `ContextTrimmed`
  (`notice`) com a contagem; teto que não comporta nenhum trecho → nenhuma mensagem `tool`, `generation_context` vazio,
  `ContextTrimmed` com a contagem total
- [X] T084 [P] [US4] `tests/graph/integration/test_rag_first_with_pack.py` (R46; ADR-026): `PackRuntime` real com um
  pack de teste em memória (`InMemoryPackSource`) que declara um retriever (coleção concedida no grant), um reranker e
  um validator que aceita só `[[chunk_id]]` presente no `generation_context`; gateway real da 004 (`CapabilityService`,
  como em `test_agentic_with_generic_pack.py`): a geração vê `· id: <chunk_id>` em cada trecho; resposta citando um id
  entregue passa; citando um id cortado pelo teto, o validator aponta; o `ToolCall` da recuperação está no trace

### Implementation for User Story 4

- [X] T085 [US4] Ajustes em `nodes/rag.py`, `nodes/common.py` ou `view.py` até T083–T084 passarem; `uv run pytest
  packages/core/tests/graph` verde

**Checkpoint**: US3 e US4 completas no motor

---

## Phase 11: Encaixe na 011 (`AI_CORE_RAG_*`, `rag_first` em `flows()`)

**Purpose**: a composition root passa `RagSettings` ao motor e o `rag_first` atravessa a API (R44; R35)

- [X] T086 [P] `src/ai_core/bootstrap/settings.py`. **Teste primeiro** em `tests/bootstrap/unit/test_settings.py`:
  `Settings` tem `rag_candidates == 20`, `rag_passages == 5`, `rag_min_score is None`; `EnvConfigSource` lê
  `AI_CORE_RAG_CANDIDATES`, `AI_CORE_RAG_PASSAGES` e `AI_CORE_RAG_MIN_SCORE` (vazia = sem limiar); `0`, negativo, texto,
  `1.5` e `nan` → `ConfigurationError` nomeando a variável. Depois: os campos, a validação no `__post_init__` (mesmas
  regras de `RagSettings`, mensagem com a variável) e a leitura; a tabela de
  `specs/011-core-bootstrap/contracts/configuration.md`
- [X] T087 `src/ai_core/bootstrap/wiring.py` (depende de T076, T086): `_engine` passa `rag=RagSettings(candidates=…,
  passages=…, min_score=…)` ao `ExecutionService`. **Teste** em `tests/bootstrap/unit/test_profiles.py` (ou no teste de
  perfis já existente): nos três perfis, `engine.flows()` contém `rag_first` e `flow_roles()["rag_first"] ==
  ("generation",)`. *Acrescido na implementação*: a porta `CollectionCatalog` da 003 passa a ser atendida pelo Pack
  Registry (`PackCollectionCatalog`, 011 research R35) — sem isso, todo Assistant com `collections` ficava
  indisponível (424)
- [X] T088 [US3] `tests/bootstrap/integration/test_platform_rag_first.py` (teste de ponta a ponta da US3; depende de T087): perfil `test` com
  `overrides={"pack_source": InMemoryPackSource(...), "providers": {...}}` — um pack de teste com retriever (coleção
  `docs`) e reranker; `assistants.yaml` com um Assistant `flow: rag_first`, `packs: [<pack>]`, `collections: [docs]` e
  só `generation` — servido (não 424); pela API, 200 e as mensagens enviadas ao provider têm `· id: <chunk_id>`; o
  trace tem `coverage_gate`; retriever que levanta → 502 sem streaming com `x-should-retry: false` (008 FR-022); com
  `AI_CORE_RAG_MIN_SCORE=0.99` e sem `controller` → 200 e a geração sem trechos

---

## Phase 12: Polish da Fase 5

- [X] T089 `uv run lint-imports` a partir de `ai-core/` com todos `KEPT` e nenhum contrato novo (R47): `domain/gate.py`
  e `fit_chunks` só importam stdlib, contratos e `api.py`s; `nodes/rag.py` só seams
- [X] T090 Executar a seção "Fase 5" de [quickstart.md](quickstart.md) e corrigir divergências entre o resultado e o
  "Esperado"
- [X] T091 [P] Documentação: [contracts/execution-engine.md](contracts/execution-engine.md) (`FLOW_RAG_FIRST`,
  `RagSettings`, `flow_roles()["rag_first"]`); linha da 005 em `specs/README.md` ("Fase 5 implementada (US3, US4: flow
  `rag_first`)"), com as mudanças de seam da passada nas linhas de Pack Hooks (002), Capabilities (004) e Trace Sink
  (009); seção "Código" de `CLAUDE.md` (o `rag_first`, o portão sem limiar por default, `AI_CORE_RAG_*`, o `· id:` do
  ADR-026 e o `CoverageGate`)
- [X] T092 Verificação completa a partir de `ai-core/`: `uv run pytest`, `uv run mypy`, `uv run ruff check packages`,
  `uv run lint-imports`, e a suíte com `AI_CORE_TEST_POSTGRES_DSN` apontando para o Postgres de teste
- [X] T093 Conferir que o `ai-generic` e o pack `scouting` (submódulo `ai-scouting/`) continuam verdes contra o core
  local: a suíte do workspace (o `ai-generic` roda nela) e, dentro de `ai-scouting/`, `uv run --python 3.14 --group
  platform --with-editable ../ai-core/packages/core pytest tests/integration` — a troca vale só para essa execução, sem
  mexer no `pyproject.toml` nem no lock; se o `--with-editable` não sobrepuser a fonte da tag, a tarefa fica reduzida à
  suíte padrão do pack (`uv run pytest`)
- [X] T094 Release (R48; ADR-021), **só com aprovação do mantenedor**: `version = "0.2.0"` em
  `ai-core/packages/core/pyproject.toml` (os contratos ficam em `0.1.1`; o `ai-generic` não muda), `uv lock`, commit,
  tag anotada `v0.2.0` no `agentic-app` e push da tag

---

## Passada de 2026-10-13: desfecho de etapa ([ADR-028](../../docs/adr/ADR-028-o-motor-publica-o-desfecho-de-cada-etapa.md); research R49)

- [X] T095 `api.py`: `StepFinished`, `StepOutcome` e os desfechos (`SourceRef`, `ToolCallSummary`, `ToolCallsOutcome`,
  `RerankOutcome`, `GateOutcome`, `GateRoute`, `ControllerOutcome`, `ControllerAction`, `GenerationOutcome`,
  `CatalogOutcome`), validados na construção; `domain/gate.py` importa o `GateRoute`; `domain/steps.py` (puro)
- [X] T096 Nós: `finished(stage, outcome)` em `nodes/common.py` e o desfecho de cada etapa em `common.py`,
  `agentic.py` e `rag.py`, inclusive nos caminhos de falha; `runtime.py` traduz o pedaço `step`
- [X] T097 Testes: `tests/graph/unit/test_graph_api.py` (nomes e validação), `tests/graph/unit/test_graph_steps.py`,
  `tests/graph/contract/test_step_outcomes.py` (pareamento, desfecho por etapa nos três flows, sem texto de trecho nem
  de erro, `stream=False`)

---

## Fase 5 — Dependencies & Execution Order

- **Fundação da Fase 5 (Phase 8)**: depende das Phases 1–7 (concluídas); T059, T060, T062, T063, T064, T066, T067 e
  T068 em paralelo; T061 depois de T060; T065 depois de T064; T069 depois de T061, T062 e T064
- **US3 (Phase 9)**: depende da Phase 8; testes (T070–T075) antes da implementação e falhando; T076 → T077 → T078 →
  T079 → T080 → T081; T082 é o portão da fase
- **US4 (Phase 10)**: depende da Phase 9 (usa o flow); T083 e T084 em paralelo; T085 é o portão
- **Encaixe na 011 (Phase 11)**: T086 pode começar junto com a Phase 8; T087 depois de T076 e T086; T088 depois de T087
  e da Phase 10
- **Polish (Phase 12)**: T089 e T091 depois de T085; T090, T092 e T093 depois de T088; T094 por último, com aprovação

## Parallel Example: Fase 5

```bash
# Fundação, juntos:
Task: "004 · id: na renderização (T060)"
Task: "002 PackHooks.reranker (T062)"
Task: "009 CoverageGate (T063)"
Task: "005 api.py: FLOW_RAG_FIRST, RagSettings (T064)"
Task: "domain/gate.py (T066)"
Task: "domain/budget.py fit_chunks (T067)"

# Testes da US3, juntos (depois da Phase 8):
Task: "contract/test_rag_first_flow.py (T070)"
Task: "contract/test_rag_first_failures.py (T071)"
Task: "contract/test_rag_first_packs.py (T072)"
Task: "contract/test_flow_registry.py (T073)"
Task: "unit/test_state_view.py (T074)"
Task: "contract/test_rag_first_properties.py (T075)"
```

## Fase 5 — Implementation Strategy

1. Phase 8: os toques fora da 005 primeiro (cada um com o próprio teste), depois seam, domínio e testkit
2. Phase 9: testes da US3; serviço, estado, nós, projeção e grafo — **PARE e VALIDE**: SC-003 (uma chamada de modelo no
   caminho coberto) e as três rotas do portão
3. Phase 10: a validação com o corte por posição (US4)
4. Phase 11: a 011 liga as variáveis; o `rag_first` atravessa a API no perfil `test`
5. Phase 12: fronteiras, quickstart, documentação, verificação e a tag `v0.2.0` — que destrava a US5 da 101 e a
   publicação dos validators da 104

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 e T002 primeiro (o `uv sync` precede qualquer import do framework); T003 em paralelo
- **Foundational (Phase 2)**: T004 antes de tudo; T005 e T006 em paralelo depois dele; T007 depois de T004–T006 e do
  adapter de relógio (T016), que por isso pode ser antecipado
- **User Story 1 (Phase 3)**: depende de Setup + Foundational
- **Polish (Phase 4)**: T024 depois de T022; T025 depois de T023; T026 em paralelo
- **Fundação da Fase 3 (Phase 5)**: depende das Phases 1–4 (todas concluídas); T027–T030 em paralelo; T031 depois de
  T028
- **US2 (Phase 6)**: depende da Phase 5
- **Polish da Fase 3 (Phase 7)**: T053 depois de T046; T054 e T056 depois de T052; T055 em paralelo

### Within User Story 1

- Testes (T008–T015) antes da implementação e falhando
- T016 é independente; T017 → T018 → T019 → T020 → T021 (cada um usa o anterior); T022 depende de T021 e de T006
- T023 é o portão da fase: nenhuma tarefa da Phase 4 antes dele

### Within User Story 2

- Testes (T032–T040) antes da implementação e falhando
- T041, T042 e T043 em paralelo; T044 depois de T041; T045 → T046
- T047 → T048 → T049 → T050 → T051 (cada um usa o anterior); T052 é o portão da fase

### Parallel Opportunities

- T008, T009, T010, T011, T012, T013, T014 e T015 em paralelo (arquivos distintos)
- T016 em paralelo com qualquer teste já escrito
- T026 em paralelo com qualquer tarefa da Phase 3 concluída
- Fase 3: T027, T028, T029 e T030; T032–T040 entre si; T041, T042 e T043; T055 com qualquer tarefa concluída

---

## Parallel Example: User Story 1

```bash
# Testes da US1, juntos:
Task: "unit/test_graph_api.py (T008)"
Task: "unit/test_graph_request.py (T009)"
Task: "unit/test_graph_outcome.py (T010)"
Task: "contract/test_clock_port.py (T011)"
Task: "unit/test_state_view.py (T012)"
Task: "contract/test_execution_engine_seam.py (T013)"
Task: "contract/test_flow_registry.py (T014)"
Task: "integration/test_chat_with_generic_pack.py (T015)"
```


## Parallel Example: User Story 2

```bash
# Testes da US2, juntos (depois da Phase 5):
Task: "unit/test_graph_actions.py (T032)"
Task: "unit/test_graph_limits.py (T033)"
Task: "unit/test_graph_budget.py (T034)"
Task: "unit/test_graph_transcript.py (T035)"
Task: "contract/test_agentic_flow.py (T037)"
Task: "contract/test_agentic_properties.py (T038)"
Task: "integration/test_agentic_with_generic_pack.py (T040)"

# Políticas puras, juntas:
Task: "domain/actions.py (T041)"
Task: "domain/limits.py (T042)"
Task: "domain/budget.py (T043)"
```
---

## Implementation Strategy

### MVP (US1, o escopo desta fase)

1. Phase 1 e 2: esqueleto, dependência, `api.py`, porta e regras puras
2. Phase 3: testes primeiro; depois relógio, estado, projeção, nós, grafo, runtime e serviço
3. **PARE e VALIDE**: quickstart, cenários 1–4 — streaming, falha antes do stream, validator que altera e caminho
   completo com o pack de referência
4. Phase 4: fronteiras de import, quickstart completo, documentação

### Depois desta fase

- 008 (mesma fase) traduz os eventos em SSE no formato OpenAI; 011 monta o motor e constrói o grant por requisição
- Fase 2: a 003 passa a produzir o grant e `assistants validate` usa `flows()`
- Fase 3 (Phases 5–7 acima): nós de catálogo, controller e tool; `domain/actions.py`, `limits.py`, `budget.py` e
  `transcript.py`; a porta de checkpoint foi adiada (R30)
- Depois da Fase 3 da 005: a 011 liga `capabilities`, a 008 adota `severity`, a 003 valida o papel `controller` (R33)
- Fase 5 (Phases 8–12 acima): `rag_first`, `domain/gate.py`, `fit_chunks` e os toques na 002, 004, 009 e 011

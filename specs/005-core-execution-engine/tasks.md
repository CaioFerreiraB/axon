---

description: "Task list for 005 — motor de execução: flow chat (Fase 1) e flow agentic (Fase 3)"
---

# Tasks: Motor de execução — flows `chat` e `agentic`

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
- Fase 5: `rag_first`, `domain/gate.py` e `domain/budget.py`

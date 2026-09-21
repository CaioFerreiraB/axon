---

description: "Task list for 005 — motor de execução, flow chat, Fase 1"
---

# Tasks: Motor de execução — flow `chat`

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

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 e T002 primeiro (o `uv sync` precede qualquer import do framework); T003 em paralelo
- **Foundational (Phase 2)**: T004 antes de tudo; T005 e T006 em paralelo depois dele; T007 depois de T004–T006 e do
  adapter de relógio (T016), que por isso pode ser antecipado
- **User Story 1 (Phase 3)**: depende de Setup + Foundational
- **Polish (Phase 4)**: T024 depois de T022; T025 depois de T023; T026 em paralelo

### Within User Story 1

- Testes (T008–T015) antes da implementação e falhando
- T016 é independente; T017 → T018 → T019 → T020 → T021 (cada um usa o anterior); T022 depende de T021 e de T006
- T023 é o portão da fase: nenhuma tarefa da Phase 4 antes dele

### Parallel Opportunities

- T008, T009, T010, T011, T012, T013, T014 e T015 em paralelo (arquivos distintos)
- T016 em paralelo com qualquer teste já escrito
- T026 em paralelo com qualquer tarefa da Phase 3 concluída

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
- Fase 3: nós de catálogo, controller e tool; `domain/actions.py` e `domain/limits.py`; porta de checkpoint
- Fase 5: `rag_first`, `domain/gate.py` e `domain/budget.py`

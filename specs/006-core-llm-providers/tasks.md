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

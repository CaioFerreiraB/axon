# Implementation Plan: Motor de execução — flow `chat`

**Branch**: `005-core-execution-engine` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-core-execution-engine/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/005-core-execution-engine/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-001, ADR-005, ADR-006, ADR-007, ADR-010, ADR-011, ADR-012, ADR-013;
contratos da 001 (`TurnView`, `Citation`, `Message`, `Chunk`, `ValidationResult`), Pack Hooks da 002, Model Router da
006 e Trace Sink da 009, todos já implementados. Consumidores conferidos: 008 (Fase 1, traduz eventos em SSE), 011
(monta e injeta), 003 (Fase 2, produz o grant e valida nomes de flow), 009 (harness, Fase 6).

**Duas diferenças em relação ao interior do `design.md`, ambas dentro do que ele declara livre** ("tudo abaixo da seção
Seams é interno e pode ser reescrito livremente"), e nenhuma toca os seams — portanto **sem ADR novo**:
o streaming sai por `astream(stream_mode=["custom", "values"])` em vez de `astream_events`, porque o modelo vem do
Model Router e não do framework ([research.md](research.md) R2); e `validate_request` não é nó do grafo, e sim a
primeira coisa que `run()` faz, porque o erro precisa aparecer na chamada para a 008 responder 4xx sem abrir o stream
(R5). A política em si continua pura, em `domain/`.

## Summary

Entregar o módulo `ai_core/graph/`: o seam **Execution Engine** (`run(grant, request) → fluxo de eventos`, mais o
registro de nomes de flow) e o flow `chat` — preparação de contexto dos packs, geração em streaming pelo papel
`generation` e validação determinística da resposta. Eventos neutros (token, progresso, final com resposta, citações,
erros e marcações); erro de requisição levanta antes do primeiro evento, erro posterior vira evento final. O grafo é
adapter interno em LangGraph, e nada dele atravessa o seam. Escopo da Fase 1: **US1**, mais o registro de flows da US5.
`agentic`, `rag_first`, rotina de pack, checkpoint e corte por orçamento ficam para as fases deles
([research.md](research.md) R11).

## Technical Context

**Language/Version**: Python 3.14 (módulo da distribuição `ai-core`, `requires-python = ">=3.14"`)

**Primary Dependencies**: `ai-core-contracts` (Turn View, `Citation`, `Message`, `ValidationResult`); `ai_core.packs`,
`ai_core.llm` e `ai_core.observability`, pelos `api.py`; **nova** — `langgraph>=1.2,<2`, confinada a
`ai_core/graph/adapters/langgraph/` por contrato de import (R1, R12)

**Storage**: N/A nesta fase — o estado da execução vive na memória do processo enquanto a requisição corre; a porta de
checkpoint entra na Fase 3 (R7)

**Testing**: pytest + pytest-asyncio; `domain/` puro; conformidade do seam rodando o grafo **real** com o Pack Runtime
real, o `ai-generic` e o provider simulado da 006 — só o modelo é simulado (R13)

**Target Platform**: processo do core na imagem Linux ARM64

**Project Type**: módulo de biblioteca dentro do monolito modular (`ai-core`)

**Performance Goals**: SC-004 — primeiro sinal (progresso ou token) em até 2 s no hardware alvo. O motor não acrescenta
latência entre o modelo e o consumidor: cada pedaço do `BoundModel` vira um `TokenEvent` no mesmo instante, pelo canal
de stream do framework, sem acumular (verificado em R2)

**Constraints**: nenhum tipo de framework de grafo atravessa o seam (ADR-011, SC-001); o motor só fala com packs,
modelos e trace pelos seams de 002, 006 e 009 (FR-002); nenhuma leitura de relógio fora da porta (ADR-013); nada de
domínio (princípio I); o motor não conhece HTTP, autenticação nem Pack Registry (R4)

**Scale/Scope**: 1 módulo — `api.py` (2 Protocols de seam + 3 eventos + 2 value objects + 3 erros), `domain/` com 2
arquivos, `ports.py` com 1 porta, `service.py`, e `adapters/` com o relógio e o pacote `langgraph/` (estado, projeção
da Turn View, nós, flow `chat`, registro e runtime); 1 flow dos 3

Nenhum `NEEDS CLARIFICATION`: as quatro perguntas abertas foram resolvidas em 2026-09-21 e estão em
[research.md](research.md) R1, R3, R5 e R7.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | O motor ordena etapas e não conhece assunto nenhum: prompts vêm dos packs, a pergunta vem da requisição |
| II. Seams | ✅ | Expõe Execution Engine e os nomes de flow, com suíte de conformidade; consome só os `api.py` de 001, 002, 006 e 009. **Não** consome o Pack Registry: a composição chega no grant (R4) |
| III. O core orquestra | ✅ | É a spec que implementa o ADR-001: topologia escrita à mão, pack não cria nem inspeciona flow (FR-004). Nós finos — cada um delega a um seam ou a uma função de `domain/` |
| IV. Assistant é a fronteira | ✅ | O motor recebe o grant já resolvido e não amplia nada: packs e modelos vêm dele. Na Fase 1 quem o monta é a 011 (R3) |
| V. Determinismo | ✅ | Validação da requisição, montagem do evento final e projeção da Turn View são puras; nenhuma decisão de controle por modelo existe no `chat` |
| VI. Conteúdo externo | ✅ | A resposta do modelo é dado: o motor não a interpreta, só a entrega aos validators. Mensagem de erro de outro módulo entra no evento final como texto, e a 009 a redige antes de sair do processo |
| VII. Falha fechada | ✅ | Requisição inválida e flow inexistente levantam antes de qualquer evento e de qualquer chamada de modelo (FR-013); falha posterior vira evento final com erro nomeado, nunca silêncio (R6) |
| VIII. Modelos por papel | ✅ | A geração pede `for_role("generation")` ao Model Router; o motor não escolhe provider nem modelo |
| IX. Proveniência | ✅ | As citações do evento final são as que os validators encadearam; o motor não inventa nem remove citação |
| X. Medir antes de calibrar | ✅ | Nenhum número calibrável nesta fase: o limiar do portão é Fase 6 e o limite de iteração é Fase 3 |
| XI. Streaming | ✅ | É o ponto da fase: o token chega ao consumidor enquanto o nó de geração ainda roda (R2) |
| XII. Simplicidade | ✅ | Sem checkpoint, sem catálogo, sem orçamento, sem loop — cada um adiado para a fase que o usa (R7, R11) |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-core/packages/core/src/ai_core/graph/**` e
  `ai-core/packages/core/tests/graph/**`; fora dele, apenas `ai-core/packages/core/pyproject.toml` (dependência
  `langgraph`) e `ai-core/pyproject.toml` (import-linter, pytest)
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — `TurnView`,
  `Citation`, `Message`, `ValidationResult` de `ai_core_contracts` (001); `PackHooks`, `Composition`,
  `ValidationOutcome`, `PackHookError` de `ai_core.packs.api` (002); `ModelRouting`, `ModelPolicy`, `ModelCallFailed`
  de `ai_core.llm.api` (006); `TraceSink` e eventos de `ai_core.observability.api` (009)
- [x] Every seam this module exposes has a conformance test planned — `tests/graph/contract/test_execution_engine_seam.py`
  (ordem dos eventos, streaming incremental, erros antes e depois do primeiro evento, resposta alterada por validator,
  Turn View entregue aos hooks) e `test_flow_registry.py` (nomes de flow, flow inexistente)
- [x] No seam changes — o Execution Engine nasce aqui, com a assinatura do `design.md`. A forma exigida do grant entra
  como `Protocol` deste módulo, o que **não** move a posse do seam Execution Grant, que continua da 003 (R3)
- [x] Import boundaries (import-linter) cover the new code — contratos novos do R12, incluindo o que prende o framework
  de grafo a `adapters/langgraph/`

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/`
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — nenhum deles importa
  `langgraph` nem `langchain_core`; o contrato de import-linter do R12 barra, e o `service.py` fala com o grafo por uma
  função de fábrica do adapter, injetada na construção
- [x] Other modules are imported only through their `api.py` — 001, 002, 006 e 009; o `api.py` da 005 não importa o
  resto do próprio módulo
- [x] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O — tempo pela
  porta `Clock` (data de referência e duração); rede, packs e modelos só pelos seams; `domain/` é puro
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — só `Clock`, por não-determinismo.
  `CheckpointStore` é da Fase 3, quando houver execução a retomar (R7)
- [x] Every secondary port has an in-memory adapter and a conformance suite that also runs against the real adapter —
  `FixedClock` × `SystemClock` em `adapters/clock.py`
- [x] Services and adapters of other modules are instantiated only in the composition root — a 005 não instancia nada
  de outro módulo: recebe `PackHooks`, `ModelRouting` e `TraceSink` prontos. Quem os monta é a 011 (e os testes)

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/005-core-execution-engine/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── execution-engine.md   # seam: run, flows, eventos, erros, forma exigida do grant
│   ├── ports.md              # Clock e sua conformidade
│   └── chat-flow.md          # a topologia da fase: etapas, o que cada uma delega, Turn View e trace
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-core/
├── pyproject.toml                       # contratos novos de import-linter (R12)
└── packages/core/
    ├── pyproject.toml                   # dependência langgraph>=1.2,<2 (R1)
    ├── src/ai_core/graph/
    │   ├── __init__.py                  # docstring: consumidores importam graph.api
    │   ├── api.py                       # seam ExecutionEngine + ExecutionGrant (Protocol), ExecutionRequest,
    │   │                                #   TokenEvent/ProgressEvent/FinalEvent, ExecutionIssue, erros, FLOW_CHAT
    │   ├── domain/
    │   │   ├── __init__.py
    │   │   ├── request.py               # validação de requisição e flow — pura (FR-013)
    │   │   └── outcome.py               # resultado dos validators + resposta gerada → FinalEvent (US1 cen. 3)
    │   ├── ports.py                     # Clock (now + monotonic)
    │   ├── service.py                   # ExecutionService: valida, fixa reference_time, monta o contexto e delega
    │   └── adapters/
    │       ├── __init__.py
    │       ├── clock.py                 # SystemClock, FixedClock
    │       └── langgraph/               # tudo que conhece o framework — trocável por inteiro (ADR-011)
    │           ├── __init__.py          # fábrica do runtime, é o que o service recebe
    │           ├── state.py             # AgentState com reducers — PRIVADO
    │           ├── view.py              # AgentState → TurnView (contrato 001)
    │           ├── nodes.py             # prepare_context · generate · validate_answer (finos)
    │           ├── flows.py             # grafo do chat + registro de nomes
    │           └── runtime.py           # astream(custom+values) → ExecutionEvent; falha vira FinalEvent
    └── tests/graph/
        ├── conftest.py                  # grant de exemplo, hooks reais com ai-generic, provider simulado
        ├── graph_testkit.py             # fábricas compartilhadas
        ├── unit/                        # domain/ puro; projeção da Turn View; tradução de eventos
        ├── contract/                    # conformidade do seam e do registro de flows; porta Clock
        └── integration/                 # caminho completo com Pack Runtime real + ai-generic (R13)
```

**Structure Decision**: layout hexagonal do ADR-012 no caminho do `design.md`. O pacote `adapters/langgraph/` concentra
tudo que conhece o framework — é literalmente o que o SC-001 manda poder jogar fora. `nodes/` e `flows/` do `design.md`
nascem como um arquivo cada (`nodes.py`, `flows.py`): com um flow e três nós, uma pasta por arquivo seria cerimônia;
viram pastas quando `agentic` e `rag_first` chegarem. `gate.py`, `limits.py`, `actions.py` e `budget.py` de `domain/`
não nascem nesta fase (R11).

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 008 (Fase 1) | `engine.run(grant, request)` levanta `ExecutionRequestInvalid`/`UnknownFlow` **na chamada** — responder 4xx aí, antes de abrir o SSE. Depois, iterar: `TokenEvent` vira `delta`, `ProgressEvent` é opcional na tradução, `FinalEvent` fecha com resposta, citações, erros e marcações. Nenhuma exceção depois do primeiro evento (R6) |
| 011 (Fase 1) | Montar `ExecutionService(flows=..., hooks=pack_runtime, routing=model_routing, trace=trace_service, clock=SystemClock())` e construir, por requisição, um objeto que cumpra `ExecutionGrant` — `assistant`, `flow`, `composition` (vinda do Pack Registry) e `models` (a `ModelPolicy` da 006). Injetar o mesmo relógio nos módulos com porta de tempo (011 FR-008) |
| 003 (Fase 2) | Passa a produzir o grant: qualquer objeto com `assistant`, `flow`, `composition` e `models` satisfaz o `Protocol`, sem import nem registro. `engine.flows()` dá os nomes válidos para `assistants validate` |
| 002 | Recebe `Composition`, `TurnView` e as fatias em `prepare` e `validate`; as fatias devolvidas por `prepare` voltam em `validate`, na mesma execução |
| 009 | Recebe `ExecutionStarted` (com `reference_time`), `ValidationRun` por validator, `ExecutionError` em falha e `ExecutionFinished`. As chamadas de modelo são emitidas pela 006 — o motor não as duplica (R10) |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- II: o `api.py` só tem Protocols, dataclasses congeladas, erros e tipos de `ai_core_contracts`, `ai_core.packs.api` e
  `ai_core.llm.api`; nenhum tipo de framework atravessa o seam, e o contrato de import-linter torna isso verificável.
- III: a tabela de etapas de [contracts/chat-flow.md](contracts/chat-flow.md) mostra cada nó delegando a um seam ou a
  uma função pura — nenhuma regra de negócio mora no grafo.
- VII: a tabela de falhas do [data-model.md](data-model.md) cobre os seis modos (requisição inválida, flow
  desconhecido, hook de pack que falha, provider fora do ar, validator que falha, cliente que desiste), cada um com
  resultado explícito e com o dado de trace correspondente.
- XI: `contracts/execution-engine.md` fixa que o primeiro `TokenEvent` sai antes de o nó de geração terminar, e a
  suíte de conformidade verifica isso.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Framework de grafo para uma topologia linear (R1) | é a decisão pré-aprovada, e a tradução do streaming precisa ser provada na fase em que streaming é o requisito | adapter sequencial exigiria ADR, seria escrito duas vezes e adiaria para a Fase 3 a descoberta de como o framework entrega token |
| `ExecutionGrant` como `Protocol` em vez de tipo concreto (R3) | o dono do value object é a 003, que é Fase 2 | definir o tipo aqui inverteria a posse do seam; antecipar a 003 criaria código sem spec planejada |
| Dois canais de stream consumidos juntos, `custom` e `values` (R2) | `custom` dá o evento ao vivo, `values` dá o estado final completo | só `custom` obrigaria cada nó a repetir o estado no evento; só `values` entregaria o token depois do nó terminar, matando o streaming |

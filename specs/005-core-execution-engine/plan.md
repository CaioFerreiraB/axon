# Implementation Plan: Motor de execução — flows `chat` e `agentic`

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

**Fase 3 (2026-10-01): US2, flow `agentic`.** O loop do controller sobre o grafo existente: a sessão de tools da 004
abre depois da preparação; a cada iteração o papel `controller` (006) devolve uma ação estruturada por
`response_format` — um ramo por tool do catálogo —, o gateway executa e o resultado cercado volta ao controller pelo
formato nativo de tool; limite do grant ou **3**, teto de contexto do grant aplicado ao loop e à geração, falha do
controller seguindo para a geração. Registro com gravidade (`ExecutionIssue.severity`, aditivo), decisão do controller
no trace por um evento novo da 009 sob o [ADR-017](../../docs/adr/ADR-017-trace-sink-cresce-por-eventos-aditivos.md),
e o grant passa a ser o value object da 003 (fim da ponte do R3). Checkpoint adiado de novo. Decisões em
[research.md](research.md) R14–R33; topologia em [contracts/agentic-flow.md](contracts/agentic-flow.md).

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
│   ├── chat-flow.md          # a topologia da fase: etapas, o que cada uma delega, Turn View e trace
│   └── agentic-flow.md       # Fase 3: loop do controller, ação, limite, teto, Turn View e trace
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

## Fase 3 (US2, flow `agentic`) — 2026-10-01

Insumos lidos: [design.md](design.md) ("`agentic`", "Controller", "Nós finos"), ADR-001, ADR-005, ADR-008, ADR-011,
ADR-012, ADR-013; as cinco clarificações de 2026-10-01; seams consumidos já implementados — `Capabilities`/`ToolSession`,
`ToolContext`, `ToolCall`, `CatalogTool`, `FencedToolResult`, `FENCE_INSTRUCTION` (004), `ModelRouter.for_role` e
`BoundModel.complete(response_format=…)` (006), `ExecutionGrant` e `Limits` (003), `TraceSink` (009), `PackHooks`
(002), `ToolResult`, `ChatMessage` com `tool_calls`/`tool_call_id` e `RETRIEVAL_FILTERS_KEY` (001).

**Divergências do `design.md`, todas abaixo da seção "Seams" (livre) e registradas com nota datada lá**: a porta
`CheckpointStore` não nasce (clarificação 1, R30); o contexto do controller não traz os prompts de pack, como a tabela
de nós já indicava (R19). **Mudanças de seam**: `FLOW_AGENTIC` (nome já previsto na FR-003 e no ADR-001); `ExecutionGrant` passa a ser o da
003, reexportado, sem mudar `run` (R15), e `ExecutionIssue.severity` com default, que muda o significado de
`ExecutionFinished.ok` (R23) — as duas no [ADR-018](../../docs/adr/ADR-018-seam-execution-engine-fase-3.md), com as
consumidoras listadas; e, na 009, o evento `ControllerDecision`, sob o ADR-017 (R24).

### Technical Context — o que muda

- **Dependências**: nenhuma nova. Seams novos consumidos: 004 (`ai_core.capabilities.api`) e 003
  (`ai_core.assistants.api`, o grant).
- **Storage**: nenhum — o estado do loop vive na execução; checkpoint adiado (R30).
- **Testing**: controller simulado por um provider de teste com roteiro no testkit, entrando no `ModelRoutingService`
  real; gateway falso do testkit na conformidade e na propriedade (hypothesis, SC-002/SC-005); `CapabilityService` real
  com `PackRuntime` e `ai-generic` na integração (R29). Marca `us2`.
- **Performance**: o controller é uma chamada sem streaming por iteração; o primeiro sinal continua sendo o progresso
  de `prepare_context` (SC-004). Limite padrão 3 e catálogo enxuto mantêm o custo do loop no hardware alvo (arch-v1 §9).
- **Constraints**: o motor só alcança tools pela 004 e nunca importa a 007 (R32); a ação nunca leva conteúdo ao trace
  (ADR-017); nada de domínio no texto do controller (princípio I).
- **Scale/Scope**: `domain/` ganha `actions.py`, `limits.py`, `budget.py` e `transcript.py`; `adapters/langgraph/`
  ganha o grafo `agentic`, `nodes/` como pacote e a projeção da Turn View com resultados; `api.py` ganha `FLOW_AGENTIC` e
  `severity`; 1 flow novo dos 3.

Nenhum `NEEDS CLARIFICATION`: as cinco perguntas de 2026-10-01 estão na spec e em R20–R24/R30.

### Constitution Check — Fase 3

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | A instrução do controller fala de "ferramentas" e "ação", sem assunto; o catálogo vem da 004 |
| II. Seams | ✅ | Consome 004 e 003 pelos `api.py`; as mudanças no próprio seam (grant da 003, `severity`) estão no ADR-018 com as consumidoras listadas; evento novo na 009 sob o ADR-017, com o toque declarado |
| III. O core orquestra | ✅ | ADR-001: a topologia `agentic` é a do `design.md`, escrita à mão; ADR-005: toda tool, inclusive recuperação, passa pelo gateway; rota, leitura da ação, limite e teto são funções puras de `domain/` |
| IV. Assistant é a fronteira | ✅ | O catálogo e a execução vêm da sessão aberta com o grant (004); o motor não filtra nem amplia nada; nome fora do catálogo é "tool inexistente" |
| V. Determinismo | ✅ | O limite é contador, o teto é estimativa determinística, a rota é tabela; o modelo só escolhe a ação, e a forma dela é restringida |
| VI. Conteúdo externo | ✅ | Resultado entra cercado e neutralizado (004), no papel `tool`, com a `FENCE_INSTRUCTION` no sistema do controller e da geração; a saída inválida do modelo não volta ao contexto nem ao trace (R18, R19) |
| VII. Falha fechada | ✅ | Papel ausente e flow sem gateway levantam antes de qualquer custo (R16, R25); `CatalogConflict` encerra sem gerar; falha do controller e MCP indisponível são registrados como `error` — degradação explícita, nunca silenciosa (R21, R23) |
| VIII. Modelos por papel | ✅ | Controller por `for_role("controller")` com `response_format`; geração por `for_role("generation")`; o motor não escolhe modelo |
| IX. Proveniência | ✅ | A Turn View de `validate` traz exatamente os resultados e chunks que a geração recebeu (R26) |
| X. Medir antes de calibrar | ✅ | O 3 é o default do `design.md` ("3–4"), não calibração; a estimativa de tokens é proteção, não métrica |
| XI. Streaming | ✅ | O progresso sai antes de cada etapa do loop; a geração continua em streaming |
| XII. Simplicidade | ✅ | Sem checkpoint, sem tokenizador, sem tool calling nativo, sem porta nova (R22, R30) |
| XIII. Portas e adapters | ✅ | Nenhuma porta nova: tudo que é I/O chega por seam (004, 006, 009); política nova em `domain/` |

**Module boundary gate (Fase 3)**:

- [x] Source changes stay inside this module's paths — `ai_core/graph/**` e `tests/graph/**`; fora dele, os **toques
  declarados**: na 009 (`observability/api.py`: `ControllerDecision` e o membro da união; o teste de nomes públicos; e
  `specs/009-…/contracts/{trace-api,record-format}.md` e `data-model.md`), sob o ADR-017; `ai-core/pyproject.toml`
  (import-linter e a descrição da marca `us2`); e documentação (`docs/roadmap.md`, `docs/adr/`, `specs/README.md`,
  `CLAUDE.md`)
- [x] Every consumed seam is listed with its owner spec — 004: `Capabilities`, `ToolSession`, `ToolContext`, `ToolCall`,
  `CatalogTool`, `FencedToolResult`, `FENCE_INSTRUCTION`, `CatalogConflict`; 003: `ExecutionGrant`, `Limits`; 006:
  `ModelRouter`, `ModelRoutingError` e subclasses; 001: `ToolResult`, `Chunk`, `ChatMessage`, `RETRIEVAL_FILTERS_KEY`
- [x] Every seam this module exposes has a conformance test planned — `test_agentic_flow.py` e
  `test_agentic_properties.py` (itens 13–22 de [contracts/execution-engine.md](contracts/execution-engine.md));
  `test_flow_registry.py` cobre `agentic` com e sem `Capabilities`
- [x] Seam changes — com ADR: grant da 003 e `severity` no ADR-018 (consumidoras 008, 009, 011, 003); na 009, o
  evento novo sob o ADR-017
- [x] Import boundaries cover the new code — R32: o motor não importa a 007; `capabilities` e `mcp` entram na regra do
  framework de grafo

**Ports & adapters gate (Fase 3)**: sem porta nova; `domain/` continua sem I/O (os quatro arquivos novos são funções
puras sobre value objects de 001, 004 e 006); quem monta `Capabilities` é a 011 (pendência dela, R33). **Resultado**:
PASS.

### Project Structure — Fase 3

```text
ai-core/packages/core/src/ai_core/graph/
├── api.py                     # + FLOW_AGENTIC; ExecutionIssue.severity; ExecutionGrant = o da 003 (reexportado)
├── domain/
│   ├── request.py             # + papéis exigidos por flow; flows que exigem tools
│   ├── outcome.py             # severity nos apontamentos; succeeded() = nenhum "error"
│   ├── actions.py             # NOVO: instrução do controller, esquema anyOf, parse_action
│   ├── limits.py              # NOVO: DEFAULT_MAX_ITERATIONS = 3; rota depois de cada decisão
│   ├── budget.py              # NOVO: estimativa de tokens, parada do loop, omissão dos resultados antigos
│   └── transcript.py          # NOVO: mensagens do controller e da geração (formato nativo de tool)
├── ports.py                   # ExecutionPlan + grant, capabilities, limite e teto
├── service.py                 # + capabilities opcional; papéis em run(); flows() sem agentic sem gateway
└── adapters/langgraph/
    ├── state.py               # + campos do loop com reducers; AgentContext com a sessão
    ├── view.py                # + tool_results, retrieved, generation_context
    ├── nodes/                 # era nodes.py
    │   ├── common.py          # canais de stream, prepare_context, generate, validate_answer
    │   └── agentic.py         # load_capabilities, controller, execute_tool
    ├── flows.py               # + agentic_graph(); registro com os dois
    └── runtime.py             # issue com stage/kind dos novos erros

ai-core/packages/core/tests/graph/
├── graph_testkit.py           # + grant da 003, ScriptedController, FakeCapabilities/FakeSession
├── unit/                      # + test_graph_actions.py, test_graph_limits.py, test_graph_budget.py, test_graph_transcript.py
├── contract/                  # + test_agentic_flow.py, test_agentic_properties.py
└── integration/               # + test_agentic_with_generic_pack.py
```

### Seam Notes for Consumers — Fase 3

| Consumidor | O que precisa saber |
|---|---|
| 008 | Nada quebra: o grant que passa já é o da 003. Na passada de encaixe, trocar a regra de `finish_reason` de `kind == "ValidatorIssue"` para `severity == "notice"` (R23); até lá, `agentic` truncado sai com `finish_reason: "error"` e a resposta inteira. Os progressos novos (`load_capabilities`, `controller`, `execute_tool`) passam pelo campo extra que já existe |
| 011 | Passar `capabilities=<CapabilityService>` ao `ExecutionService` nos perfis; sem isso, `agentic` não está em `flows()` e a validação de Assistants o acusa |
| 003 | `engine.flows()` passa a ter `agentic` quando a 011 ligar a 004; Assistant `agentic` precisa do papel `controller` — hoje o motor recusa na chamada; a validação pode passar a acusá-lo (R33) |
| 004 | Consumida como está: `open` depois da preparação, `execute` por iteração, `unavailable` vira aviso, `FENCE_INSTRUCTION` no sistema |
| 006 | Consumida como está: `complete(..., response_format=…)` no papel `controller`. A US4 dela decide `strict` e a recusa de provider sem suporte |
| 009 | Recebe `ControllerDecision` (toque desta passada) além dos eventos de sempre; `ExecutionFinished.ok` passa a ignorar registros `notice` |

### Constitution Check — pós-design (Fase 3)

Reavaliado com [data-model.md](data-model.md), [contracts/agentic-flow.md](contracts/agentic-flow.md),
[contracts/execution-engine.md](contracts/execution-engine.md) e [quickstart.md](quickstart.md): **PASS**.

- III/V: a tabela "Limite" do contrato é a função de rota; nenhuma aresta decide por conta própria.
- VI: o contrato de mensagens põe conteúdo externo só no papel `tool`, cercado; a saída inválida não volta.
- VII: a tabela de modos de falha do `data-model.md` cobre os onze casos do loop, cada um com resultado e trace.
- II: a tabela de seams muda só pelo acréscimo do `ControllerDecision` (009, ADR-017) e pelas duas mudanças do
  ADR-018 aqui.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Framework de grafo para uma topologia linear (R1) | é a decisão pré-aprovada, e a tradução do streaming precisa ser provada na fase em que streaming é o requisito | adapter sequencial exigiria ADR, seria escrito duas vezes e adiaria para a Fase 3 a descoberta de como o framework entrega token |
| `ExecutionGrant` como `Protocol` em vez de tipo concreto (R3) | o dono do value object é a 003, que é Fase 2 | definir o tipo aqui inverteria a posse do seam; antecipar a 003 criaria código sem spec planejada |
| Dois canais de stream consumidos juntos, `custom` e `values` (R2) | `custom` dá o evento ao vivo, `values` dá o estado final completo | só `custom` obrigaria cada nó a repetir o estado no evento; só `values` entregaria o token depois do nó terminar, matando o streaming |
| Esquema `anyOf` com um ramo por tool (R17) | é o que transforma a saída estruturada em proteção real no modelo pequeno: nome e forma dos argumentos restringidos | esquema plano deixaria os argumentos livres, que é exatamente onde o arch-v1 §9 diz que o modelo erra |
| `ExecutionIssue.severity` (R23, ADR-018) | o loop cria seis registros que não são falha; sem gravidade, o sucesso no trace e o `finish_reason` da 008 mentem | lista de `kind`s acoplaria a 008 aos nomes da 005; usar `flags` contraria a US2 cen. 2 |

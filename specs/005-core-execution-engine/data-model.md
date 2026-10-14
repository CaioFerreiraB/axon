# Data model — 005 Execution Engine (Fase 1)

Tudo que é publicado vive em `ai_core/graph/api.py` e é imutável
(`@dataclass(frozen=True, slots=True, kw_only=True)`). Nenhum tipo de framework de grafo, de HTTP ou de estado interno
aparece aqui — é o que o ADR-011 e o SC-001 exigem.

## Entrada

### `ExecutionRequest`

| Campo | Tipo | Regra |
|---|---|---|
| `messages` | `Sequence[Message]` | ao menos uma; a última de papel `user` é a pergunta (`Message` é do contrato 001) |
| `stream` | `bool` | default `True`; com `False` o consumidor recebe só o `FinalEvent` |
| `reference_time` | `datetime \| None` | só em execução de avaliação, preenchida pelo harness em processo; a API HTTP rejeita o campo (008 FR-012). Exige timezone |

### `ExecutionGrant` — a forma exigida, não o valor

```python
class ExecutionGrant(Protocol):
    @property
    def assistant(self) -> str: ...
    @property
    def flow(self) -> str: ...
    @property
    def composition(self) -> Composition: ...   # 002, já validada
    @property
    def models(self) -> ModelPolicy: ...        # 006
```

Publicado por este módulo; o Execution Grant da 003 o satisfaz estruturalmente a partir da Fase 2
([research.md](research.md) R3). Cresce de forma aditiva: limites de iteração entram na Fase 3 e teto de contexto na
Fase 5. O motor **não** recebe lista de nomes de pack — recebe a composição pronta (R4).

## Saída

### `TokenEvent`

| Campo | Tipo | Significado |
|---|---|---|
| `text` | `str` | pedaço de resposta, na ordem em que o modelo produziu |

### `ProgressEvent`

| Campo | Tipo | Significado |
|---|---|---|
| `stage` | `str` | etapa que começou: `prepare_context`, `generate`, `validate_answer` |
| `detail` | `str \| None` | complemento livre; `None` quando não há |

### `ExecutionIssue` — um item de `FinalEvent.errors`

| Campo | Tipo | Regra |
|---|---|---|
| `stage` | `str` | etapa onde ocorreu; não vazio |
| `kind` | `str` | classe curta e estável (`PackHookError`, `ModelCallFailed`, `ValidatorIssue`, `Truncated`); não vazio |
| `message` | `str` | texto livre; a 009 o redige e trunca antes de gravar |

### `FinalEvent`

| Campo | Tipo | Regra |
|---|---|---|
| `answer` | `str` | resposta final — a do validator quando ele a alterou, senão a gerada (US1 cen. 3) |
| `citations` | `tuple[Citation, ...]` | as que os validators encadearam; vazio no `chat` sem retrieval |
| `errors` | `tuple[ExecutionIssue, ...]` | vazio quando nada deu errado |
| `flags` | `frozenset[str]` | marcações dos validators (ex.: resposta não fundamentada) |

```python
type ExecutionEvent = TokenEvent | ProgressEvent | FinalEvent
```

Toda execução termina com **exatamente um** `FinalEvent`, inclusive quando falha no meio.

## Seam

```python
class ExecutionEngine(Protocol):
    def flows(self) -> frozenset[str]: ...
    def run(self, grant: ExecutionGrant, request: ExecutionRequest) -> AsyncIterator[ExecutionEvent]: ...
```

`run` **não** é gerador: valida e levanta de forma síncrona, depois devolve o iterador (R5).

## Erros (`api.py`)

| Erro | Quando | Mensagem contém |
|---|---|---|
| `ExecutionError` | base da hierarquia | — |
| `ExecutionRequestInvalid` | requisição sem mensagem, sem pergunta de usuário, ou `reference_time` sem timezone | o campo e o motivo |
| `UnknownFlow` | o flow do grant não está no registro (US5 cen. 2) | o flow pedido e os disponíveis |

Os dois erros de requisição herdam **só** de `ExecutionError`: quem consome trata uma hierarquia, não duas.

Os três acontecem **antes** do primeiro evento. Depois dele, nada levanta: vira `FinalEvent` com `errors` (R6).

## Estado interno — privado (ADR-011)

`AgentState` vive em `adapters/langgraph/state.py` e **não** é contrato. Na Fase 1 carrega identidade
(`request_id`, `assistant`, `flow`, `reference_time`), `messages`, as fatias por pack (`packs`), `answer`, `citations`,
`flags` e `errors` — estes três últimos com reducer de acumulação, porque é o que impede perda quando o grafo ganhar
loop e ramos (FR-009, SC-005). Campos de retrieval e de loop entram nas fases deles.

A projeção `AgentState → TurnView` está em `adapters/langgraph/view.py`: `question` é a última mensagem de papel
`user`; `reference_time` é a mesma em toda Turn View da execução; `generation_context` é vazio no `chat`, que não tem
retrieval, e é o campo que os validators leem para verificar citação (ADR-007).

## Modos de falha

| Situação | Resultado | Trace |
|---|---|---|
| Requisição sem mensagens ou sem pergunta | `ExecutionRequestInvalid` na chamada de `run` | nenhum — a execução não começou |
| Flow do grant não registrado | `UnknownFlow` na chamada de `run`, nomeando os disponíveis | nenhum |
| Hook de pack levanta (002 FR-011) | `FinalEvent` com `kind="PackHookError"` e o pack nomeado; resposta parcial preservada | `ExecutionError` + `ExecutionFinished(ok=False)` |
| Provider fora do ar na geração | `FinalEvent` com `kind="ModelCallFailed"`, provider e modelo na mensagem | idem (o `ModelCall` da falha já vem da 006) |
| Validator devolve `ok=False` | execução **não** falha: `answer`, `citations` e `flags` do validator vão ao `FinalEvent`, e cada `issue` vira um `ExecutionIssue` | `ValidationRun` por validator |
| Cliente desiste no meio do streaming | o iterador é fechado, o grafo é cancelado e os recursos liberados; nenhum evento a mais | `ExecutionFinished(ok=False, reason="cancelled")` |

## Fase 3 (US2, flow `agentic`) — 2026-10-01

O que muda no que é publicado ([research.md](research.md) R14–R33). As duas mudanças de seam — o tipo do grant (R15)
e a gravidade dos registros (R23) — estão no [ADR-018](../../docs/adr/ADR-018-seam-execution-engine-fase-3.md); a
assinatura de `run` não muda.

### `ExecutionGrant` — agora o da 003

`ai_core.graph.api.ExecutionGrant` é o `ExecutionGrant` de `ai_core.assistants.api`, reexportado. O motor lê dele:

| Campo (003) | Uso no motor |
|---|---|
| `assistant`, `flow`, `composition`, `models` | como na Fase 1 |
| `limits.max_iterations` | limite do loop; `None` → `DEFAULT_MAX_ITERATIONS = 3` (FR-006) |
| `limits.max_context_tokens` | teto de contexto do loop e da geração; `None` → sem corte (FR-011) |
| o grant inteiro | entregue a `Capabilities.open(grant, contexto)` (004) — o motor não lê `principal`, `mcp_aliases`, `collections`, `allowed_tools` nem `write_tools` |

### Nomes de flow

| Constante | Valor | Disponível quando |
|---|---|---|
| `FLOW_CHAT` | `"chat"` | sempre |
| `FLOW_AGENTIC` | `"agentic"` | o motor foi montado com `Capabilities` (R16) |

### `ExecutionIssue` — campo novo ([ADR-018](../../docs/adr/ADR-018-seam-execution-engine-fase-3.md))

| Campo | Tipo | Regra |
|---|---|---|
| `severity` | `Literal["error", "notice"]` | default `"error"`. `notice` = registrado, mas não é falha da execução (R23) |

`kind`s acrescentados pelo `agentic`:

| `stage` | `kind` | `severity` | Quando | Mensagem contém |
|---|---|---|---|---|
| `load_capabilities` | `McpUnavailable` | `error` | um MCP do grant falhou na descoberta (`session.unavailable`) | alias e motivo |
| `controller` | `InvalidAction` | `notice` | a saída do controller não é uma ação (R18) | iteração e motivo |
| `controller` | `IterationLimit` | `notice` | o limite foi atingido sem `answer` (FR-006) | o limite |
| `controller` | `ContextLimit` | `notice` | a próxima chamada ao controller passaria do teto (FR-011) | teto e estimativa |
| `controller` | `ModelCallFailed` | `error` | a chamada ao controller falhou (FR-006a) | provider e modelo |
| `generate` | `ContextTrimmed` | `notice` | resultados de tool omitidos para caber no teto | quantos e o teto |
| `generate` | `ContextOverflow` | `notice` | nem sem resultados coube no teto | teto e estimativa |
| `validate_answer` | `ValidatorIssue` | `notice` | apontamento de validator (já existia; agora com `severity`) | pack.validator: apontamento |

`ExecutionFinished.ok` (009) = nenhum registro `error` no `FinalEvent`.

### `ProgressEvent.stage` — valores acrescentados

| `stage` | `detail` |
|---|---|
| `load_capabilities` | `None` |
| `controller` | `"iteração <n>"` |
| `execute_tool` | o nome que o controller pediu |
| `retrieve` | `"<n> tool(s) de recuperação"` (Fase 5, `rag_first`) |
| `rerank` | `"<n> candidato(s)"` (Fase 5, `rag_first`) |
| `gate` | `"<n> trecho(s)"` (Fase 5, `rag_first`) |

Os três do `rag_first` são emitidos desde a Fase 5 e conferidos na conformidade do flow
(`tests/graph/contract/test_rag_first_flow.py`: `prepare_context → retrieve → rerank → gate → generate →
validate_answer`); publicados aqui em 2026-10-13, quando a 008 passou a mostrá-los como texto (008 research R34).

### Ação do controller (`domain/actions.py`, interno)

| Tipo | Campos | Origem |
|---|---|---|
| `ToolAction` | `name: str`, `arguments: Mapping[str, JSONValue]` | `{"action": "tool", "name": …, "arguments": {…}}` |
| `AnswerAction` | — | `{"action": "answer"}` |
| `InvalidAction` | `reason: str` (texto do motor, nunca da saída do modelo) | qualquer outra coisa |

Esquema enviado em `response_format`: `anyOf` com um ramo `answer` e um ramo por tool do catálogo, com o nome como
`const` e os parâmetros saneados (sem `pattern`/`patternProperties`; `$ref` → `{"type": "object"}`) — R17.

### Evento novo na 009 (toque declarado, ADR-017)

`ControllerDecision`:

| Campo | Tipo | Regra |
|---|---|---|
| `request_id` | `str` | não vazio |
| `iteration` | `int` | ≥ 1; 0 só em `limit` antes da primeira chamada |
| `action` | `Literal["tool", "answer", "invalid", "limit"]` | — |
| `tool` | `str \| None` | obrigatório em `tool`, ausente nos outros |
| `reason` | `str \| None` | obrigatório em `invalid` e em `limit` (`"iterations"` ou `"context"`) |

Nunca argumentos nem saída do modelo. Tipo no registro: `controller_decision`.

### Estado interno — o que o loop acrescenta (privado, ADR-011)

`AgentState` ganha `iteration`, `limit`, `ceiling`, `next_action`, e os acumuladores com reducer `steps` (cada tool
executada com o `ToolCall` e o `FencedToolResult` da 004, ou cada ação inválida com o motivo) e `decisions`, além do
`errors` que já existia. O `AgentContext` ganha `capabilities`, o grant,
e um compartimento para a `ToolSession` aberta no passo `load_capabilities`. A Turn View (`view.py`) passa a projetar
`tool_results`, `retrieved` e `generation_context` como no R26.

### Modos de falha do `agentic`

| Situação | Resultado | Trace |
|---|---|---|
| Grant `agentic` sem papel `controller`, ou fora da allowlist | `ExecutionRequestInvalid` na chamada de `run`, nomeando o papel (R25) | nenhum |
| Motor sem `Capabilities` e grant `agentic` | `UnknownFlow` na chamada de `run` (R16) | nenhum |
| `CatalogConflict` ao abrir a sessão | `FinalEvent` com `kind="CatalogConflict"`, `stage="load_capabilities"`, sem geração | `ExecutionError` + `ExecutionFinished(ok=False)` |
| MCP indisponível na descoberta | segue com o catálogo que há; `McpUnavailable` (`error`: degradação explícita, princípio VII) | `ExecutionError(stage="catalog")` emitido pela 004 |
| Catálogo vazio | direto à geração, sem controller (R27) | — |
| Ação malformada | conta como iteração, `InvalidAction`, volta ao controller (ou à geração no limite) | `ControllerDecision(action="invalid")` |
| Tool fora do catálogo | o gateway devolve "tool inexistente", que volta ao controller; conta como iteração | `ControllerDecision(action="tool")` + `ToolCall(status="unknown")` |
| Limite atingido | geração com o que há; `IterationLimit` | `ControllerDecision(action="limit", reason="iterations")` |
| Teto de contexto | loop para (`ContextLimit`) ou resultados antigos omitidos (`ContextTrimmed`) | `ControllerDecision(action="limit", reason="context")` quando para |
| Falha do controller | geração com o que há; `ModelCallFailed` (`error`) | `ExecutionError(stage="controller")`; o `ModelCall` da falha vem da 006 |
| Tool que falha, estoura prazo ou volta grande | resultado cercado com o status da 004, que volta ao controller | `ToolCall` (004) |

## Fase 5 (US3, US4, flow `rag_first`) — 2026-10-09

Decisões em [research.md](research.md) R35–R48.

### Seam (`api.py`)

| Elemento | Mudança |
|---|---|
| `FLOW_RAG_FIRST` | `"rag_first"`; em `flows()` quando há gateway de tools (como o `agentic`) |
| `flow_roles()` | `"rag_first": ("generation",)` — o `controller` é opcional (FR-007a) |
| `RagSettings` | `candidates: int = 20`, `passages: int = 5`, `min_score: float \| None = None`; `≥ 1`, `≥ 1`, `[0, 1]` |

### Estado interno (privado)

`retrieved: tuple[Passage, ...]` (todos os candidatos, com o pack e a tool de origem) e `reranked: tuple[Passage, ...]`
(junção do R38); a rota ganha `"end"` (recuperação que falhou). `Passage(pack, tool, chunk)` é dado puro de
`domain/gate.py`; a Turn View expõe só os `chunk`.

### Domínio (puro)

| Elemento | Regra |
|---|---|
| `ToolStep.synthetic: bool = False` | marca o passo que o portão grava (R41); entra na geração como um passo executado, e a projeção não soma os chunks dele em `retrieved` (já estão nos candidatos) |
| `optional_roles(flow)` | `("controller",)` no `rag_first`, `()` nos outros; papel opcional declarado no grant é resolvido antes do primeiro evento (FR-013, R40) |

### Turn View no `rag_first`

| Campo | Caminho coberto | Sem cobertura, sem `controller` | Loop escalado |
|---|---|---|---|
| `retrieved` | candidatos | candidatos | os da recuperação inicial + os do loop |
| `reranked` | junção do R38 | junção do R38 | junção do R38 |
| `generation_context` | os trechos que couberam (R42) | vazio | os do loop entregues (como no `agentic`) |

### Registros (`ExecutionIssue`)

| `kind` | Severidade | Quando |
|---|---|---|
| `RetrievalFailed` | `error` | tool de recuperação com status diferente de `ok`; a execução termina sem gerar |
| `RerankFailed` | `notice` | o reranker de um pack levantou, devolveu trecho que não veio da recuperação ou mais que `top_k`; vale a ordem do retriever |
| `CoverageInsufficient` | `notice` | sem cobertura e sem `controller`; a geração roda sem trechos |
| `ContextTrimmed` | `notice` | trechos de menor posição tirados para caber no teto |

### Trace (009, aditivo — ADR-017)

`CoverageGate(request_id, candidates, passages, best_score: float | None, threshold: float | None, covered: bool,
route)` — sem texto nem identificadores de trecho. `route ∈ {"generate", "controller", "fallback"}` (`fallback` = gerar
sem trechos); `covered` vale exatamente quando `route == "generate"`; `passages ≤ candidates`; `best_score` é `None`
exatamente quando `passages == 0`.

### Fora da 005 (toques declarados)

| Módulo | Mudança |
|---|---|
| 002 | `PackHooks.reranker(composition, pack) -> Reranker \| None` |
| 004 | renderização `[documento — seção, p. N · id: <chunk_id>]`; `ToolSession.fence_chunks(name, chunks) -> FencedToolResult` |
| 009 | evento `CoverageGate` |
| 011 | `AI_CORE_RAG_CANDIDATES`, `AI_CORE_RAG_PASSAGES`, `AI_CORE_RAG_MIN_SCORE` → `RagSettings` |

## Desfecho de etapa ([ADR-028](../../docs/adr/ADR-028-o-motor-publica-o-desfecho-de-cada-etapa.md)) — 2026-10-13

### `StepFinished` (membro novo de `ExecutionEvent`)

| Campo | Tipo | Regra |
|---|---|---|
| `stage` | `str` | a etapa que terminou; não vazio; o mesmo valor do `ProgressEvent` dela |
| `outcome` | `StepOutcome \| None` | `None` quando não há o que contar (`prepare_context`, `validate_answer`) |

Sai depois de todo o trabalho e de todo token da etapa, antes do progresso da seguinte. Com `stream=False`, não sai.

### Desfechos (`StepOutcome`)

| Tipo | Etapa | Campos |
|---|---|---|
| `ToolCallsOutcome` | `retrieve`, `execute_tool` | `calls: tuple[ToolCallSummary, ...]` — no `retrieve`, uma por tool de recuperação, até a que falhou |
| `ToolCallSummary` | — | `tool`, `kind` (do catálogo; `None` fora dele), `arguments` (congelados), `status` (o do gateway da 004), `truncated`, `sources: tuple[SourceRef, ...]` |
| `SourceRef` | — | `document` (não vazio), `section`, `page` — nunca o texto |
| `RerankOutcome` | `rerank` | `candidates ≥ 0`, `kept: tuple[SourceRef, ...]` (na ordem), `degraded` (packs cujo reranker falhou) |
| `GateOutcome` | `gate` | `covered`, `route` (`GateRoute`: `generate`, `controller`, `fallback`), `best_score`, `threshold`, `delivered ≥ 0` (trechos que couberam no teto; 0 fora de `generate`) |
| `ControllerOutcome` | `controller` | `iteration ≥ 1`, `action` (`tool`, `answer`, `invalid`, `failed`), `model` (`provider/modelo`), `tool`, `arguments`, `reason` (o motivo da ação inválida, ou o tipo da falha) |
| `GenerationOutcome` | `generate` | `model`, `input_tokens`, `output_tokens` (do `usage` do provider; `None` sem ele) |
| `CatalogOutcome` | `load_capabilities` | `tools ≥ 0`, `unavailable` (aliases MCP, sem o motivo) |

Os limites (iterações, contexto) não chamam o controller e não ganham desfecho: continuam como registros `notice`.
`GateRoute` passou a ser publicado aqui; `domain/gate.py` o importa. Os desfechos são montados em `domain/steps.py`
(`source_refs`, `tool_summary`), puro.


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

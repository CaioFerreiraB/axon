# Contrato — superfície pública de `ai_core_contracts` 0.1

Esta é a superfície que o FR-020 congela: tudo o que está em `ai_core_contracts.__all__` e em
`ai_core_contracts.testing.__all__` ([testing-kit.md](testing-kit.md)). Símbolo fora do `__all__` é interno (prefixo `_`)
e pode mudar sem aviso. Todo módulo começa com `from __future__ import annotations`.

Campos, defaults e invariantes estão no [data-model.md](../data-model.md); aqui ficam só as assinaturas.

```python
# ai_core_contracts/__init__.py — reexporta tudo abaixo; __all__ explícito
__version__: str                      # "0.1.0"; igual aos metadados da distribuição (teste)

# ai_core_contracts/_freeze.py (tipos públicos reexportados)
type JSONValue = str | int | float | bool | Sequence[JSONValue] | Mapping[str, JSONValue] | None

# ai_core_contracts/pack.py
RETRIEVAL_FILTERS_KEY: Final = "retrieval_filters"

@dataclass(frozen=True, slots=True, kw_only=True)
class PackManifest:
    name: str
    version: str
    preferred_flow: str | None = None
    depends_on: Sequence[str] = ()
    requires_collections: Sequence[str] = ()
    config_schema: Mapping[str, JSONValue] | None = None

@dataclass(frozen=True, slots=True, kw_only=True)
class PackContext:
    pack_name: str
    config: Mapping[str, JSONValue] = ...        # default: mapeamento vazio

@runtime_checkable
class AgentPack(Protocol):
    name: str
    contract_version: str
    def manifest(self) -> PackManifest: ...
    def system_prompt(self, ctx: PackContext) -> str | None: ...
    async def prepare_context(self, view: TurnView, ctx: PackContext) -> Mapping[str, JSONValue]: ...
    def tools(self, ctx: PackContext) -> Sequence[ToolSpec]: ...
    def retrievers(self, ctx: PackContext) -> Sequence[NamedRetriever]: ...
    def reranker(self, ctx: PackContext) -> Reranker | None: ...
    def validators(self, ctx: PackContext) -> Sequence[AnswerValidator]: ...

class PackBase:
    """Defaults dos hooks opcionais. Packs herdam e definem name, contract_version e manifest()."""
    def system_prompt(self, ctx: PackContext) -> str | None: ...                  # None
    async def prepare_context(self, view: TurnView, ctx: PackContext) -> Mapping[str, JSONValue]: ...  # {}
    def tools(self, ctx: PackContext) -> Sequence[ToolSpec]: ...                  # ()
    def retrievers(self, ctx: PackContext) -> Sequence[NamedRetriever]: ...       # ()
    def reranker(self, ctx: PackContext) -> Reranker | None: ...                  # None
    def validators(self, ctx: PackContext) -> Sequence[AnswerValidator]: ...      # ()
    def eval_metrics(self, ctx: PackContext) -> Sequence[EvalMetric]: ...         # () — 0.1.2, ADR-027

# ai_core_contracts/tools.py
type ToolKind = Literal["retrieval", "mcp", "native"]

@dataclass(frozen=True, slots=True, kw_only=True)
class ToolInvocation:
    arguments: Mapping[str, JSONValue]
    request_id: str
    reference_time: datetime                      # aware

type NativeHandler = Callable[[ToolInvocation], Awaitable[object]]

@dataclass(frozen=True, slots=True, kw_only=True)
class ToolSpec:
    name: str
    description: str
    parameters: Mapping[str, JSONValue]
    kind: ToolKind
    mutates: bool = False
    handler: NativeHandler | None = None          # não-None ⇔ kind == "native"

@dataclass(frozen=True, slots=True, kw_only=True)
class ToolResult:
    content: object
    untrusted: bool = True
    truncated: bool = False
    error: str | None = None

# ai_core_contracts/retrieval.py
@dataclass(frozen=True, slots=True, kw_only=True)
class Chunk:
    chunk_id: str
    text: str
    score: float
    document: str
    version: str | None = None
    status: str | None = None
    section: str | None = None
    page: int | None = None
    metadata: Mapping[str, JSONValue] = ...       # default: mapeamento vazio

@runtime_checkable
class Retriever(Protocol):
    async def search(
        self, query: str, *, top_k: int = 20, filters: Mapping[str, JSONValue] | None = None
    ) -> Sequence[Chunk]: ...

@runtime_checkable
class Reranker(Protocol):
    async def rerank(self, query: str, documents: Sequence[Chunk], *, top_k: int = 5) -> Sequence[Chunk]: ...

@dataclass(frozen=True, slots=True, kw_only=True)
class NamedRetriever:
    name: str
    description: str
    collections: frozenset[str]                   # não vazio
    retriever: Retriever

RETRIEVAL_TOOL_PARAMETERS: Final[Mapping[str, JSONValue]]
def retrieval_tool_spec(named: NamedRetriever) -> ToolSpec: ...

# ai_core_contracts/view.py
class Message(TypedDict):
    role: ReadOnly[str]
    content: ReadOnly[str]

class Citation(TypedDict, total=False):
    chunk_id: Required[ReadOnly[str]]
    document: ReadOnly[str]
    version: ReadOnly[str | None]
    status: ReadOnly[str | None]
    section: ReadOnly[str | None]
    page: ReadOnly[int | None]

@dataclass(frozen=True, slots=True, kw_only=True)
class TurnView:
    request_id: str
    assistant: str
    reference_time: datetime                      # aware
    question: str
    messages: Sequence[Message] = ()
    retrieved: Sequence[Chunk] = ()
    reranked: Sequence[Chunk] = ()
    generation_context: Sequence[Chunk] = ()
    tool_results: Sequence[ToolResult] = ()
    answer: str | None = None
    citations: Sequence[Citation] = ()
    own_slice: Mapping[str, JSONValue] = ...
    dependency_slices: Mapping[str, Mapping[str, JSONValue]] = ...

# ai_core_contracts/validation.py
@dataclass(frozen=True, slots=True, kw_only=True)
class ValidatorContext:
    pack_name: str
    config: Mapping[str, JSONValue] = ...

@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationResult:
    ok: bool
    issues: Sequence[str] = ()
    answer: str | None = None
    citations: Sequence[Citation] | None = None
    flags: frozenset[str] = frozenset()

@runtime_checkable
class AnswerValidator(Protocol):
    name: str
    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult: ...

# ai_core_contracts/declaration.py
@dataclass(frozen=True, slots=True, kw_only=True)
class ContractIssue:
    code: str
    message: str
    subject: str | None = None
    severity: Literal["error", "warning"] = "error"

def check_declaration(
    *,
    pack_name: str,
    contract_version: str,
    manifest: PackManifest,
    tools: Sequence[ToolSpec] = (),
    retrievers: Sequence[NamedRetriever] = (),
    validators: Sequence[AnswerValidator] = (),
) -> tuple[ContractIssue, ...]: ...

# ai_core_contracts/llm.py — provisório até a tag (R21)
class ChatToolCall(TypedDict):
    id: str
    name: str
    arguments: str                                # texto JSON

class ChatMessage(TypedDict):
    role: str                                     # "system" | "user" | "assistant" | "tool"
    content: str | None
    name: NotRequired[str]
    tool_calls: NotRequired[Sequence[ChatToolCall]]
    tool_call_id: NotRequired[str]

class ChatTool(TypedDict):
    name: str
    description: str
    parameters: Mapping[str, JSONValue]

class ChatUsage(TypedDict):
    prompt_tokens: int
    completion_tokens: int

class ChatResponse(TypedDict):
    message: ChatMessage
    finish_reason: str
    usage: NotRequired[ChatUsage]
    model: NotRequired[str]

class ChatChunk(TypedDict):
    delta: str
    tool_calls: NotRequired[Sequence[ChatToolCall]]
    finish_reason: NotRequired[str]
    usage: NotRequired[ChatUsage]

@runtime_checkable
class LLMProvider(Protocol):
    @overload
    async def chat(
        self, messages: Sequence[ChatMessage], model: str, *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
        stream: Literal[False] = False,
    ) -> ChatResponse: ...
    @overload
    async def chat(
        self, messages: Sequence[ChatMessage], model: str, *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
        stream: Literal[True],
    ) -> AsyncIterator[ChatChunk]: ...

# ai_core_contracts/mcp.py — provisório até a tag (R22)
@runtime_checkable
class MCPClient(Protocol):
    async def discover_tools(self, aliases: Sequence[str]) -> Sequence[ToolSpec]: ...
    async def execute(self, alias: str, tool: str, arguments: Mapping[str, JSONValue]) -> ToolResult: ...

# ai_core_contracts/compat.py — ver compatibility.md
class InvalidVersion(ValueError): ...
class InvalidSpecifier(ValueError): ...

@dataclass(frozen=True, slots=True)
class Version:
    release: tuple[int, ...]
    pre: tuple[str, int] | None = None
    dev: int | None = None
    @classmethod
    def parse(cls, text: str) -> Version: ...
    @property
    def is_prerelease(self) -> bool: ...          # pré-release ou dev
    @property
    def base_release(self) -> tuple[int, ...]: ...  # release sem zeros à direita
    # ordem total do PEP 440 (__lt__, __le__, ...); __str__ normalizado

@dataclass(frozen=True, slots=True)
class VersionRange:
    clauses: tuple[tuple[str, str], ...]          # (operador, operando) na ordem canônica, ex.: ((">=", "0.1"), ("<", "0.2"))
    @classmethod
    def parse(cls, text: str) -> VersionRange: ...        # ">=0.1,<0.2"
    def contains(self, version: str | Version) -> bool: ...
    def violated_by(self, version: str | Version) -> str | None: ...   # cláusula violada, ex.: ">=0.2"
    # __str__ canônico

@dataclass(frozen=True, slots=True, kw_only=True)
class Compatibility:
    ok: bool
    installed: str
    required: str                                 # faixa efetiva, ex.: ">=0.2,<0.3"
    violated: str | None
    message: str | None                           # "requer ai-core-contracts>=0.2, instalado 0.1.4"

type ChangeKind = Literal["none", "additive", "breaking"]
type BumpKind = Literal["none", "patch", "minor", "major"]

def parse_contract_version(text: str) -> Version: ...          # só "X.Y" ou "X.Y.Z"
def derive_range(contract_version: str) -> VersionRange: ...
def check_compatibility(requirement: str | VersionRange, *, installed: str | None = None) -> Compatibility: ...
def removal_version(since: str) -> str: ...
def required_bump(change: ChangeKind, *, current: str) -> BumpKind: ...
def declared_bump(previous: str, current: str) -> BumpKind: ...

# ai_core_contracts/deprecation.py
class ContractDeprecationWarning(DeprecationWarning): ...
def contract_deprecated[T](since: str, *, use_instead: str | None = None) -> Callable[[T], T]: ...
```

## Comportamentos que fazem parte do contrato

| Comportamento | Onde se verifica |
|---|---|
| Value objects são imutáveis em profundidade; dois produtores com os mesmos dados geram objetos iguais | `tests/unit`; US4 |
| `TurnView`, `ToolInvocation`: `reference_time` sem fuso → `ValueError` | `tests/unit` |
| `ToolSpec`: `handler` presente ⇔ `kind == "native"`; senão `ValueError` | `tests/unit`; US2 cenário 3 |
| `NamedRetriever`: `collections` vazio → `ValueError` | `tests/unit`; edge case |
| `PackBase`: hooks opcionais devolvem `None`, `()` ou `{}` sem erro | `tests/unit`; US2 cenário 2 |
| `retrieval_tool_spec`: tipo `retrieval`, nome e descrição do retriever, `RETRIEVAL_TOOL_PARAMETERS`, sem handler | `tests/unit`; US2 cenário 4 |
| Nenhum módulo de runtime faz I/O ou lê relógio; imports só da stdlib e de `typing_extensions` | `tests/boundary`; FR-001, FR-017 |

## `StreamingValidator` e `AnswerStream` (contratos 0.1.1 — ADR-024)

```python
class AnswerStream(Protocol):
    def feed(self, delta: str) -> str: ...          # o texto pronto para sair agora (pode segurar)
    def finish(self) -> ValidationResult: ...       # answer começa com o que feed liberou; igual a validate

class StreamingValidator(AnswerValidator, Protocol):
    def open_stream(self, view: TurnView, ctx: ValidatorContext) -> AnswerStream: ...
```

Regras: a sessão vê a Turn View da abertura (antes da geração, sem `answer`) e não depende de citações de validators
anteriores; `finish().answer` é `None` só quando nada muda e `feed` liberou a resposta inteira; determinístico e sem
modelos, como `validate`.

## Avaliação: `ai_core_contracts.eval` (contratos 0.1.2 — ADR-027)

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class EvalEvidence:          # document (não vazio), section=None, chunk_id=None
class EvalItem:              # id, question, reference_time (com fuso), expected_documents=(), reference_answer=None,
                             # expected_citations=(), extra={} (opaco, congelado)
class EvalChunk:             # chunk_id, score (não NaN), document, version=None, status=None, section=None, page=None (>= 1)
class EvalObservation:       # answer, citations=(), flags=frozenset(), retrieved=(), reranked=(), delivered=(), issue_kinds=()

@runtime_checkable
class EvalMetric(Protocol):
    name: str
    better: Literal["higher", "lower"]
    deterministic: bool
    def measure(self, item: EvalItem, observation: EvalObservation) -> float | None: ...   # síncrono e puro

@runtime_checkable
class ProvidesEvalMetrics(Protocol):
    def eval_metrics(self, ctx: PackContext) -> Sequence[EvalMetric]: ...
```

Regras: o hook é **opcional** — `AgentPack` não muda, e um pack sem ele continua conforme; `PackBase` devolve `()`. É
chamado uma vez, na carga, como os hooks de catálogo. `measure` devolve `None` quando a métrica não se aplica ao item;
só métricas `deterministic` (que não dependem do texto gerado) podem barrar uma regressão no harness da 009.
`EvalChunk` nunca carrega o texto do trecho.


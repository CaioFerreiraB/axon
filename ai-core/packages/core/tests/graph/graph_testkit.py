"""Fábricas dos testes da 005 (T007, T031): grant, hooks programáveis, controller e gateway simulados e o motor.

A construção do motor está num **único** helper (`engine`): é o único ponto do testkit que conhece o adapter de fluxo,
e é o que faz valer a promessa do SC-001 de que as suítes de conformidade e de `domain/` sobrevivem à troca do grafo.

Fase 3 (research R29): o controller é um provider de teste com roteiro (`ScriptedController`), que entra no roteador
real da 006 sob o provider `ctrl`; o gateway é um falso (`FakeCapabilities`/`FakeSession`) que cumpre os `Protocol`s da
004 com os value objects dela. O grant é o da 003 (ADR-018).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Final, Literal

from ai_core.assistants.api import ExecutionGrant, Limits, Principal
from ai_core.capabilities.api import CatalogTool, FencedToolResult, ToolCall, ToolContext
from ai_core.graph.adapters.clock import FixedClock
from ai_core.graph.adapters.langgraph import langgraph_runtime
from ai_core.graph.api import ExecutionRequest
from ai_core.graph.ports import FlowRuntime
from ai_core.graph.service import ExecutionService
from ai_core.llm.adapters.fake import ScriptedProvider
from ai_core.llm.api import ModelCallFailed, ModelPolicy, ModelRef
from ai_core.llm.ports import ProbeResult
from ai_core.llm.service import ModelRoutingService
from ai_core.observability.api import TraceEvent
from ai_core.packs.api import Composition, Slices, StreamedValidation, ValidationOutcome, ValidatorRun
from ai_core_contracts import ChatMessage, ChatResponse, Chunk, Citation, JSONValue, Message, TurnView, ValidationResult

REQUEST_ID: Final = "req-005-1"
ASSISTANT: Final = "geral"
MODEL: Final = "qwen3:1.7b"
CONTROLLER_PROVIDER: Final = "ctrl"
CONTROLLER_MODEL: Final = "controlador"
PRINCIPAL: Final = Principal(subject="user:test", scheme="oidc")
REFERENCE_TIME: Final = datetime(2026, 9, 21, 12, tzinfo=UTC)

MESSAGES: Final[tuple[Message, ...]] = ({"role": "user", "content": "qual é a capital?"},)


class RecordingTraceSink:
    """Trace Sink (seam da 009) que acumula o que foi emitido."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)

    def of_type(self, kind: type) -> list[Any]:
        return [event for event in self.events if isinstance(event, kind)]


def models(*, controller: bool = True) -> ModelPolicy:
    """Geração local e, por default, o controller no provider de teste `ctrl`."""
    roles: dict[Any, ModelRef] = {"generation": ModelRef(provider="ollama", model=MODEL)}
    if controller:
        roles["controller"] = ModelRef(provider=CONTROLLER_PROVIDER, model=CONTROLLER_MODEL)
    return ModelPolicy(roles=roles, allow=("ollama/*", f"{CONTROLLER_PROVIDER}/*"))


def Grant(**overrides: Any) -> ExecutionGrant:
    """O `ExecutionGrant` da 003, como a resolução de Assistant o produz (ADR-018). Qualquer campo pode ser trocado."""
    fields: dict[str, Any] = {
        "assistant": ASSISTANT,
        "principal": PRINCIPAL,
        "flow": "chat",
        "composition": Composition(packs=("generic",)),
        "models": models(),
        "limits": Limits(),
    }
    return ExecutionGrant(**(fields | overrides))


def agentic(**overrides: Any) -> ExecutionGrant:
    return Grant(**({"flow": "agentic"} | overrides))


class ScriptedHooks:
    """`PackHooks` programável: prompts, fatias e validators, com opção de levantar como um pack defeituoso faria."""

    def __init__(
        self,
        *,
        prompts: Sequence[str] = ("Responda em português.",),
        slice_update: dict[str, Any] | None = None,
        outcome: ValidationOutcome | None = None,
        prepare_error: Exception | None = None,
        validate_error: Exception | None = None,
        answer_filter: Any = None,
    ) -> None:
        self._prompts = tuple(prompts)
        self._slice_update = slice_update or {"preparado": True}
        self._outcome = outcome
        self._prepare_error = prepare_error
        self._validate_error = validate_error
        self._answer_filter = answer_filter
        self.prepare_views: list[TurnView] = []
        self.stream_views: list[TurnView] = []
        self.validate_streamed: list[StreamedValidation | None] = []
        self.validate_views: list[TurnView] = []
        self.validate_slices: list[Slices] = []

    def system_prompts(self, composition: Composition) -> tuple[str, ...]:
        return self._prompts

    async def prepare(self, composition: Composition, view: TurnView, slices: Slices) -> Slices:
        if self._prepare_error is not None:
            raise self._prepare_error
        self.prepare_views.append(view)
        return {name: {**dict(slices.get(name, {})), **self._slice_update} for name in composition.packs}

    def open_answer_stream(self, composition: Composition, view: TurnView, slices: Slices) -> Any:
        """O filtro programado, ou um que deixa tudo passar (ADR-024)."""
        self.stream_views.append(view)
        return self._answer_filter if self._answer_filter is not None else PassThroughFilter()

    async def validate(
        self, composition: Composition, view: TurnView, slices: Slices, streamed: StreamedValidation | None = None
    ) -> ValidationOutcome:
        if self._validate_error is not None:
            raise self._validate_error
        self.validate_streamed.append(streamed)
        self.validate_views.append(view)
        self.validate_slices.append(slices)
        if self._outcome is not None:
            return self._outcome
        return ValidationOutcome(ok=True, answer=None, citations=(), flags=frozenset(), runs=())


class PassThroughFilter:
    """`AnswerFilter` sem validators de streaming: tudo passa, nada sobra para o fim."""

    def __init__(self) -> None:
        self._emitted = ""

    def feed(self, delta: str) -> str:
        self._emitted += delta
        return delta

    def finish(self) -> StreamedValidation:
        return StreamedValidation(tail="", answer=self._emitted)


class DropFilter:
    """`AnswerFilter` que tira um caractere à medida que a resposta chega e acrescenta uma cauda no fim."""

    def __init__(self, drop: str = "X", tail: str = "") -> None:
        self._drop = drop
        self._tail = tail
        self._emitted = ""

    def feed(self, delta: str) -> str:
        released = delta.replace(self._drop, "")
        self._emitted += released
        return released

    def finish(self) -> StreamedValidation:
        return StreamedValidation(tail=self._tail, answer=self._emitted + self._tail)


def outcome(
    *,
    ok: bool = True,
    answer: str | None = None,
    citations: Sequence[Citation] = (),
    issues: Sequence[str] = (),
    flags: frozenset[str] = frozenset(),
    pack: str = "generic",
    validator: str = "checa",
) -> ValidationOutcome:
    """Resultado de validators com um único run — o suficiente para os cenários da US1."""
    result = ValidationResult(ok=ok, issues=issues, answer=answer, citations=citations or None, flags=flags)
    return ValidationOutcome(
        ok=ok,
        answer=answer,
        citations=tuple(citations),
        flags=flags,
        runs=(ValidatorRun(pack=pack, validator=validator, result=result),),
    )


def provider(*, deltas: Sequence[str] = ("Bras", "ília"), error: Exception | None = None) -> ScriptedProvider:
    return ScriptedProvider(name="ollama", deltas=deltas, error=error)  # type: ignore[arg-type]


def engine(
    *,
    hooks: Any = None,
    llm: ScriptedProvider | None = None,
    trace: RecordingTraceSink | None = None,
    clock: FixedClock | None = None,
    flows: FlowRuntime | None = None,
    capabilities: Any = None,
    controller: ScriptedController | None = None,
) -> ExecutionService:
    """Monta o motor com o adapter de fluxo real. Trocar o grafo é trocar `flows` — e só isto muda nos testes."""
    sink = trace or RecordingTraceSink()
    extra: dict[str, Any] = {} if capabilities is None else {"capabilities": capabilities}
    return ExecutionService(
        flows=flows or langgraph_runtime(),
        hooks=hooks or ScriptedHooks(),
        routing=ModelRoutingService(
            providers={"ollama": llm or provider(), CONTROLLER_PROVIDER: controller or ScriptedController(())},
            trace=sink,
            clock=clock or FixedClock(REFERENCE_TIME),
        ),
        trace=sink,
        clock=clock or FixedClock(REFERENCE_TIME),
        **extra,
    )


def request(**overrides: Any) -> ExecutionRequest:
    fields: dict[str, Any] = {"request_id": REQUEST_ID, "messages": MESSAGES}
    return ExecutionRequest(**(fields | overrides))


# --- Fase 3: controller e gateway simulados (T031, research R29) ----------------------------------------------------

ANSWER: Final = '{"action": "answer"}'


def tool_action(name: str, **arguments: JSONValue) -> str:
    """A saída de um controller que pede `name` com `arguments`."""
    return json.dumps({"action": "tool", "name": name, "arguments": arguments}, ensure_ascii=False)


type Line = str | BaseException | None
"""Um item do roteiro do controller: o conteúdo que ele devolve, `None` (sem conteúdo) ou a exceção que levanta."""


class ScriptedController:
    """Provider de teste do papel `controller`: cumpre o `ModelProvider` da 006 estruturalmente.

    Cada chamada consome o próximo item do roteiro; chamar além do roteiro é erro de teste — é o que prova que o motor
    nunca passa do limite.
    """

    def __init__(self, script: Sequence[Line]) -> None:
        self._script = list(script)
        self.calls: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return CONTROLLER_PROVIDER

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        model: str,
        *,
        tools: Any = None,
        response_format: Mapping[str, JSONValue] | None = None,
        stream: bool = False,
    ) -> ChatResponse:
        assert not stream, "o controller é chamado sem streaming"
        self.calls.append({"model": model, "messages": list(messages), "response_format": response_format})
        assert self._script, f"controller chamado além do roteiro (chamada {len(self.calls)})"
        line = self._script.pop(0)
        if isinstance(line, BaseException):
            raise line
        return {"message": {"role": "assistant", "content": line}, "finish_reason": "stop", "model": model}

    async def probe(self, model: str) -> ProbeResult:
        return ProbeResult(available=True)


def controller_down() -> ModelCallFailed:
    return ModelCallFailed(provider=CONTROLLER_PROVIDER, model=CONTROLLER_MODEL, reason="fora do ar")


TEXT_PARAMETERS: Final[Mapping[str, JSONValue]] = {
    "type": "object",
    "properties": {"expression": {"type": "string"}},
    "required": ["expression"],
}


def catalog_tool(
    name: str = "generic.calculate",
    *,
    description: str = "Calcula uma expressão aritmética.",
    parameters: Mapping[str, JSONValue] = TEXT_PARAMETERS,
    kind: Literal["native", "retrieval", "mcp"] = "native",
) -> CatalogTool:
    return CatalogTool(name=name, description=description, parameters=parameters, kind=kind)


def fenced(name: str, text: str, *, status: str = "ok", truncated: bool = False) -> str:
    """O formato da cerca da 004 (contracts/fencing.md), para o gateway falso produzir o mesmo que o real."""
    return f'<tool_result name="{name}" status="{status}" truncated="{str(truncated).lower()}">\n{text}\n</tool_result>'


class FakeSession:
    """`ToolSession` da 004 programável: catálogo, indisponíveis e o conteúdo de cada tool; guarda as chamadas."""

    def __init__(
        self,
        tools: Sequence[CatalogTool] = (),
        *,
        results: Mapping[str, str] | None = None,
        chunks: Mapping[str, Sequence[Chunk]] | None = None,
        unavailable: Mapping[str, str] | None = None,
    ) -> None:
        self._tools = {tool.name: tool for tool in tools}
        self._results = dict(results or {})
        self._chunks = dict(chunks or {})
        self._unavailable = dict(unavailable or {})
        self.calls: list[ToolCall] = []

    @property
    def tools(self) -> Mapping[str, CatalogTool]:
        return self._tools

    @property
    def unavailable(self) -> Mapping[str, str]:
        return self._unavailable

    async def execute(self, call: ToolCall) -> FencedToolResult:
        self.calls.append(call)
        tool = self._tools.get(call.name)
        if tool is None:
            text = f"tool inexistente: {call.name}"
            return FencedToolResult(
                name=call.name, kind=None, status="unknown", text=fenced(call.name, text, status="unknown"), error=text
            )
        content = self._results.get(call.name, f"resultado {len(self.calls)}")
        return FencedToolResult(
            name=call.name,
            kind=tool.kind,
            status="ok",
            text=fenced(call.name, content),
            chunks=tuple(self._chunks.get(call.name, ())),
        )


class FakeCapabilities:
    """`Capabilities` da 004: devolve a sessão programada ou levanta o erro programado; guarda o que recebeu."""

    def __init__(self, session: FakeSession | None = None, *, error: Exception | None = None) -> None:
        self.session = session or FakeSession((catalog_tool(),))
        self._error = error
        self.opened: list[tuple[ExecutionGrant, ToolContext]] = []

    async def open(self, grant: ExecutionGrant, context: ToolContext) -> FakeSession:
        self.opened.append((grant, context))
        if self._error is not None:
            raise self._error
        return self.session

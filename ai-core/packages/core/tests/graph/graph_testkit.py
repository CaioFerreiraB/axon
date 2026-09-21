"""Fábricas dos testes da 005 (T007): grant, hooks programáveis e a montagem do motor.

A construção do motor está num **único** helper (`engine`): é o único ponto do testkit que conhece o adapter de fluxo,
e é o que faz valer a promessa do SC-001 de que as suítes de conformidade e de `domain/` sobrevivem à troca do grafo.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

from ai_core.graph.adapters.clock import FixedClock
from ai_core.graph.adapters.langgraph import langgraph_runtime
from ai_core.graph.api import ExecutionRequest
from ai_core.graph.ports import FlowRuntime
from ai_core.graph.service import ExecutionService
from ai_core.llm.adapters.fake import ScriptedProvider
from ai_core.llm.api import ModelPolicy, ModelRef
from ai_core.llm.service import ModelRoutingService
from ai_core.observability.api import TraceEvent
from ai_core.packs.api import Composition, Slices, ValidationOutcome, ValidatorRun
from ai_core_contracts import Citation, Message, TurnView, ValidationResult

REQUEST_ID: Final = "req-005-1"
ASSISTANT: Final = "geral"
MODEL: Final = "qwen3:1.7b"
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


@dataclass(frozen=True, slots=True)
class Grant:
    """Objeto que cumpre o `Protocol` `ExecutionGrant` — é o que a 011 monta na Fase 1 e a 003 produzirá na Fase 2."""

    assistant: str = ASSISTANT
    flow: str = "chat"
    composition: Composition = field(default_factory=lambda: Composition(packs=("generic",)))
    models: ModelPolicy = field(
        default_factory=lambda: ModelPolicy(
            roles={"generation": ModelRef(provider="ollama", model=MODEL)}, allow=("ollama/*",)
        )
    )


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
    ) -> None:
        self._prompts = tuple(prompts)
        self._slice_update = slice_update or {"preparado": True}
        self._outcome = outcome
        self._prepare_error = prepare_error
        self._validate_error = validate_error
        self.prepare_views: list[TurnView] = []
        self.validate_views: list[TurnView] = []
        self.validate_slices: list[Slices] = []

    def system_prompts(self, composition: Composition) -> tuple[str, ...]:
        return self._prompts

    async def prepare(self, composition: Composition, view: TurnView, slices: Slices) -> Slices:
        if self._prepare_error is not None:
            raise self._prepare_error
        self.prepare_views.append(view)
        return {name: {**dict(slices.get(name, {})), **self._slice_update} for name in composition.packs}

    async def validate(self, composition: Composition, view: TurnView, slices: Slices) -> ValidationOutcome:
        if self._validate_error is not None:
            raise self._validate_error
        self.validate_views.append(view)
        self.validate_slices.append(slices)
        if self._outcome is not None:
            return self._outcome
        return ValidationOutcome(ok=True, answer=None, citations=(), flags=frozenset(), runs=())


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
) -> ExecutionService:
    """Monta o motor com o adapter de fluxo real. Trocar o grafo é trocar `flows` — e só isto muda nos testes."""
    sink = trace or RecordingTraceSink()
    return ExecutionService(
        flows=flows or langgraph_runtime(),
        hooks=hooks or ScriptedHooks(),
        routing=ModelRoutingService(
            providers={"ollama": llm or provider()},
            trace=sink,
            clock=clock or FixedClock(REFERENCE_TIME),
        ),
        trace=sink,
        clock=clock or FixedClock(REFERENCE_TIME),
    )


def request(**overrides: Any) -> ExecutionRequest:
    fields: dict[str, Any] = {"request_id": REQUEST_ID, "messages": MESSAGES}
    return ExecutionRequest(**(fields | overrides))

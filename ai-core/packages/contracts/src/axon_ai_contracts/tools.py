"""Tools: especificação, invocação de tool nativa e resultado (FR-004, FR-005, ADR-005, research R10)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from axon_ai_contracts._freeze import JSONValue, freeze, freeze_mapping, require_aware, require_non_empty

type ToolKind = Literal["retrieval", "mcp", "native"]

_TOOL_KINDS = frozenset({"retrieval", "mcp", "native"})


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolInvocation:
    """O que um handler nativo recebe: argumentos já validados e os dados da execução que o gateway conhece."""

    arguments: Mapping[str, JSONValue]
    request_id: str
    reference_time: datetime

    def __post_init__(self) -> None:
        require_non_empty("request_id", self.request_id)
        require_aware("reference_time", self.reference_time)
        object.__setattr__(self, "arguments", freeze_mapping(self.arguments))


type NativeHandler = Callable[[ToolInvocation], Awaitable[object]]


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolSpec:
    """Capacidade invocável. O nome é local; o core aplica o namespace (`<pack>.<nome>`)."""

    name: str
    description: str
    parameters: Mapping[str, JSONValue]
    kind: ToolKind
    mutates: bool = False
    handler: NativeHandler | None = None

    def __post_init__(self) -> None:
        require_non_empty("name", self.name)
        require_non_empty("description", self.description)
        if self.kind not in _TOOL_KINDS:
            raise ValueError(f"kind inválido: {self.kind!r} (esperado retrieval, mcp ou native)")
        if (self.handler is not None) != (self.kind == "native"):
            raise ValueError("handler é obrigatório em tool 'native' e proibido nos outros tipos")
        object.__setattr__(self, "parameters", freeze_mapping(self.parameters))


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolResult:
    """Resultado de tool: sempre dado não-confiável, nunca instrução (princípio VI)."""

    content: object
    untrusted: bool = True
    truncated: bool = False
    error: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "content", freeze(self.content))

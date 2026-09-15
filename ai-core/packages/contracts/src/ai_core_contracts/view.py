"""Turn View: visão somente-leitura e estável da execução entregue aos hooks de pack (FR-009, ADR-011, ADR-013).

O estado interno do motor é privado do core; o pack só enxerga estes campos. Campo novo entra com default (aditivo).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Required

from typing_extensions import ReadOnly, TypedDict

from ai_core_contracts._freeze import (
    JSONValue,
    empty_mapping,
    freeze_mapping,
    freeze_sequence,
    require_aware,
    require_non_empty,
)
from ai_core_contracts.retrieval import Chunk
from ai_core_contracts.tools import ToolResult


class Message(TypedDict):
    """Mensagem do histórico da conversa. Papéis conhecidos: `system`, `user`, `assistant`, `tool`."""

    role: ReadOnly[str]
    content: ReadOnly[str]


class Citation(TypedDict, total=False):
    """Citação corrente da resposta; `chunk_id` aponta para um chunk entregue à geração."""

    chunk_id: Required[ReadOnly[str]]
    document: ReadOnly[str]
    version: ReadOnly[str | None]
    status: ReadOnly[str | None]
    section: ReadOnly[str | None]
    page: ReadOnly[int | None]


@dataclass(frozen=True, slots=True, kw_only=True)
class TurnView:
    """O que um hook de pack enxerga de uma execução. Imutável em profundidade.

    `reference_time` é a data de referência da execução, a mesma em toda Turn View dela: packs usam este valor, nunca
    o relógio do sistema. `generation_context` são os chunks efetivamente entregues à geração. `dependency_slices` só
    contém as fatias dos packs em `manifest.depends_on`.
    """

    request_id: str
    assistant: str
    reference_time: datetime
    question: str
    messages: Sequence[Message] = ()
    retrieved: Sequence[Chunk] = ()
    reranked: Sequence[Chunk] = ()
    generation_context: Sequence[Chunk] = ()
    tool_results: Sequence[ToolResult] = ()
    answer: str | None = None
    citations: Sequence[Citation] = ()
    own_slice: Mapping[str, JSONValue] = field(default_factory=empty_mapping)
    dependency_slices: Mapping[str, Mapping[str, JSONValue]] = field(default_factory=empty_mapping)

    def __post_init__(self) -> None:
        require_non_empty("request_id", self.request_id)
        require_non_empty("assistant", self.assistant)
        require_aware("reference_time", self.reference_time)
        for name in ("messages", "retrieved", "reranked", "generation_context", "tool_results", "citations"):
            object.__setattr__(self, name, freeze_sequence(getattr(self, name)))
        object.__setattr__(self, "own_slice", freeze_mapping(self.own_slice))
        object.__setattr__(self, "dependency_slices", freeze_mapping(self.dependency_slices))

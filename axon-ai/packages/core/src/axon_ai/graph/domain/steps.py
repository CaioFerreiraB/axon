"""Desfecho de etapa (ADR-028): puro, montado com o que a etapa já tem nas mãos.

Só fontes, contagens e status — o texto do trecho, o conteúdo do resultado e o texto de erro ficam de fora.
"""

from __future__ import annotations

from collections.abc import Iterable

from axon_ai.capabilities.api import FencedToolResult, ToolCall
from axon_ai.graph.api import SourceRef, ToolCallSummary
from axon_ai_contracts import Chunk


def source_refs(chunks: Iterable[Chunk]) -> tuple[SourceRef, ...]:
    """A proveniência de cada trecho, na ordem."""
    return tuple(SourceRef(document=chunk.document, section=chunk.section, page=chunk.page) for chunk in chunks)


def tool_summary(call: ToolCall, result: FencedToolResult) -> ToolCallSummary:
    """Uma chamada como a etapa a fez: o pedido e o desfecho do gateway, sem `result.text` nem `result.error`."""
    return ToolCallSummary(
        tool=call.name,
        kind=result.kind,
        arguments=call.arguments,
        status=result.status,
        truncated=result.truncated,
        sources=source_refs(result.chunks),
    )

"""Construtores determinísticos de fixtures: Turn View, chunks, contextos e invocação de tool (SC-003).

Nenhuma fixture lê o relógio: a data padrão é `REFERENCE_TIME` (ADR-013).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Final

from ai_core_contracts._freeze import JSONValue
from ai_core_contracts.pack import PackContext
from ai_core_contracts.retrieval import Chunk
from ai_core_contracts.tools import ToolInvocation, ToolResult
from ai_core_contracts.validation import ValidatorContext
from ai_core_contracts.view import Citation, Message, TurnView

REFERENCE_TIME: Final = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def turn_view(
    *,
    request_id: str = "req-test",
    assistant: str = "test-assistant",
    reference_time: datetime = REFERENCE_TIME,
    question: str = "",
    messages: Sequence[Message] = (),
    retrieved: Sequence[Chunk] = (),
    reranked: Sequence[Chunk] = (),
    generation_context: Sequence[Chunk] = (),
    tool_results: Sequence[ToolResult] = (),
    answer: str | None = None,
    citations: Sequence[Citation] = (),
    own_slice: Mapping[str, JSONValue] | None = None,
    dependency_slices: Mapping[str, Mapping[str, JSONValue]] | None = None,
) -> TurnView:
    return TurnView(
        request_id=request_id,
        assistant=assistant,
        reference_time=reference_time,
        question=question,
        messages=messages,
        retrieved=retrieved,
        reranked=reranked,
        generation_context=generation_context,
        tool_results=tool_results,
        answer=answer,
        citations=citations,
        own_slice=own_slice or {},
        dependency_slices=dependency_slices or {},
    )


def chunk(
    chunk_id: str = "doc#1",
    *,
    text: str = "",
    score: float = 1.0,
    document: str = "doc",
    version: str | None = None,
    status: str | None = None,
    section: str | None = None,
    page: int | None = None,
    metadata: Mapping[str, JSONValue] | None = None,
) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        text=text,
        score=score,
        document=document,
        version=version,
        status=status,
        section=section,
        page=page,
        metadata=metadata or {},
    )


def pack_context(pack_name: str, config: Mapping[str, JSONValue] | None = None) -> PackContext:
    return PackContext(pack_name=pack_name, config=config or {})


def validator_context(pack_name: str, config: Mapping[str, JSONValue] | None = None) -> ValidatorContext:
    return ValidatorContext(pack_name=pack_name, config=config or {})


def tool_invocation(
    arguments: Mapping[str, JSONValue] | None = None,
    *,
    request_id: str = "req-test",
    reference_time: datetime = REFERENCE_TIME,
) -> ToolInvocation:
    return ToolInvocation(arguments=arguments or {}, request_id=request_id, reference_time=reference_time)

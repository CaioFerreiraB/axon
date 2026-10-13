"""O que um item produziu, a partir do evento final e do trace da requisição — puro (research R14, R15, R17).

O harness não conhece internals do motor: lê os eventos tipados que a 009 grava. Sem `Retrieval` no trace, as três
listas de trechos ficam vazias (o flow não recuperou nada).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from ai_core.eval.domain.metrics import ModelCallSample, Operation
from ai_core.graph.api import FinalEvent
from ai_core.observability.api import TraceRecord
from ai_core_contracts import EvalChunk, EvalObservation, JSONValue


def observe(final: FinalEvent, records: Sequence[TraceRecord]) -> EvalObservation:
    retrieval = next((record for record in records if record.type == "retrieval"), None)
    lists = {name: _chunks(retrieval.attributes.get(name)) if retrieval else () for name in _LISTS}
    return EvalObservation(
        answer=final.answer,
        citations=final.citations,
        flags=final.flags,
        retrieved=lists["retrieved"],
        reranked=lists["reranked"],
        delivered=lists["delivered"],
        issue_kinds=tuple(issue.kind for issue in final.errors),
    )


_LISTS = ("retrieved", "reranked", "delivered")


def delivered_texts(records: Sequence[TraceRecord]) -> tuple[str, ...]:
    """O texto dos trechos entregues à geração (o evento `Retrieval` o leva só para eles): o que o juiz lê."""
    retrieval = next((record for record in records if record.type == "retrieval"), None)
    raw = retrieval.attributes.get("delivered") if retrieval else None
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        return ()
    return tuple(
        text for item in raw if isinstance(item, Mapping) and isinstance(text := item.get("text"), str) and text
    )


def operation(
    final: FinalEvent | None, records: Sequence[TraceRecord], *, latency_ms: float, ttft_ms: float | None
) -> Operation:
    calls = tuple(
        ModelCallSample(
            role=str(record.attributes.get("role")),
            input_tokens=_int(record.attributes.get("input_tokens")),
            output_tokens=_int(record.attributes.get("output_tokens")),
            duration_ms=float(_number(record.attributes.get("duration_ms")) or 0.0),
        )
        for record in records
        if record.type == "model_call"
    )
    decisions = tuple(
        str(record.attributes.get("action")) for record in records if record.type == "controller_decision"
    )
    gate = next((record for record in records if record.type == "coverage_gate"), None)
    route = gate.attributes.get("route") if gate else None
    return Operation(
        latency_ms=latency_ms,
        ttft_ms=ttft_ms,
        model_calls=calls,
        decisions=decisions,
        gate_route=route if isinstance(route, str) else None,
        has_error=final is None or any(issue.severity == "error" for issue in final.errors),
    )


def _chunks(value: JSONValue) -> tuple[EvalChunk, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        return ()
    chunks: list[EvalChunk] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            continue
        chunks.append(
            EvalChunk(
                chunk_id=str(raw.get("chunk_id")),
                score=float(_number(raw.get("score")) or 0.0),
                document=str(raw.get("document")),
                version=_text(raw.get("version")),
                status=_text(raw.get("status")),
                section=_text(raw.get("section")),
                page=_int(raw.get("page")),
            )
        )
    return tuple(chunks)


def _text(value: JSONValue) -> str | None:
    return value if isinstance(value, str) else None


def _number(value: JSONValue) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _int(value: JSONValue) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None

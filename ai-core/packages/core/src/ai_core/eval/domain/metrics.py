"""Métricas do core por item e a agregação da rodada — puras (FR-004; research R17).

"Determinística" = depende só do índice, da data e da composição, nunca do texto gerado; só essas podem barrar o CI
(R20). Métricas de domínio (`<pack>:<nome>`, ADR-027) e de juiz entram na mesma agregação.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from ai_core.eval.api import Better, GoldenItem, MetricValue
from ai_core.eval.domain.matching import first_match, found, matches
from axon_ai_contracts import EvalChunk, EvalObservation

type Aggregate = Literal["mean", "percentiles"]


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricSpec:
    name: str
    better: Better | None
    deterministic: bool
    aggregate: Aggregate = "mean"


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelCallSample:
    role: str
    input_tokens: int | None
    output_tokens: int | None
    duration_ms: float


@dataclass(frozen=True, slots=True, kw_only=True)
class Operation:
    """O que a execução de um item custou, medido pelo harness e lido do trace."""

    latency_ms: float
    ttft_ms: float | None = None
    model_calls: Sequence[ModelCallSample] = ()
    decisions: Sequence[str] = ()
    gate_route: str | None = None
    has_error: bool = False


RECALL: Final = "recall@{k}"
CORE: Final[tuple[MetricSpec, ...]] = (
    MetricSpec(name="mrr", better="higher", deterministic=True),
    MetricSpec(name="delivered_recall", better="higher", deterministic=True),
    MetricSpec(name="rerank_gain", better="higher", deterministic=True),
    MetricSpec(name="citation_resolvable_rate", better="higher", deterministic=False),
    MetricSpec(name="citation_invented_rate", better="lower", deterministic=False),
    MetricSpec(name="expected_citation_recall", better="higher", deterministic=False),
    MetricSpec(name="faithfulness", better="higher", deterministic=False),
    MetricSpec(name="coverage", better="higher", deterministic=False),
    MetricSpec(name="latency_ms", better="lower", deterministic=False, aggregate="percentiles"),
    MetricSpec(name="ttft_ms", better="lower", deterministic=False, aggregate="percentiles"),
    MetricSpec(name="tokens_per_answer", better="lower", deterministic=False),
    MetricSpec(name="model_calls_per_answer", better="lower", deterministic=False),
    MetricSpec(name="generation_tokens_per_s", better="higher", deterministic=False),
    MetricSpec(name="controller_invalid_rate", better="lower", deterministic=False),
    MetricSpec(name="error_rate", better="lower", deterministic=False),
)
"""As métricas do core além de `recall@k` (uma por k do conjunto)."""


def core_specs(k: Sequence[int]) -> tuple[MetricSpec, ...]:
    recalls = tuple(MetricSpec(name=RECALL.format(k=value), better="higher", deterministic=True) for value in k)
    return (*recalls, *CORE)


def _ratio(numerator: float, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def retrieval_metrics(item: GoldenItem, observation: EvalObservation, k: Sequence[int]) -> dict[str, float | None]:
    expected = item.expected_documents
    metrics: dict[str, float | None] = {}
    if not expected:
        for value in k:
            metrics[RECALL.format(k=value)] = None
        metrics.update({"mrr": None, "delivered_recall": None, "rerank_gain": None})
        return metrics
    total = len(expected)
    for value in k:
        metrics[RECALL.format(k=value)] = found(expected, observation.retrieved[:value]) / total
    position = first_match(expected, observation.retrieved)
    metrics["mrr"] = 0.0 if position is None else 1 / position
    metrics["delivered_recall"] = found(expected, observation.delivered) / total
    n = len(observation.reranked)
    metrics["rerank_gain"] = (
        None
        if n == 0
        else (found(expected, observation.reranked[:n]) - found(expected, observation.retrieved[:n])) / total
    )
    return metrics


def citation_metrics(item: GoldenItem, observation: EvalObservation) -> dict[str, float | None]:
    delivered = {chunk.chunk_id for chunk in observation.delivered}
    cited = [citation.get("chunk_id") for citation in observation.citations]
    resolvable = sum(chunk_id in delivered for chunk_id in cited)
    cited_chunks = [_as_chunk(citation) for citation in observation.citations]
    expected = item.expected_citations
    return {
        "citation_resolvable_rate": _ratio(resolvable, len(cited)),
        "citation_invented_rate": _ratio(len(cited) - resolvable, len(cited)),
        "expected_citation_recall": (
            None if not expected else sum(any(matches(e, c) for c in cited_chunks) for e in expected) / len(expected)
        ),
    }


def _as_chunk(citation: Mapping[str, object]) -> EvalChunk:
    document = citation.get("document")
    section = citation.get("section")
    return EvalChunk(
        chunk_id=str(citation.get("chunk_id") or "?"),
        score=0.0,
        document=document if isinstance(document, str) and document.strip() else "?",
        section=section if isinstance(section, str) else None,
    )


def operation_metrics(operation: Operation) -> dict[str, float | None]:
    tokens = [
        (call.input_tokens or 0) + (call.output_tokens or 0)
        for call in operation.model_calls
        if call.input_tokens is not None or call.output_tokens is not None
    ]
    generation = [call for call in operation.model_calls if call.role == "generation" and call.output_tokens]
    generation_seconds = sum(call.duration_ms for call in generation) / 1000
    invalid = sum(decision == "invalid" for decision in operation.decisions)
    return {
        "latency_ms": operation.latency_ms,
        "ttft_ms": operation.ttft_ms,
        "tokens_per_answer": float(sum(tokens)) if tokens else None,
        "model_calls_per_answer": float(len(operation.model_calls)),
        "generation_tokens_per_s": (
            None
            if not generation or generation_seconds <= 0
            else sum(call.output_tokens or 0 for call in generation) / generation_seconds
        ),
        "controller_invalid_rate": _ratio(invalid, len(operation.decisions)),
        "error_rate": 1.0 if operation.has_error else 0.0,
    }


def item_metrics(
    item: GoldenItem, observation: EvalObservation, operation: Operation, k: Sequence[int]
) -> dict[str, float | None]:
    return {
        **retrieval_metrics(item, observation, k),
        **citation_metrics(item, observation),
        **operation_metrics(operation),
    }


def unseen_evidence(items: Sequence[GoldenItem], retrieved: Sequence[Sequence[EvalChunk]]) -> dict[str, list[str]]:
    """Por item, as evidências esperadas que não casam com nenhum candidato de nenhum item da rodada (R16): sinal de
    evidência mal escrita ou fora do índice — aviso, nunca invalidação."""
    pool = [chunk for chunks in retrieved for chunk in chunks]
    warnings: dict[str, list[str]] = {}
    for item in items:
        for evidence in item.expected_documents:
            if not any(matches(evidence, chunk) for chunk in pool):
                label = evidence.document if evidence.section is None else f"{evidence.document} — {evidence.section}"
                warnings.setdefault(item.id, []).append(f"evidência não vista: {label}")
    return warnings


def percentile(values: Sequence[float], q: float) -> float:
    """Posição mais próxima (nearest-rank): o menor valor com pelo menos q dos valores até ele."""
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


def aggregate(
    specs: Sequence[MetricSpec],
    per_item: Sequence[Mapping[str, float | None]],
    *,
    variances: Mapping[str, float | None] | None = None,
) -> list[MetricValue]:
    """Média dos itens em que a métrica se aplica (com `n`), ou p50/p95 nas de latência."""
    aggregated: list[MetricValue] = []
    for spec in specs:
        values = [value for metrics in per_item if (value := metrics.get(spec.name)) is not None]
        if spec.aggregate == "percentiles":
            for label, q in (("p50", 0.5), ("p95", 0.95)):
                aggregated.append(
                    MetricValue(
                        name=f"{spec.name}_{label}",
                        value=percentile(values, q) if values else None,
                        n=len(values),
                        deterministic=spec.deterministic,
                        better=spec.better,
                    )
                )
            continue
        aggregated.append(
            MetricValue(
                name=spec.name,
                value=sum(values) / len(values) if values else None,
                n=len(values),
                deterministic=spec.deterministic,
                better=spec.better,
                variance=(variances or {}).get(spec.name),
            )
        )
    return aggregated


def shares(prefix: str, labels: Sequence[Sequence[str]], total: int) -> list[MetricValue]:
    """A fração dos itens com cada rótulo (flags, rotas do portão): informativas, sem sentido de melhora."""
    counts: dict[str, int] = {}
    for item_labels in labels:
        for label in set(item_labels):
            counts[label] = counts.get(label, 0) + 1
    return [
        MetricValue(name=f"{prefix}:{label}", value=count / total, n=total, deterministic=False, better=None)
        for label, count in sorted(counts.items())
        if total
    ]

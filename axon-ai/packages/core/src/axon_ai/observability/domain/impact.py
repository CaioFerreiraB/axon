"""Impacto ambiental das chamadas de modelo (ADR-056; research R45, R48, R49). Puro: sem relógio, banco nem EcoLogits.

Três peças. A **resolução** liga o modelo do Axon (`openrouter` + `z-ai/glm-5.3-flash`, `ollama` + `qwen3:1.7b`) a um
modelo da base do EcoLogits: nome normalizado igual é casamento exato; senão, o mais parecido com nota ≥ 75 e a mesma
família de nome é aproximado; senão, não há par — um modelo errado com cara de certo é pior que "sem estimativa". Os
**grãos** põem cada dia local num balde (semana ISO, mês, trimestre, semestre de janeiro e julho). O **relatório** soma
mínimos e máximos, mostra a média, mede a cobertura e divide as emissões pelo fator das árvores. A agregação daqui é a
referência que o armazenamento em memória usa e que o SQL repete.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Final, cast

from axon_ai.observability.api import (
    ImpactBucket,
    ImpactCoverage,
    ImpactGrain,
    ImpactMatch,
    ImpactMetric,
    ImpactMetrics,
    ImpactQuery,
    ImpactReport,
    ImpactRow,
    ImpactTotals,
    UsageGrouping,
    UsageOrigin,
)
from axon_ai.observability.domain.usage import key_of, local_day, zone
from axon_ai.observability.domain.usage_records import (
    IMPACT_COLUMNS,
    IMPACT_METRICS,
    ImpactAggregate,
    ImpactCell,
    ModelCallRow,
    eligible,
)

APPROXIMATE_MIN_SCORE: Final = 75.0
"""Nota mínima (de 0 a 100) do casamento aproximado; medida contra a base da 0.11.3 (research R45)."""

PROVIDER_ORDER: Final = ("openai", "anthropic", "google_genai", "mistralai", "cohere", "huggingface_hub")
"""Desempate entre provedores do EcoLogits que têm o mesmo nome, quando o fornecedor não decide."""

VENDOR_PROVIDER: Final = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "google_genai",
    "mistralai": "mistralai",
    "cohere": "cohere",
}
"""O prefixo do fornecedor no nome do modelo (sem hífens) → o provedor do EcoLogits."""

type Similarity = Callable[[str, str], float]
"""Nota de 0 a 100; o adapter passa a do `rapidfuzz`, e o domínio não depende dela."""

type ImpactIndex = Mapping[str, tuple[tuple[str, str], ...]]
"""Nome normalizado → os `(provedor, nome)` da base que o têm, na ordem da base."""


# --- resolução do modelo ----------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Resolution:
    provider: str
    name: str
    match: ImpactMatch
    score: float


def normalize(text: str) -> str:
    """Minúsculas, sem o sufixo `:<tag>` do Ollama, com `.`, `_` e espaços como `-`."""
    lowered = text.strip().lower().split(":", 1)[0]
    return re.sub(r"-{2,}", "-", re.sub(r"[.\s_]+", "-", lowered)).strip("-")


def family(name: str) -> str:
    """O primeiro termo só de letras do nome (`glm`, `llama`, `gpt`): o aproximado nunca troca de família."""
    found = re.match(r"[a-z]+", normalize(name.rsplit("/", 1)[-1]))
    return found.group(0) if found else ""


def build_index(models: Iterable[tuple[str, str]]) -> ImpactIndex:
    index: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for provider, name in models:
        index[normalize(name.rsplit("/", 1)[-1])].append((provider, name))
    return {key: tuple(options) for key, options in index.items()}


def _pick(options: Sequence[tuple[str, str]], preferred: str | None) -> tuple[str, str]:
    for option in options:
        if option[0] == preferred:
            return option
    order = {provider: position for position, provider in enumerate(PROVIDER_ORDER)}
    return min(options, key=lambda option: order.get(option[0], len(order)))


def resolve(provider: str, model: str, index: ImpactIndex, similarity: Similarity) -> Resolution | None:
    """O modelo do EcoLogits para a chamada (ADR-056, item 3). O fornecedor é o prefixo do nome, ou o provider."""
    vendor = model.split("/", 1)[0] if "/" in model else provider
    name = model.rsplit("/", 1)[-1]
    base = normalize(name)
    if not base:
        return None
    vendor_key = normalize(vendor).replace("-", "")
    candidates = (base, f"{vendor_key}-{base}") if vendor_key else (base,)
    preferred = VENDOR_PROVIDER.get(vendor_key)
    for candidate in candidates:
        if candidate in index:
            chosen = _pick(index[candidate], preferred)
            return Resolution(chosen[0], chosen[1], "exact", 100.0)
    kin = family(name)
    if not kin:
        return None
    best: tuple[float, str] | None = None
    for candidate in candidates:
        for key in index:
            if kin not in key:
                continue
            score = similarity(candidate, key)
            if score >= APPROXIMATE_MIN_SCORE and (best is None or score > best[0]):
                best = (score, key)
    if best is None:
        return None
    chosen = _pick(index[best[1]], preferred)
    return Resolution(chosen[0], chosen[1], "approximate", best[0])


# --- grãos ------------------------------------------------------------------------------------------------------------


def bucket_start(day: date, grain: ImpactGrain) -> date:
    if grain == "week":
        return day - timedelta(days=day.weekday())
    if grain == "month":
        return day.replace(day=1)
    if grain == "quarter":
        return date(day.year, 3 * ((day.month - 1) // 3) + 1, 1)
    if grain == "semester":
        return date(day.year, 1 if day.month <= 6 else 7, 1)
    return day


def _next(start: date, grain: ImpactGrain) -> date:
    if grain == "day":
        return start + timedelta(days=1)
    if grain == "week":
        return start + timedelta(days=7)
    months = {"month": 1, "quarter": 3, "semester": 6}[grain]
    total = start.month - 1 + months
    return date(start.year + total // 12, total % 12 + 1, 1)


def buckets(start: date, end: date, grain: ImpactGrain) -> tuple[tuple[date, date], ...]:
    """Os baldes que cobrem `[start, end]`, cada um recortado ao período (o primeiro e o último podem ser parciais)."""
    out: list[tuple[date, date]] = []
    current = bucket_start(start, grain)
    while current <= end:
        following = _next(current, grain)
        out.append((max(current, start), min(following - timedelta(days=1), end)))
        current = following
    return tuple(out)


def window(query: ImpactQuery) -> tuple[datetime, datetime]:
    """O período em instantes UTC: da meia-noite local do início à meia-noite local depois do fim."""
    tz = zone(query.tz)
    start = datetime.combine(query.start, time(), tzinfo=tz)
    end = datetime.combine(query.end + timedelta(days=1), time(), tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


# --- agregação de referência ------------------------------------------------------------------------------------------


@dataclass
class _Cell:
    calls: int = 0
    eligible: int = 0
    estimated: int = 0
    approximate: int = 0
    tokens: int = 0
    sums: dict[str, float] = field(default_factory=lambda: dict.fromkeys(IMPACT_COLUMNS, 0.0))

    def add(self, other: ImpactCell | _Cell) -> None:
        self.calls += other.calls
        self.eligible += other.eligible
        self.estimated += other.estimated
        self.approximate += other.approximate
        self.tokens += other.estimated_output_tokens if isinstance(other, ImpactCell) else other.tokens
        for column in IMPACT_COLUMNS:
            self.sums[column] += other.sums.get(column, 0.0)


def aggregate_impact(
    calls: Iterable[ModelCallRow],
    *,
    start: datetime,
    end: datetime,
    tz: str,
    grain: ImpactGrain,
    by: UsageGrouping,
    origin: UsageOrigin,
) -> ImpactAggregate:
    """O que o armazenamento devolve, calculado em Python (a mesma regra do SQL do Postgres)."""
    cells: dict[tuple[date, str | None], _Cell] = defaultdict(_Cell)
    bucket_all: dict[date, set[str]] = defaultdict(set)
    bucket_done: dict[date, set[str]] = defaultdict(set)
    key_all: dict[str | None, set[str]] = defaultdict(set)
    key_done: dict[str | None, set[str]] = defaultdict(set)
    latest: dict[str | None, tuple[datetime, str, str]] = {}
    every: set[str] = set()
    done: set[str] = set()
    for row in calls:
        if not start <= row.at < end or (origin != "all" and row.origin != origin):
            continue
        bucket = bucket_start(local_day(row.at, tz), grain)
        key = key_of(row, by)
        cell = cells[(bucket, key)]
        cell.calls += 1
        bucket_all[bucket].add(row.request_id)
        key_all[key].add(row.request_id)
        every.add(row.request_id)
        if eligible(row):
            cell.eligible += 1
        if row.impact is None:
            continue
        cell.estimated += 1
        cell.approximate += row.impact.match == "approximate"
        cell.tokens += row.output_tokens
        for column in IMPACT_COLUMNS:
            cell.sums[column] += row.impact.values[column]
        bucket_done[bucket].add(row.request_id)
        key_done[key].add(row.request_id)
        done.add(row.request_id)
        if key not in latest or row.at >= latest[key][0]:
            latest[key] = (row.at, row.impact.model, row.impact.match)
    return ImpactAggregate(
        cells=tuple(
            ImpactCell(
                bucket=bucket,
                key=key,
                calls=cell.calls,
                eligible=cell.eligible,
                estimated=cell.estimated,
                approximate=cell.approximate,
                estimated_output_tokens=cell.tokens,
                sums=dict(cell.sums),
            )
            for (bucket, key), cell in sorted(cells.items(), key=lambda item: (item[0][0], item[0][1] or ""))
        ),
        bucket_responses={bucket: (len(ids), len(bucket_done[bucket])) for bucket, ids in bucket_all.items()},
        key_responses={key: (len(ids), len(key_done[key])) for key, ids in key_all.items()},
        key_models={key: (model, match) for key, (_, model, match) in latest.items()},
        responses=(len(every), len(done)),
    )


# --- relatório --------------------------------------------------------------------------------------------------------


def _metrics(sums: Mapping[str, float]) -> ImpactMetrics:
    return ImpactMetrics(
        **{name: ImpactMetric(sums.get(f"{name}_min", 0.0), sums.get(f"{name}_max", 0.0)) for name in IMPACT_METRICS}
    )


def _coverage(cell: _Cell) -> ImpactCoverage:
    return ImpactCoverage(
        calls=cell.calls, eligible=cell.eligible, estimated=cell.estimated, approximate=cell.approximate
    )


def _sorted(rows: Iterable[ImpactRow]) -> tuple[ImpactRow, ...]:
    return tuple(sorted(rows, key=lambda row: (-row.metrics.gwp_kgco2eq.mean, row.key or "")))


def _totals(aggregate: ImpactAggregate, tree_kg_co2e: float) -> ImpactTotals:
    total = _Cell()
    for cell in aggregate.cells:
        total.add(cell)
    metrics = _metrics(total.sums)
    return ImpactTotals(
        metrics=metrics,
        coverage=_coverage(total),
        responses=aggregate.responses[0],
        estimated_responses=aggregate.responses[1],
        estimated_output_tokens=total.tokens,
        trees=metrics.gwp_kgco2eq.mean / tree_kg_co2e,
    )


def build_impact_report(
    query: ImpactQuery,
    aggregate: ImpactAggregate,
    previous: ImpactAggregate | None,
    *,
    version: str | None,
    tree_kg_co2e: float,
    clipped_start: date | None = None,
) -> ImpactReport:
    by_bucket: dict[date, list[ImpactCell]] = defaultdict(list)
    by_key: dict[str | None, _Cell] = defaultdict(_Cell)
    for cell in aggregate.cells:
        by_bucket[cell.bucket].append(cell)
        by_key[cell.key].add(cell)
    report_buckets: list[ImpactBucket] = []
    for start, end in buckets(query.start, query.end, query.grain):
        anchor = bucket_start(start, query.grain)
        total = _Cell()
        rows: list[ImpactRow] = []
        for cell in by_bucket.get(anchor, ()):
            total.add(cell)
            own = _Cell()
            own.add(cell)
            rows.append(ImpactRow(key=cell.key, calls=cell.calls, coverage=_coverage(own), metrics=_metrics(cell.sums)))
        responses = aggregate.bucket_responses.get(anchor, (0, 0))
        report_buckets.append(
            ImpactBucket(
                start=start,
                end=end,
                calls=total.calls,
                responses=responses[0],
                estimated_responses=responses[1],
                metrics=_metrics(total.sums),
                rows=_sorted(rows),
            )
        )
    period_rows = []
    for key, summed in by_key.items():
        model = aggregate.key_models.get(key)
        responses = aggregate.key_responses.get(key, (0, 0))
        period_rows.append(
            ImpactRow(
                key=key,
                impact_model=model[0] if model else None,
                match=cast("ImpactMatch", model[1]) if model else None,
                calls=summed.calls,
                responses=responses[0],
                estimated_responses=responses[1],
                estimated_output_tokens=summed.tokens,
                coverage=_coverage(summed),
                metrics=_metrics(summed.sums),
            )
        )
    return ImpactReport(
        query=query,
        enabled=True,
        version=version,
        tree_kg_co2e=tree_kg_co2e,
        buckets=tuple(report_buckets),
        rows=_sorted(period_rows),
        totals=_totals(aggregate, tree_kg_co2e),
        previous=None if previous is None else _totals(previous, tree_kg_co2e),
        clipped_start=clipped_start,
    )

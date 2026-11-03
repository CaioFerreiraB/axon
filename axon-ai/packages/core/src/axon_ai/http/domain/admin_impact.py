"""Formato do impacto ambiental na administração (contracts/admin-api.md, "Impacto ambiental"; 009 US9; research R64,
R65). Puro. Números como texto decimal, sem expoente: a console não perde precisão nem mostra `3.2e-5`."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from axon_ai.http.domain.admin_common import AdminInvalid, day, only
from axon_ai.http.domain.admin_usage import DEFAULT_DAYS, today
from axon_ai.observability.api import (
    DEFAULT_TREE_KG_CO2E,
    TREE_YEARS,
    ImpactBucket,
    ImpactCoverage,
    ImpactMetrics,
    ImpactQuery,
    ImpactReport,
    ImpactRow,
    ImpactTotals,
    InvalidQuery,
)

_PARAMS = ("from", "to", "tz", "grain", "by", "origin")


def impact_query(params: Mapping[str, str], *, now: datetime, default_tz: str) -> ImpactQuery:
    """Padrões: fuso da instalação, por dia, por modelo, produção, os últimos 30 dias no fuso."""
    only(params, _PARAMS)
    tz = params.get("tz") or default_tz
    end = day(params["to"], "to") if "to" in params else today(now, tz)
    start = day(params["from"], "from") if "from" in params else end - timedelta(days=DEFAULT_DAYS - 1)
    try:
        return ImpactQuery(
            start=start,
            end=end,
            tz=tz,
            grain=params.get("grain", "day"),  # type: ignore[arg-type]
            by=params.get("by", "model"),  # type: ignore[arg-type]
            origin=params.get("origin", "production"),  # type: ignore[arg-type]
        )
    except InvalidQuery as error:
        field = {"start": "from", "end": "to"}.get(error.field, error.field)
        raise AdminInvalid(str(error), field=field) from None


def decimal_number(value: float) -> str:
    """6 algarismos significativos, sem expoente (research R65)."""
    text = format(Decimal(f"{value:.6g}"), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _metrics(metrics: ImpactMetrics) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in dataclasses.fields(metrics):
        metric = getattr(metrics, item.name)
        out[item.name] = {
            "min": decimal_number(metric.min),
            "max": decimal_number(metric.max),
            "mean": decimal_number(metric.mean),
        }
    return out


def _coverage(coverage: ImpactCoverage) -> dict[str, int]:
    return {
        "calls": coverage.calls,
        "eligible": coverage.eligible,
        "estimated": coverage.estimated,
        "approximate": coverage.approximate,
        "unestimated": coverage.unestimated,
    }


def _row(row: ImpactRow) -> dict[str, Any]:
    return {
        "key": row.key,
        "impact_model": row.impact_model,
        "match": row.match,
        "calls": row.calls,
        "responses": row.responses,
        "estimated_responses": row.estimated_responses,
        "estimated_output_tokens": row.estimated_output_tokens,
        "coverage": _coverage(row.coverage),
        "metrics": _metrics(row.metrics),
    }


def _bucket(bucket: ImpactBucket) -> dict[str, Any]:
    return {
        "start": bucket.start.isoformat(),
        "end": bucket.end.isoformat(),
        "calls": bucket.calls,
        "responses": bucket.responses,
        "estimated_responses": bucket.estimated_responses,
        "metrics": _metrics(bucket.metrics),
        "rows": [_row(row) for row in bucket.rows],
    }


def _totals(totals: ImpactTotals | None) -> dict[str, Any] | None:
    if totals is None:
        return None
    return {
        "metrics": _metrics(totals.metrics),
        "coverage": _coverage(totals.coverage),
        "responses": totals.responses,
        "estimated_responses": totals.estimated_responses,
        "estimated_output_tokens": totals.estimated_output_tokens,
        "trees": decimal_number(totals.trees),
    }


def _query(query: ImpactQuery) -> dict[str, str]:
    return {
        "from": query.start.isoformat(),
        "to": query.end.isoformat(),
        "tz": query.tz,
        "grain": query.grain,
        "by": query.by,
        "origin": query.origin,
    }


def impact_json(report: ImpactReport) -> dict[str, Any]:
    if not report.enabled:
        return disabled_json(report.query, tree_kg_co2e=report.tree_kg_co2e)
    return {
        "enabled": True,
        "query": _query(report.query),
        "method": {
            "ecologits_version": report.version,
            "tree_kg_co2e": decimal_number(report.tree_kg_co2e),
            "tree_years": report.tree_years,
        },
        "clipped_from": report.clipped_start.isoformat() if report.clipped_start else None,
        "totals": _totals(report.totals),
        "previous_totals": _totals(report.previous),
        "buckets": [_bucket(bucket) for bucket in report.buckets],
        "rows": [_row(row) for row in report.rows],
    }


def disabled_json(query: ImpactQuery, *, tree_kg_co2e: float = DEFAULT_TREE_KG_CO2E) -> dict[str, Any]:
    """Estimativa desligada pela instalação (009 FR-030): a console explica, em vez de mostrar zero."""
    return {
        "enabled": False,
        "query": _query(query),
        "method": {
            "ecologits_version": None,
            "tree_kg_co2e": decimal_number(tree_kg_co2e),
            "tree_years": TREE_YEARS,
        },
        "clipped_from": None,
        "totals": None,
        "previous_totals": None,
        "buckets": [],
        "rows": [],
    }

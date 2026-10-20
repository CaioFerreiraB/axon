"""Formatos de uso e preços na administração (contracts/admin-api.md; 009 US5). Puro. Dinheiro como string decimal."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ai_core.http.domain.admin_common import AdminInvalid, day, decimal_text, money, only, text
from ai_core.llm.api import ProviderStatus
from ai_core.observability.api import InvalidQuery, Price, UsageQuery, UsageReport, UsageRow

DEFAULT_DAYS = 30
_USAGE_PARAMS = ("from", "to", "tz", "by", "origin")


def _today(now: datetime, tz: str) -> date:
    try:
        return now.astimezone(ZoneInfo(tz)).date()
    except (ZoneInfoNotFoundError, ValueError):
        raise AdminInvalid(f"tz: fuso desconhecido: {tz!r}", field="tz") from None


def usage_query(params: Mapping[str, str], *, now: datetime, default_tz: str) -> UsageQuery:
    """Padrões: fuso da instalação, por modelo, produção, os últimos 30 dias no fuso."""
    only(params, _USAGE_PARAMS)
    tz = params.get("tz") or default_tz
    end = day(params["to"], "to") if "to" in params else _today(now, tz)
    start = day(params["from"], "from") if "from" in params else end - timedelta(days=DEFAULT_DAYS - 1)
    try:
        return UsageQuery(
            start=start,
            end=end,
            tz=tz,
            by=params.get("by", "model"),  # type: ignore[arg-type]
            origin=params.get("origin", "production"),  # type: ignore[arg-type]
        )
    except InvalidQuery as error:
        field = {"start": "from", "end": "to"}.get(error.field, error.field)
        raise AdminInvalid(str(error), field=field) from None


def _row(row: UsageRow) -> dict[str, Any]:
    return {
        "key": row.key,
        "calls": row.calls,
        "requests": row.requests,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "cost": decimal_text(row.cost),
        "priced": row.priced,
    }


def report_json(report: UsageReport) -> dict[str, Any]:
    query = report.query
    return {
        "query": {
            "from": query.start.isoformat(),
            "to": query.end.isoformat(),
            "tz": query.tz,
            "by": query.by,
            "origin": query.origin,
        },
        "currency": "USD",
        "totals": [_row(row) for row in report.totals],
        "total_cost": decimal_text(report.total_cost),
        "requests": report.requests,
        "incomplete": report.incomplete,
        "previous_total_cost": decimal_text(report.previous_total_cost),
        "days": [
            {"day": d.day.isoformat(), "requests": d.requests, "rows": [_row(row) for row in d.rows]}
            for d in report.days
        ],
    }


def price_json(price: Price) -> dict[str, Any]:
    return {
        "provider": price.provider,
        "model": price.model,
        "input": decimal_text(price.usd_per_mtok_in),
        "output": decimal_text(price.usd_per_mtok_out),
        "effective_from": price.effective_from.isoformat(),
        "state": price.state,
        "created_by": price.created_by,
        "created_at": price.created_at.isoformat(),
    }


def price_body(body: Mapping[str, Any]) -> dict[str, Any]:
    only(body, ("provider", "model", "input", "output", "effective_from"))
    return {
        "provider": text(body, "provider"),
        "model": text(body, "model"),
        "usd_per_mtok_in": money(body, "input"),
        "usd_per_mtok_out": money(body, "output"),
        "effective_from": day(body.get("effective_from"), "effective_from"),
    }


def check_price_provider(provider: str, statuses: Sequence[ProviderStatus]) -> None:
    """Provider que informa o custo de cada chamada não tem preço de tabela (ADR-036)."""
    if any(status.name == provider and status.reports_cost for status in statuses):
        raise AdminInvalid(
            f"provider: {provider} informa o custo de cada chamada; preço de tabela não se aplica", field="provider"
        )


def period_params(params: Mapping[str, str], *, now: datetime, default_tz: str) -> tuple[date, date]:
    only(params, ("from", "to"))
    query = usage_query(params, now=now, default_tz=default_tz)
    return query.start, query.end

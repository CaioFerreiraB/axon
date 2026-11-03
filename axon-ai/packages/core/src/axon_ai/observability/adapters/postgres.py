"""Armazenamentos da 009 em Postgres, no schema `observability` (ADR-015; research R30, R31, R33).

A agregação do uso é do banco: dia local por `(at AT TIME ZONE tz)::date`, chave por modelo ou por Assistant, a parte
com custo informado pelo provider (ADR-035), e as requisições distintas por dia, por chave no período e no total — o
mesmo que `domain/usage.aggregate` faz em memória.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any, Final

from psycopg_pool import AsyncConnectionPool

from axon_ai.observability.api import ImpactGrain, Price, UsageGrouping, UsageOrigin
from axon_ai.observability.domain.usage_records import IMPACT_COLUMNS
from axon_ai.observability.ports import (
    DailyRequests,
    DailyTokens,
    DayRequests,
    DestinationSettings,
    ExecutionRow,
    ImpactAggregate,
    ImpactCell,
    ImpactEstimate,
    KeyRequests,
    ModelCallRow,
    UnestimatedCall,
    UsageAggregate,
)

_KEY: Final = {"model": "provider || '/' || model", "assistant": "assistant"}

_DAY: Final = "(at AT TIME ZONE %(tz)s)::date"
_BUCKET: Final = {
    "day": _DAY,
    "week": f"date_trunc('week', {_DAY})::date",
    "month": f"date_trunc('month', {_DAY})::date",
    "quarter": f"date_trunc('quarter', {_DAY})::date",
    "semester": (
        f"make_date(extract(year FROM {_DAY})::int, CASE WHEN extract(month FROM {_DAY}) <= 6 THEN 1 ELSE 7 END, 1)"
    ),
}
"""O balde de cada grão no dia local (research R48): `date_trunc('week')` é a semana ISO, começando na segunda."""

_IMPACT: Final = (
    "impact_model",
    "impact_match",
    "impact_zone",
    "ecologits_version",
    "impact_warnings",
    *IMPACT_COLUMNS,
)
"""As colunas de impacto da linha (migração `005`), na ordem de `_impact_values`."""


def _impact_values(impact: ImpactEstimate | None, tried: bool) -> tuple[Any, ...]:
    """As colunas de impacto de uma linha: `none` quando tentada sem par; tudo nulo quando nunca tentada."""
    if impact is None:
        return (None, "none" if tried else None, *([None] * (len(_IMPACT) - 2)))
    return (
        impact.model,
        impact.match,
        impact.zone,
        impact.version,
        list(impact.warnings),
        *(impact.values[column] for column in IMPACT_COLUMNS),
    )


class PostgresUsageStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def append(self, calls: Sequence[ModelCallRow], executions: Sequence[ExecutionRow]) -> None:
        async with self._pool.connection() as connection, connection.transaction(), connection.cursor() as cursor:
            if calls:
                await cursor.executemany(
                    "INSERT INTO observability.model_calls (request_id, at, origin, assistant, provider, model, role, "
                    "input_tokens, output_tokens, duration_ms, failed, reported_cost_usd, "
                    f"{', '.join(_IMPACT)}) VALUES ({', '.join(['%s'] * (12 + len(_IMPACT)))})",
                    [
                        (
                            row.request_id,
                            row.at,
                            row.origin,
                            row.assistant,
                            row.provider,
                            row.model,
                            row.role,
                            row.input_tokens,
                            row.output_tokens,
                            row.duration_ms,
                            row.failed,
                            row.reported_cost,
                            *_impact_values(row.impact, row.impact_tried),
                        )
                        for row in calls
                    ],
                )
            if executions:
                await cursor.executemany(
                    "INSERT INTO observability.executions (request_id, started_at, finished_at, origin, assistant, "
                    "flow, ok, duration_ms) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (request_id) DO UPDATE SET "
                    "finished_at = COALESCE(EXCLUDED.finished_at, observability.executions.finished_at), "
                    "ok = COALESCE(EXCLUDED.ok, observability.executions.ok), "
                    "duration_ms = COALESCE(EXCLUDED.duration_ms, observability.executions.duration_ms)",
                    [
                        (
                            row.request_id,
                            row.started_at,
                            row.finished_at,
                            row.origin,
                            row.assistant,
                            row.flow,
                            row.ok,
                            row.duration_ms,
                        )
                        for row in executions
                    ],
                )

    async def daily(
        self, *, start: datetime, end: datetime, tz: str, by: UsageGrouping, origin: UsageOrigin
    ) -> UsageAggregate:
        key = _KEY[by]
        where = "at >= %(start)s AND at < %(end)s" + ("" if origin == "all" else " AND origin = %(origin)s")
        params: dict[str, Any] = {"start": start, "end": end, "tz": tz, "origin": origin}
        day = "(at AT TIME ZONE %(tz)s)::date"
        reported = "FILTER (WHERE reported_cost_usd IS NOT NULL)"
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {day}, {key}, provider, model, count(*), COALESCE(sum(input_tokens), 0), "
                f"COALESCE(sum(output_tokens), 0), count(reported_cost_usd), "
                f"COALESCE(sum(input_tokens) {reported}, 0), COALESCE(sum(output_tokens) {reported}, 0), "
                f"COALESCE(sum(reported_cost_usd), 0) FROM observability.model_calls WHERE {where} "
                "GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 4",
                params,
            )
            tokens = [
                DailyTokens(
                    day=row[0],
                    key=row[1],
                    provider=row[2],
                    model=row[3],
                    calls=int(row[4]),
                    input_tokens=int(row[5]),
                    output_tokens=int(row[6]),
                    reported_calls=int(row[7]),
                    reported_input_tokens=int(row[8]),
                    reported_output_tokens=int(row[9]),
                    reported_cost=Decimal(row[10]),
                )
                for row in await cursor.fetchall()
            ]
            cursor = await connection.execute(
                f"SELECT {day}, {key}, count(DISTINCT request_id) FROM observability.model_calls WHERE {where} "
                "GROUP BY 1, 2 ORDER BY 1, 2",
                params,
            )
            requests = [DailyRequests(day=row[0], key=row[1], requests=int(row[2])) for row in await cursor.fetchall()]
            cursor = await connection.execute(
                f"SELECT {key}, count(DISTINCT request_id) FROM observability.model_calls WHERE {where} GROUP BY 1",
                params,
            )
            per_key = [KeyRequests(key=row[0], requests=int(row[1])) for row in await cursor.fetchall()]
            cursor = await connection.execute(
                f"SELECT {day}, count(DISTINCT request_id) FROM observability.model_calls WHERE {where} "
                "GROUP BY 1 ORDER BY 1",
                params,
            )
            per_day = [DayRequests(day=row[0], requests=int(row[1])) for row in await cursor.fetchall()]
            cursor = await connection.execute(
                f"SELECT count(DISTINCT request_id) FROM observability.model_calls WHERE {where}", params
            )
            total = await cursor.fetchone()
        return UsageAggregate(
            tokens=tuple(tokens),
            requests=tuple(requests),
            key_requests=tuple(sorted(per_key, key=lambda item: item.key or "")),
            day_requests=tuple(per_day),
            total_requests=int(total[0]) if total else 0,
        )

    async def impact(
        self, *, start: datetime, end: datetime, tz: str, grain: ImpactGrain, by: UsageGrouping, origin: UsageOrigin
    ) -> ImpactAggregate:
        """Mesma regra de `domain/impact.aggregate_impact` (research R49), no banco."""
        key = _KEY[by]
        bucket = _BUCKET[grain]
        where = "at >= %(start)s AND at < %(end)s" + ("" if origin == "all" else " AND origin = %(origin)s")
        params: dict[str, Any] = {"start": start, "end": end, "tz": tz, "origin": origin}
        done = "FILTER (WHERE impact_model IS NOT NULL)"
        sums = ", ".join(f"COALESCE(sum({column}) {done}, 0)" for column in IMPACT_COLUMNS)
        base = f"FROM observability.model_calls WHERE {where}"
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT {bucket}, {key}, count(*), count(*) FILTER (WHERE NOT failed AND output_tokens > 0), "
                f"count(*) {done}, count(*) FILTER (WHERE impact_match = 'approximate'), "
                f"COALESCE(sum(output_tokens) {done}, 0), {sums} {base} GROUP BY 1, 2 ORDER BY 1, 2",
                params,
            )
            cells = [
                ImpactCell(
                    bucket=row[0],
                    key=row[1],
                    calls=int(row[2]),
                    eligible=int(row[3]),
                    estimated=int(row[4]),
                    approximate=int(row[5]),
                    estimated_output_tokens=int(row[6]),
                    sums=dict(zip(IMPACT_COLUMNS, (float(value) for value in row[7:]), strict=True)),
                )
                for row in await cursor.fetchall()
            ]

            # Respostas distintas: primeiro uma linha por requisição (agregação por hash), depois a contagem — o
            # `count(DISTINCT …)` ordena, e era a maior parte do tempo do relatório (SC-011).
            def distinct(group: str) -> str:
                outer = "r.g, " if group else ""
                inner = f"{group} AS g, " if group else ""
                return (
                    f"SELECT {outer}count(*), count(*) FILTER (WHERE r.d) FROM (SELECT {inner}request_id, "
                    f"bool_or(impact_model IS NOT NULL) AS d {base} GROUP BY {'1, 2' if group else '1'}) AS r"
                    + (" GROUP BY 1" if group else "")
                )

            cursor = await connection.execute(distinct(bucket), params)
            per_bucket = {row[0]: (int(row[1]), int(row[2])) for row in await cursor.fetchall()}
            cursor = await connection.execute(distinct(key), params)
            per_key = {row[0]: (int(row[1]), int(row[2])) for row in await cursor.fetchall()}
            cursor = await connection.execute(
                f"SELECT DISTINCT ON ({key}) {key}, impact_model, impact_match {base} AND impact_model IS NOT NULL "
                f"ORDER BY {key}, at DESC, id DESC",
                params,
            )
            models = {row[0]: (row[1], row[2]) for row in await cursor.fetchall()}
            cursor = await connection.execute(distinct(""), params)
            total = await cursor.fetchone()
        return ImpactAggregate(
            cells=tuple(sorted(cells, key=lambda cell: (cell.bucket, cell.key or ""))),
            bucket_responses=per_bucket,
            key_responses=per_key,
            key_models=models,
            responses=(int(total[0]), int(total[1])) if total else (0, 0),
        )

    async def unestimated(self, limit: int, *, after: int = -1) -> tuple[UnestimatedCall, ...]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT id, provider, model, output_tokens, duration_ms FROM observability.model_calls "
                "WHERE impact_match IS NULL AND NOT failed AND output_tokens > 0 AND id > %s ORDER BY id LIMIT %s",
                (after, limit),
            )
            return tuple(
                UnestimatedCall(
                    id=int(row[0]),
                    provider=row[1],
                    model=row[2],
                    output_tokens=int(row[3]),
                    duration_ms=float(row[4]),
                )
                for row in await cursor.fetchall()
            )

    async def set_impacts(self, items: Sequence[tuple[int, ImpactEstimate | None]]) -> None:
        if not items:
            return
        assignments = ", ".join(f"{column} = %s" for column in _IMPACT)
        async with self._pool.connection() as connection, connection.transaction(), connection.cursor() as cursor:
            await cursor.executemany(
                f"UPDATE observability.model_calls SET {assignments} WHERE id = %s AND impact_match IS NULL",
                [(*_impact_values(estimate, True), call_id) for call_id, estimate in items],
            )

    async def purge(self, *, before: datetime) -> int:
        async with self._pool.connection() as connection, connection.transaction():
            calls = await connection.execute("DELETE FROM observability.model_calls WHERE at < %s", (before,))
            executions = await connection.execute(
                "DELETE FROM observability.executions WHERE started_at < %s", (before,)
            )
            return max(calls.rowcount, 0) + max(executions.rowcount, 0)


class PostgresPriceStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def all(self) -> Sequence[Price]:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT provider, model, usd_per_mtok_in, usd_per_mtok_out, effective_from, created_by, created_at "
                "FROM observability.prices ORDER BY provider, model, effective_from"
            )
            rows = await cursor.fetchall()
        return [
            Price(
                provider=row[0],
                model=row[1],
                usd_per_mtok_in=row[2],
                usd_per_mtok_out=row[3],
                effective_from=row[4],
                created_by=row[5],
                created_at=row[6],
            )
            for row in rows
        ]

    async def add(self, price: Price) -> Price:
        async with self._pool.connection() as connection:
            await connection.execute(
                "INSERT INTO observability.prices (provider, model, effective_from, usd_per_mtok_in, usd_per_mtok_out, "
                "created_by, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (provider, model, "
                "effective_from) DO UPDATE SET usd_per_mtok_in = EXCLUDED.usd_per_mtok_in, "
                "usd_per_mtok_out = EXCLUDED.usd_per_mtok_out, created_by = EXCLUDED.created_by, "
                "created_at = EXCLUDED.created_at",
                (
                    price.provider,
                    price.model,
                    price.effective_from,
                    price.usd_per_mtok_in,
                    price.usd_per_mtok_out,
                    price.created_by,
                    price.created_at,
                ),
            )
        return price


class PostgresDestinationSettingsStore:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def get(self) -> DestinationSettings:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                "SELECT langfuse_enabled, langfuse_host, langfuse_public_key, langfuse_secret_sealed, capture_content, "
                "version, updated_by, updated_at FROM observability.destination_settings WHERE id = 1"
            )
            row = await cursor.fetchone()
        if row is None:
            return DestinationSettings()
        return DestinationSettings(
            langfuse_enabled=row[0],
            langfuse_host=row[1],
            langfuse_public_key=row[2],
            langfuse_secret_sealed=bytes(row[3]) if row[3] is not None else None,
            capture_content=row[4],
            version=row[5],
            updated_by=row[6],
            updated_at=row[7],
        )

    async def put(self, settings: DestinationSettings, *, expected_version: int) -> bool:
        values = (
            settings.langfuse_enabled,
            settings.langfuse_host,
            settings.langfuse_public_key,
            settings.langfuse_secret_sealed,
            settings.capture_content,
            settings.version,
            settings.updated_by,
            settings.updated_at,
        )
        async with self._pool.connection() as connection:
            if expected_version == 0:
                cursor = await connection.execute(
                    "INSERT INTO observability.destination_settings (id, langfuse_enabled, langfuse_host, "
                    "langfuse_public_key, langfuse_secret_sealed, capture_content, version, updated_by, updated_at) "
                    "VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                    values,
                )
            else:
                cursor = await connection.execute(
                    "UPDATE observability.destination_settings SET langfuse_enabled = %s, langfuse_host = %s, "
                    "langfuse_public_key = %s, langfuse_secret_sealed = %s, capture_content = %s, version = %s, "
                    "updated_by = %s, updated_at = %s WHERE id = 1 AND version = %s",
                    (*values, expected_version),
                )
        return cursor.rowcount == 1

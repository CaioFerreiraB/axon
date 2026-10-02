"""O comando `ai-core audit` da 004 (contracts/audit.md; FR-015; clarificação 5).

Função que recebe a consulta já montada e as saídas, e devolve o código de saída. Quem a registra na raiz `ai-core` é a
composition root (011): o framework de linha de comando é decisão dela, por isso não há parser aqui.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Final, TextIO

from ai_core.capabilities.api import AuditFilter, AuditQuery, AuditRecord

EXIT_OK: Final = 0
EXIT_INVALID_FILTER: Final = 2


async def audit_command(
    query: AuditQuery,
    *,
    principal: str | None = None,
    assistant: str | None = None,
    tool: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 100,
    results: bool = False,
    out: TextIO,
    err: TextIO,
) -> int:
    """Uma linha por registro, do mais recente: início, status, Principal, Assistant, tool e argumentos em JSON."""
    try:
        filter = AuditFilter(
            principal=principal,
            assistant=assistant,
            tool=tool,
            since=_moment("since", since),
            until=_moment("until", until),
            limit=limit,
        )
    except ValueError as error:
        print(f"filtro inválido: {error}", file=err)
        return EXIT_INVALID_FILTER
    for record in await query.records(filter):
        print(_line(record), file=out)
        if results and record.result is not None:
            print(f"  resultado: {record.result}", file=out)
    return EXIT_OK


def _moment(name: str, value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        moment = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{name} precisa ser uma data ISO 8601 com fuso: {value!r}") from None
    if moment.tzinfo is None:
        raise ValueError(f"{name} precisa de fuso: {value!r}")
    return moment


def _line(record: AuditRecord) -> str:
    arguments = json.dumps(dict(record.arguments), ensure_ascii=False, sort_keys=True, default=str)
    fields = [record.started_at.isoformat(), record.status, record.principal, record.assistant, record.tool, arguments]
    return "  ".join(fields)

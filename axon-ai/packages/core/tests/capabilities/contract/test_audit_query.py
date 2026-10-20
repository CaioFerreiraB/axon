"""T029 — o comando de auditoria, por função (contracts/audit.md; FR-015; US4 cen. 3)."""

from __future__ import annotations

import io
import json
from datetime import timedelta

import pytest
from capabilities_testkit import T0

from axon_ai.capabilities.adapters.cli import audit_command
from axon_ai.capabilities.adapters.memory import InMemoryAuditLog
from axon_ai.capabilities.api import AuditEntry

pytestmark = pytest.mark.us4


class Query:
    def __init__(self, log: InMemoryAuditLog) -> None:
        self._log = log

    async def records(self, filter):  # type: ignore[no-untyped-def]
        return await self._log.query(filter)


async def preparado() -> Query:
    log = InMemoryAuditLog()
    for n, (principal, tool) in enumerate([("user:ana", "alfa.pagar"), ("user:bia", "fin.transferir")]):
        record_id = await log.begin(
            AuditEntry(
                request_id=f"req-{n}",
                principal=principal,
                assistant="geral",
                tool=tool,
                kind="native",
                arguments={"valor": n, "nota": "ç"},
                started_at=T0 + timedelta(minutes=n),
            )
        )
        await log.finish(record_id, status="ok", result=f"resultado {n}", at=T0 + timedelta(minutes=n, seconds=1))
    return Query(log)


async def run(query: Query, **kwargs: object) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = await audit_command(query, out=out, err=err, **kwargs)  # type: ignore[arg-type]
    return code, out.getvalue(), err.getvalue()


async def test_uma_linha_por_registro_do_mais_recente() -> None:
    code, out, _ = await run(await preparado())
    linhas = out.strip().splitlines()
    assert code == 0 and len(linhas) == 2
    assert linhas[0].startswith((T0 + timedelta(minutes=1)).isoformat())
    assert "user:bia" in linhas[0] and "fin.transferir" in linhas[0] and " ok " in f" {linhas[0]} "
    assert json.loads(linhas[1].split("  ")[-1]) == {"nota": "ç", "valor": 0}
    assert "resultado" not in out, "o resultado só com --results"


async def test_filtros() -> None:
    query = await preparado()
    _, out, _ = await run(query, principal="user:ana")
    assert len(out.strip().splitlines()) == 1 and "alfa.pagar" in out
    _, out, _ = await run(query, tool="fin.transferir")
    assert len(out.strip().splitlines()) == 1 and "user:bia" in out
    _, out, _ = await run(query, since=(T0 + timedelta(seconds=30)).isoformat())
    assert len(out.strip().splitlines()) == 1


async def test_results_inclui_o_resultado() -> None:
    _, out, _ = await run(await preparado(), results=True)
    assert "resultado 1" in out and "resultado 0" in out


@pytest.mark.parametrize(
    ("kwargs", "trecho"), [({"since": "ontem"}, "since"), ({"limit": 0}, "limit"), ({"until": "2026-13-01"}, "until")]
)
async def test_filtro_invalido_sai_com_2(kwargs: dict[str, object], trecho: str) -> None:
    code, _, err = await run(await preparado(), **kwargs)
    assert code == 2 and trecho in err

"""O evento `tool_call` (toque declarado pela 004, research R9): tipo, campos e nada de argumento nem conteúdo."""

from __future__ import annotations

import pytest
from trace_testkit import AT

from axon_ai.observability.api import ToolCall
from axon_ai.observability.domain.records import record_type, to_record


def test_tool_call_vira_registro_tool_call_sem_argumentos_nem_conteudo() -> None:
    event = ToolCall(
        request_id="req-1",
        tool="financeiro.saldo",
        kind="mcp",
        status="ok",
        duration_ms=12.5,
        size_bytes=340,
        truncated=False,
    )
    record = to_record(event, AT)
    assert record_type(event) == "tool_call"
    assert dict(record.attributes) == {
        "tool": "financeiro.saldo",
        "kind": "mcp",
        "status": "ok",
        "duration_ms": 12.5,
        "size_bytes": 340,
        "truncated": False,
        "attachments": [],
    }


def test_tool_inexistente_sai_sem_kind() -> None:
    """Campo `None` não vai ao registro (contracts/record-format.md da 009)."""
    event = ToolCall(request_id="req-1", tool="x.y", kind=None, status="unknown", duration_ms=0.1, size_bytes=30)
    assert "kind" not in to_record(event, AT).attributes


@pytest.mark.parametrize(("field", "value"), [("duration_ms", -1.0), ("size_bytes", -1), ("tool", " ")])
def test_campos_invalidos_sao_recusados(field: str, value: object) -> None:
    base: dict[str, object] = {
        "request_id": "req-1",
        "tool": "a.b",
        "kind": "native",
        "status": "ok",
        "duration_ms": 1.0,
        "size_bytes": 1,
    }
    with pytest.raises(ValueError):
        ToolCall(**(base | {field: value}))  # type: ignore[arg-type]

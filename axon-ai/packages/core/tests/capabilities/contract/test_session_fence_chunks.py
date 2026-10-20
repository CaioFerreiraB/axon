"""005 T061 — `ToolSession.fence_chunks` (ADR-026, decisão 2; 005 research R41).

O motor entrega à geração do `rag_first` trechos que já recuperou pelo gateway, no mesmo formato e na mesma cerca de um
resultado de recuperação — sem executar retriever de novo, sem `ToolCall` no trace e sem auditoria.
"""

from __future__ import annotations

import pytest
from capabilities_testkit import Calls, build, chunk, context, grant, native, retrieval

from axon_ai.capabilities.api import AuditFilter, GatewayLimits
from axon_ai.capabilities.domain.fencing import fence
from axon_ai.capabilities.domain.rendering import render_chunks
from axon_ai.observability.api import ToolCall as ToolCallEvent

pytestmark = pytest.mark.us3


async def _session(*, limits: GatewayLimits | None = None):  # type: ignore[no-untyped-def]
    calls = Calls()
    kit = build(tools=[retrieval("alfa", "buscar", calls), native("alfa", "ecoar", calls)], calls=calls, limits=limits)
    session = await kit.service.open(grant(packs=["alfa"], collections=["docs"]), context())
    return kit, session


async def test_cerca_os_trechos_como_um_resultado_de_recuperacao() -> None:
    kit, session = await _session()
    trechos = (chunk(3), chunk(1))
    resultado = session.fence_chunks("alfa.buscar", trechos)

    assert resultado.name == "alfa.buscar" and resultado.kind == "retrieval" and resultado.status == "ok"
    assert resultado.chunks == trechos and not resultado.truncated and resultado.error is None
    assert resultado.text == fence("alfa.buscar", status="ok", content=render_chunks(trechos), truncated=False)
    assert "· id: c3]" in resultado.text and "· id: c1]" in resultado.text
    assert kit.calls.retrieval == [], "não executa retriever"
    assert kit.trace.of_type(ToolCallEvent) == [], "os trechos já passaram pelo gateway na recuperação"
    assert await kit.audit.query(AuditFilter()) == []


async def test_sem_trechos() -> None:
    _kit, session = await _session()
    resultado = session.fence_chunks("alfa.buscar", ())
    assert resultado.chunks == () and "nenhum resultado" in resultado.text


async def test_corta_por_trecho_inteiro_no_limite_do_gateway() -> None:
    _kit, session = await _session(limits=GatewayLimits(max_response_bytes=1024))
    trechos = tuple(chunk(n, text="w" * 400) for n in range(1, 6))
    resultado = session.fence_chunks("alfa.buscar", trechos)

    assert resultado.truncated and 'truncated="true"' in resultado.text
    assert resultado.chunks == trechos[: len(resultado.chunks)] and 0 < len(resultado.chunks) < 5
    for trecho in trechos:
        assert (f"id: {trecho.chunk_id}]" in resultado.text) == (trecho in resultado.chunks)


@pytest.mark.parametrize("name", ["alfa.inexistente", "alfa.ecoar", ""])
async def test_so_aceita_tool_de_recuperacao_do_catalogo(name: str) -> None:
    _kit, session = await _session()
    with pytest.raises(ValueError, match="recuperação"):
        session.fence_chunks(name, (chunk(1),))

"""T018 — o despacho da sessão (contracts/capabilities-api.md, "Execução"; US2; FR-006 a FR-008, FR-014)."""

from __future__ import annotations

import pytest
from capabilities_testkit import (
    EMPTY_SCHEMA,
    REFERENCE,
    Calls,
    FakeClock,
    FakeServer,
    build,
    chunk,
    context,
    grant,
    mcp_tool,
    native,
    retrieval,
)

from ai_core.capabilities.api import GatewayLimits, ToolCall
from ai_core.observability.api import ToolCall as ToolCallEvent
from axon_ai_contracts import ToolResult

pytestmark = pytest.mark.us2


async def open_with(*tools: object, servers: dict[str, FakeServer] | None = None, **build_kwargs: object):  # type: ignore[no-untyped-def]
    calls: Calls = build_kwargs.pop("calls", None) or Calls()  # type: ignore[assignment]
    built = [tool(calls) if callable(tool) else tool for tool in tools]
    kit = build(tools=built, servers=servers, calls=calls, **build_kwargs)  # type: ignore[arg-type]
    packs = sorted({tool.pack for tool in built})
    session = await kit.service.open(
        grant(packs=packs, mcp=list(servers or {}), collections=["docs"]),
        context(retrieval_filters={"alfa": {"ano": 2026}, "beta": {"ano": 1999}}),
    )
    return kit, session


async def test_nativa_recebe_tool_invocation_com_o_contexto() -> None:
    kit, session = await open_with(lambda c: native("alfa", "ecoar", c))
    resultado = await session.execute(ToolCall(name="alfa.ecoar", arguments={"texto": "oi"}))

    assert resultado.status == "ok" and resultado.kind == "native" and resultado.error is None
    assert resultado.text == '<tool_result name="alfa.ecoar" status="ok" truncated="false">\noi\n</tool_result>'
    ((name, invocation),) = kit.calls.native
    assert name == "alfa.ecoar" and dict(invocation.arguments) == {"texto": "oi"}
    assert invocation.request_id == "req-1" and invocation.reference_time == REFERENCE


async def test_recuperacao_recebe_os_filtros_da_fatia_do_proprio_pack() -> None:
    kit, session = await open_with(lambda c: retrieval("alfa", "buscar", c, chunks=(chunk(1), chunk(2), chunk(3))))
    resultado = await session.execute(ToolCall(name="alfa.buscar", arguments={"query": "férias", "top_k": 2}))

    assert resultado.status == "ok" and resultado.kind == "retrieval"
    assert [c.chunk_id for c in resultado.chunks] == ["c1", "c2"]
    assert "[doc-1 — Seção 1, p. 3 · id: c1]" in resultado.text
    ((name, query, top_k, filters),) = kit.calls.retrieval
    assert (name, query, top_k) == ("alfa.buscar", "férias", 2)
    assert dict(filters or {}) == {"ano": 2026}, "nunca os filtros de outro pack, nunca do modelo"


async def test_recuperacao_sem_top_k_usa_o_default_do_retriever() -> None:
    kit, session = await open_with(lambda c: retrieval("alfa", "buscar", c))
    await session.execute(ToolCall(name="alfa.buscar", arguments={"query": "x"}))
    assert kit.calls.retrieval[0][2] == 20


async def test_mcp_recebe_alias_e_nome_local() -> None:
    servers = {"fin": FakeServer(tools=[mcp_tool("saldo")], results={"saldo": ToolResult(content="R$ 10")})}
    kit, session = await open_with(servers=servers)
    resultado = await session.execute(ToolCall(name="fin.saldo", arguments={"texto": "conta"}))

    assert resultado.status == "ok" and resultado.kind == "mcp" and "R$ 10" in resultado.text
    assert kit.calls.mcp == [("fin", "saldo", {"texto": "conta"})]


async def test_mcp_com_erro_do_servidor() -> None:
    erro = ToolResult(content="conta inexistente", error="conta inexistente")
    servers = {"fin": FakeServer(tools=[mcp_tool("saldo")], results={"saldo": erro})}
    _kit, session = await open_with(servers=servers)
    resultado = await session.execute(ToolCall(name="fin.saldo", arguments={"texto": "x"}))
    assert resultado.status == "error" and resultado.error == "conta inexistente"
    assert "conta inexistente" in resultado.text


async def test_argumentos_invalidos_nao_despacham() -> None:
    """US2 cen. 3."""
    kit, session = await open_with(lambda c: native("alfa", "ecoar", c))
    resultado = await session.execute(ToolCall(name="alfa.ecoar", arguments={"texto": 3}))
    assert resultado.status == "invalid_arguments" and "texto" in (resultado.error or "")
    assert kit.calls.total == 0


async def test_prazo_vencido_e_timeout_e_a_sessao_continua() -> None:
    """US2 cen. 1."""
    _kit, session = await open_with(
        lambda c: native("alfa", "lento", c, delay=5.0),
        lambda c: native("alfa", "ecoar", c),
        limits=GatewayLimits(timeout_ms=1000),
    )
    lento = await session.execute(ToolCall(name="alfa.lento", arguments={"texto": "x"}))
    assert lento.status == "timeout" and lento.error == "sem resposta em 1 s"
    seguinte = await session.execute(ToolCall(name="alfa.ecoar", arguments={"texto": "ok"}))
    assert seguinte.status == "ok"


async def test_resposta_acima_do_limite_e_cortada_com_marca() -> None:
    """US2 cen. 2, SC-003."""
    _kit, session = await open_with(
        lambda c: native("alfa", "grande", c, result="z" * 5000), limits=GatewayLimits(max_response_bytes=1024)
    )
    resultado = await session.execute(ToolCall(name="alfa.grande", arguments={"texto": "x"}))
    assert resultado.truncated and resultado.status == "ok"
    assert "[… resposta cortada:" in resultado.text and 'truncated="true"' in resultado.text
    corpo = resultado.text.split("\n", 1)[1].rsplit("\n", 1)[0]
    assert len(corpo.encode("utf-8")) <= 1024


async def test_recuperacao_acima_do_limite_corta_por_trecho_inteiro() -> None:
    """005 US4 cen. 2 (T061): os `chunks` do resultado são só os que aparecem no texto que o modelo recebe."""
    trechos = tuple(chunk(n, text="w" * 400) for n in range(1, 6))
    _kit, session = await open_with(
        lambda c: retrieval("alfa", "buscar", c, chunks=trechos), limits=GatewayLimits(max_response_bytes=1024)
    )
    resultado = await session.execute(ToolCall(name="alfa.buscar", arguments={"query": "x"}))

    assert resultado.status == "ok" and resultado.truncated and 'truncated="true"' in resultado.text
    assert 0 < len(resultado.chunks) < len(trechos)
    for trecho in trechos:
        assert (f"id: {trecho.chunk_id}]" in resultado.text) == (trecho in resultado.chunks)
    assert "trecho(s) omitido(s)" in resultado.text


async def test_mcp_cortado_pelo_servidor_continua_marcado_e_o_gateway_corta_de_novo() -> None:
    """Em MCP vale o menor limite: o do servidor já veio aplicado (007); o do gateway corta se for menor."""
    ja_cortado = ToolResult(content="y" * 3000, truncated=True)
    servers = {"fin": FakeServer(tools=[mcp_tool("saldo")], results={"saldo": ja_cortado})}
    _kit, session = await open_with(servers=servers, limits=GatewayLimits(max_response_bytes=1024))
    resultado = await session.execute(ToolCall(name="fin.saldo", arguments={"texto": "x"}))
    assert resultado.truncated
    corpo = resultado.text.split("\n", 1)[1].rsplit("\n", 1)[0]
    assert len(corpo.encode("utf-8")) <= 1024


async def test_mcp_lento_respeita_o_prazo_do_gateway() -> None:
    servers = {"fin": FakeServer(tools=[mcp_tool("saldo")], delay=5.0)}
    _kit, session = await open_with(servers=servers, limits=GatewayLimits(timeout_ms=1000))
    resultado = await session.execute(ToolCall(name="fin.saldo", arguments={"texto": "x"}))
    assert resultado.status == "timeout"


async def test_handler_que_levanta_vira_erro_e_a_sessao_continua() -> None:
    _kit, session = await open_with(
        lambda c: native("alfa", "quebra", c, error=RuntimeError("deu ruim\ndetalhe interno")),
        lambda c: native("alfa", "ecoar", c),
    )
    resultado = await session.execute(ToolCall(name="alfa.quebra", arguments={"texto": "x"}))
    assert resultado.status == "error" and resultado.error == "RuntimeError: deu ruim"
    assert (await session.execute(ToolCall(name="alfa.ecoar", arguments={"texto": "y"}))).status == "ok"


async def test_retorno_nao_textual_vira_json() -> None:
    _kit, session = await open_with(lambda c: native("alfa", "dados", c, result={"b": 1, "a": [1, 2]}))
    resultado = await session.execute(ToolCall(name="alfa.dados", arguments={"texto": "x"}))
    assert '{"a": [1, 2], "b": 1}' in resultado.text


async def test_um_tool_call_no_trace_por_chamada_sem_argumentos() -> None:
    """FR-014."""
    clock = FakeClock(readings=(10.0, 10.25, 20.0, 20.5))
    kit, session = await open_with(
        lambda c: native("alfa", "ecoar", c, parameters=EMPTY_SCHEMA, result="segredo-do-usuario"), clock=clock
    )
    resultado = await session.execute(ToolCall(name="alfa.ecoar", arguments={}))
    await session.execute(ToolCall(name="nada.disso", arguments={"senha": "123"}))

    primeiro, segundo = kit.trace.of_type(ToolCallEvent)
    assert (primeiro.tool, primeiro.kind, primeiro.status) == ("alfa.ecoar", "native", "ok")
    assert primeiro.duration_ms == 250.0
    assert primeiro.size_bytes == len(resultado.text.encode("utf-8")) and not primeiro.truncated
    assert (segundo.tool, segundo.status, segundo.duration_ms) == ("nada.disso", "unknown", 500.0)
    for evento in (primeiro, segundo):
        assert "segredo-do-usuario" not in repr(evento) and "123" not in repr(evento)


@pytest.mark.us3
@pytest.mark.parametrize("nome", ["", "   ", "\n"])
async def test_nome_em_branco_e_inexistente_e_vai_ao_trace_sem_quebrar(nome: str) -> None:
    """Regressão achada pela suíte adversarial: o nome vem do modelo e pode vir vazio."""
    kit, session = await open_with(lambda c: native("alfa", "ecoar", c))
    resultado = await session.execute(ToolCall(name=nome, arguments={}))
    assert resultado.status == "unknown"
    (evento,) = kit.trace.of_type(ToolCallEvent)
    assert evento.tool == "(sem nome)" and evento.status == "unknown"

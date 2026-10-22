"""T014 e T042 — conformidade da porta `McpTransport` (contracts/ports.md): o adapter programado e os reais.

O `stdio` roda o servidor de demonstração como processo filho; `http` e `sse` o servem por uvicorn em `127.0.0.1`,
alcançado como global pela exceção de hosts internos.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from axon_ai.mcp.adapters.memory import ScriptedMcpTransport, ScriptedServer
from axon_ai.mcp.domain.records import StdioCommand
from axon_ai.mcp.ports import (
    McpTransport,
    OperationLimits,
    RemotePart,
    RemoteResult,
    RemoteTool,
    Target,
    TransportFailure,
)

DEMO = Path(__file__).resolve().parent.parent / "servers" / "demo.py"
LIMITS = OperationLimits(timeout=20.0, max_bytes=2_000_000)
SHORT = OperationLimits(timeout=1.0, max_bytes=2_000_000)

Case = Callable[[str], tuple[McpTransport, Target]]
"""Monta, para um caso (`ok`, `lento`, `falha`), o transporte e o alvo."""


def stdio_target(command: str = sys.executable, **env: str) -> Target:
    return Target(
        alias="demo",
        scope="global",
        transport="stdio",
        stdio=StdioCommand(command=command, args=(str(DEMO),), env=env),
    )


def scripted_case(case: str) -> tuple[McpTransport, Target]:
    tools = (RemoteTool(name="ecoar", description="Devolve o texto recebido."), RemoteTool(name="falha"))
    server = ScriptedServer(
        tools=tools,
        results={
            "ecoar": RemoteResult(parts=(RemotePart(kind="text", text="oi"),)),
            "falha": RemoteResult(parts=(RemotePart(kind="text", text="falha programada"),), is_error=True),
            "imagem": RemoteResult(parts=(RemotePart(kind="image", mime="image/png", data=b"hello"),)),
        },
        delay=5.0 if case == "lento" else 0.0,
    )
    transport = ScriptedMcpTransport({"/bin/demo": server})
    return transport, Target(alias="demo", scope="global", transport="stdio", stdio=StdioCommand(command="/bin/demo"))


def stdio_case(_case: str) -> tuple[McpTransport, Target]:
    from axon_ai.mcp.adapters.transport_stdio import StdioMcpTransport

    return StdioMcpTransport(), stdio_target()


def http_transport(**overrides: object) -> McpTransport:
    from axon_ai.mcp.adapters.memory import FixedDnsResolver
    from axon_ai.mcp.adapters.transport_http import HttpMcpTransport

    options: dict[str, object] = {
        "dns": FixedDnsResolver(),
        "internal_hosts": frozenset({"127.0.0.1"}),
        "allowed_hosts": None,
    }
    return HttpMcpTransport(**(options | overrides))  # type: ignore[arg-type]


def http_target(endpoint: str, *, transport: str = "http", scope: str = "global", **headers: str) -> Target:
    return Target(alias="demo", scope=scope, transport=transport, endpoint=endpoint, headers=headers)  # type: ignore[arg-type]


@pytest.fixture(
    params=[
        pytest.param("programado", marks=pytest.mark.us1),
        pytest.param("stdio", marks=pytest.mark.us1),
        pytest.param("http", marks=pytest.mark.us6),
        pytest.param("sse", marks=pytest.mark.us6),
    ]
)
def make(request: pytest.FixtureRequest) -> Case:
    kind = request.param
    if kind == "programado":
        return scripted_case
    if kind == "stdio":
        return stdio_case
    endpoint = request.getfixturevalue("demo_http" if kind == "http" else "demo_sse")
    return lambda _case: (http_transport(), http_target(endpoint, transport=kind))


async def test_lista_as_tools_anunciadas(make: Case) -> None:
    transport, target = make("ok")
    tools = await transport.list_tools(target, limits=LIMITS)
    nomes = [tool.name for tool in tools]
    assert "ecoar" in nomes
    ecoar = next(tool for tool in tools if tool.name == "ecoar")
    assert ecoar.description == "Devolve o texto recebido."


async def test_chama_uma_tool(make: Case) -> None:
    transport, target = make("ok")
    resultado = await transport.call_tool(target, "ecoar", {"texto": "oi"}, limits=LIMITS)
    assert not resultado.is_error
    assert [part.text for part in resultado.parts if part.kind == "text"] == ["oi"]


async def test_parte_de_imagem_chega_com_tipo_e_bytes(make: Case) -> None:
    """R17: o `ImageContent` do SDK vira `RemotePart` com `mime` e os bytes decodificados."""
    transport, target = make("ok")
    resultado = await transport.call_tool(target, "imagem", {}, limits=LIMITS)
    [parte] = resultado.parts
    assert (parte.kind, parte.mime, parte.data) == ("image", "image/png", b"hello")


async def test_resultado_de_erro_do_servidor(make: Case) -> None:
    transport, target = make("ok")
    resultado = await transport.call_tool(target, "falha", {}, limits=LIMITS)
    assert resultado.is_error
    assert any("falha programada" in (part.text or "") for part in resultado.parts)


async def test_prazo_vencido_vira_transport_failure(make: Case) -> None:
    transport, target = make("lento")
    with pytest.raises(TransportFailure) as caught:
        if isinstance(transport, ScriptedMcpTransport):
            await transport.list_tools(target, limits=SHORT)
        else:
            await transport.call_tool(target, "lento", {"segundos": 5}, limits=SHORT)
    assert "1 s" in caught.value.reason


@pytest.mark.us1
async def test_stdio_comando_inexistente_vira_transport_failure() -> None:
    from axon_ai.mcp.adapters.transport_stdio import StdioMcpTransport

    with pytest.raises(TransportFailure):
        await StdioMcpTransport().list_tools(stdio_target(command="/nao/existe/mcp"), limits=LIMITS)


@pytest.mark.us1
async def test_stdio_env_literal_chega_ao_filho() -> None:
    from axon_ai.mcp.adapters.transport_stdio import StdioMcpTransport

    resultado = await StdioMcpTransport().call_tool(
        stdio_target(DEMO_VAR="valor"), "ambiente", {"nome": "DEMO_VAR"}, limits=LIMITS
    )
    assert [part.text for part in resultado.parts] == ["valor"]


@pytest.mark.us2
async def test_stdio_segredo_resolvido_chega_ao_filho_e_nao_ao_repr() -> None:
    from axon_ai.mcp.adapters.transport_stdio import StdioMcpTransport

    target = Target(
        alias="demo",
        scope="global",
        transport="stdio",
        stdio=StdioCommand(command=sys.executable, args=(str(DEMO),), secrets={"TOKEN": "demo_token"}),
        environment={"TOKEN": "segredo-do-filho"},
    )
    resultado = await StdioMcpTransport().call_tool(target, "ambiente", {"nome": "TOKEN"}, limits=LIMITS)
    assert [part.text for part in resultado.parts] == ["segredo-do-filho"]
    assert "segredo-do-filho" not in repr(target)


# --- http e sse reais (T042, US6) -------------------------------------------------------------------------------------


@pytest.mark.us6
async def test_http_leva_o_cabecalho_do_alvo_ao_servidor(demo_http: str) -> None:
    """US2 cen. 2 no transporte real: o segredo resolvido chega ao servidor no cabeçalho."""
    resultado = await http_transport().call_tool(
        http_target(demo_http, Authorization="Bearer s3cr3t"), "quem", {}, limits=LIMITS
    )
    assert [part.text for part in resultado.parts] == ["Bearer s3cr3t"]


@pytest.mark.us6
async def test_http_teto_de_bytes_vira_transport_failure(demo_http: str) -> None:
    with pytest.raises(TransportFailure) as caught:
        await http_transport().call_tool(
            http_target(demo_http), "grande", {"n": 200_000}, limits=OperationLimits(timeout=20, max_bytes=50_000)
        )
    assert "50000 bytes" in caught.value.reason


@pytest.mark.us6
async def test_sem_a_excecao_de_host_interno_o_mesmo_servidor_e_bloqueado(demo_http: str) -> None:
    """US6 cen. 3, lado do usuário: o host liberado vale só para global."""
    transport = http_transport()
    with pytest.raises(TransportFailure) as caught:
        await transport.list_tools(http_target(demo_http, scope="user"), limits=LIMITS)
    assert "bloqueado" in caught.value.reason and "loopback" in caught.value.reason
    with pytest.raises(TransportFailure):
        await http_transport(internal_hosts=frozenset()).list_tools(http_target(demo_http), limits=LIMITS)


@pytest.mark.us6
async def test_a_falha_nunca_repete_o_cabecalho(demo_http: str) -> None:
    with pytest.raises(TransportFailure) as caught:
        await http_transport().list_tools(
            http_target(demo_http, scope="user", Authorization="Bearer s3cr3t"), limits=LIMITS
        )
    assert "s3cr3t" not in caught.value.reason

"""Fábricas dos testes da 007: rascunhos, Principals, grants, servidores programados e a montagem do serviço."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from ai_core.assistants.api import ExecutionGrant, Limits, Principal
from ai_core.llm.api import ModelPolicy, ModelRef
from ai_core.mcp.adapters.memory import (
    InMemoryDiscoveryCache,
    InMemorySecretResolver,
    InMemoryServerStore,
    ScriptedMcpTransport,
    ScriptedServer,
)
from ai_core.mcp.api import McpServerDraft, SecurityPolicy
from ai_core.mcp.ports import McpConfig, McpServerStore, RemoteTool
from ai_core.packs.api import Composition

T0: Final = datetime(2026, 10, 1, 12, tzinfo=UTC)

ANA: Final = Principal(subject="user:ana", scheme="oidc")
BIA: Final = Principal(subject="user:bia", scheme="oidc")

FINANCEIRO_URL: Final = "https://mcp.financeiro.example/mcp"
DRIVE_URL: Final = "https://drive.example/mcp"

TOOLS: Final = (
    RemoteTool(name="saldo", description="Saldo da conta", input_schema={"type": "object"}),
    RemoteTool(name="extrato", description="Extrato", input_schema={"type": "object"}),
    RemoteTool(name="pagar", description="Paga uma conta", input_schema={"type": "object"}),
    RemoteTool(name="secreta", description="Fora da allowlist", input_schema={"type": "object"}),
)


class MutableClock:
    def __init__(self, at: datetime = T0) -> None:
        self._at = at

    def now(self) -> datetime:
        return self._at

    def advance(self, seconds: float) -> None:
        self._at += timedelta(seconds=seconds)


def policy(**overrides: Any) -> SecurityPolicy:
    base: dict[str, Any] = {"allowed_tools": ("saldo", "extrato", "pagar"), "write_tools": ("pagar",)}
    return SecurityPolicy(**(base | overrides))


def global_draft(**overrides: Any) -> McpServerDraft:
    base: dict[str, Any] = {
        "alias": "financeiro",
        "transport": "http",
        "endpoint": FINANCEIRO_URL,
        "description": "Saldos e extratos",
        "policy": policy(),
    }
    return McpServerDraft(**(base | overrides))


def user_draft(**overrides: Any) -> McpServerDraft:
    base: dict[str, Any] = {"alias": "~drive", "transport": "http", "endpoint": DRIVE_URL, "policy": policy()}
    return McpServerDraft(**(base | overrides))


def grant(*aliases: str, assistant: str = "geral", principal: Principal = ANA) -> ExecutionGrant:
    """Grant de Assistant de sistema (`geral`) ou de usuário (`~meu`, do Principal dado)."""
    return ExecutionGrant(
        assistant=assistant,
        principal=principal,
        flow="chat",
        composition=Composition(packs=()),
        mcp_aliases=frozenset(aliases),
        models=ModelPolicy(roles={"generation": ModelRef(provider="ollama", model="m")}, allow=("ollama/*",)),
        limits=Limits(),
    )


def scripted(*tools: RemoteTool, **kwargs: Any) -> ScriptedServer:
    return ScriptedServer(tools=tools or TOOLS, **kwargs)


@dataclass(slots=True, kw_only=True)
class Kit:
    """O serviço montado com adapters em memória, e os adapters à mão para as suítes."""

    service: Any
    store: McpServerStore
    transport: ScriptedMcpTransport
    clock: MutableClock
    secrets: dict[str, str] = field(default_factory=dict)


def build(
    *,
    config: McpConfig | None = None,
    store: McpServerStore | None = None,
    servers: Mapping[str, ScriptedServer] | None = None,
    secrets: Mapping[str, str] | None = None,
    transports: Mapping[str, Any] | None = None,
) -> Kit:
    """`McpService` com armazenamento, transporte programado (os três tipos), segredos, cache e relógio de teste."""
    from ai_core.mcp.service import McpService

    clock = MutableClock()
    transport = ScriptedMcpTransport({FINANCEIRO_URL: scripted(), DRIVE_URL: scripted()} | dict(servers or {}))
    values = dict(secrets or {})
    store = store or InMemoryServerStore()
    service = McpService(
        store=store,
        config=config or McpConfig(),
        transports=transports or {"http": transport, "sse": transport, "stdio": transport},
        secrets=InMemorySecretResolver(values),
        cache=InMemoryDiscoveryCache(clock),
        clock=clock,
    )
    return Kit(service=service, store=store, transport=transport, clock=clock, secrets=values)


def operations(transport: ScriptedMcpTransport) -> Sequence[str]:
    return [operation for operation, _ in transport.calls]


# --- servidor de demonstração por HTTP --------------------------------------------------------------------------------


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


@contextmanager
def serving(app: Any) -> Iterator[int]:
    """Serve uma app ASGI em `127.0.0.1` numa thread durante o bloco; devolve a porta."""
    import uvicorn

    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="on"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:  # pragma: no cover
            raise RuntimeError("o servidor de teste não subiu")
        time.sleep(0.02)
    try:
        yield port
    finally:
        server.should_exit = True
        thread.join(timeout=10)

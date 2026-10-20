"""Seams da spec 007: registry de servidores MCP, catálogo de aliases e cliente restrito ao grant.

Contrato em specs/007-core-mcp-integration/contracts/mcp-api.md; campos e regras em data-model.md.

Único módulo da 007 que outros módulos importam. Depende só da stdlib, do contrato 001 (`ToolSpec`, `ToolResult`) e do
`api.py` da 003 (`Principal`, `ExecutionGrant` e os erros base, que a tabela de erros da 008 já traduz). Não importa o
resto do próprio módulo.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Final, Literal, Protocol

from axon_ai.assistants.api import Conflict, ExecutionGrant, NotFound, Principal, RequestRejected
from axon_ai_contracts import JSONValue, ToolResult, ToolSpec

# ---------------------------------------------------------------------------------------------------------------------
# Vocabulário
# ---------------------------------------------------------------------------------------------------------------------

type Scope = Literal["global", "user"]
type Transport = Literal["http", "sse", "stdio"]
type AuthType = Literal["none", "bearer"]
type Origin = Literal["file", "registry"]

SCOPES: Final[tuple[Scope, ...]] = ("global", "user")
TRANSPORTS: Final[tuple[Transport, ...]] = ("http", "sse", "stdio")
AUTH_TYPES: Final[tuple[AuthType, ...]] = ("none", "bearer")

USER_PREFIX: Final = "~"
"""Prefixo reservado aos aliases de usuário (FR-015): os dois espaços de nomes nunca se cruzam."""

ALIAS_PATTERN: Final = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")
"""Alias sem o prefixo. Sem ponto: o ponto separa o alias da tool no namespace do catálogo (004)."""

CREDENTIAL_REF_PATTERN: Final = re.compile(r"[a-z0-9][a-z0-9_]{0,63}")
"""Referência de credencial; o valor mora em `AXON_MCP_SECRET_<REF EM MAIÚSCULAS>` (research R7)."""

DESCRIPTION_MAX: Final = 500

TIMEOUT_MS_MIN: Final = 1_000
TIMEOUT_MS_MAX: Final = 120_000
DEFAULT_TIMEOUT_MS: Final = 30_000
MAX_RESPONSE_BYTES_MIN: Final = 1_024
MAX_RESPONSE_BYTES_MAX: Final = 1_048_576
DEFAULT_MAX_RESPONSE_BYTES: Final = 65_536

NOT_FOUND_MESSAGE: Final = "MCP não encontrado"
"""Mensagem fixa: MCP alheio e inexistente são indistinguíveis (SC-004)."""

UNKNOWN_SERVER: Final = "servidor desconhecido"


# ---------------------------------------------------------------------------------------------------------------------
# Erros
# ---------------------------------------------------------------------------------------------------------------------


class McpNotFound(NotFound):
    """MCP inexistente **ou** de outro dono — mesma mensagem nos dois casos."""

    def __init__(self) -> None:
        super().__init__(NOT_FOUND_MESSAGE)


class McpRejected(RequestRejected):
    """Registro fora das regras. `field` nomeia o campo, para que a borda o devolva ao cliente."""


class McpConflict(Conflict):
    """Alias já usado no escopo, ou entrada do arquivo do operador, que é somente leitura."""


class UnknownServer(LookupError):
    """Alias fora do grant — ou que deixou de ser visível — pedido ao cliente restrito (US3)."""

    def __init__(self, alias: str) -> None:
        super().__init__(f"{UNKNOWN_SERVER}: {alias}")
        self.alias = alias


class McpConfigError(ValueError):
    """Erro de arquivo no `mcp.yaml`: o boot para. A mensagem nomeia o caminho do campo."""


# ---------------------------------------------------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------------------------------------------------


def _bounded(name: str, value: int, low: int, high: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        message = f"policy.{name} precisa ser um inteiro entre {low} e {high}: {value!r}"
        raise McpRejected(message, field=f"policy.{name}")


def _tool_names(name: str, values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, str):
        raise McpRejected(f"policy.{name} precisa ser uma lista de nomes", field=f"policy.{name}")
    items = tuple(values)
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise McpRejected(f"policy.{name}: itens precisam ser nomes não vazios", field=f"policy.{name}")
    repeated = sorted({item for item in items if items.count(item) > 1})
    if repeated:
        raise McpRejected(f"policy.{name}: nomes repetidos: {', '.join(repeated)}", field=f"policy.{name}")
    return items


@dataclass(frozen=True, slots=True, kw_only=True)
class SecurityPolicy:
    """Política por servidor (FR-001, US5). A allowlist é obrigatória: capacidade não declarada não existe."""

    allowed_tools: tuple[str, ...]
    write_tools: tuple[str, ...] = ()
    timeout_ms: int = DEFAULT_TIMEOUT_MS
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES

    def __post_init__(self) -> None:
        allowed = _tool_names("allowed_tools", self.allowed_tools)
        if not allowed:
            raise McpRejected("policy.allowed_tools é obrigatória e não pode ser vazia", field="policy.allowed_tools")
        write = _tool_names("write_tools", self.write_tools)
        outside = sorted(set(write) - set(allowed))
        if outside:
            raise McpRejected(
                f"policy.write_tools fora de allowed_tools: {', '.join(outside)}", field="policy.write_tools"
            )
        _bounded("timeout_ms", self.timeout_ms, TIMEOUT_MS_MIN, TIMEOUT_MS_MAX)
        _bounded("max_response_bytes", self.max_response_bytes, MAX_RESPONSE_BYTES_MIN, MAX_RESPONSE_BYTES_MAX)
        object.__setattr__(self, "allowed_tools", allowed)
        object.__setattr__(self, "write_tools", write)


@dataclass(frozen=True, slots=True, kw_only=True)
class McpServerDraft:
    """O que a API envia ao criar ou alterar um servidor. As regras por escopo são do domínio (research R11)."""

    alias: str
    transport: str
    endpoint: str | None = None
    description: str | None = None
    auth_type: str = "none"
    credential_ref: str | None = None
    enabled: bool = True
    user_access: bool = False
    policy: SecurityPolicy


@dataclass(frozen=True, slots=True, kw_only=True)
class McpServer:
    """A visão publicada de um servidor. Nunca contém o valor de um segredo — só o **nome** da referência.

    `transport` e `policy` só são `None` numa entrada do arquivo do operador com erro (`available=False`).
    """

    alias: str
    scope: Scope
    owner: str | None
    transport: Transport | None
    endpoint: str | None
    command: str | None = None
    description: str | None = None
    auth_type: AuthType = "none"
    credential_ref: str | None = None
    enabled: bool = True
    user_access: bool = False
    policy: SecurityPolicy | None
    origin: Origin
    available: bool = True
    reason: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def read_only(self) -> bool:
        """Entrada do arquivo do operador: muda só com restart (FR-013)."""
        return self.origin == "file"


@dataclass(frozen=True, slots=True, kw_only=True)
class McpSummary:
    """O que um Principal pode referenciar num Assistant próprio — sem endpoint, credencial nem política."""

    alias: str
    scope: Scope
    description: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ServerHealth:
    """Saúde de um servidor (FR-011): o que ele anuncia e o que a allowlist pede e ele não anuncia."""

    alias: str
    ok: bool
    detail: str | None = None
    tools: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Discovery:
    """Tools descobertas e os servidores que falharam, com o motivo — para a 004 registrar e sinalizar."""

    tools: tuple[ToolSpec, ...] = ()
    unavailable: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "tools", tuple(self.tools))
        object.__setattr__(self, "unavailable", MappingProxyType(dict(self.unavailable)))


# ---------------------------------------------------------------------------------------------------------------------
# Seams
# ---------------------------------------------------------------------------------------------------------------------


class McpRegistry(Protocol):
    """CRUD por escopo. Globais: autoridade do operador — quem confere o grupo de administração é a borda (008)."""

    async def globals(self) -> Sequence[McpServer]: ...

    async def get_global(self, alias: str) -> McpServer: ...

    async def create_global(self, draft: McpServerDraft) -> McpServer: ...

    async def update_global(self, alias: str, draft: McpServerDraft) -> McpServer: ...

    async def delete_global(self, alias: str) -> None: ...

    async def mine(self, principal: Principal) -> Sequence[McpServer]: ...

    async def get_mine(self, principal: Principal, alias: str) -> McpServer: ...

    async def create_mine(self, principal: Principal, draft: McpServerDraft) -> McpServer: ...

    async def update_mine(self, principal: Principal, alias: str, draft: McpServerDraft) -> McpServer: ...

    async def delete_mine(self, principal: Principal, alias: str) -> None: ...

    async def available(self, principal: Principal) -> Sequence[McpSummary]:
        """O que o Principal pode referenciar num Assistant próprio: os seus e os globais liberados a usuários."""
        ...

    async def check(self, alias: str, *, owner: str | None = None) -> ServerHealth:
        """Saúde por servidor (FR-011): ignora o cache e exercita o caminho real inteiro."""
        ...


class McpCatalog(Protocol):
    """Aliases referenciáveis — a forma exata da porta `McpDirectory` que a 003 declarou."""

    async def aliases(self, *, owner: str | None) -> frozenset[str]:
        """`owner=None`: globais habilitados e disponíveis; `owner`: os `~` dele e os globais liberados a usuários."""
        ...


class RestrictedMcpClient(Protocol):
    """Cumpre o `MCPClient` do contrato 001 e acrescenta `discover`. Só conhece os aliases do grant (US3)."""

    async def discover(self, aliases: Sequence[str]) -> Discovery: ...

    async def discover_tools(self, aliases: Sequence[str]) -> Sequence[ToolSpec]: ...

    async def execute(self, alias: str, tool: str, arguments: Mapping[str, JSONValue]) -> ToolResult:
        """Falha de servidor, prazo ou rede volta como `ToolResult(error=...)`; alias fora do grant levanta
        `UnknownServer`."""
        ...


class McpClients(Protocol):
    def client_for(self, grant: ExecutionGrant) -> RestrictedMcpClient:
        """O cliente de uma execução. Não faz I/O."""
        ...

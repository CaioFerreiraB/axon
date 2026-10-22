"""`McpService`: o registry, o catálogo de aliases e o cliente restrito (specs/007-core-mcp-integration).

Orquestra o domínio e as portas; não importa adapter nenhum. O arquivo do operador chega já carregado — quem o lê é a
composition root, no boot —, e o armazenamento guarda o que a API cria. O segredo de uma credencial só existe dentro
de uma operação: é resolvido ao montar o `Target` e nunca sai em valor devolvido, exceção ou log (FR-004).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta
from typing import Final

from axon_ai.assistants.api import ExecutionGrant, Principal
from axon_ai.mcp.api import (
    DEFAULT_MAX_ATTACHMENT_BYTES,
    Discovery,
    McpConflict,
    McpNotFound,
    McpRejected,
    McpServer,
    McpServerDraft,
    McpSummary,
    ServerHealth,
    UnknownServer,
)
from axon_ai.mcp.domain import results, tools
from axon_ai.mcp.domain.servers import validate_draft
from axon_ai.mcp.domain.visibility import (
    Server,
    for_users,
    from_stored,
    grant_owner,
    is_user_alias,
    merge_globals,
    usable,
)
from axon_ai.mcp.ports import (
    CachedDiscovery,
    CacheKey,
    Clock,
    DiscoveryCache,
    McpConfig,
    McpServerStore,
    McpTransport,
    OperationLimits,
    RemoteTool,
    SecretResolver,
    StoredServer,
    Target,
    TransportFailure,
)
from axon_ai_contracts import JSONValue, ToolResult, ToolSpec

DEFAULT_DISCOVERY_TTL: Final = timedelta(seconds=300)
DEFAULT_FAILURE_TTL: Final = timedelta(seconds=30)
TRANSPORT_SLACK_BYTES: Final = 1_048_576
"""Folga do teto do transporte sobre `max_response_bytes`: inicialização e lista de tools (research R6)."""
TRANSPORT_ATTACHMENTS: Final = 4
"""Quantos anexos no teto, em base64, o transporte comporta além do texto (R17)."""


class CredentialMissing(Exception):
    """Referência sem valor no ambiente. A mensagem nomeia a referência — nunca um valor (R7)."""

    def __init__(self, ref: str) -> None:
        super().__init__(f"credencial '{ref}' não configurada")


class McpService:
    """`McpRegistry`, `McpCatalog` e `McpClients` (axon_ai.mcp.api)."""

    def __init__(
        self,
        *,
        store: McpServerStore,
        config: McpConfig,
        transports: Mapping[str, McpTransport],
        secrets: SecretResolver,
        cache: DiscoveryCache,
        clock: Clock,
        discovery_ttl: timedelta = DEFAULT_DISCOVERY_TTL,
        failure_ttl: timedelta = DEFAULT_FAILURE_TTL,
        max_attachment_bytes: int = DEFAULT_MAX_ATTACHMENT_BYTES,
    ) -> None:
        self._store = store
        self._config = config
        self._file_aliases = frozenset(entry.alias for entry in config.entries)
        self._transports = dict(transports)
        self._secrets = secrets
        self._cache = cache
        self._clock = clock
        self._discovery_ttl = discovery_ttl
        self._failure_ttl = failure_ttl
        self._max_attachment_bytes = max_attachment_bytes

    # --- McpRegistry: globais --------------------------------------------------------------------------------------

    async def globals(self) -> Sequence[McpServer]:
        return [server.view for server in await self._globals()]

    async def get_global(self, alias: str) -> McpServer:
        server = await self._global(alias)
        if server is None:
            raise McpNotFound()
        return server.view

    async def create_global(self, draft: McpServerDraft) -> McpServer:
        validate_draft(draft, scope="global", origin="registry")
        if draft.alias in self._file_aliases:
            raise McpConflict(f"o alias '{draft.alias}' é declarado no arquivo do operador")
        now = self._clock.now()
        record = StoredServer(owner=None, draft=draft, created_at=now, updated_at=now)
        if not await self._store.insert(record):
            raise McpConflict(f"o alias '{draft.alias}' já existe")
        return from_stored(record).view

    async def update_global(self, alias: str, draft: McpServerDraft) -> McpServer:
        self._read_only_guard(alias)
        return await self._update(None, alias, draft, scope="global")

    async def delete_global(self, alias: str) -> None:
        self._read_only_guard(alias)
        if not await self._store.delete(None, alias):
            raise McpNotFound()

    def _read_only_guard(self, alias: str) -> None:
        if alias in self._file_aliases:
            raise McpConflict(f"'{alias}' é declarado no arquivo do operador: somente leitura, muda só com restart")

    # --- McpRegistry: do usuário -----------------------------------------------------------------------------------

    async def mine(self, principal: Principal) -> Sequence[McpServer]:
        return [from_stored(record).view for record in await self._store.list(principal.subject)]

    async def get_mine(self, principal: Principal, alias: str) -> McpServer:
        record = await self._store.get(principal.subject, alias) if is_user_alias(alias) else None
        if record is None:
            raise McpNotFound()
        return from_stored(record).view

    async def create_mine(self, principal: Principal, draft: McpServerDraft) -> McpServer:
        validate_draft(draft, scope="user", origin="registry")
        now = self._clock.now()
        record = StoredServer(owner=principal.subject, draft=draft, created_at=now, updated_at=now)
        if not await self._store.insert(record):
            raise McpConflict(f"você já tem um MCP '{draft.alias}'")
        return from_stored(record).view

    async def update_mine(self, principal: Principal, alias: str, draft: McpServerDraft) -> McpServer:
        if not is_user_alias(alias):
            raise McpNotFound()
        return await self._update(principal.subject, alias, draft, scope="user")

    async def delete_mine(self, principal: Principal, alias: str) -> None:
        if not is_user_alias(alias) or not await self._store.delete(principal.subject, alias):
            raise McpNotFound()

    async def _update(self, owner: str | None, alias: str, draft: McpServerDraft, *, scope: str) -> McpServer:
        if draft.alias != alias:
            raise McpRejected("alias: não muda numa alteração — crie outro e apague este", field="alias")
        validate_draft(draft, scope="user" if scope == "user" else "global", origin="registry")
        existing = await self._store.get(owner, alias)
        if existing is None:
            raise McpNotFound()
        record = StoredServer(owner=owner, draft=draft, created_at=existing.created_at, updated_at=self._clock.now())
        if not await self._store.replace(record):
            raise McpNotFound()
        return from_stored(record).view

    async def available(self, principal: Principal) -> Sequence[McpSummary]:
        visible = [server for server in await self._globals() if usable(server) and for_users(server)]
        visible += [from_stored(record) for record in await self._store.list(principal.subject)]
        return [
            McpSummary(alias=server.view.alias, scope=server.view.scope, description=server.view.description)
            for server in visible
            if usable(server)
        ]

    # --- McpRegistry: saúde (FR-011, R14) --------------------------------------------------------------------------

    async def check(self, alias: str, *, owner: str | None = None) -> ServerHealth:
        server = await self._find(alias, owner)
        if server is None:
            raise McpNotFound()
        if not server.view.available:
            return ServerHealth(alias=alias, ok=False, detail=server.view.reason)
        if not server.view.enabled:
            return ServerHealth(alias=alias, ok=False, detail="desabilitado no registry")
        policy = server.view.policy
        assert policy is not None  # disponível ⇒ definição válida
        try:
            remote = await self._list_remote(server)
        except (TransportFailure, CredentialMissing) as error:
            return ServerHealth(alias=alias, ok=False, detail=_reason(error))
        return ServerHealth(
            alias=alias,
            ok=True,
            tools=tuple(tool.name for tool in remote),
            missing=tools.missing_tools(remote, policy),
        )

    # --- McpCatalog (forma de McpDirectory, 003) -------------------------------------------------------------------

    async def aliases(self, *, owner: str | None) -> frozenset[str]:
        globals_ = [server for server in await self._globals() if usable(server)]
        if owner is None:
            return frozenset(server.alias for server in globals_)
        own = [from_stored(record) for record in await self._store.list(owner)]
        return frozenset(server.alias for server in globals_ if for_users(server)) | frozenset(
            server.alias for server in own if usable(server)
        )

    # --- McpClients ------------------------------------------------------------------------------------------------

    def client_for(self, grant: ExecutionGrant) -> RestrictedClient:
        owner = grant_owner(grant.assistant, grant.principal.subject)
        return RestrictedClient(self, aliases=frozenset(grant.mcp_aliases), owner=owner)

    # --- internos usados pelo cliente --------------------------------------------------------------------------------

    async def visible(self, alias: str, *, owner: str | None) -> Server | None:
        """O servidor que um grant com este dono alcança agora — revalidado a cada operação (R9)."""
        if is_user_alias(alias):
            if owner is None:
                return None
            record = await self._store.get(owner, alias)
            server = from_stored(record) if record is not None else None
        else:
            server = await self._global(alias)
            if server is not None and owner is not None and not for_users(server):
                return None
        return server if server is not None and usable(server) else None

    async def discover_one(self, server: Server) -> tuple[RemoteTool, ...] | str:
        """A lista bruta do cache ou do servidor, ou o motivo da falha (R8)."""
        key = CacheKey(scope=server.view.scope, owner=server.view.owner, alias=server.alias, version=server.version)
        cached = self._cache.get(key)
        if cached is not None:
            return cached.tools if cached.tools is not None else (cached.failure or "falha na descoberta")
        try:
            remote = tuple(await self._list_remote(server))
        except (TransportFailure, CredentialMissing) as error:
            reason = _reason(error)
            self._cache.put(key, CachedDiscovery(failure=reason), ttl=self._failure_ttl)
            return reason
        self._cache.put(key, CachedDiscovery(tools=remote), ttl=self._discovery_ttl)
        return remote

    async def call(self, server: Server, tool: str, arguments: Mapping[str, JSONValue]) -> ToolResult:
        policy = server.view.policy
        assert policy is not None
        if tool not in policy.allowed_tools:
            return results.failure(f"tool '{tool}' não permitida em '{server.alias}'")
        try:
            target = self._target(server)
            try:
                remote = await self._transport(server).call_tool(
                    target, tool, arguments, limits=_limits(server, self._max_attachment_bytes)
                )
            except TransportFailure as error:
                raise TransportFailure(_redact(error.reason, target)) from None
        except (TransportFailure, CredentialMissing) as error:
            return results.failure(_reason(error))
        return results.to_tool_result(
            remote, max_bytes=policy.max_response_bytes, max_attachment_bytes=self._max_attachment_bytes
        )

    async def _list_remote(self, server: Server) -> Sequence[RemoteTool]:
        target = self._target(server)
        try:
            return await self._transport(server).list_tools(target, limits=_limits(server))
        except TransportFailure as error:
            raise TransportFailure(_redact(error.reason, target)) from None

    def _transport(self, server: Server) -> McpTransport:
        transport = server.view.transport
        if transport is None or transport not in self._transports:
            raise TransportFailure(f"transporte '{transport}' não configurado")
        return self._transports[transport]

    def _target(self, server: Server) -> Target:
        """O alvo da operação, com o segredo resolvido agora e só agora (R7)."""
        view, draft = server.view, server.draft
        assert draft is not None and view.transport is not None
        headers: dict[str, str] = {}
        environment: dict[str, str] = {}
        if draft.auth_type == "bearer" and draft.credential_ref is not None:
            headers["Authorization"] = f"Bearer {self._secret(draft.credential_ref)}"
        if server.stdio is not None:
            for name, ref in server.stdio.secrets.items():
                environment[name] = self._secret(ref)
        return Target(
            alias=view.alias,
            scope=view.scope,
            transport=view.transport,
            endpoint=view.endpoint,
            stdio=server.stdio,
            headers=headers,
            environment=environment,
        )

    def _secret(self, ref: str) -> str:
        value = self._secrets.resolve(ref)
        if value is None:
            raise CredentialMissing(ref)
        return value

    async def _globals(self) -> list[Server]:
        return merge_globals(self._config.entries, await self._store.list(None))

    async def _global(self, alias: str) -> Server | None:
        """No mesmo alias, a entrada do arquivo vem antes do registro sombreado."""
        return next((server for server in await self._globals() if server.alias == alias), None)

    async def _find(self, alias: str, owner: str | None) -> Server | None:
        if owner is None:
            return await self._global(alias)
        record = await self._store.get(owner, alias)
        return from_stored(record) if record is not None else None


class RestrictedClient:
    """O cliente de uma execução: só os aliases do grant, revalidados a cada operação (US3, R9)."""

    def __init__(self, service: McpService, *, aliases: frozenset[str], owner: str | None) -> None:
        self._service = service
        self._aliases = aliases
        self._owner = owner

    async def discover(self, aliases: Sequence[str]) -> Discovery:
        servers = [await self._resolve(alias) for alias in aliases]
        specs: list[ToolSpec] = []
        unavailable: dict[str, str] = {}
        for server in servers:
            found = await self._service.discover_one(server)
            if isinstance(found, str):
                unavailable[server.alias] = found
                continue
            policy = server.view.policy
            assert policy is not None
            specs.extend(tools.allowed_specs(found, policy))
        return Discovery(tools=tuple(specs), unavailable=unavailable)

    async def discover_tools(self, aliases: Sequence[str]) -> Sequence[ToolSpec]:
        return (await self.discover(aliases)).tools

    async def execute(self, alias: str, tool: str, arguments: Mapping[str, JSONValue]) -> ToolResult:
        server = await self._resolve(alias)
        return await self._service.call(server, tool, arguments)

    async def _resolve(self, alias: str) -> Server:
        if alias not in self._aliases:
            raise UnknownServer(alias)
        server = await self._service.visible(alias, owner=self._owner)
        if server is None:
            raise UnknownServer(alias)
        return server


def _limits(server: Server, max_attachment_bytes: int = 0) -> OperationLimits:
    """Prazo e teto da política; numa chamada de tool, o teto comporta também os anexos em base64 (R17)."""
    policy = server.view.policy
    assert policy is not None
    attachments = TRANSPORT_ATTACHMENTS * (-(-max_attachment_bytes // 3) * 4)
    return OperationLimits(
        timeout=policy.timeout_ms / 1000, max_bytes=policy.max_response_bytes + TRANSPORT_SLACK_BYTES + attachments
    )


def _reason(error: Exception) -> str:
    return error.reason if isinstance(error, TransportFailure) else str(error)


def _redact(reason: str, target: Target) -> str:
    """Defesa a mais (FR-004): o transporte não deve repetir cabeçalho nem ambiente na falha — e, se repetir, o serviço,
    que conhece os segredos desta operação, os apaga antes de o motivo sair em descoberta, saúde ou resultado."""
    secrets = [*target.headers.values(), *target.environment.values()]
    secrets += [value.removeprefix("Bearer ") for value in target.headers.values()]
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        reason = reason.replace(secret, "***")
    return reason

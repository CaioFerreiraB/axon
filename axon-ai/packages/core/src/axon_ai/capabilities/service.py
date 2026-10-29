"""`CapabilityService`: a sessão de tools de uma execução e a consulta de auditoria (specs/004-core-capability-gateway).

Orquestra o domínio e as portas; não importa adapter nenhum. A sessão é montada uma vez por execução — catálogo,
contexto e cliente MCP amarrados —, e o gateway nunca executa fora do catálogo daquela execução, por construção (R2).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from axon_ai.assistants.api import ExecutionGrant
from axon_ai.capabilities.api import (
    UNKNOWN_TOOL,
    AuditEntry,
    AuditFilter,
    AuditRecord,
    AuditStatus,
    CatalogTool,
    FencedToolResult,
    GatewayLimits,
    ToolCall,
    ToolContext,
    ToolStatus,
)
from axon_ai.capabilities.domain.arguments import validate_arguments
from axon_ai.capabilities.domain.catalog import Entry, assemble
from axon_ai.capabilities.domain.fencing import cut, fence
from axon_ai.capabilities.domain.rendering import attachment_markers, chart_markers, render_value, render_within
from axon_ai.capabilities.ports import AuditLog, Clock, PackToolSource
from axon_ai.mcp.api import McpClients, RestrictedMcpClient, UnknownServer
from axon_ai.observability.api import ExecutionError, TraceSink, attachment_info, chart_info
from axon_ai.observability.api import ToolCall as ToolCallEvent
from axon_ai_contracts import Attachment, Chart, Chunk, ToolInvocation, ToolResult, ToolSpec

logger: Final = logging.getLogger("axon_ai.capabilities")

AUDIT_UNAVAILABLE: Final = "auditoria indisponível: a tool de escrita não foi executada"
BLANK_NAME: Final = "(sem nome)"


class CapabilityService:
    """`Capabilities` e `AuditQuery` (axon_ai.capabilities.api)."""

    def __init__(
        self,
        *,
        pack_tools: PackToolSource,
        mcp: McpClients,
        audit: AuditLog,
        trace: TraceSink,
        clock: Clock,
        limits: GatewayLimits,
    ) -> None:
        self._pack_tools = pack_tools
        self._mcp = mcp
        self._audit = audit
        self._trace = trace
        self._clock = clock
        self._limits = limits

    async def open(self, grant: ExecutionGrant, context: ToolContext) -> Session:
        client = self._mcp.client_for(grant)
        discovered: list[tuple[str, Sequence[ToolSpec]]] = []
        unavailable: dict[str, str] = {}
        # Um alias por vez: um que falhe — ou que deixou de ser visível — não derruba a descoberta dos outros (R3).
        for alias in sorted(grant.mcp_aliases):
            try:
                discovery = await client.discover([alias])
            except UnknownServer as error:
                unavailable[alias] = str(error)
                continue
            if alias in discovery.unavailable:
                unavailable[alias] = discovery.unavailable[alias]
                continue
            discovered.append((alias, discovery.tools))
        for alias, reason in unavailable.items():
            self._emit_catalog_problem(context, "mcp_unavailable", f"{alias}: {reason}")

        assembly = assemble(
            self._pack_tools.toolset(grant.composition),
            discovered,
            allowed=frozenset(grant.allowed_tools) if grant.allowed_tools is not None else None,
            write=frozenset(grant.write_tools),
            collections=frozenset(grant.collections),
        )
        for name, problem in assembly.invalid:
            self._emit_catalog_problem(context, "invalid_tool_schema", f"{name}: {problem}")
        return Session(
            grant=grant,
            context=context,
            entries=assembly.entries,
            unavailable=unavailable,
            client=client,
            audit=self._audit,
            trace=self._trace,
            clock=self._clock,
            limits=self._limits,
        )

    async def records(self, filter: AuditFilter) -> Sequence[AuditRecord]:
        return await self._audit.query(filter)

    def _emit_catalog_problem(self, context: ToolContext, kind: str, message: str) -> None:
        self._trace.emit(ExecutionError(request_id=context.request_id, stage="catalog", kind=kind, message=message))


@dataclass(slots=True, kw_only=True)
class _Outcome:
    """O que o despacho produziu, antes do corte e da cerca."""

    status: ToolStatus
    content: str
    error: str | None = None
    chunks: tuple[Chunk, ...] = ()
    truncated: bool = False
    attachments: tuple[Attachment, ...] = ()
    charts: tuple[Chart, ...] = ()


class Session:
    """`ToolSession`: o catálogo e o gateway de uma execução."""

    def __init__(
        self,
        *,
        grant: ExecutionGrant,
        context: ToolContext,
        entries: Mapping[str, Entry],
        unavailable: Mapping[str, str],
        client: RestrictedMcpClient,
        audit: AuditLog,
        trace: TraceSink,
        clock: Clock,
        limits: GatewayLimits,
    ) -> None:
        self._grant = grant
        self._context = context
        self._entries = dict(entries)
        self._tools = {name: entry.tool for name, entry in entries.items()}
        self._unavailable = dict(unavailable)
        self._client = client
        self._audit = audit
        self._trace = trace
        self._clock = clock
        self._limits = limits

    @property
    def tools(self) -> Mapping[str, CatalogTool]:
        return dict(self._tools)

    @property
    def unavailable(self) -> Mapping[str, str]:
        return dict(self._unavailable)

    async def execute(self, call: ToolCall) -> FencedToolResult:
        started = self._clock.monotonic()
        entry = self._entries.get(call.name)
        if entry is None:
            unknown = _Outcome(status="unknown", content="", error=f"{UNKNOWN_TOOL}: {call.name}")
            result = self._finish(call.name, None, unknown)
        else:
            problem = validate_arguments(entry.tool.parameters, call.arguments, trusted=entry.trusted_schema)
            if problem is not None:
                result = self._finish(call.name, entry, _Outcome(status="invalid_arguments", content="", error=problem))
            elif entry.tool.mutates:
                result = await self._audited(entry, call)
            else:
                result = self._finish(call.name, entry, await self._dispatch(entry, call))
        self._trace.emit(
            ToolCallEvent(
                request_id=self._context.request_id,
                # O nome vem do modelo e pode vir vazio: o trace registra a tentativa, e o resultado já é "inexistente".
                tool=call.name if call.name.strip() else BLANK_NAME,
                kind=result.kind,
                status=result.status,
                duration_ms=max(0.0, (self._clock.monotonic() - started) * 1000),
                size_bytes=len(result.text.encode("utf-8")),
                truncated=result.truncated,
                attachments=tuple(attachment_info(item) for item in result.attachments),
                charts=tuple(chart_info(item) for item in result.charts),
            )
        )
        return result

    # --- despacho (R4, R6) ------------------------------------------------------------------------------------------

    async def _dispatch(self, entry: Entry, call: ToolCall) -> _Outcome:
        timeout = self._limits.timeout_ms / 1000
        try:
            return await asyncio.wait_for(self._run(entry, call), timeout)
        except TimeoutError:
            return _Outcome(status="timeout", content="", error=f"sem resposta em {timeout:g} s")
        except Exception as error:
            return _Outcome(status="error", content="", error=_describe(error))

    async def _run(self, entry: Entry, call: ToolCall) -> _Outcome:
        kind = entry.tool.kind
        if kind == "native":
            assert entry.handler is not None
            invocation = ToolInvocation(
                arguments=call.arguments,
                request_id=self._context.request_id,
                reference_time=self._context.reference_time,
            )
            value = await entry.handler(invocation)
            if isinstance(value, ToolResult):
                return _from_result(value)
            return _Outcome(status="ok", content=render_value(value))
        if kind == "retrieval":
            assert entry.retriever is not None and entry.pack is not None
            query = str(call.arguments["query"])
            filters = self._context.retrieval_filters.get(entry.pack)
            top_k = call.arguments.get("top_k")
            retriever = entry.retriever.retriever
            if isinstance(top_k, int) and not isinstance(top_k, bool):
                found = await retriever.search(query, top_k=top_k, filters=filters)
            else:
                found = await retriever.search(query, filters=filters)
            return self._chunks_outcome(tuple(found))
        assert entry.alias is not None
        return _from_result(await self._client.execute(entry.alias, entry.local_name, call.arguments))

    def fence_chunks(self, name: str, chunks: Sequence[Chunk]) -> FencedToolResult:
        """Trechos já recuperados, na cerca de um resultado de recuperação (ADR-026; 005 research R41)."""
        entry = self._entries.get(name)
        if entry is None or entry.tool.kind != "retrieval":
            raise ValueError(f"fence_chunks: {name!r} não é tool de recuperação do catálogo")
        return self._finish(name, entry, self._chunks_outcome(tuple(chunks)))

    def _chunks_outcome(self, chunks: tuple[Chunk, ...]) -> _Outcome:
        """Corte por trecho inteiro: `chunks` são só os que o modelo vê (005 US4, cenário 2)."""
        rendered = render_within(chunks, max_bytes=self._limits.max_response_bytes)
        return _Outcome(status="ok", content=rendered.text, chunks=rendered.chunks, truncated=rendered.truncated)

    def _finish(self, name: str, entry: Entry | None, outcome: _Outcome) -> FencedToolResult:
        """Corte pelo limite do gateway — em MCP o do servidor já veio aplicado, e vale o menor — e cerca (R6, R7)."""
        content = outcome.content or outcome.error or ""
        content, cut_here = cut(content, max_bytes=self._limits.max_response_bytes)
        truncated = cut_here or outcome.truncated
        # As marcas das imagens entram depois do corte: são o único rastro delas que o modelo vê (R13).
        attachments = tuple({item.id: item for item in outcome.attachments}.values())
        charts = tuple({item.id: item for item in outcome.charts}.values())
        content += attachment_markers(attachments) + chart_markers(charts)
        return FencedToolResult(
            name=name,
            kind=entry.tool.kind if entry is not None else None,
            status=outcome.status,
            text=fence(name, status=outcome.status, content=content, truncated=truncated),
            truncated=truncated,
            error=outcome.error,
            chunks=outcome.chunks,
            attachments=attachments,
            charts=charts,
        )

    # --- escrita auditada (R8) --------------------------------------------------------------------------------------

    async def _audited(self, entry: Entry, call: ToolCall) -> FencedToolResult:
        audit_entry = AuditEntry(
            request_id=self._context.request_id,
            principal=self._grant.principal.subject,
            assistant=self._grant.assistant,
            tool=entry.tool.name,
            kind=entry.tool.kind,
            arguments=call.arguments,
            started_at=self._clock.now(),
        )
        try:
            record_id = await self._audit.begin(audit_entry)
        except Exception:
            # Sem registro, sem escrita (SC-002): a escrita acontece num sistema externo, fora de qualquer transação.
            logger.exception("auditoria indisponível; tool de escrita '%s' não executada", entry.tool.name)
            return self._finish(call.name, entry, _Outcome(status="error", content="", error=AUDIT_UNAVAILABLE))
        result = self._finish(call.name, entry, await self._dispatch(entry, call))
        status: AuditStatus = "ok" if result.status == "ok" else "timeout" if result.status == "timeout" else "error"
        try:
            await self._audit.finish(
                record_id,
                status=status,
                result=result.text,
                at=self._clock.now(),
                attachments=tuple(attachment_info(item) for item in result.attachments),
            )
        except Exception:
            # A tentativa já está registrada como `started`; o resultado segue para o modelo.
            logger.exception("auditoria: não foi possível fechar o registro %s", record_id)
        return result


def _from_result(result: ToolResult) -> _Outcome:
    """Um `ToolResult` — de MCP ou de tool nativa — com os anexos e os gráficos fora do texto (R13, R15)."""
    content = render_value(result.content)
    status: ToolStatus = "error" if result.error is not None else "ok"
    return _Outcome(
        status=status,
        content=content,
        error=result.error,
        truncated=result.truncated,
        attachments=result.attachments,
        charts=result.charts,
    )


def _describe(error: BaseException) -> str:
    text = str(error).strip()
    first = text.splitlines()[0] if text else ""
    return f"{type(error).__name__}: {first}" if first else type(error).__name__

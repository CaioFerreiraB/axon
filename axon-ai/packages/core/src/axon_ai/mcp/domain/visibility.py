"""Quem enxerga e quem referencia cada servidor (research R3, R9, R13; FR-006). Puro.

Globais vêm de duas origens — o arquivo do operador e o armazenamento —, e o arquivo prevalece: registro armazenado com
alias que o arquivo também declara fica indisponível, com o motivo (R3). Os `~` são do dono e de mais ninguém.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from axon_ai.mcp.api import USER_PREFIX, McpServer, McpServerDraft
from axon_ai.mcp.domain.records import ConfigEntry, StdioCommand, StoredServer
from axon_ai.mcp.domain.servers import broken_view, to_view

FILE_VERSION: Final = "file"
SHADOWED: Final = "sombreado: o arquivo do operador declara o mesmo alias e prevalece"


@dataclass(frozen=True, slots=True, kw_only=True)
class Server:
    """Um servidor como o serviço o usa: a visão publicada, a definição e a versão que entra na chave do cache."""

    view: McpServer
    draft: McpServerDraft | None
    stdio: StdioCommand | None = None
    version: str

    @property
    def alias(self) -> str:
        return self.view.alias


def from_entry(entry: ConfigEntry) -> Server:
    if entry.draft is None:
        return Server(view=broken_view(entry), draft=None, version=FILE_VERSION)
    view = to_view(entry.draft, scope="global", owner=None, origin="file", stdio=entry.stdio)
    return Server(view=view, draft=entry.draft, stdio=entry.stdio, version=FILE_VERSION)


def from_stored(record: StoredServer, *, shadowed: bool = False) -> Server:
    view = to_view(
        record.draft,
        scope="global" if record.owner is None else "user",
        owner=record.owner,
        origin="registry",
        available=not shadowed,
        reason=SHADOWED if shadowed else None,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
    return Server(view=view, draft=record.draft, version=record.updated_at.isoformat())


def merge_globals(entries: Iterable[ConfigEntry], stored: Sequence[StoredServer]) -> list[Server]:
    """Arquivo + armazenamento, por alias; no mesmo alias, o do arquivo vem primeiro e o armazenado fica sombreado."""
    from_file = [from_entry(entry) for entry in entries]
    declared = {server.alias for server in from_file}
    merged = from_file + [from_stored(record, shadowed=record.alias in declared) for record in stored]
    return sorted(merged, key=lambda server: (server.alias, server.view.origin != "file"))


def usable(server: Server) -> bool:
    """Habilitado e disponível — o que entra no catálogo e o que o cliente alcança."""
    return server.view.available and server.view.enabled and server.draft is not None


def for_users(server: Server) -> bool:
    """Um global entra em Assistant de usuário só se liberado, servidor a servidor (clarificação 4)."""
    return server.view.scope == "user" or server.view.user_access


def grant_owner(assistant: str, subject: str) -> str | None:
    """Assistant de usuário (`~nome`) só resolve para o próprio dono (003); de sistema, não tem dono."""
    return subject if assistant.startswith(USER_PREFIX) else None


def is_user_alias(alias: str) -> bool:
    return alias.startswith(USER_PREFIX)

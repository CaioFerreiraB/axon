"""Registros internos da 007, puros: usados pelas regras de `domain/` e pelas portas.

Moram em `domain/` para que as regras os usem sem importar `ports.py` (a camada vai de fora para dentro); `ports.py`
os reexporta para quem implementa as portas.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from axon_ai.mcp.api import McpServerDraft
from axon_ai_contracts import JSONValue


def _frozen(mapping: Mapping[str, str]) -> Mapping[str, str]:
    return MappingProxyType(dict(mapping))


@dataclass(frozen=True, slots=True, kw_only=True)
class StdioCommand:
    """Comando de um servidor `stdio`, fixado no arquivo do operador. `secrets`: variável do filho → referência."""

    command: str
    args: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    secrets: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "args", tuple(self.args))
        object.__setattr__(self, "env", _frozen(self.env))
        object.__setattr__(self, "secrets", _frozen(self.secrets))


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfigEntry:
    """Um servidor do arquivo do operador: a definição validada, ou o problema que o deixa indisponível."""

    alias: str
    draft: McpServerDraft | None = None
    stdio: StdioCommand | None = None
    problem: str | None = None

    def __post_init__(self) -> None:
        if (self.draft is None) == (self.problem is None):
            raise ValueError("uma entrada tem definição válida ou problema, nunca os dois nem nenhum")


@dataclass(frozen=True, slots=True, kw_only=True)
class McpConfig:
    """O arquivo do operador: globais (inclusive `stdio`), hosts internos e a allowlist de hosts de destino."""

    entries: tuple[ConfigEntry, ...] = ()
    internal_hosts: frozenset[str] = frozenset()
    allowed_hosts: frozenset[str] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries))
        object.__setattr__(self, "internal_hosts", frozenset(self.internal_hosts))
        if self.allowed_hosts is not None:
            object.__setattr__(self, "allowed_hosts", frozenset(self.allowed_hosts))


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredServer:
    """Um servidor como o armazenamento o guarda: dono (`None` = global) e o rascunho validado."""

    owner: str | None
    draft: McpServerDraft
    created_at: datetime
    updated_at: datetime

    @property
    def alias(self) -> str:
        return self.draft.alias


@dataclass(frozen=True, slots=True, kw_only=True)
class RemoteTool:
    """Uma tool como o servidor a anuncia."""

    name: str
    description: str | None = None
    input_schema: Mapping[str, JSONValue] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True, kw_only=True)
class RemotePart:
    """Uma parte do resultado: texto, ou uma parte não textual (imagem, áudio, recurso).

    A imagem traz o tipo (`mime`) e os bytes (`data`); sem bytes, ela chegou inválida (R17).
    """

    kind: str
    text: str | None = None
    mime: str | None = None
    data: bytes | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class RemoteResult:
    """O resultado de uma chamada como o servidor o devolve."""

    parts: tuple[RemotePart, ...] = ()
    structured: JSONValue | None = None
    is_error: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "parts", tuple(self.parts))

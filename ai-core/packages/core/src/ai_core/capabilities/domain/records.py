"""Registros internos da 004, puros: usados pelas regras de `domain/` e pelas portas, que os reexportam."""

from __future__ import annotations

from dataclasses import dataclass

from ai_core_contracts import NamedRetriever, ToolSpec


@dataclass(frozen=True, slots=True, kw_only=True)
class PackTool:
    """Uma tool de pack como a 002 a entrega: nome já com namespace, o `ToolSpec` (nome local) e, em recuperação, o
    retriever com as coleções que declara."""

    name: str
    pack: str
    spec: ToolSpec
    retriever: NamedRetriever | None = None

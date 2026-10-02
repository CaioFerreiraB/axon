"""Conteúdo de um resultado em texto (contracts/fencing.md, "Renderização"). Puro."""

from __future__ import annotations

import json
from collections.abc import Sequence

from ai_core_contracts import Chunk


def render_value(value: object) -> str:
    """Texto como está; qualquer outro valor em JSON, com as chaves ordenadas."""
    if isinstance(value, str):
        return value
    return json.dumps(_plain(value), ensure_ascii=False, sort_keys=True, default=str)


def render_chunks(chunks: Sequence[Chunk]) -> str:
    """Um bloco por chunk: `[documento — seção, p. N]` e o texto (princípio IX: a proveniência vai junto)."""
    if not chunks:
        return "nenhum resultado"
    return "\n\n".join(f"{_reference(chunk)}\n{chunk.text}" for chunk in chunks)


def _reference(chunk: Chunk) -> str:
    reference = chunk.document
    if chunk.section:
        reference += f" — {chunk.section}"
    if chunk.page is not None:
        reference += f", p. {chunk.page}"
    return f"[{reference}]"


def _plain(value: object) -> object:
    from collections.abc import Mapping

    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list | set | frozenset):
        return [_plain(item) for item in value]
    return value

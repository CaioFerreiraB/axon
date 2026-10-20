"""Conteúdo de um resultado em texto (contracts/fencing.md, "Renderização"). Puro.

Todo trecho entregue ao modelo traz o identificador na linha de referência,
`[documento — seção, p. N · id: <chunk_id>]`, seguido do texto (ADR-026). O formato é garantia aos packs: um prompt
pode mandar citar "o identificador que aparece depois de `id:`", e mudá-lo exige ADR. O texto do `Chunk` não muda — o
identificador é apresentação, não dado do trecho.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from axon_ai.capabilities.domain.fencing import cut
from axon_ai_contracts import Chunk

NO_RESULTS: Final = "nenhum resultado"
OMITTED_CHUNKS: Final = "\n\n[… {count} trecho(s) omitido(s): limite de resposta]"
_SEPARATOR: Final = "\n\n"


def render_value(value: object) -> str:
    """Texto como está; qualquer outro valor em JSON, com as chaves ordenadas."""
    if isinstance(value, str):
        return value
    return json.dumps(_plain(value), ensure_ascii=False, sort_keys=True, default=str)


def render_chunks(chunks: Sequence[Chunk]) -> str:
    """Um bloco por chunk: a linha de referência do ADR-026 e o texto (princípio IX: a proveniência vai junto)."""
    if not chunks:
        return NO_RESULTS
    return _SEPARATOR.join(_block(chunk) for chunk in chunks)


@dataclass(frozen=True, slots=True, kw_only=True)
class Rendered:
    """Os trechos renderizados dentro de um limite: `chunks` são só os que aparecem em `text`, na ordem."""

    text: str
    chunks: tuple[Chunk, ...]
    truncated: bool


def render_within(chunks: Sequence[Chunk], *, max_bytes: int) -> Rendered:
    """Trechos **inteiros** enquanto o texto couber em `max_bytes` (UTF-8), com a contagem dos omitidos no fim.

    Se nem o primeiro cabe inteiro, entra só ele, cortado no texto — a linha de referência e o `id` ficam. O que o
    modelo não vê não entra em `chunks`, e é isso que mantém o `generation_context` exato (005 US4, cenário 2).
    """
    if not chunks:
        return Rendered(text=NO_RESULTS, chunks=(), truncated=False)
    blocks = [_block(chunk) for chunk in chunks]
    for kept in range(len(blocks), 0, -1):
        text = _SEPARATOR.join(blocks[:kept]) + _omitted(len(blocks) - kept)
        if _size(text) <= max_bytes:
            return Rendered(text=text, chunks=tuple(chunks[:kept]), truncated=kept < len(blocks))
    omitted = _omitted(len(blocks) - 1)
    first, _ = cut(blocks[0], max_bytes=max(0, max_bytes - _size(omitted)))
    return Rendered(text=first + omitted, chunks=(chunks[0],), truncated=True)


def _block(chunk: Chunk) -> str:
    return f"{_reference(chunk)}\n{chunk.text}"


def _reference(chunk: Chunk) -> str:
    reference = chunk.document
    if chunk.section:
        reference += f" — {chunk.section}"
    if chunk.page is not None:
        reference += f", p. {chunk.page}"
    return f"[{reference} · id: {chunk.chunk_id}]"


def _omitted(count: int) -> str:
    return OMITTED_CHUNKS.format(count=count) if count else ""


def _size(text: str) -> int:
    return len(text.encode("utf-8"))


def _plain(value: object) -> object:
    from collections.abc import Mapping

    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list | set | frozenset):
        return [_plain(item) for item in value]
    return value

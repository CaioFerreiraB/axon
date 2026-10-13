"""Casamento de evidência esperada com trechos observados — puro (research R16; clarificação 2 de 2026-10-13).

Por documento (e seção, se dada), com igualdade normalizada — caixa, espaços em sequência e acentos —, para o conjunto
dourado sobreviver a mudanças de chunking; o identificador de trecho, quando dado, casa sozinho e com prioridade.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence

from ai_core.eval.api import Evidence
from ai_core_contracts import EvalChunk


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(stripped.casefold().split())


def matches(evidence: Evidence, chunk: EvalChunk) -> bool:
    if evidence.chunk_id is not None:
        return evidence.chunk_id == chunk.chunk_id
    if normalize(evidence.document) != normalize(chunk.document):
        return False
    return evidence.section is None or normalize(evidence.section) == normalize(chunk.section or "")


def first_match(evidences: Sequence[Evidence], chunks: Sequence[EvalChunk]) -> int | None:
    """A posição (1-based) do primeiro trecho que casa com alguma evidência; `None` se nenhum."""
    for position, chunk in enumerate(chunks, start=1):
        if any(matches(evidence, chunk) for evidence in evidences):
            return position
    return None


def found(evidences: Sequence[Evidence], chunks: Sequence[EvalChunk]) -> int:
    """Quantas evidências casam com algum dos trechos."""
    return sum(any(matches(evidence, chunk) for chunk in chunks) for evidence in evidences)

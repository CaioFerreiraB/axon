"""Resultado remoto → `ToolResult` (research R9; FR-008, princípio VI). Puro.

O texto vem primeiro: o protocolo pede que o servidor repita em texto o que devolve estruturado, e o SDK embrulha o
retorno de uma tool simples em `{"result": ...}`. O estruturado só vira conteúdo quando não há texto. Acima do teto, o
texto é cortado com marca visível — o modelo precisa saber que não viu tudo.
"""

from __future__ import annotations

import json
from typing import Final

from ai_core.mcp.domain.records import RemoteResult
from axon_ai_contracts import ToolResult

CUT_MARKER: Final = "\n[… resposta cortada: {shown} de {total} bytes]"


def to_tool_result(result: RemoteResult, *, max_bytes: int) -> ToolResult:
    """Sempre `untrusted`. Resultado de erro do servidor vira `error` com o mesmo texto."""
    text = _text(result)
    text, truncated = cut(text, max_bytes=max_bytes)
    return ToolResult(content=text, untrusted=True, truncated=truncated, error=text if result.is_error else None)


def failure(reason: str) -> ToolResult:
    """Falha que não veio do servidor — prazo, rede, credencial, tool fora da allowlist."""
    return ToolResult(content="", untrusted=True, error=reason)


def _text(result: RemoteResult) -> str:
    pieces: list[str] = []
    has_text = False
    for part in result.parts:
        if part.kind == "text" and part.text is not None:
            pieces.append(part.text)
            has_text = True
        else:
            pieces.append(f"[conteúdo {part.kind} omitido]")
    if not has_text and result.structured is not None:
        pieces.insert(0, json.dumps(result.structured, ensure_ascii=False, sort_keys=True, default=str))
    return "\n\n".join(pieces)


def cut(text: str, *, max_bytes: int) -> tuple[str, bool]:
    """O texto até `max_bytes` em UTF-8, contando a marca, cortado em fronteira de caractere."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, False
    marker = CUT_MARKER.format(shown="{shown}", total=len(encoded))
    budget = max(0, max_bytes - len(marker.encode("utf-8")) - 16)
    shown = encoded[:budget].decode("utf-8", errors="ignore")
    return shown + marker.format(shown=len(shown.encode("utf-8"))), True

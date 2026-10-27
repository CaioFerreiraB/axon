"""Resultado remoto → `ToolResult` (research R9; FR-008, princípio VI). Puro.

O texto vem primeiro: o protocolo pede que o servidor repita em texto o que devolve estruturado, e o SDK embrulha o
retorno de uma tool simples em `{"result": ...}`. O estruturado só vira conteúdo quando não há texto. Acima do teto, o
texto é cortado com marca visível — o modelo precisa saber que não viu tudo.

Imagens (R17, ADR-044): a do tipo aceito e no teto por anexo vai para `attachments`, fora do texto — a marca no texto
cercado é da 004; a recusada vira a marca de omissão com o motivo. O corte do texto não conta os anexos.
"""

from __future__ import annotations

import json
from typing import Final

from axon_ai.mcp.domain.records import RemotePart, RemoteResult
from axon_ai_contracts import ATTACHMENT_MIME_TYPES, Attachment, ToolResult

CUT_MARKER: Final = "\n[… resposta cortada: {shown} de {total} bytes]"


def to_tool_result(result: RemoteResult, *, max_bytes: int, max_attachment_bytes: int = 0) -> ToolResult:
    """Sempre `untrusted`. Resultado de erro do servidor vira `error` com o mesmo texto."""
    attachments: dict[str, Attachment] = {}
    text = _text(result, attachments, max_attachment_bytes=max_attachment_bytes)
    text, truncated = cut(text, max_bytes=max_bytes)
    return ToolResult(
        content=text,
        untrusted=True,
        truncated=truncated,
        error=text if result.is_error else None,
        attachments=tuple(attachments.values()),
    )


def failure(reason: str) -> ToolResult:
    """Falha que não veio do servidor — prazo, rede, credencial, tool fora da allowlist."""
    return ToolResult(content="", untrusted=True, error=reason)


def _text(result: RemoteResult, attachments: dict[str, Attachment], *, max_attachment_bytes: int) -> str:
    pieces: list[str] = []
    has_text = False
    for part in result.parts:
        if part.kind == "text" and part.text is not None:
            pieces.append(part.text)
            has_text = True
        elif part.kind == "image":
            refused = _refusal(part, max_attachment_bytes=max_attachment_bytes)
            if refused is not None:
                pieces.append(f"[conteúdo image omitido: {refused}]")
                continue
            assert part.mime is not None and part.data is not None
            attachment = Attachment(mime=part.mime, data=part.data)
            attachments.setdefault(attachment.id, attachment)
        else:
            pieces.append(f"[conteúdo {part.kind} omitido]")
    if not has_text and result.structured is not None:
        pieces.insert(0, json.dumps(result.structured, ensure_ascii=False, sort_keys=True, default=str))
    return "\n\n".join(pieces)


def _refusal(part: RemotePart, *, max_attachment_bytes: int) -> str | None:
    """O motivo de uma imagem não sair como anexo, ou `None` se ela sai."""
    if part.mime is None or part.mime.lower() not in ATTACHMENT_MIME_TYPES:
        return f"tipo {part.mime or 'desconhecido'} não aceito"
    if part.data is None:
        return "imagem inválida"
    if len(part.data) > max_attachment_bytes:
        return f"{len(part.data)} bytes acima do teto de {max_attachment_bytes}"
    return None


def cut(text: str, *, max_bytes: int) -> tuple[str, bool]:
    """O texto até `max_bytes` em UTF-8, contando a marca, cortado em fronteira de caractere."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text, False
    marker = CUT_MARKER.format(shown="{shown}", total=len(encoded))
    budget = max(0, max_bytes - len(marker.encode("utf-8")) - 16)
    shown = encoded[:budget].decode("utf-8", errors="ignore")
    return shown + marker.format(shown=len(shown.encode("utf-8"))), True

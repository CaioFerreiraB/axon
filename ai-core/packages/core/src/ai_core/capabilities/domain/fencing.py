"""A cerca (contracts/fencing.md; FR-008, FR-009; research R6, R7). Pura e determinística.

Todo resultado entra no contexto delimitado e rotulado; dentro dele, qualquer `<tool_result` ou `</tool_result` vira
entidade — um resultado não fecha a própria cerca nem abre outra. A defesa de verdade é estrutural (o catálogo não muda,
e fora dele é "tool inexistente"); a cerca é para o modelo não confundir dado com instrução.
"""

from __future__ import annotations

import re
from typing import Final

CUT_MARKER: Final = "\n[… resposta cortada: {shown} de {total} bytes]"
_FENCE_TAG: Final = re.compile(r"<(/?)(tool_result)", re.IGNORECASE)


def neutralize(content: str) -> str:
    """`<tool_result` e `</tool_result`, em qualquer caixa, viram `&lt;…`. Nada mais muda."""
    return _FENCE_TAG.sub(lambda match: f"&lt;{match.group(1)}{match.group(2)}", content)


def _attribute(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def fence(name: str, *, status: str, content: str, truncated: bool) -> str:
    opening = f'<tool_result name="{_attribute(name)}" status="{status}" truncated="{str(truncated).lower()}">'
    return f"{opening}\n{neutralize(content)}\n</tool_result>"


def cut(content: str, *, max_bytes: int) -> tuple[str, bool]:
    """O conteúdo até `max_bytes` em UTF-8, contando a marca, cortado em fronteira de caractere."""
    encoded = content.encode("utf-8")
    if len(encoded) <= max_bytes:
        return content, False
    longest = CUT_MARKER.format(shown=len(encoded), total=len(encoded))
    budget = max(0, max_bytes - len(longest.encode("utf-8")))
    shown = encoded[:budget].decode("utf-8", errors="ignore")
    return shown + CUT_MARKER.format(shown=len(shown.encode("utf-8")), total=len(encoded)), True

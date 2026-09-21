"""Serialização do stream: `data: <json>` por evento e o marcador de fim.

Só formato de linha e tipo de conteúdo — nenhuma regra sobre o que vai dentro do chunk, que é de `domain/`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any, Final

MEDIA_TYPE: Final = "text/event-stream"
DONE: Final = "data: [DONE]\n\n"


def line(chunk: Mapping[str, Any]) -> str:
    """Um evento SSE: uma linha `data:` com JSON compacto e a linha em branco que o encerra."""
    return f"data: {json.dumps(chunk, ensure_ascii=False, separators=(',', ':'))}\n\n"


async def event_stream(chunks: AsyncIterator[Mapping[str, Any]]) -> AsyncIterator[str]:
    """Serializa os chunks e fecha com o marcador de fim, para nunca deixar cliente pendurado.

    O marcador fica **fora** do `finally` de propósito: quando o cliente desconecta, o encerramento chega como
    `GeneratorExit`, e escrever numa conexão que já morreu é erro — a execução é simplesmente cancelada (005).
    """
    try:
        async for chunk in chunks:
            yield line(chunk)
    except Exception:
        # O motor promete não levantar depois do primeiro evento; se algo escapar mesmo assim, o stream fecha limpo.
        pass
    yield DONE

"""Marcação de chamada de tool no texto da geração — puro (research R50).

A geração roda sem tools. Alguns modelos, mesmo assim, escrevem a própria sintaxe de chamada como texto
(`<tool_call>nome<arg_key>…</tool_call>`); sem este filtro, ela chegaria ao usuário e ficaria no histórico, onde
ensina o próximo turno a repetir. O filtro corta cada bloco inteiro, em streaming: segura só o pedaço do fim que ainda
pode ser o começo de uma marca.
"""

from __future__ import annotations

from typing import Final

OPEN: Final = "<tool_call>"
CLOSE: Final = "</tool_call>"


def _held(text: str, tag: str) -> int:
    """Quantos caracteres do fim de `text` podem ser o começo de `tag` (nunca a marca inteira)."""
    for size in range(min(len(text), len(tag) - 1), 0, -1):
        if text.endswith(tag[:size]):
            return size
    return 0


class ToolMarkupFilter:
    """`feed` devolve o que já pode sair; `finish`, o resto. Bloco aberto e nunca fechado é descartado até o fim."""

    def __init__(self) -> None:
        self._pending = ""
        self._inside = False
        self.removed = 0

    def feed(self, text: str) -> str:
        self._pending += text
        out: list[str] = []
        while True:
            if self._inside:
                end = self._pending.find(CLOSE)
                if end < 0:
                    keep = _held(self._pending, CLOSE)
                    self._pending = self._pending[len(self._pending) - keep :]
                    return "".join(out)
                self._pending = self._pending[end + len(CLOSE) :]
                self._inside = False
                continue
            start = self._pending.find(OPEN)
            if start < 0:
                cut = len(self._pending) - _held(self._pending, OPEN)
                out.append(self._pending[:cut])
                self._pending = self._pending[cut:]
                return "".join(out)
            out.append(self._pending[:start])
            self._pending = self._pending[start + len(OPEN) :]
            self._inside = True
            self.removed += 1

    def finish(self) -> str:
        rest = "" if self._inside else self._pending
        self._pending = ""
        return rest

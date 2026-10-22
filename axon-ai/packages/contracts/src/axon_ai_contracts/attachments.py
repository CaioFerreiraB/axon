"""Anexos: imagens que uma tool devolve ou que o usuário envia (FR-028, ADR-044, research R34)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

ATTACHMENT_MIME_TYPES: frozenset[str] = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})
"""Os únicos tipos aceitos. SVG fica fora: é documento ativo e viraria vetor de XSS no cliente."""

_ALT_MAX_CHARS = 120
_ALT_REMOVED = re.compile(r"[\[\]()]")
_ALT_SPACES = re.compile(r"\s+")


def _clean_alt(alt: str | None) -> str | None:
    """O `alt` vem de fora: sem quebras de linha nem `[`, `]`, `(`, `)`, no máximo 120 caracteres (ADR-044, item 1)."""
    if alt is None:
        return None
    if not isinstance(alt, str):
        raise TypeError(f"alt precisa ser str ou None, recebido {type(alt).__name__}")
    text = _ALT_SPACES.sub(" ", _ALT_REMOVED.sub("", alt)).strip()[:_ALT_MAX_CHARS].strip()
    return text or None


@dataclass(frozen=True, slots=True, kw_only=True)
class Attachment:
    """Imagem que acompanha um resultado de tool ou uma mensagem.

    O `id` vem do conteúdo — `img-` mais os 12 primeiros hexadecimais do SHA-256 dos bytes —, então a mesma imagem tem o
    mesmo id em qualquer lugar, inclusive quando volta pelo histórico do cliente. O `alt` é dado não confiável e sai
    limpo da construção.
    """

    mime: str
    data: bytes = field(repr=False)
    alt: str | None = None
    id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.mime, str) or self.mime.lower() not in ATTACHMENT_MIME_TYPES:
            raise ValueError(f"mime fora da lista de anexos: {self.mime!r} (esperado {sorted(ATTACHMENT_MIME_TYPES)})")
        if not isinstance(self.data, bytes):
            raise TypeError(f"data precisa ser bytes, recebido {type(self.data).__name__}")
        if not self.data:
            raise ValueError("data não pode ser vazio")
        object.__setattr__(self, "mime", self.mime.lower())
        object.__setattr__(self, "alt", _clean_alt(self.alt))
        object.__setattr__(self, "id", "img-" + hashlib.sha256(self.data).hexdigest()[:12])

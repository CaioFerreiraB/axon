"""Redação de credenciais no trace (spec 009 FR-002, research R7).

Duas camadas: nenhum tipo de evento tem campo onde um segredo caiba, e o que é texto livre — hoje a mensagem de erro —
passa por aqui antes de sair do processo. Módulo puro: sem I/O, sem relógio, idempotente.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Final

from ai_core_contracts import JSONValue

REDACTED: Final = "«redigido»"
"""Marcador que substitui o valor sensível."""

MAX_TEXT: Final = 2000
"""Tamanho máximo de texto livre; o excedente é truncado com marca."""

SENSITIVE_NAMES: Final = frozenset(
    {
        "authorization",
        "api-key",
        "apikey",
        "token",
        "access-token",
        "refresh-token",
        "secret",
        "password",
        "passwd",
        "cookie",
        "set-cookie",
        "private-key",
    }
)
"""Nomes cujo valor nunca é registrado. A comparação normaliza maiúsculas, `-` e `_`."""

_NAMES_PATTERN: Final = "|".join(
    sorted((name.replace("-", "[-_]?") for name in SENSITIVE_NAMES), key=len, reverse=True)
)
_DELIMITED: Final = r"[^\s'\"&,;}\)]+"
"""Um valor de credencial termina no primeiro espaço, aspa ou delimitador de estrutura."""

_BEARER: Final = re.compile(rf"\b(bearer)\s+{_DELIMITED}", re.IGNORECASE)
_ASSIGNMENT: Final = re.compile(rf"\b({_NAMES_PATTERN})(\s*[=:]\s*)('|\"|)({_DELIMITED})", re.IGNORECASE)
_URL_CREDENTIAL: Final = re.compile(r"(://[^/\s:@]+:)([^/\s@]+)(@)")


def _normalize(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def is_sensitive(name: str) -> bool:
    """Se o valor guardado sob este nome deve ser redigido."""
    return _normalize(name) in SENSITIVE_NAMES


def _truncate(text: str) -> str:
    if len(text) <= MAX_TEXT:
        return text
    return f"{text[:MAX_TEXT]}… [truncado: {len(text) - MAX_TEXT} caracteres]"


def redact_text(text: str) -> str:
    """Substitui padrões de credencial em texto livre e trunca texto longo."""
    redacted = _BEARER.sub(rf"\1 {REDACTED}", text)
    redacted = _ASSIGNMENT.sub(rf"\1\2\3{REDACTED}", redacted)
    redacted = _URL_CREDENTIAL.sub(rf"\1{REDACTED}\3", redacted)
    return _truncate(redacted)


def redact_value(value: JSONValue) -> JSONValue:
    """Percorre a estrutura: valor de chave sensível vira marcador; texto livre é redigido e truncado."""
    if isinstance(value, Mapping):
        return {key: REDACTED if is_sensitive(str(key)) else redact_value(item) for key, item in value.items()}
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [redact_value(item) for item in value]
    return value

"""Nomes de função na API da OpenAI: só `[a-zA-Z0-9_-]`, até 64 caracteres (ADR-023).

As tools do core têm namespace com ponto (`demo.eco`, `generic.calculate` — 004). Na ida, o adapter troca cada nome que
não cabe por um apelido determinístico e sem colisão; na volta, desfaz. Puro.
"""

from __future__ import annotations

import hashlib
import re
from typing import Final

_ALLOWED: Final = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_INVALID: Final = re.compile(r"[^a-zA-Z0-9_-]")
_PREFIX: Final = 55
"""Prefixo legível; o resto é `_` mais 8 hexadecimais do hash — 64 caracteres no máximo."""


def function_name(name: str) -> str:
    """O próprio nome quando cabe; senão, `<prefixo legível>_<8 hex do sha256 do nome>`."""
    if _ALLOWED.match(name):
        return name
    readable = _INVALID.sub("_", name)[:_PREFIX] or "tool"
    digest = hashlib.sha256(name.encode()).hexdigest()[:8]
    return f"{readable}_{digest}"

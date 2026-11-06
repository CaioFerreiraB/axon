"""Formatos do pseudônimo nos autores (incremento 9.7, ADR-059; research R53).

Repetidos aqui de propósito: a 009 é consumida por quase todos os módulos e não importa a 003 nem a 012 — que têm as
mesmas formas (`SUBJECT_PATTERN` no `api.py` da 003; `PSEUDONYM_PATTERN` no da 003 e no domínio da 012).
"""

from __future__ import annotations

import re
from typing import Final

SUBJECT_PATTERN: Final = re.compile(r"(user|svc):\S+")
"""Identificador de Principal: `user:<id>` ou `svc:<id>`."""

PSEUDONYM_PATTERN: Final = re.compile(r"deleted:[0-9a-f]{16}")
"""O pseudônimo de uma conta apagada (ADR-059 item 2)."""

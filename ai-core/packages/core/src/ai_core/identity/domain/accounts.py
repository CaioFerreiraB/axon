"""Regras de cadastro e a proteção do grupo de administração (FR-010, FR-011, FR-012)."""

from __future__ import annotations

import re
from collections.abc import Collection
from typing import Final

PASSWORD_ALPHABET: Final = "abcdefghjkmnpqrstuvwxyz23456789"
"""Sem `0`/`o`, `1`/`l`/`i`: a senha temporária é ditada ou copiada à mão (R10). 20 de 31 símbolos ≈ 99 bits."""
TEMPORARY_PASSWORD_PATTERN: Final = re.compile(rf"[{PASSWORD_ALPHABET}]{{4}}(-[{PASSWORD_ALPHABET}]{{4}}){{4}}")

PROTECTED_LAST_ADMIN = "o grupo de administração precisa manter ao menos um membro ativo"
PROTECTED_DELETE = "o grupo de administração não pode ser apagado"


def leaves_admin_group_empty(*, before: Collection[str], after: Collection[str]) -> bool:
    """A operação tira o último membro ativo do grupo de administração.

    Só vale quando havia alguém: numa instalação sem admin, cadastrar outras contas não é bloqueado — o admin inicial
    vem da linha de comando ou das variáveis da instalação (FR-018).
    """
    return bool(before) and not after


def missing_groups(wanted: Collection[str], existing: Collection[str]) -> tuple[str, ...]:
    return tuple(sorted(set(wanted) - set(existing)))


def group_password(text: str) -> str:
    """20 símbolos em grupos de 4 com hífen: `abcd-efgh-jkmn-pqrs-tuvw`."""
    return "-".join(text[start : start + 4] for start in range(0, len(text), 4))

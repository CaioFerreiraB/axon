"""Regras de cadastro, a proteção do grupo de administração (FR-010, FR-011, FR-012), o pseudônimo de uma conta
apagada (ADR-059) e o que um ator que não administra não pode fazer (ADR-057, item 4; FR-034)."""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable
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


# --- apagamento (ADR-058, ADR-059; research R28) ----------------------------------------------------------------------

PSEUDONYM_PATTERN: Final = re.compile(r"deleted:[0-9a-f]{16}")
"""`deleted:` + 16 hexadecimais: nunca casa com um nome de usuário (que não tem `:`) nem com um subject."""


def pseudonym_of(uuid: str) -> str:
    """O pseudônimo de uma conta apagada, tirado de um uuid aleatório — nunca do nome, que é adivinhável."""
    digits = uuid.replace("-", "").lower()
    if len(digits) < 16 or any(char not in "0123456789abcdef" for char in digits[:16]):
        raise ValueError("uuid sem 16 hexadecimais")
    return f"deleted:{digits[:16]}"


# --- o ator que não administra (research R31) -------------------------------------------------------------------------
# Cada função devolve o campo recusado, ou `None` quando a operação não toca o grupo de administração
# nem uma conta dele.


def escalation_create(groups: Collection[str], *, admin_group: str) -> str | None:
    """Cadastrar alguém já no grupo de administração."""
    return "groups" if admin_group in groups else None


def escalation_target(target_groups: Collection[str], *, admin_group: str) -> str | None:
    """Qualquer escrita sobre uma conta que está no grupo de administração."""
    return "username" if admin_group in target_groups else None


def escalation_groups(before: Collection[str], after: Collection[str], *, admin_group: str) -> str | None:
    """Alterar os grupos de uma conta de modo a pô-la ou tirá-la do grupo de administração."""
    return "groups" if (admin_group in before) != (admin_group in after) else None


def escalation_membership(group: str, target_groups: Collection[str], *, admin_group: str) -> str | None:
    """Pôr ou tirar um grupo de uma conta: o de administração, ou numa conta que está nele."""
    if group == admin_group:
        return "group"
    return escalation_target(target_groups, admin_group=admin_group)


def escalation_members(group: str, changed_members: Iterable[Collection[str]], *, admin_group: str) -> str | None:
    """Definir membros: os do grupo de administração, ou pondo ou tirando uma conta que está nele."""
    if group == admin_group:
        return "name"
    return "members" if any(admin_group in groups for groups in changed_members) else None

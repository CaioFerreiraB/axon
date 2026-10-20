"""Nomes, e-mails, senhas e o identificador do login (FR-001, FR-002, FR-003, FR-012; research R10)."""

from __future__ import annotations

from typing import Literal

from axon_ai.identity.api import EMAIL_MAX, EMAIL_PATTERN, PASSWORD_MAX, PASSWORD_MIN, USERNAME_PATTERN

type IdentifierKind = Literal["username", "email"]


def is_username(value: str) -> bool:
    """Usuário e grupo seguem o mesmo padrão: minúsculas, sem `@`, até 64 caracteres."""
    return bool(USERNAME_PATTERN.fullmatch(value))


def normalize_email(value: str) -> str:
    return value.strip().lower()


def is_email(value: str) -> bool:
    """Para um e-mail **já normalizado**."""
    return len(value) <= EMAIL_MAX and bool(EMAIL_PATTERN.fullmatch(value))


def password_problem(password: str) -> str | None:
    """Motivo pelo qual a senha não serve, ou `None`. Conta códigos Unicode; sem regra de composição."""
    if len(password) < PASSWORD_MIN:
        return f"A senha precisa ter pelo menos {PASSWORD_MIN} caracteres."
    if len(password) > PASSWORD_MAX:
        return f"A senha pode ter no máximo {PASSWORD_MAX} caracteres."
    return None


def read_identifier(raw: str) -> tuple[IdentifierKind, str]:
    """O campo "Usuário ou e-mail": com `@` é e-mail (normalizado); sem, é usuário (sem espaços, minúsculo)."""
    value = raw.strip()
    if "@" in value:
        return "email", normalize_email(value)
    return "username", value.lower()

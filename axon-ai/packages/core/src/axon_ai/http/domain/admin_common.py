"""Leitura estrita dos corpos da superfície de administração (contracts/admin-api.md; research R44).

Puro. Campo desconhecido, tipo errado ou campo obrigatório ausente viram `AdminInvalid(field)`, que a tabela de erros
devolve como `422 invalid_field` com `param` — a console mostra o motivo junto ao campo (013 FR-001).
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any


class AdminInvalid(ValueError):
    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


def only(body: Mapping[str, Any], allowed: Collection[str]) -> None:
    unknown = sorted(set(body) - set(allowed))
    if unknown:
        raise AdminInvalid(f"{unknown[0]}: campo desconhecido", field=unknown[0])


def required(body: Mapping[str, Any], field: str) -> Any:
    if field not in body:
        raise AdminInvalid(f"{field}: obrigatório", field=field)
    return body[field]


def version_of(body: Mapping[str, Any], *, nullable: bool = False) -> int | None:
    """`version` obrigatória (R45); `null` só onde o recurso pode ainda não existir."""
    value = required(body, "version")
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        expected = "um inteiro não negativo" + (" ou null" if nullable else "")
        raise AdminInvalid(f"version: precisa ser {expected}", field="version")
    return value


def text(body: Mapping[str, Any], field: str, *, optional: bool = False) -> str | None:
    if field not in body or body[field] is None:
        if optional:
            return None
        raise AdminInvalid(f"{field}: obrigatório", field=field)
    value = body[field]
    if not isinstance(value, str):
        raise AdminInvalid(f"{field}: precisa ser texto", field=field)
    return value


def flag(body: Mapping[str, Any], field: str, *, optional: bool = False) -> bool | None:
    if field not in body or body[field] is None:
        if optional:
            return None
        raise AdminInvalid(f"{field}: obrigatório", field=field)
    value = body[field]
    if not isinstance(value, bool):
        raise AdminInvalid(f"{field}: precisa ser true ou false", field=field)
    return value


def texts(body: Mapping[str, Any], field: str, *, optional: bool = False) -> list[str] | None:
    if field not in body:
        if optional:
            return None
        raise AdminInvalid(f"{field}: obrigatório", field=field)
    value = body[field]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise AdminInvalid(f"{field}: precisa ser uma lista de textos", field=field)
    return value


def money(body: Mapping[str, Any], field: str) -> Decimal:
    """Dinheiro chega como string decimal (nunca número de ponto flutuante)."""
    value = required(body, field)
    if not isinstance(value, str):
        raise AdminInvalid(f'{field}: precisa ser uma string decimal, como "0.15"', field=field)
    try:
        return Decimal(value.strip())
    except InvalidOperation:
        raise AdminInvalid(f"{field}: não é um número decimal", field=field) from None


def day(value: object, field: str) -> date:
    if not isinstance(value, str):
        raise AdminInvalid(f"{field}: precisa ser uma data AAAA-MM-DD", field=field)
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise AdminInvalid(f"{field}: data inválida (AAAA-MM-DD)", field=field) from None


def decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")

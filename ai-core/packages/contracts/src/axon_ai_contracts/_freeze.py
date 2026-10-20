"""Valores JSON, congelamento em profundidade e checagens de construção dos value objects (research R11).

Todo value object dos contratos congela o que recebe: dois produtores com os mesmos dados — a fixture e o motor —
geram objetos iguais, e nenhum hook consegue mutar o que recebeu.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from types import MappingProxyType
from typing import cast

type JSONValue = str | int | float | bool | Sequence[JSONValue] | Mapping[str, JSONValue] | None


def freeze(value: object) -> object:
    """Congela contêineres em profundidade; folhas (inclusive `str` e `bytes`) voltam inalteradas."""
    if isinstance(value, str | bytes):
        return value
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(freeze(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(freeze(item) for item in value)
    return value


def freeze_mapping[V](value: Mapping[str, V]) -> Mapping[str, V]:
    """Cópia somente-leitura e congelada em profundidade de um mapeamento."""
    if not isinstance(value, Mapping):
        raise TypeError(f"esperado um mapeamento, recebido {type(value).__name__}")
    return cast("Mapping[str, V]", freeze(value))


def freeze_sequence[T](value: Iterable[T]) -> tuple[T, ...]:
    """Tupla com os itens congelados; rejeita texto e mapeamento, que não são sequências de itens aqui."""
    if isinstance(value, str | bytes | Mapping):
        raise TypeError(f"esperada uma sequência de itens, recebido {type(value).__name__}")
    return tuple(cast("T", freeze(item)) for item in value)


def empty_mapping[V]() -> Mapping[str, V]:
    """Default dos campos de mapeamento dos value objects."""
    return MappingProxyType({})


def is_json_value(value: object) -> bool:
    """Verdadeiro se o valor é serializável em JSON: escalares, sequências e mapeamentos com chave `str`."""
    if value is None or isinstance(value, str | bool | int | float):
        return True
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and is_json_value(item) for key, item in value.items())
    if isinstance(value, list | tuple):
        return all(is_json_value(item) for item in value)
    return False


def require_non_empty(field: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} não pode ser vazio")


def require_aware(field: str, value: object) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{field} precisa ser datetime, recebido {type(value).__name__}")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} precisa ter fuso horário (datetime aware)")

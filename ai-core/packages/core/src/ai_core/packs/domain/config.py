"""Configuração de pack contra o `config_schema` do manifest (FR-004, research R6) e checagem de valores JSON.

Validação pura com `jsonschema`: sem `$ref` remoto (nenhum registry de recursos é passado ao validador).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jsonschema import Draft202012Validator, exceptions, validators

from axon_ai_contracts import JSONValue


def is_json(value: object) -> bool:
    """Verdadeiro se o valor é serializável em JSON: escalares, sequências e mapeamentos com chave `str`."""
    if value is None or isinstance(value, str | bool | int | float):
        return True
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and is_json(item) for key, item in value.items())
    if isinstance(value, list | tuple):
        return all(is_json(item) for item in value)
    return False


def _plain(value: object) -> Any:
    """Mapeamentos congelados viram `dict` e tuplas viram `list`, como o `jsonschema` espera."""
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    return value


def config_error(config: Mapping[str, JSONValue], schema: Mapping[str, JSONValue] | None) -> str | None:
    """Mensagem que nomeia o campo inválido (US1 cenário 3), ou `None` se a configuração conforma."""
    if schema is None:
        return None
    plain_schema = _plain(schema)
    validator_class = validators.validator_for(plain_schema, default=Draft202012Validator)
    try:
        validator_class.check_schema(plain_schema)
    except exceptions.SchemaError as error:
        return f"config_schema inválido: {error.message}"
    first = exceptions.best_match(validator_class(plain_schema).iter_errors(_plain(config)))
    if first is None:
        return None
    path = ".".join(str(part) for part in first.absolute_path) or "(raiz)"
    return f"configuração inválida em '{path}': {first.message}"

"""Conferência de esquema e validação de argumentos (research R5; FR-006). Pura.

`jsonschema` (Draft 2020-12), sem registry de recursos: `$ref` remoto não é buscado — vira erro. Para tools de MCP o
esquema vem de terceiro e os argumentos vêm do modelo: expressão regular de um servidor externo sobre texto escolhido
pelo modelo é ReDoS, e nenhum prazo assíncrono interrompe CPU. Por isso o validador delas ignora `pattern` e
`patternProperties`; o servidor valida de novo do lado dele.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

from jsonschema import Draft202012Validator, exceptions, validators

from ai_core_contracts import JSONValue

_UntrustedValidator: Final[Any] = validators.extend(  # type: ignore[no-untyped-call]
    Draft202012Validator, validators={"pattern": None, "patternProperties": None}
)


def _plain(value: object) -> Any:
    """Mapeamentos congelados viram `dict` e tuplas viram `list`, como o `jsonschema` espera."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_plain(item) for item in value]
    return value


def check_schema(schema: Mapping[str, JSONValue]) -> str | None:
    """`None` se o esquema é válido; senão o motivo."""
    try:
        Draft202012Validator.check_schema(_plain(schema))
    except exceptions.SchemaError as error:
        return f"esquema inválido: {error.message}"
    return None


def validate_arguments(
    schema: Mapping[str, JSONValue], arguments: Mapping[str, JSONValue], *, trusted: bool
) -> str | None:
    """`None` se os argumentos cumprem o esquema; senão o motivo, nomeando o caminho."""
    validator_class = Draft202012Validator if trusted else _UntrustedValidator
    validator = validator_class(_plain(schema))
    try:
        error = next(iter(sorted(validator.iter_errors(_plain(arguments)), key=lambda e: list(e.absolute_path))), None)
    except Exception as failure:  # $ref que não resolve, esquema que quebra na validação
        return f"argumentos não puderam ser validados: {type(failure).__name__}"
    if error is None:
        return None
    path = "/".join(str(part) for part in error.absolute_path) or "(raiz)"
    return f"argumento inválido em {path}: {error.message}"

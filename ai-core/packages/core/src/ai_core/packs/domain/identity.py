"""Identidade de um pack lida da classe, antes de instanciar (FR-002, FR-017)."""

from __future__ import annotations


def read_identity(entry_name: str, target: object) -> tuple[str, str] | str:
    """`(name, contract_version)` lidos como atributos de classe, ou a mensagem de erro.

    O nome do entry point precisa ser igual ao `name` da classe — é esse nome que identifica o pack na configuração
    do operador e no Pack Registry.
    """
    if not isinstance(target, type):
        return f"entry point '{entry_name}' não aponta para uma classe"
    values: dict[str, str] = {}
    for attribute in ("name", "contract_version"):
        value = getattr(target, attribute, None)
        if not isinstance(value, str):
            return f"classe sem atributo de classe '{attribute}'"
        values[attribute] = value
    if values["name"] != entry_name:
        return f"entry point '{entry_name}' aponta para classe com name '{values['name']}'"
    return values["name"], values["contract_version"]

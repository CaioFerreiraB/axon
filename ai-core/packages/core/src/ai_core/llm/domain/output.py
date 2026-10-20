"""Restrição de formato por papel: a camada 1 da FR-005 (research R17). Pura — sem I/O, sem relógio, sem trace.

O papel `controller` decide a próxima ação, e quem consome lê essa decisão como dado: sem esquema, nada garante a forma.
Por isso nenhuma chamada dele sai sem um `response_format` de esquema — por construção, não por disciplina de quem chama
(SC-003). `json_object` não basta: garante JSON, não a ação.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from ai_core.llm.api import ModelRole
from axon_ai_contracts import JSONValue

CONSTRAINED_ROLES: Final = frozenset({"controller"})
"""Papéis cuja saída precisa vir restrita por esquema."""

REQUIREMENT: Final = "o papel 'controller' exige response_format com esquema (json_schema com 'schema')"


def constraint_problem(role: ModelRole, response_format: Mapping[str, JSONValue] | None) -> str | None:
    """O motivo da recusa, ou None quando a chamada pode seguir. Não altera o formato recebido."""
    if role not in CONSTRAINED_ROLES:
        return None
    if response_format is None:
        return f"{REQUIREMENT}; nenhum foi enviado"
    kind = response_format.get("type")
    if kind != "json_schema":
        return f"{REQUIREMENT}; recebido: {kind!s}"
    body = response_format.get("json_schema")
    if not isinstance(body, Mapping) or not isinstance(body.get("schema"), Mapping):
        return f"{REQUIREMENT}; recebido: json_schema sem 'schema' como objeto"
    return None

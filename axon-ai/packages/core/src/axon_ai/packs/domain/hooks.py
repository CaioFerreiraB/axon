"""Regras puras do Pack Hooks: recorte da Turn View por pack, merge raso da fatia e encadeamento de validators.

FR-009 e research R7/R8: cada pack vê só a própria fatia e as de `depends_on`; o retorno de `prepare_context` entra
por merge raso na fatia do pack; cada validator vê a resposta e as citações deixadas pelos anteriores.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence

from axon_ai.packs.api import Slices
from axon_ai.packs.domain.config import is_json
from axon_ai_contracts import JSONValue, TurnView, ValidationResult


def scope_view(view: TurnView, pack: str, depends_on: Sequence[str], slices: Slices) -> TurnView:
    """Turn View do pack: `own_slice` é a fatia dele; `dependency_slices`, só as de `depends_on`."""
    return dataclasses.replace(
        view,
        own_slice=slices.get(pack, {}),
        dependency_slices={dependency: slices.get(dependency, {}) for dependency in depends_on},
    )


def merge_slice(current: Mapping[str, JSONValue], update: object) -> dict[str, JSONValue]:
    """Merge raso: chaves devolvidas substituem as da fatia; as ausentes permanecem. `TypeError` se não for JSON."""
    if not isinstance(update, Mapping):
        raise TypeError(f"devolveu {type(update).__name__}; esperado a atualização da fatia (mapeamento)")
    if not is_json(update):
        raise TypeError("devolveu atualização com valores que não são JSON")
    merged: dict[str, JSONValue] = dict(current)
    merged.update(update)
    return merged


def apply_validation(view: TurnView, result: ValidationResult) -> TurnView:
    """A view que o próximo validator vê: resposta e citações trocadas só quando o resultado as traz."""
    if result.answer is None and result.citations is None:
        return view
    return dataclasses.replace(
        view,
        answer=result.answer if result.answer is not None else view.answer,
        citations=result.citations if result.citations is not None else view.citations,
    )

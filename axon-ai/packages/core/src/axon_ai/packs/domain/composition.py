"""Regras de `PackRegistry.compose`: packs existentes, habilitados, sem repetição e dependência antes do
dependente (FR-008, research R10). O runtime nunca reordena packs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from axon_ai.packs.api import PackEntry, PackStatus

_UNAVAILABLE = {PackStatus.DISABLED: "está desabilitado", PackStatus.ERROR: "está em erro"}


def composition_error(
    pack_names: Sequence[str], entries: Mapping[str, PackEntry]
) -> tuple[str, tuple[str, ...]] | None:
    """`(mensagem, packs envolvidos)` se a lista não pode ser composta, ou `None`."""
    seen: set[str] = set()
    for name in pack_names:
        if name in seen:
            return f"o pack '{name}' aparece mais de uma vez na composição", (name,)
        seen.add(name)
        entry = entries.get(name)
        if entry is None:
            return f"o pack '{name}' não está instalado", (name,)
        if entry.status is not PackStatus.ENABLED:
            detail = f": {entry.error}" if entry.error else ""
            return f"o pack '{name}' {_UNAVAILABLE[entry.status]}{detail}", (name,)
    position = {name: index for index, name in enumerate(pack_names)}
    for name in pack_names:
        capabilities = entries[name].capabilities
        for dependency in capabilities.depends_on if capabilities is not None else ():
            if dependency not in position:
                return (
                    f"o pack '{name}' depende da fatia de '{dependency}', que não está na composição",
                    (name, dependency),
                )
            if position[dependency] > position[name]:
                return (
                    f"o pack '{name}' depende da fatia de '{dependency}', que precisa vir antes dele na composição",
                    (name, dependency),
                )
    return None

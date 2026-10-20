"""Dependências de fatia na carga: indisponibilidade em cascata e ciclos (FR-010, research R9)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from axon_ai.packs.api import PackStatus

_STATE = {PackStatus.DISABLED: "está desabilitado", PackStatus.ERROR: "está em erro"}


def _cycles(graph: Mapping[str, Sequence[str]]) -> dict[str, str]:
    """Mensagem de ciclo para cada pack que participa de um, com o caminho a partir dele."""
    messages: dict[str, str] = {}
    visiting: list[str] = []
    done: set[str] = set()

    def visit(node: str) -> None:
        if node in done:
            return
        if node in visiting:
            cycle = visiting[visiting.index(node) :]
            for index, member in enumerate(cycle):
                rotated = [*cycle[index:], *cycle[:index], member]
                messages.setdefault(member, "dependência circular: " + " → ".join(rotated))
            return
        visiting.append(node)
        for dependency in graph.get(node, ()):
            if dependency in graph:
                visit(dependency)
        visiting.pop()
        done.add(node)

    for node in sorted(graph):
        visit(node)
    return messages


def dependency_errors(status: Mapping[str, PackStatus], depends_on: Mapping[str, Sequence[str]]) -> dict[str, str]:
    """Packs habilitados que passam a erro por dependência indisponível (em cascata) ou por ciclo.

    `status` traz todo pack conhecido; `depends_on`, as dependências dos packs habilitados.
    """
    graph = {name: tuple(deps) for name, deps in depends_on.items() if status.get(name) is PackStatus.ENABLED}
    errors = _cycles(graph)
    current = dict(status)
    for name in errors:
        current[name] = PackStatus.ERROR
    changed = True
    while changed:
        changed = False
        for name in sorted(graph):
            if name in errors:
                continue
            for dependency in graph[name]:
                dependency_status = current.get(dependency)
                if dependency_status is PackStatus.ENABLED:
                    continue
                reason = "não está instalado" if dependency_status is None else _STATE[dependency_status]
                errors[name] = f"depende de '{dependency}', que {reason}"
                current[name] = PackStatus.ERROR
                changed = True
                break
    return dict(sorted(errors.items()))

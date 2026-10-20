"""Dependência de `axon-ai-contracts` declarada pelo pack cabe na faixa derivada (FR-018, compatibility.md §5).

`check_contracts_requirement` é pura. `find_distribution` e `read_requirements` são a borda fina que lê metadados.
"""

from __future__ import annotations

import importlib.metadata
import re
from collections.abc import Sequence

from axon_ai_contracts.compat import InvalidSpecifier, InvalidVersion, Version, VersionRange, derive_range
from axon_ai_contracts.declaration import ContractIssue

_DISTRIBUTION = "axon-ai-contracts"
_REQUIREMENT_RE = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)\s*(?:\[[^\]]*\])?\s*(?P<rest>.*)$"
)

type _Bound = tuple[Version, bool] | None  # (versão, inclusivo) ou sem limite


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _bump_prefix(release: tuple[int, ...]) -> Version:
    return Version(release=(*release[:-1], release[-1] + 1))


def _interval(version_range: VersionRange) -> tuple[_Bound, _Bound]:
    """Intervalo [inferior, superior] do conjunto; `!=` só remove pontos e não muda a inclusão."""
    lower: _Bound = None
    upper: _Bound = None

    def raise_lower(bound: tuple[Version, bool]) -> None:
        nonlocal lower
        if lower is None or bound[0] > lower[0] or (bound[0] == lower[0] and not bound[1]):
            lower = bound

    def cut_upper(bound: tuple[Version, bool]) -> None:
        nonlocal upper
        if upper is None or bound[0] < upper[0] or (bound[0] == upper[0] and not bound[1]):
            upper = bound

    for operator, operand in version_range.clauses:
        if operator == "!=":
            continue
        if operand.endswith(".*"):
            prefix = tuple(int(part) for part in operand[:-2].split("."))
            raise_lower((Version(release=prefix), True))
            cut_upper((_bump_prefix(prefix), False))
            continue
        version = Version.parse(operand)
        if operator in (">=", "~="):
            raise_lower((version, True))
        if operator == ">":
            raise_lower((version, False))
        if operator == "<=":
            cut_upper((version, True))
        if operator == "<":
            cut_upper((version, False))
        if operator == "==":
            raise_lower((version, True))
            cut_upper((version, True))
        if operator == "~=":
            cut_upper((_bump_prefix(version.release[:-1]), False))
    return lower, upper


def _is_empty(lower: _Bound, upper: _Bound) -> bool:
    if lower is None or upper is None:
        return False
    return lower[0] > upper[0] or (lower[0] == upper[0] and not (lower[1] and upper[1]))


def _within(declared: VersionRange, derived: VersionRange) -> str:
    """'subset', 'wider' ou 'disjoint' do conjunto declarado em relação à faixa derivada."""
    lower, upper = _interval(declared)
    floor, ceiling = _interval(derived)
    assert floor is not None and ceiling is not None
    both_lower = floor if lower is None or floor[0] > lower[0] else lower
    both_upper = ceiling if upper is None or ceiling[0] < upper[0] else upper
    if _is_empty(lower, upper) or _is_empty(both_lower, both_upper):
        return "disjoint"
    below = lower is None or lower[0] < floor[0] or (lower[0] == floor[0] and lower[1] and not floor[1])
    above = upper is None or upper[0] > ceiling[0] or (upper[0] == ceiling[0] and upper[1] and not ceiling[1])
    return "wider" if below or above else "subset"


def check_contracts_requirement(requirements: Sequence[str], contract_version: str) -> tuple[ContractIssue, ...]:
    """Aponta a dependência de axon-ai-contracts que aceita versões fora da faixa derivada da contract_version."""
    derived = derive_range(contract_version)
    issues: list[ContractIssue] = []
    found = False
    for requirement in requirements:
        body, _, marker = requirement.partition(";")
        if "extra" in marker:
            continue
        match = _REQUIREMENT_RE.match(body)
        if match is None or _normalize(match["name"]) != _DISTRIBUTION:
            continue
        found = True
        rest = match["rest"].strip()
        subject = f"requirement:{requirement.strip()}"
        if rest.startswith("@"):
            issues.append(
                ContractIssue(
                    code="distribution.direct_reference",
                    message=f"dependência de axon-ai-contracts por referência direta, sem faixa; declare {derived}",
                    subject=subject,
                )
            )
            continue
        specifier = rest.strip("() ")
        if not specifier:
            issues.append(
                ContractIssue(
                    code="distribution.range_too_wide",
                    message=f"dependência de axon-ai-contracts sem faixa aceita qualquer versão; declare {derived}",
                    subject=subject,
                )
            )
            continue
        try:
            declared = VersionRange.parse(specifier)
        except (InvalidSpecifier, InvalidVersion):
            issues.append(
                ContractIssue(
                    code="distribution.unsupported_specifier",
                    message=f"especificador fora do subconjunto suportado: {specifier!r}; declare {derived}",
                    subject=subject,
                )
            )
            continue
        relation = _within(declared, derived)
        if relation == "wider":
            issues.append(
                ContractIssue(
                    code="distribution.range_too_wide",
                    message=f"a dependência {declared} aceita versões fora da faixa derivada {derived}",
                    subject=subject,
                )
            )
        elif relation == "disjoint":
            issues.append(
                ContractIssue(
                    code="distribution.range_disjoint",
                    message=f"a dependência {declared} não tem nenhuma versão em comum com a faixa derivada {derived}",
                    subject=subject,
                )
            )
    if not found:
        issues.append(
            ContractIssue(
                code="distribution.missing_requirement",
                message=f"o pacote do pack não declara dependência de axon-ai-contracts; declare {derived}",
                subject="distribution",
            )
        )
    return tuple(issues)


def find_distribution(pack: object) -> str | None:
    """Distribuição instalada que contém o pacote de topo do pack, ou `None`."""
    top_level = type(pack).__module__.split(".")[0]
    distributions = importlib.metadata.packages_distributions().get(top_level, [])
    return sorted(distributions)[0] if distributions else None


def read_requirements(distribution: str) -> tuple[str, ...]:
    return tuple(importlib.metadata.requires(distribution) or ())

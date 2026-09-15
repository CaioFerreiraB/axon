"""Versões, faixas e compatibilidade de `ai-core-contracts` (FR-016, FR-018, ADR-014).

Subconjunto do PEP 440 implementado só com a stdlib (research R5): o FR-001 proíbe depender de `packaging`. A gramática,
os especificadores e as mensagens estão em specs/001-core-contracts/contracts/compatibility.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from ai_core_contracts._version import __version__

type ChangeKind = Literal["none", "additive", "breaking"]
type BumpKind = Literal["none", "patch", "minor", "major"]

_NUMBER = r"(?:0|[1-9]\d*)"
_VERSION_RE = re.compile(
    rf"^(?P<release>{_NUMBER}(?:\.{_NUMBER})*)"
    rf"(?:(?P<pre_letter>a|b|rc)(?P<pre_number>{_NUMBER}))?"
    rf"(?:\.dev(?P<dev>{_NUMBER}))?$"
)
_CONTRACT_VERSION_RE = re.compile(rf"^{_NUMBER}\.{_NUMBER}(?:\.{_NUMBER})?$")
_WILDCARD_RE = re.compile(rf"^{_NUMBER}(?:\.{_NUMBER})*$")
_CLAUSE_RE = re.compile(r"^(?P<op>~=|==|!=|<=|>=|<|>)\s*(?P<version>\S+)$")
_PRE_ORDER = {"a": 0, "b": 1, "rc": 2}
_OPERATOR_RANK = {">=": 0, ">": 0, "~=": 1, "==": 2, "!=": 3, "<=": 4, "<": 4}


class InvalidVersion(ValueError):
    """Versão fora do subconjunto do PEP 440 aceito pelos contratos."""


class InvalidSpecifier(ValueError):
    """Especificador de versão malformado ou fora do subconjunto suportado."""


@dataclass(frozen=True, slots=True, eq=False)
class Version:
    """Versão do subconjunto do PEP 440: release, pré-release (`a`, `b`, `rc`) e `.dev` opcionais."""

    release: tuple[int, ...]
    pre: tuple[str, int] | None = None
    dev: int | None = None

    @classmethod
    def parse(cls, text: str) -> Version:
        match = _VERSION_RE.match(text) if isinstance(text, str) else None
        if match is None:
            raise InvalidVersion(f"versão inválida: {text!r}")
        pre = None
        if match["pre_letter"] is not None:
            pre = (match["pre_letter"], int(match["pre_number"]))
        dev = int(match["dev"]) if match["dev"] is not None else None
        return cls(release=tuple(int(part) for part in match["release"].split(".")), pre=pre, dev=dev)

    @property
    def is_prerelease(self) -> bool:
        return self.pre is not None or self.dev is not None

    @property
    def base_release(self) -> tuple[int, ...]:
        """Release sem os zeros à direita — a forma usada nas comparações (`0.1 == 0.1.0`)."""
        release = self.release
        while len(release) > 1 and release[-1] == 0:
            release = release[:-1]
        return release

    def _key(self) -> tuple[tuple[int, ...], tuple[int, int], float]:
        if self.pre is None:
            pre_key = (-1, 0) if self.dev is not None else (3, 0)
        else:
            pre_key = (_PRE_ORDER[self.pre[0]], self.pre[1])
        dev_key = float(self.dev) if self.dev is not None else float("inf")
        return (self.base_release, pre_key, dev_key)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() == other._key()

    def __hash__(self) -> int:
        return hash(self._key())

    def __lt__(self, other: Version) -> bool:
        return self._key() < other._key()

    def __le__(self, other: Version) -> bool:
        return self._key() <= other._key()

    def __gt__(self, other: Version) -> bool:
        return self._key() > other._key()

    def __ge__(self, other: Version) -> bool:
        return self._key() >= other._key()

    def __str__(self) -> str:
        text = ".".join(str(part) for part in self.release)
        if self.pre is not None:
            text += f"{self.pre[0]}{self.pre[1]}"
        if self.dev is not None:
            text += f".dev{self.dev}"
        return text


def parse_contract_version(text: str) -> Version:
    """`contract_version` de pack: só `X.Y` ou `X.Y.Z`, sem pré-release nem dev."""
    if not isinstance(text, str) or not _CONTRACT_VERSION_RE.match(text):
        raise InvalidVersion(f"contract_version inválida: {text!r} (esperado X.Y ou X.Y.Z)")
    return Version.parse(text)


def _as_version(value: str | Version) -> Version:
    return value if isinstance(value, Version) else Version.parse(value)


def _prefix_matches(version: Version, prefix: tuple[int, ...]) -> bool:
    padded = version.release + (0,) * max(0, len(prefix) - len(version.release))
    return padded[: len(prefix)] == prefix


def _clause_matches(operator: str, operand: str, version: Version) -> bool:
    if operand.endswith(".*"):
        prefix = tuple(int(part) for part in operand[:-2].split("."))
        matched = _prefix_matches(version, prefix)
        return matched if operator == "==" else not matched
    target = Version.parse(operand)
    if operator == "==":
        return version == target
    if operator == "!=":
        return version != target
    if operator == ">=":
        return version >= target
    if operator == "<=":
        return version <= target
    if operator == ">":
        return version > target
    if operator == "<":
        if not version < target:
            return False
        # PEP 440: `<V` não aceita pré-release do próprio V quando V é final.
        return not (not target.is_prerelease and version.is_prerelease and version.base_release == target.base_release)
    # "~=": >=V e mesmo prefixo de release sem o último componente.
    return version >= target and _prefix_matches(version, target.release[:-1])


def _parse_clause(text: str) -> tuple[str, str]:
    match = _CLAUSE_RE.match(text.strip())
    if match is None:
        raise InvalidSpecifier(f"especificador inválido: {text.strip()!r}")
    operator, operand = match["op"], match["version"]
    if operand.endswith(".*"):
        if operator not in ("==", "!=") or not _WILDCARD_RE.match(operand[:-2]):
            raise InvalidSpecifier(f"curinga inválido: {text.strip()!r}")
        return operator, operand
    try:
        version = Version.parse(operand)
    except InvalidVersion as error:
        raise InvalidSpecifier(f"especificador inválido: {text.strip()!r}") from error
    if operator == "~=" and len(version.release) < 2:
        raise InvalidSpecifier(f"'~=' exige ao menos dois componentes: {text.strip()!r}")
    return operator, str(version)


@dataclass(frozen=True, slots=True)
class VersionRange:
    """Conjunto de cláusulas combinadas com E, como `>=0.1,<0.2`."""

    clauses: tuple[tuple[str, str], ...]

    @classmethod
    def parse(cls, text: str) -> VersionRange:
        parts = [part for part in text.split(",")] if isinstance(text, str) else []
        if not parts or any(not part.strip() for part in parts):
            raise InvalidSpecifier(f"faixa inválida: {text!r}")
        clauses = [_parse_clause(part) for part in parts]
        clauses.sort(key=lambda clause: _OPERATOR_RANK[clause[0]])
        return cls(clauses=tuple(clauses))

    def contains(self, version: str | Version) -> bool:
        return self.violated_by(version) is None

    def violated_by(self, version: str | Version) -> str | None:
        """Primeira cláusula violada, na ordem canônica (limite inferior antes do superior), ou `None`."""
        candidate = _as_version(version)
        for operator, operand in self.clauses:
            if not _clause_matches(operator, operand, candidate):
                return f"{operator}{operand}"
        return None

    def __str__(self) -> str:
        return ",".join(f"{operator}{operand}" for operator, operand in self.clauses)


def derive_range(contract_version: str) -> VersionRange:
    """Faixa aceita por um pack, derivada da `contract_version` (FR-018, ADR-014)."""
    version = parse_contract_version(contract_version)
    major, minor = version.release[0], version.release[1]
    upper = f"0.{minor + 1}" if major == 0 else f"{major + 1}"
    return VersionRange(clauses=((">=", str(version)), ("<", upper)))


@dataclass(frozen=True, slots=True, kw_only=True)
class Compatibility:
    """Resultado da regra de compatibilidade entre a versão instalada e o que o pack exige."""

    ok: bool
    installed: str
    required: str
    violated: str | None
    message: str | None


def check_compatibility(requirement: str | VersionRange, *, installed: str | None = None) -> Compatibility:
    """Compara a versão instalada com a `contract_version` do pack (faixa derivada) ou com uma faixa explícita."""
    installed_text = installed if installed is not None else __version__
    installed_version = Version.parse(installed_text)
    if isinstance(requirement, VersionRange):
        version_range = requirement
    else:
        text = requirement.strip()
        version_range = VersionRange.parse(text) if text[:1] in "<>=!~" and text else derive_range(text)
    violated = version_range.violated_by(installed_version)
    message = None if violated is None else f"requer ai-core-contracts{violated}, instalado {installed_text}"
    return Compatibility(
        ok=violated is None,
        installed=installed_text,
        required=str(version_range),
        violated=violated,
        message=message,
    )


def _release3(version: Version) -> tuple[int, int, int]:
    padded = (*version.release, 0, 0, 0)
    return padded[0], padded[1], padded[2]


def removal_version(since: str) -> str:
    """Primeira versão em que um símbolo depreciado em `since` pode sair (janela de uma série, ADR-014)."""
    major, minor, _ = _release3(Version.parse(since))
    return f"0.{minor + 1}.0" if major == 0 else f"{major + 1}.0.0"


def required_bump(change: ChangeKind, *, current: str) -> BumpKind:
    """Bump exigido por uma mudança, a partir da versão `current` (a da última tag): tabela §8."""
    if change == "none":
        return "none"
    major, _, _ = _release3(Version.parse(current))
    if change == "additive":
        return "patch" if major == 0 else "minor"
    return "minor" if major == 0 else "major"


def declared_bump(previous: str, current: str) -> BumpKind:
    """Bump que a versão `current` representa em relação a `previous`."""
    before, after = _release3(Version.parse(previous)), _release3(Version.parse(current))
    if after[0] > before[0]:
        return "major"
    if after[0] == before[0] and after[1] > before[1]:
        return "minor"
    if after[:2] == before[:2] and after[2] > before[2]:
        return "patch"
    return "none"

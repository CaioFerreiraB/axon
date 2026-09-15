"""Teste diferencial: o subconjunto do PEP 440 coincide com `packaging` (oráculo só de dev; research R5; T035)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st
from packaging.specifiers import SpecifierSet
from packaging.version import Version as PackagingVersion

from ai_core_contracts import Version, VersionRange

RELEASES = st.lists(st.integers(0, 4), min_size=1, max_size=3)
PRE = st.none() | st.tuples(st.sampled_from(["a", "b", "rc"]), st.integers(0, 2))
DEV = st.none() | st.integers(0, 2)


def _render(release: list[int], pre: tuple[str, int] | None, dev: int | None) -> str:
    text = ".".join(str(part) for part in release)
    if pre is not None:
        text += f"{pre[0]}{pre[1]}"
    if dev is not None:
        text += f".dev{dev}"
    return text


VERSIONS = st.builds(_render, RELEASES, PRE, DEV)


@st.composite
def clauses(draw: st.DrawFn) -> str:
    operator = draw(st.sampled_from(["==", "!=", ">=", "<=", ">", "<", "~="]))
    if operator in ("==", "!=") and draw(st.booleans()):
        return f"{operator}{_render(draw(RELEASES), None, None)}.*"
    if operator == "~=":
        release = draw(st.lists(st.integers(0, 4), min_size=2, max_size=3))
        return f"~={_render(release, draw(PRE), None)}"
    return f"{operator}{draw(VERSIONS)}"


SPECIFIERS = st.lists(clauses(), min_size=1, max_size=3).map(",".join)


@settings(max_examples=600, deadline=None)
@given(VERSIONS, VERSIONS)
def test_ordering_matches_packaging(left: str, right: str) -> None:
    ours, theirs = (Version.parse(left), Version.parse(right)), (PackagingVersion(left), PackagingVersion(right))
    assert (ours[0] < ours[1]) == (theirs[0] < theirs[1])
    assert (ours[0] == ours[1]) == (theirs[0] == theirs[1])


@settings(max_examples=1500, deadline=None)
@given(SPECIFIERS, VERSIONS)
def test_contains_matches_packaging(specifier: str, version: str) -> None:
    expected = SpecifierSet(specifier).contains(version, prereleases=True)
    assert VersionRange.parse(specifier).contains(version) is expected, (specifier, version)

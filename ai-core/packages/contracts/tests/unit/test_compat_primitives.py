from __future__ import annotations

from itertools import pairwise

import pytest

from axon_ai_contracts._version import __version__
from axon_ai_contracts.compat import (
    InvalidSpecifier,
    InvalidVersion,
    Version,
    VersionRange,
    check_compatibility,
    derive_range,
    parse_contract_version,
)


@pytest.mark.parametrize(
    ("text", "release", "pre", "dev"),
    [
        ("0.1", (0, 1), None, None),
        ("1.2.3", (1, 2, 3), None, None),
        ("0.2.0rc1", (0, 2, 0), ("rc", 1), None),
        ("1.0a2.dev3", (1, 0), ("a", 2), 3),
        ("2.dev0", (2,), None, 0),
    ],
)
def test_parse(text: str, release: tuple[int, ...], pre: tuple[str, int] | None, dev: int | None) -> None:
    version = Version.parse(text)
    assert (version.release, version.pre, version.dev) == (release, pre, dev)
    assert str(version) == text


@pytest.mark.parametrize("text", ["1!2.0", "1.0.post1", "1.0+local", "v1.0", "1.0-rc1", "01.0", "1.", "", "1.0 "])
def test_parse_rejects_outside_subset(text: str) -> None:
    with pytest.raises(InvalidVersion):
        Version.parse(text)


def test_ordering_follows_pep440() -> None:
    ordered = ["1.0.dev1", "1.0a1.dev1", "1.0a1", "1.0b2", "1.0rc1", "1.0", "1.0.1", "1.1"]
    versions = [Version.parse(text) for text in ordered]
    assert versions == sorted(versions)
    assert all(a < b for a, b in pairwise(versions))


def test_trailing_zeros_are_ignored() -> None:
    assert Version.parse("0.1") == Version.parse("0.1.0")
    assert hash(Version.parse("0.1")) == hash(Version.parse("0.1.0.0"))


@pytest.mark.parametrize("text", ["0.1", "0.1.3", "1.2", "10.20.30"])
def test_contract_version_accepts(text: str) -> None:
    assert str(parse_contract_version(text)) == text


@pytest.mark.parametrize("text", ["1", "0.1rc1", "0.1.dev0", "1.2.3.4", "x.y"])
def test_contract_version_rejects(text: str) -> None:
    with pytest.raises(InvalidVersion):
        parse_contract_version(text)


def test_range_parse_and_canonical_order() -> None:
    version_range = VersionRange.parse("<0.2, >=0.1")
    assert str(version_range) == ">=0.1,<0.2"
    assert version_range.contains("0.1.7")
    assert not version_range.contains("0.2.0")
    assert version_range.violated_by("0.0.9") == ">=0.1"


@pytest.mark.parametrize(
    ("spec", "version", "expected"),
    [
        ("==0.1", "0.1.0", True),
        ("==0.1.*", "0.1.9", True),
        ("==0.1.*", "0.2", False),
        ("!=0.1.*", "0.2", True),
        ("~=0.1.3", "0.1.9", True),
        ("~=0.1.3", "0.2.0", False),
        ("<0.2", "0.2.0rc1", False),
        ("<0.2rc2", "0.2rc1", True),
        (">0.1", "0.1.1", True),
        ("<=0.1", "0.1.0", True),
    ],
)
def test_range_operators(spec: str, version: str, expected: bool) -> None:
    assert VersionRange.parse(spec).contains(version) is expected


@pytest.mark.parametrize("spec", ["", "0.1", "===0.1", ">=", "~=1", ">=0.1.*", "==1.0a1.*", ">=0.1,"])
def test_range_rejects(spec: str) -> None:
    with pytest.raises(InvalidSpecifier):
        VersionRange.parse(spec)


def test_derive_range() -> None:
    assert str(derive_range("0.1")) == ">=0.1,<0.2"
    assert str(derive_range("1.2")) == ">=1.2,<2"


def test_check_compatibility_uses_installed_default() -> None:
    result = check_compatibility("0.2")
    assert result.ok
    assert result.installed == __version__
    assert result.message is None


def test_check_compatibility_message_names_violated_clause() -> None:
    result = check_compatibility("0.2", installed="0.1.4")
    assert not result.ok
    assert result.violated == ">=0.2"
    assert result.required == ">=0.2,<0.3"
    assert result.message == "requer axon-ai-contracts>=0.2, instalado 0.1.4"


def test_check_compatibility_accepts_explicit_range() -> None:
    assert check_compatibility(">=0.1,<1", installed="0.9.0").ok
    assert check_compatibility(VersionRange.parse(">=0.1"), installed="0.3").ok

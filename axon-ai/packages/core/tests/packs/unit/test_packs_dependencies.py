"""Grafo de dependências entre fatias: indisponibilidade em cascata e ciclos (FR-010, research R9; T019)."""

from __future__ import annotations

from axon_ai.packs.api import PackStatus
from axon_ai.packs.domain.dependencies import dependency_errors

E, D, X = PackStatus.ENABLED, PackStatus.DISABLED, PackStatus.ERROR


def test_packs_without_dependencies_are_untouched() -> None:
    assert dependency_errors({"a": E, "b": E}, {"a": (), "b": ()}) == {}


def test_unavailable_dependency() -> None:
    status = {"a": E, "b": D, "c": X, "d": E}
    depends_on = {"a": ("b",), "d": ("c",)}
    assert dependency_errors(status, depends_on) == {
        "a": "depende de 'b', que está desabilitado",
        "d": "depende de 'c', que está em erro",
    }
    assert dependency_errors({"a": E}, {"a": ("fantasma",)}) == {"a": "depende de 'fantasma', que não está instalado"}


def test_cascade_until_fixed_point() -> None:
    status = {"a": E, "b": E, "c": X}
    depends_on = {"a": ("b",), "b": ("c",)}
    assert dependency_errors(status, depends_on) == {
        "a": "depende de 'b', que está em erro",
        "b": "depende de 'c', que está em erro",
    }


def test_cycles() -> None:
    status = {"a": E, "b": E, "c": E, "livre": E}
    depends_on = {"a": ("b",), "b": ("c",), "c": ("a",), "livre": ()}
    assert dependency_errors(status, depends_on) == {
        "a": "dependência circular: a → b → c → a",
        "b": "dependência circular: b → c → a → b",
        "c": "dependência circular: c → a → b → c",
    }


def test_pack_depending_on_a_cycle_fails_in_cascade() -> None:
    status = {"a": E, "b": E, "fora": E}
    depends_on = {"a": ("b",), "b": ("a",), "fora": ("a",)}
    assert dependency_errors(status, depends_on)["fora"] == "depende de 'a', que está em erro"

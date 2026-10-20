"""T025 — conformidade da porta `SecretResolver` da 006 (contracts/ports.md, "Fase 3"; research R21).

Roda contra os dois adapters: o de ambiente, sobre um dicionário injetado, e o em memória.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest

from axon_ai.llm.adapters.secrets import EnvSecretResolver, InMemorySecretResolver
from axon_ai.llm.ports import SecretResolver

pytestmark = pytest.mark.us3

Make = Callable[[Mapping[str, str]], SecretResolver]

NAME = "AXON_OPENAI_API_KEY"


def memory(values: Mapping[str, str]) -> SecretResolver:
    return InMemorySecretResolver(values)


def environment(values: Mapping[str, str]) -> SecretResolver:
    return EnvSecretResolver({**values, "PATH": "/usr/bin", "AXON_DATABASE_URL": "postgresql://u:senha@db/x"})


ADAPTERS = pytest.mark.parametrize("make", [memory, environment], ids=["memoria", "ambiente"])


@ADAPTERS
def test_nome_presente_devolve_o_valor_exato(make: Make) -> None:
    assert make({NAME: " sk-teste "}).resolve(NAME) == " sk-teste "


@ADAPTERS
def test_nome_ausente_devolve_none(make: Make) -> None:
    assert make({}).resolve(NAME) is None


@ADAPTERS
@pytest.mark.parametrize("value", ["", "   "])
def test_valor_vazio_conta_como_ausente(make: Make, value: str) -> None:
    assert make({NAME: value}).resolve(NAME) is None


@ADAPTERS
def test_nome_vazio_devolve_none_sem_levantar(make: Make) -> None:
    assert make({"": "x"}).resolve("") is None


def test_ambiente_por_default_le_o_processo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(NAME, "sk-do-processo")
    assert EnvSecretResolver().resolve(NAME) == "sk-do-processo"

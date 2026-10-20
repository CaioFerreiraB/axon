"""T021 — conformidade da porta `SecretResolver` (research R7): memória e ambiente."""

from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest

from axon_ai.mcp.adapters.memory import InMemorySecretResolver
from axon_ai.mcp.adapters.secrets_env import EnvSecretResolver
from axon_ai.mcp.ports import SecretResolver

pytestmark = pytest.mark.us2

Make = Callable[[Mapping[str, str]], SecretResolver]


def memory(values: Mapping[str, str]) -> SecretResolver:
    return InMemorySecretResolver(values)


def environment(values: Mapping[str, str]) -> SecretResolver:
    env = {f"AXON_MCP_SECRET_{ref.upper()}": value for ref, value in values.items()}
    env |= {"AXON_DATABASE_URL": "postgresql://u:senha@db/x", "PATH": "/usr/bin", "AXON_DEV_API_KEY": "axn_x"}
    return EnvSecretResolver(env)


ADAPTERS = pytest.mark.parametrize("make", [memory, environment], ids=["memoria", "ambiente"])


@ADAPTERS
def test_referencia_presente_devolve_o_valor(make: Make) -> None:
    assert make({"financeiro_token": "s3cr3t"}).resolve("financeiro_token") == "s3cr3t"


@ADAPTERS
def test_referencia_ausente_devolve_none(make: Make) -> None:
    assert make({}).resolve("financeiro_token") is None


@ADAPTERS
@pytest.mark.parametrize("ref", ["Financeiro", "a-b", "_x", "a" * 65, "", "x y", "../etc"])
def test_referencia_fora_da_gramatica_devolve_none(make: Make, ref: str) -> None:
    assert make({ref: "valor"}).resolve(ref) is None


@pytest.mark.parametrize("ref", ["database_url", "dev_api_key", "path", "axon_ai_database_url"])
def test_segredos_do_core_e_do_processo_nao_sao_alcancaveis(ref: str) -> None:
    """Um global não aponta para `AXON_DATABASE_URL`: o prefixo é fixo (R7)."""
    resolver = environment({})
    assert resolver.resolve(ref) is None

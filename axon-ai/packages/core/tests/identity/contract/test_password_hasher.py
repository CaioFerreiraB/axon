"""T016 — `PasswordHasher`: argon2id real e o rápido de memória na mesma suíte (FR-002, FR-003; R2)."""

from __future__ import annotations

import time
from typing import Any

import pytest

from axon_ai.identity.adapters.memory import FastPasswordHasher
from axon_ai.identity.adapters.passwords import Argon2PasswordHasher


@pytest.fixture(params=["argon2", "memoria"])
def hasher(request: pytest.FixtureRequest) -> Any:
    if request.param == "memoria":
        return FastPasswordHasher()
    # parâmetros reduzidos: a suíte confere o contrato, não o custo do perfil de produção
    return Argon2PasswordHasher(time_cost=1, memory_cost=8 * 1024, parallelism=1)


async def test_verifica_a_senha_certa_e_recusa_a_errada(hasher: Any) -> None:
    stored = await hasher.hash("senha-forte-da-ana")
    assert "senha-forte-da-ana" not in stored
    assert await hasher.verify(stored, "senha-forte-da-ana") is True
    assert await hasher.verify(stored, "senha-forte-da-bia") is False
    assert await hasher.verify("lixo", "senha-forte-da-ana") is False
    assert hasher.needs_rehash(stored) is False
    assert hasher.needs_rehash("lixo") is True
    await hasher.dummy_verify("qualquer coisa")


async def test_argon2_e_argon2id_com_o_perfil_padrao() -> None:
    real = Argon2PasswordHasher()
    stored = await real.hash("senha-forte-da-ana")
    assert stored.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    weaker = Argon2PasswordHasher(time_cost=1, memory_cost=8 * 1024, parallelism=1)
    assert real.needs_rehash(await weaker.hash("x" * 12)) is True


async def test_hash_ficticio_custa_o_mesmo_que_uma_verificacao_real() -> None:
    real = Argon2PasswordHasher()
    stored = await real.hash("senha-forte-da-ana")
    start = time.perf_counter()
    await real.verify(stored, "senha-errada-qualquer")
    verify = time.perf_counter() - start
    start = time.perf_counter()
    await real.dummy_verify("senha-errada-qualquer")
    dummy = time.perf_counter() - start
    assert 0.5 < dummy / verify < 2.0

"""T045 — conformidade da porta `RateCounterStore` (contracts/ports.md): janela deslizante por par, atômica."""

from __future__ import annotations

from datetime import timedelta

from assistants_testkit import T0

from ai_core.assistants.adapters.rate_memory import InMemoryRateCounterStore

MINUTO = timedelta(seconds=60)
PAR = ("user:ana", "geral")


async def test_rate_limite_concessoes_por_janela_e_a_seguinte_recusada() -> None:
    store = InMemoryRateCounterStore()
    for _ in range(20):
        assert (await store.acquire(PAR, now=T0, limit=20, window=MINUTO)).allowed
    recusa = await store.acquire(PAR, now=T0 + timedelta(seconds=15), limit=20, window=MINUTO)
    assert not recusa.allowed
    assert recusa.retry_after == timedelta(seconds=45)


async def test_rate_pares_sao_independentes() -> None:
    store = InMemoryRateCounterStore()
    assert (await store.acquire(PAR, now=T0, limit=1, window=MINUTO)).allowed
    assert not (await store.acquire(PAR, now=T0, limit=1, window=MINUTO)).allowed
    assert (await store.acquire(("user:bia", "geral"), now=T0, limit=1, window=MINUTO)).allowed
    assert (await store.acquire(("user:ana", "outro"), now=T0, limit=1, window=MINUTO)).allowed


async def test_rate_recusa_nao_consome_e_a_janela_libera_depois() -> None:
    store = InMemoryRateCounterStore()
    assert (await store.acquire(PAR, now=T0, limit=1, window=MINUTO)).allowed
    for segundos in (10, 20, 30):
        assert not (await store.acquire(PAR, now=T0 + timedelta(seconds=segundos), limit=1, window=MINUTO)).allowed
    assert (await store.acquire(PAR, now=T0 + MINUTO, limit=1, window=MINUTO)).allowed

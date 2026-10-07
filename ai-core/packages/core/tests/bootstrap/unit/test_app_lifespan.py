"""T027 — o ciclo de vida da app: pool de serviço e tarefas periódicas (research R13, R14)."""

from __future__ import annotations

import asyncio

from fastapi import FastAPI

from ai_core.bootstrap.wiring import PeriodicTask, app_lifespan


class FakePool:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def open(self, *, wait: bool = False, timeout: float = 30.0) -> None:
        self.events.append("open")

    async def close(self) -> None:
        self.events.append("close")


async def test_abre_o_pool_no_inicio_e_fecha_no_fim() -> None:
    pool = FakePool()
    async with app_lifespan(database=pool, tasks=())(FastAPI()):
        assert pool.events == ["open"]
    assert pool.events == ["open", "close"]


async def test_sem_banco_o_ciclo_de_vida_so_cuida_das_tarefas() -> None:
    async with app_lifespan(database=None, tasks=())(FastAPI()):
        pass


async def test_a_tarefa_roda_no_inicio_e_a_cada_intervalo_e_e_cancelada_no_fim() -> None:
    """No início: um processo que reinicia antes do intervalo não pode adiar a expiração para sempre."""
    runs: list[int] = []

    async def expire() -> int:
        runs.append(len(runs))
        return 0

    async with app_lifespan(database=None, tasks=(PeriodicTask(name="expirar", interval=0.01, run=expire),))(FastAPI()):
        await asyncio.sleep(0.05)
        assert len(runs) >= 2
    count = len(runs)
    await asyncio.sleep(0.03)
    assert len(runs) == count, "cancelada no fim do ciclo de vida"


async def test_falha_numa_execucao_nao_mata_a_tarefa() -> None:
    runs: list[int] = []

    async def flaky() -> None:
        runs.append(1)
        if len(runs) == 1:
            raise RuntimeError("banco piscou")

    async with app_lifespan(database=None, tasks=(PeriodicTask(name="instavel", interval=0.01, run=flaky),))(FastAPI()):
        await asyncio.sleep(0.05)
    assert len(runs) >= 2


async def test_o_pool_fecha_mesmo_quando_a_app_falha() -> None:
    pool = FakePool()
    try:
        async with app_lifespan(database=pool, tasks=())(FastAPI()):
            raise RuntimeError("falha servindo")
    except RuntimeError:
        pass
    assert pool.events == ["open", "close"]

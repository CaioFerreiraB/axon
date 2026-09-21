"""T011 — conformidade da porta `Clock` (contracts/ports.md)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from graph_testkit import REFERENCE_TIME

from ai_core.graph.adapters.clock import FixedClock, SystemClock


def test_os_dois_adapters_devolvem_instante_com_timezone() -> None:
    for clock in (SystemClock(), FixedClock(REFERENCE_TIME)):
        agora = clock.now()
        assert agora.tzinfo is not None
        assert agora.utcoffset() is not None


def test_cronometro_nunca_anda_para_tras() -> None:
    clock = SystemClock()
    leituras = [clock.monotonic() for _ in range(5)]
    assert leituras == sorted(leituras)


def test_relogio_fixo_repete_a_mesma_data() -> None:
    clock = FixedClock(REFERENCE_TIME)
    assert [clock.now() for _ in range(3)] == [REFERENCE_TIME] * 3


def test_duas_execucoes_com_o_mesmo_relogio_recebem_a_mesma_data() -> None:
    """011 US3 cenário 2: com o relógio fixado, toda execução tem a mesma data de referência."""
    clock = FixedClock(REFERENCE_TIME)
    primeira, segunda = clock.now(), clock.now()
    assert primeira == segunda == REFERENCE_TIME


def test_cronometro_programado_repete_a_ultima_leitura() -> None:
    clock = FixedClock(REFERENCE_TIME, readings=[1.0, 1.25])
    assert [clock.monotonic() for _ in range(3)] == [1.0, 1.25, 1.25]


def test_relogio_fixo_exige_data_com_timezone() -> None:
    with pytest.raises(ValueError):
        FixedClock(datetime(2026, 9, 21))


def test_relogio_fixo_exige_ao_menos_uma_leitura() -> None:
    with pytest.raises(ValueError):
        FixedClock(datetime(2026, 9, 21, tzinfo=UTC), readings=[])

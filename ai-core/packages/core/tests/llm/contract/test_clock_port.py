"""T011 — conformidade da porta `Clock` (contracts/ports.md): relógio de sistema e programado."""

from __future__ import annotations

import pytest

from ai_core.llm.adapters.clock import MonotonicClock, ScriptedClock


def test_relogio_do_sistema_nunca_anda_para_tras() -> None:
    clock = MonotonicClock()
    leituras = [clock.monotonic() for _ in range(5)]
    assert leituras == sorted(leituras)


def test_relogio_programado_devolve_a_sequencia() -> None:
    clock = ScriptedClock([1.0, 1.25, 4.0])
    assert [clock.monotonic() for _ in range(3)] == [1.0, 1.25, 4.0]


def test_diferenca_do_relogio_programado_e_exatamente_a_programada() -> None:
    """É o que torna `duration_ms` verificável na suíte do seam."""
    clock = ScriptedClock([1.0, 1.25])
    assert clock.monotonic() - clock.monotonic() == pytest.approx(-0.25)


def test_relogio_programado_repete_o_ultimo_valor_quando_a_sequencia_acaba() -> None:
    clock = ScriptedClock([2.0])
    assert [clock.monotonic() for _ in range(3)] == [2.0, 2.0, 2.0]


def test_relogio_programado_exige_ao_menos_um_valor() -> None:
    with pytest.raises(ValueError):
        ScriptedClock([])

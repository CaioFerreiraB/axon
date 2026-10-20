"""T045 — janela deslizante do orçamento (research R9): regra pura, com instantes explícitos."""

from __future__ import annotations

from datetime import timedelta

from assistants_testkit import T0

from axon_ai.assistants.domain.rate import sliding_window

MINUTO = timedelta(seconds=60)


def test_rate_concede_ate_o_limite_e_recusa_o_seguinte_com_espera_exata() -> None:
    instantes: tuple = ()
    for segundo in range(3):
        decisao, instantes = sliding_window(instantes, now=T0 + timedelta(seconds=segundo), limit=3, window=MINUTO)
        assert decisao.allowed
    decisao, instantes = sliding_window(instantes, now=T0 + timedelta(seconds=10), limit=3, window=MINUTO)
    assert not decisao.allowed
    assert decisao.retry_after == timedelta(seconds=50)  # o mais antigo (T0) sai da janela em T0 + 60


def test_rate_recusado_nao_registra_instante() -> None:
    _, instantes = sliding_window((T0, T0), now=T0 + timedelta(seconds=1), limit=2, window=MINUTO)
    assert instantes == (T0, T0)


def test_rate_concessao_volta_quando_o_mais_antigo_sai_da_janela() -> None:
    instantes = (T0, T0 + timedelta(seconds=30))
    recusa, _ = sliding_window(instantes, now=T0 + timedelta(seconds=59), limit=2, window=MINUTO)
    assert not recusa.allowed and recusa.retry_after == timedelta(seconds=1)
    volta, restantes = sliding_window(instantes, now=T0 + timedelta(seconds=60), limit=2, window=MINUTO)
    assert volta.allowed
    assert restantes == (T0 + timedelta(seconds=30), T0 + timedelta(seconds=60))

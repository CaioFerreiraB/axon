"""T053 — bloqueio por tentativas com relógio fixo (FR-013; R11)."""

from __future__ import annotations

from datetime import timedelta

from identity_testkit import T0

from ai_core.identity.domain.attempts import (
    AttemptPolicy,
    AttemptState,
    attempt_keys,
    is_blocked,
    is_idle,
    register_failure,
)

POLICY = AttemptPolicy()


def _fail(state: AttemptState, *minutes: float) -> AttemptState:
    for minute in minutes:
        state = register_failure(state, now=T0 + timedelta(minutes=minute), policy=POLICY)
    return state


def test_cinco_falhas_em_15_minutos_bloqueiam_por_15() -> None:
    state = _fail(AttemptState(), 0, 1, 2, 3)
    assert not is_blocked(state, now=T0 + timedelta(minutes=3))
    state = _fail(state, 4)
    assert is_blocked(state, now=T0 + timedelta(minutes=4))
    assert is_blocked(state, now=T0 + timedelta(minutes=18, seconds=59))
    assert not is_blocked(state, now=T0 + timedelta(minutes=19))


def test_janela_deslizante() -> None:
    state = _fail(AttemptState(), 0, 1, 2, 3, 15.5)
    # a falha do minuto 0 já saiu da janela: são 4 nos últimos 15 minutos
    assert not is_blocked(state, now=T0 + timedelta(minutes=15.5))
    assert len(state.failures) == 4


def test_tentativa_bloqueada_nao_estende_o_bloqueio() -> None:
    state = _fail(AttemptState(), 0, 1, 2, 3, 4)
    locked = state.locked_until
    state = _fail(state, 10)
    assert state.locked_until == locked


def test_estado_ocioso_pode_sair() -> None:
    state = _fail(AttemptState(), 0)
    assert not is_idle(state, now=T0 + timedelta(minutes=14), policy=POLICY)
    assert is_idle(state, now=T0 + timedelta(minutes=15), policy=POLICY)


def test_chaves_por_usuario_e_por_origem() -> None:
    assert attempt_keys(identifier="ana", source="203.0.113.7") == ("id:ana", "ip:203.0.113.7")
    assert attempt_keys(identifier="", source=None) == ()

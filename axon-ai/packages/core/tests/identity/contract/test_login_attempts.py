"""T053 — conformidade da porta `LoginAttempts` contra o adapter de memória, o único (processo único, R11)."""

from __future__ import annotations

from datetime import timedelta

from identity_testkit import T0

from axon_ai.identity.adapters.memory import InMemoryLoginAttempts


def test_bloqueia_qualquer_chave_e_reset_libera_so_a_pedida() -> None:
    attempts = InMemoryLoginAttempts()
    for minute in range(5):
        attempts.fail(["id:ana", "ip:1.1.1.1"], now=T0 + timedelta(minutes=minute))
    now = T0 + timedelta(minutes=5)
    assert attempts.blocked(["id:ana"], now=now)
    assert attempts.blocked(["id:bia", "ip:1.1.1.1"], now=now)
    assert not attempts.blocked(["id:bia", "ip:2.2.2.2"], now=now)
    attempts.reset(["id:ana"])
    assert not attempts.blocked(["id:ana"], now=now)
    assert attempts.blocked(["ip:1.1.1.1"], now=now)
    assert not attempts.blocked(["ip:1.1.1.1"], now=T0 + timedelta(minutes=19))


def test_estados_ociosos_sao_descartados_quando_o_mapa_cresce() -> None:
    attempts = InMemoryLoginAttempts()
    attempts._PRUNE_AT = 3  # type: ignore[misc]
    for index in range(5):
        attempts.fail([f"ip:{index}"], now=T0)
    attempts.fail(["ip:novo"], now=T0 + timedelta(hours=1))
    assert set(attempts._states) == {"ip:novo"}

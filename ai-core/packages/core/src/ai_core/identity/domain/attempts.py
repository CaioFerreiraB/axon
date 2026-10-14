"""Bloqueio por tentativas (FR-013; research R11): 5 falhas em 15 min bloqueiam por 15 min, por chave.

A chave é o usuário normalizado ou a origem; quem chama decide quais. Tentativas recusadas pelo bloqueio não contam
como falha, para o bloqueio não se estender sozinho.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True, kw_only=True)
class AttemptPolicy:
    limit: int = 5
    window: timedelta = timedelta(minutes=15)
    lockout: timedelta = timedelta(minutes=15)


@dataclass(frozen=True, slots=True, kw_only=True)
class AttemptState:
    failures: tuple[datetime, ...] = ()
    locked_until: datetime | None = None


def is_blocked(state: AttemptState, *, now: datetime) -> bool:
    return state.locked_until is not None and now < state.locked_until


def register_failure(state: AttemptState, *, now: datetime, policy: AttemptPolicy) -> AttemptState:
    if is_blocked(state, now=now):
        return state
    recent = (*(instant for instant in state.failures if now - instant < policy.window), now)
    if len(recent) >= policy.limit:
        return AttemptState(locked_until=now + policy.lockout)
    return AttemptState(failures=recent)


def is_idle(state: AttemptState, *, now: datetime, policy: AttemptPolicy) -> bool:
    """Estado sem efeito algum — pode ser descartado."""
    return not is_blocked(state, now=now) and all(now - instant >= policy.window for instant in state.failures)


def attempt_keys(*, identifier: str | None, source: str | None) -> tuple[str, ...]:
    keys: list[str] = []
    if identifier:
        keys.append(f"id:{identifier}")
    if source:
        keys.append(f"ip:{source}")
    return tuple(keys)

"""Adapters das portas para a Fase 1: identidade anônima, identificadores e relógio.

O autenticador anônimo aceita qualquer requisição — é de **desenvolvimento**, e o nome diz isso para que a composition
root (011) o anuncie no boot e ninguém o confunda com configuração de produção. Na Fase 2 a 003 fornece o verificador
real, e nenhuma rota muda (research R1).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from ai_core.http.ports import Principal

ANONYMOUS_ID = "anonymous"


@dataclass(frozen=True, slots=True)
class DevelopmentPrincipal:
    """Principal sem autenticação de verdade. Cumpre `Principal` (spec 008)."""

    id: str = ANONYMOUS_ID


class AnonymousAuthenticator:
    """Aceita qualquer credencial, nas duas superfícies, e devolve sempre o mesmo Principal."""

    def __init__(self, principal: Principal | None = None) -> None:
        self._principal = principal or DevelopmentPrincipal()

    async def authenticate(self, *, surface: str, credential: str | None) -> Principal:
        return self._principal


class Uuid4RequestIds:
    """Identificador aleatório por requisição."""

    def next(self) -> str:
        return uuid.uuid4().hex


class SequentialRequestIds:
    """Identificadores previsíveis (`req-1`, `req-2`, …): a suíte confere o valor exato, e não o formato."""

    def __init__(self, prefix: str = "req") -> None:
        self._prefix = prefix
        self._count = 0

    def next(self) -> str:
        self._count += 1
        return f"{self._prefix}-{self._count}"


class SystemClock:
    """Relógio do processo."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()


class FixedClock:
    """Instante fixo: torna verificável o campo `created` das respostas."""

    def __init__(self, at: datetime, readings: Sequence[float] = (0.0, 1.0)) -> None:
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("o relógio fixo precisa de uma data com timezone")
        self._at = at
        self._readings = tuple(readings) or (0.0,)
        self._index = 0

    def now(self) -> datetime:
        return self._at

    def monotonic(self) -> float:
        reading = self._readings[min(self._index, len(self._readings) - 1)]
        self._index += 1
        return reading

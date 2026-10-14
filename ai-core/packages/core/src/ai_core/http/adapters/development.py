"""Adapters de desenvolvimento e de teste: identidade anônima, saúde fixa, identificadores e relógio.

O autenticador anônimo aceita qualquer requisição — é de **desenvolvimento**, e o nome diz isso para que a composition
root (011) o anuncie no boot e ninguém o confunda com configuração de produção. O verificador real é o
`AccessService` da 003; pôr autenticação real nos perfis é da passada da Fase 2 da 011 (research R13).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from ai_core.assistants.api import SCHEMES_OF_SURFACE, Principal, Scheme
from ai_core.http.ports import HealthItem, HealthReport

ANONYMOUS_SUBJECT = "user:anonymous"


class AnonymousAuthenticator:
    """Aceita qualquer credencial, nas duas superfícies, e devolve `user:anonymous` com o esquema da superfície.

    O Principal é o da 003: a ACL dos Assistants continua valendo — um Assistant com `allow: ["*"]` atende; um privado,
    não. Superfície desconhecida é recusada, como no autenticador real.
    """

    def __init__(self, subject: str = ANONYMOUS_SUBJECT, groups: frozenset[str] = frozenset()) -> None:
        self._subject = subject
        self._groups = groups

    async def authenticate(self, *, surface: str, credential: str | None) -> Principal | None:
        schemes = SCHEMES_OF_SURFACE.get(surface)
        if schemes is None:
            return None
        scheme: Scheme = "api_key" if schemes == {"api_key"} else "oidc"
        return Principal(subject=self._subject, scheme=scheme, groups=self._groups)


class StaticHealthProvider:
    """Saúde fixa, para testes e para quem ainda não tem o agregador da 011."""

    def __init__(self, *items: HealthItem) -> None:
        self._report = HealthReport(items=tuple(items))

    async def health(self) -> HealthReport:
        return self._report


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

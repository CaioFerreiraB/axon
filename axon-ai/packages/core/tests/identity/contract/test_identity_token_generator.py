"""T035 — `TokenGenerator`: o real e o sequencial de memória no mesmo formato (R10)."""

from __future__ import annotations

import re
import uuid
from typing import Any

import pytest

from axon_ai.identity.adapters.memory import SequentialTokenGenerator
from axon_ai.identity.adapters.system import SystemTokenGenerator
from axon_ai.identity.domain.accounts import TEMPORARY_PASSWORD_PATTERN
from axon_ai.identity.domain.names import password_problem


@pytest.fixture(params=["sistema", "memoria"])
def generator(request: pytest.FixtureRequest) -> Any:
    return SystemTokenGenerator() if request.param == "sistema" else SequentialTokenGenerator()


def test_formatos(generator: Any) -> None:
    token = generator.token()
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
    assert len(generator.token(48)) == 64
    assert uuid.UUID(generator.uuid())
    password = generator.password()
    assert TEMPORARY_PASSWORD_PATTERN.fullmatch(password)
    assert password_problem(password) is None
    assert generator.token() != token and generator.password() != password


def test_senha_temporaria_sem_simbolos_ambiguos() -> None:
    generator = SystemTokenGenerator()
    joined = "".join(generator.password() for _ in range(200)).replace("-", "")
    assert not set(joined) & set("0o1li")

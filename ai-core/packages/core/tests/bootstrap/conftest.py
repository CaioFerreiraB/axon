"""Fixtures dos testes da 011. As fábricas ficam em `bootstrap_testkit`."""

from __future__ import annotations

import pytest
from bootstrap_testkit import FakeServer, Recorder


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def server() -> FakeServer:
    return FakeServer()

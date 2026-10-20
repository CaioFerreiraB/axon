"""Fixtures dos testes da 006. As fábricas ficam em `llm_testkit` (mesmo padrão de `trace_testkit`)."""

from __future__ import annotations

import pytest
from llm_testkit import RecordingTraceSink

from axon_ai.llm.adapters.clock import ScriptedClock
from axon_ai.llm.adapters.fake import ScriptedProvider


@pytest.fixture
def trace() -> RecordingTraceSink:
    return RecordingTraceSink()


@pytest.fixture
def clock() -> ScriptedClock:
    """Duas leituras por chamada: 1.0 e 1.25 → 250 ms de duração, verificável no trace."""
    return ScriptedClock([1.0, 1.25])


@pytest.fixture
def provider() -> ScriptedProvider:
    return ScriptedProvider(name="ollama")

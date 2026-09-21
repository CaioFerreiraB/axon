"""Fixtures dos testes da 005. As fábricas ficam em `graph_testkit` (mesmo padrão de `llm_testkit`)."""

from __future__ import annotations

import pytest
from graph_testkit import REFERENCE_TIME, Grant, RecordingTraceSink, ScriptedHooks

from ai_core.graph.adapters.clock import FixedClock


@pytest.fixture
def trace() -> RecordingTraceSink:
    return RecordingTraceSink()


@pytest.fixture
def clock() -> FixedClock:
    """Data de referência fixa e cronômetro programado: 250 ms por execução."""
    return FixedClock(REFERENCE_TIME, readings=[1.0, 1.25])


@pytest.fixture
def grant() -> Grant:
    return Grant()


@pytest.fixture
def hooks() -> ScriptedHooks:
    return ScriptedHooks()

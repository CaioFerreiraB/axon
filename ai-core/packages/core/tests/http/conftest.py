"""Fixtures dos testes da 008. As fábricas ficam em `http_testkit`."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from graph_testkit import RecordingTraceSink
from http_testkit import app


@pytest.fixture
def trace() -> RecordingTraceSink:
    return RecordingTraceSink()


@pytest.fixture
def client(trace: RecordingTraceSink) -> Iterator[TestClient]:
    with TestClient(app(trace=trace)) as test_client:
        yield test_client

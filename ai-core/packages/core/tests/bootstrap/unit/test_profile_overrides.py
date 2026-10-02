"""T043 — trocas de porta na montagem (contracts/profiles.md, "Trocas de porta"; research R31; clarificação 2).

A suíte troca o adapter de uma porta sem montar o resto. Porta desconhecida ou de armazenamento é recusada nomeando a
porta: as sessões de armazenamento reconstroem essas portas pelas fábricas, e uma troca nelas seria ignorada.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from bootstrap_testkit import MemoryConfig, write_config

from ai_core.bootstrap.wiring import platform
from ai_core.graph.adapters.clock import FixedClock
from ai_core.http.adapters.development import SequentialRequestIds

pytestmark = pytest.mark.us3


def test_a_troca_substitui_o_adapter_da_porta(tmp_path: Path) -> None:
    ids = SequentialRequestIds(prefix="meu")
    plataforma = platform(config=MemoryConfig(write_config(tmp_path)), overrides={"request_ids": ids})
    assert plataforma.ok, plataforma.report.render()
    assert plataforma.parts["request_ids"] is ids


def test_as_fabricas_seguintes_enxergam_a_troca(tmp_path: Path) -> None:
    relogio = FixedClock(datetime(2030, 5, 1, 9, tzinfo=UTC))
    plataforma = platform(config=MemoryConfig(write_config(tmp_path)), overrides={"clock": relogio})
    assert plataforma.ok
    assert plataforma.parts["clock"] is relogio
    assert plataforma.parts["mcp_cache"]._clock is relogio  # a fábrica de `mcp_cache` recebeu o relógio trocado


def test_porta_desconhecida_e_recusada_nomeando_a_porta(tmp_path: Path) -> None:
    plataforma = platform(config=MemoryConfig(write_config(tmp_path)), overrides={"teletransporte": object()})
    failure = plataforma.report.failure()
    assert failure is not None and failure.name == "adapters"
    assert "teletransporte" in (failure.detail or "")


@pytest.mark.parametrize("port", ["database", "api_keys", "user_assistants", "conversations", "mcp_store", "audit"])
def test_porta_de_armazenamento_e_recusada(tmp_path: Path, port: str) -> None:
    plataforma = platform(config=MemoryConfig(write_config(tmp_path)), overrides={port: object()})
    failure = plataforma.report.failure()
    assert failure is not None and failure.name == "adapters"
    assert port in (failure.detail or "")

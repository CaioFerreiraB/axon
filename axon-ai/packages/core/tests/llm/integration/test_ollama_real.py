"""T014 — integração opcional contra um Ollama de verdade.

Pulada por default: roda só com `OLLAMA_BASE_URL` definida (ver quickstart.md). É o "Independent Test" da US1 tal como
a spec o descreve — provider local no ar e um modelo pequeno disponível.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from axon_ai.llm.adapters.clock import MonotonicClock
from axon_ai.llm.adapters.ollama import OllamaProvider
from axon_ai.llm.api import ModelCallFailed, ModelPolicy, ModelRef
from axon_ai.llm.service import ModelRoutingService

BASE_URL = os.environ.get("OLLAMA_BASE_URL")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:1.7b")

pytestmark = pytest.mark.skipif(BASE_URL is None, reason="defina OLLAMA_BASE_URL para rodar contra um Ollama real")

MESSAGES: list[Any] = [{"role": "user", "content": "Responda apenas: oi"}]


def routing(trace: Any, *, base_url: str | None = None) -> ModelRoutingService:
    provider = OllamaProvider(base_url=base_url or BASE_URL or "")
    return ModelRoutingService(providers={"ollama": provider}, trace=trace, clock=MonotonicClock())


def policy() -> ModelPolicy:
    return ModelPolicy(roles={"generation": ModelRef(provider="ollama", model=MODEL)}, allow=("ollama/*",))


async def test_geracao_local_em_streaming(trace: Any) -> None:
    router = routing(trace).for_execution(policy=policy(), request_id="req-integracao")
    pedacos = [chunk async for chunk in router.for_role("generation").stream(MESSAGES)]
    assert len(pedacos) > 1, "a geração deve chegar em pedaços, não de uma vez"
    assert "".join(chunk["delta"] for chunk in pedacos).strip()
    assert pedacos[-1].get("finish_reason")
    assert len(trace.events) == 1
    assert trace.events[0].duration_ms > 0


async def test_saude_confirma_o_modelo_presente_e_nega_o_ausente(trace: Any) -> None:
    service = routing(trace)
    assert (await service.check(policy()))[0].available
    ausente = ModelPolicy(roles={"generation": ModelRef(provider="ollama", model="nao-existe:0b")})
    resultado = (await service.check(ausente))[0]
    assert not resultado.available
    assert resultado.detail


async def test_provider_fora_do_ar_nomeia_provider_e_modelo(trace: Any) -> None:
    router = routing(trace, base_url="http://127.0.0.1:1/v1").for_execution(
        policy=policy(), request_id="req-integracao"
    )
    with pytest.raises(ModelCallFailed) as error:
        await router.for_role("generation").complete(MESSAGES)
    assert "ollama" in str(error.value)
    assert MODEL in str(error.value)

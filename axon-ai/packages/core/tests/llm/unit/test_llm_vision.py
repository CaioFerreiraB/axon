"""ADR-044, itens 10 e 11 (research R32): `vision` por papel, a guarda no cliente instrumentado e a marca no trace."""

from __future__ import annotations

from typing import Any

import pytest
from llm_testkit import REQUEST_ID, RecordingTraceSink, policy

from axon_ai.llm.adapters.clock import ScriptedClock
from axon_ai.llm.adapters.fake import ScriptedProvider
from axon_ai.llm.api import ModelCallFailed, ModelPolicy, ModelRef, has_image, image_part
from axon_ai.llm.service import ModelRoutingService
from axon_ai.observability.api import ModelCall
from axon_ai_contracts import Attachment

PNG = b"\x89PNG\r\n\x1a\n" + b"p" * 40


def mensagens() -> list[Any]:
    return [{"role": "user", "content": [{"type": "text", "text": "veja"}, image_part("image/png", PNG)]}]


def montar(*, vision: frozenset[str]) -> tuple[Any, ScriptedProvider, RecordingTraceSink]:
    provider = ScriptedProvider(name="ollama")
    trace = RecordingTraceSink()
    service = ModelRoutingService(providers={"ollama": provider}, trace=trace, clock=ScriptedClock([0.0] * 8))
    router = service.for_execution(policy=policy(vision=vision), request_id=REQUEST_ID)
    return router.for_role("generation"), provider, trace


def test_image_part_e_has_image() -> None:
    part = image_part("image/png", b"oi")
    assert part == {"type": "image_url", "image_url": {"url": "data:image/png;base64,b2k="}}
    assert has_image({"role": "user", "content": [part]})
    assert not has_image({"role": "user", "content": "texto"})
    assert not has_image({"role": "assistant", "content": None})


def test_vision_so_em_papel_declarado() -> None:
    ref = ModelRef.parse("ollama/m")
    assert ModelPolicy(roles={"generation": ref}, vision=frozenset({"generation"})).vision == {"generation"}
    with pytest.raises(ValueError, match="controller"):
        ModelPolicy(roles={"generation": ref}, vision=frozenset({"controller"}))


@pytest.mark.parametrize("stream", [False, True], ids=["completa", "streaming"])
async def test_papel_sem_vision_recusa_imagem_antes_do_provider(stream: bool) -> None:
    model, provider, trace = montar(vision=frozenset())
    assert model.vision is False
    with pytest.raises(ModelCallFailed, match="não declara vision"):
        if stream:
            async for _ in model.stream(mensagens()):
                pass
        else:
            await model.complete(mensagens())
    assert provider.calls == [] and provider.images == []
    (call,) = [event for event in trace.events if isinstance(event, ModelCall)]
    assert call.finish_reason == "error"


async def test_papel_com_vision_entrega_a_imagem_e_o_simulado_a_registra() -> None:
    model, provider, _trace = montar(vision=frozenset({"generation"}))
    assert model.vision is True
    await model.complete(mensagens())
    assert provider.images == [image_part("image/png", PNG)["image_url"]["url"]]


async def test_sem_imagem_nada_muda_para_papel_sem_vision() -> None:
    model, provider, _trace = montar(vision=frozenset())
    await model.complete([{"role": "user", "content": "oi"}])
    assert len(provider.calls) == 1


async def test_model_exchange_leva_a_marca_no_lugar_da_imagem() -> None:
    model, _provider, trace = montar(vision=frozenset({"generation"}))
    await model.complete(mensagens())
    (exchange,) = trace.exchanges
    marca = f"[imagem {Attachment(mime='image/png', data=PNG).id}]"
    assert exchange.messages[0].content == f"veja\n{marca}"
    assert "base64" not in exchange.messages[0].content

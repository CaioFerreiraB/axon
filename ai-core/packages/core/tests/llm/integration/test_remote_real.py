"""T046 — integração opcional contra os providers remotos de verdade (contracts/remote-adapters.md; research R25).

Faz chamadas **pagas**: cada provider só roda com a própria credencial no ambiente (`AI_CORE_OPENROUTER_API_KEY`,
`AI_CORE_OPENAI_API_KEY`; ver quickstart.md). É o "Independent Test" da US4 — o controller com um esquema de ação de
raiz objeto recebe JSON que o esquema aceita — e a sondagem com modelo presente e ausente.
"""

from __future__ import annotations

import json
import os
from typing import Any

import jsonschema
import pytest

from ai_core.llm.adapters.clock import MonotonicClock
from ai_core.llm.adapters.openai import OpenAIProvider
from ai_core.llm.adapters.openrouter import OpenRouterProvider
from ai_core.llm.adapters.remote import RemoteProvider
from ai_core.llm.adapters.secrets import EnvSecretResolver
from ai_core.llm.api import ModelPolicy, ModelRef
from ai_core.llm.service import ModelRoutingService

pytestmark = pytest.mark.us4

ESQUEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"action": {"enum": ["answer", "tool"]}},
    "required": ["action"],
    "additionalProperties": False,
}
"""Esquema de ação de raiz objeto — a forma que o modo estrito da OpenAI aceita (research R19)."""

MESSAGES: list[Any] = [
    {"role": "system", "content": "Decida a próxima ação. Responda só com o objeto JSON pedido."},
    {"role": "user", "content": "Quanto é 2 + 2? Você já sabe responder sem ferramentas."},
]

REMOTOS = pytest.mark.parametrize(
    ("cls", "model"),
    [
        pytest.param(
            OpenRouterProvider,
            # Default com `structured_outputs` no OpenRouter (2026-10-07): o `qwen/qwen3-8b` e os `:free` do Gemma não
            # o anunciam, e o `require_parameters` os recusa com 404 — o controller exige esquema (R18).
            os.environ.get("OPENROUTER_MODEL", "~z-ai/glm-flash-latest"),
            id="openrouter",
            marks=pytest.mark.skipif(
                not os.environ.get(OpenRouterProvider.CREDENTIAL),
                reason=f"defina {OpenRouterProvider.CREDENTIAL} para rodar contra o OpenRouter (pago)",
            ),
        ),
        pytest.param(
            OpenAIProvider,
            os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            id="openai",
            marks=pytest.mark.skipif(
                not os.environ.get(OpenAIProvider.CREDENTIAL),
                reason=f"defina {OpenAIProvider.CREDENTIAL} para rodar contra a OpenAI (pago)",
            ),
        ),
    ],
)


def routing(cls: type[RemoteProvider], trace: Any) -> ModelRoutingService:
    provider = cls(secrets=EnvSecretResolver())
    return ModelRoutingService(providers={provider.name: provider}, trace=trace, clock=MonotonicClock())


def policy(cls: type[RemoteProvider], model: str) -> ModelPolicy:
    ref = ModelRef(provider=cls.NAME, model=model)
    return ModelPolicy(roles={"generation": ref, "controller": ref}, allow=(f"{cls.NAME}/*",))


@REMOTOS
async def test_controller_devolve_acao_segundo_o_esquema(cls: Any, model: str, trace: Any) -> None:
    router = routing(cls, trace).for_execution(policy=policy(cls, model), request_id="req-remoto-real")
    response = await router.for_role("controller").complete(
        MESSAGES, response_format={"type": "json_schema", "json_schema": {"name": "acao", "schema": ESQUEMA}}
    )

    conteudo = response["message"]["content"]
    assert conteudo, response
    jsonschema.validate(json.loads(conteudo), ESQUEMA)
    assert len(trace.events) == 1
    assert trace.events[0].provider == cls.NAME
    assert trace.events[0].finish_reason != "error"


@REMOTOS
async def test_saude_confirma_o_modelo_e_nega_o_inexistente(cls: Any, model: str, trace: Any) -> None:
    service = routing(cls, trace)
    presente = await service.check(policy(cls, model))
    assert all(item.available for item in presente), presente

    ausente = ModelPolicy(roles={"generation": ModelRef(provider=cls.NAME, model="inexistente/modelo")})
    resultado = (await service.check(ausente))[0]
    assert not resultado.available
    assert resultado.detail
    assert os.environ[cls.CREDENTIAL] not in resultado.detail

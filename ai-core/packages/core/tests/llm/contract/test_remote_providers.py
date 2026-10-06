"""T032 e T045 — o que os providers remotos acrescentam à camada compatível (contracts/remote-adapters.md).

US3: credencial pela porta `SecretResolver` (FR-011, research R21), URL base fixa (R20), chave nunca em mensagem e
sondagem por variante e com lista truncada (R22). US4: a restrição de formato na forma mais rígida de cada provider
(R18) e a recusa dela como erro, sem reenvio (R19). Sem rede: o transporte HTTP falso do testkit (research R10).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx2
import pytest
from llm_testkit import (
    CHAT,
    HTTP_CASES,
    MODEL,
    MODELS,
    REMOTE_BASE_URL,
    SECRET,
    Handler,
    RecordingTransport,
    completion,
    delta_chunk,
    final_chunk,
    json_route,
    models_route,
    sse,
    sse_route,
)

from ai_core.llm.adapters.openai import OpenAIProvider
from ai_core.llm.adapters.openrouter import OpenRouterProvider
from ai_core.llm.adapters.remote import RemoteProvider
from ai_core.llm.adapters.secrets import InMemorySecretResolver
from ai_core.llm.api import ModelCallFailed

MESSAGES: list[Any] = [{"role": "user", "content": "oi"}]

REMOTES = pytest.mark.parametrize(
    ("cls", "variable"),
    [(OpenAIProvider, "AI_CORE_OPENAI_API_KEY"), (OpenRouterProvider, "AI_CORE_OPENROUTER_API_KEY")],
    ids=["openai", "openrouter"],
)


def build(
    cls: type[RemoteProvider],
    *,
    values: Mapping[str, str] | None = None,
    routes: Mapping[str, Handler] | None = None,
    base_url: str | None = REMOTE_BASE_URL,
) -> tuple[Any, RecordingTransport]:
    transport = RecordingTransport(routes or {CHAT: json_route(completion()), MODELS: models_route(MODEL)})
    kwargs: dict[str, Any] = {
        "secrets": InMemorySecretResolver(values if values is not None else {cls.CREDENTIAL: SECRET}),
        "http_client": httpx2.AsyncClient(transport=transport.transport()),
    }
    if base_url is not None:
        kwargs["base_url"] = base_url
    return cls(**kwargs), transport


# --- sem credencial (FR-011) -----------------------------------------------------------------------------------------


@pytest.mark.us3
@REMOTES
@pytest.mark.parametrize("stream", [False, True], ids=["completa", "streaming"])
async def test_sem_credencial_chat_falha_antes_da_rede(cls: Any, variable: str, stream: bool) -> None:
    provider, transport = build(cls, values={})
    with pytest.raises(ModelCallFailed) as erro:
        result = await provider.chat(MESSAGES, MODEL, stream=stream)
        if stream:
            async for _ in result:
                pass
    assert erro.value.provider == cls.NAME
    assert erro.value.model == MODEL
    assert erro.value.reason == f"sem credencial: defina {variable}"
    assert transport.requests == []


@pytest.mark.us3
@REMOTES
async def test_credencial_em_branco_conta_como_ausente(cls: Any, variable: str) -> None:
    provider, transport = build(cls, values={variable: "   "})
    with pytest.raises(ModelCallFailed, match="sem credencial"):
        await provider.chat(MESSAGES, MODEL)
    assert transport.requests == []


@pytest.mark.us3
@REMOTES
async def test_sem_credencial_probe_relata_a_falta(cls: Any, variable: str) -> None:
    provider, transport = build(cls, values={})
    result = await provider.probe(MODEL)
    assert not result.available
    assert result.detail == f"sem credencial: defina {variable}"
    assert transport.requests == []


# --- com credencial ---------------------------------------------------------------------------------------------------


@pytest.mark.us3
@REMOTES
async def test_credencial_vai_no_cabecalho(cls: Any, variable: str) -> None:
    provider, transport = build(cls)
    await provider.chat(MESSAGES, MODEL)
    assert transport.requests[-1].headers["authorization"] == f"Bearer {SECRET}"


@pytest.mark.us3
@pytest.mark.parametrize(
    ("cls", "host", "path"),
    [
        (OpenAIProvider, "api.openai.com", "/v1/chat/completions"),
        (OpenRouterProvider, "openrouter.ai", "/api/v1/chat/completions"),
    ],
    ids=["openai", "openrouter"],
)
async def test_url_base_default(cls: Any, host: str, path: str) -> None:
    provider, transport = build(cls, base_url=None)
    await provider.chat(MESSAGES, MODEL)
    assert transport.requests[-1].url.host == host
    assert transport.requests[-1].url.path == path


@pytest.mark.us3
@REMOTES
async def test_chave_nunca_aparece_no_motivo(cls: Any, variable: str) -> None:
    recusa = json_route({"error": {"message": f"Incorrect API key provided: {SECRET}"}}, status=401)
    provider, _ = build(cls, routes={CHAT: recusa, MODELS: recusa})

    with pytest.raises(ModelCallFailed) as erro:
        await provider.chat(MESSAGES, MODEL)
    assert SECRET not in str(erro.value)
    assert "***" in erro.value.reason
    assert "401" in erro.value.reason

    result = await provider.probe(MODEL)
    assert not result.available
    assert SECRET not in (result.detail or "")
    assert "***" in (result.detail or "")


# --- sondagem (R22) ---------------------------------------------------------------------------------------------------


@pytest.mark.us3
@pytest.mark.parametrize(
    ("model", "available"),
    [("qwen/qwen3-8b:nitro", True), ("outro/y:free", True), ("qwen/qwen3-8b", True), ("outro/x:nitro", False)],
)
async def test_probe_openrouter_aceita_base_da_variante(model: str, available: bool) -> None:
    rotas = {CHAT: json_route(completion()), MODELS: models_route("qwen/qwen3-8b", "outro/y:free")}
    provider, _ = build(OpenRouterProvider, routes=rotas)
    assert (await provider.probe(model)).available is available


@pytest.mark.us3
async def test_probe_openai_nao_aceita_variante() -> None:
    provider, _ = build(OpenAIProvider, routes={CHAT: json_route(completion()), MODELS: models_route("gpt-4o")})
    assert not (await provider.probe("gpt-4o:nitro")).available


@pytest.mark.us3
@REMOTES
async def test_probe_trunca_a_lista_de_disponiveis(cls: Any, variable: str) -> None:
    ids = [f"m{index:02d}" for index in range(25)]
    provider, _ = build(cls, routes={CHAT: json_route(completion()), MODELS: models_route(*ids)})
    result = await provider.probe("ausente")
    assert not result.available
    detail = result.detail or ""
    assert "m00" in detail and "m19" in detail
    assert "m20" not in detail and "m24" not in detail
    assert "(+5)" in detail


# --- restrição de formato (US4, FR-005 camadas 2 e 3) -----------------------------------------------------------------

ESQUEMA: dict[str, Any] = {"type": "object", "properties": {"action": {"enum": ["answer"]}}, "required": ["action"]}


def formato(**extra: Any) -> dict[str, Any]:
    return {"type": "json_schema", "json_schema": {"name": "acao", "schema": ESQUEMA, **extra}}


@pytest.mark.us4
@pytest.mark.parametrize("make", HTTP_CASES, ids=[case.id for case in HTTP_CASES])
@pytest.mark.parametrize("extra", [{}, {"strict": False}], ids=["sem-strict", "strict-false"])
async def test_strict_forcado(make: Any, extra: dict[str, Any]) -> None:
    case = make()
    provider = case.ok()
    enviado = formato(**extra)

    await provider.chat(MESSAGES, MODEL, response_format=enviado)

    corpo = case.sent_response_format()
    assert corpo["type"] == "json_schema"
    assert corpo["json_schema"]["strict"] is True
    assert corpo["json_schema"]["name"] == "acao"
    assert corpo["json_schema"]["schema"] == ESQUEMA
    assert enviado == formato(**extra), "o mapeamento recebido não pode mudar"


@pytest.mark.us4
@pytest.mark.parametrize("make", HTTP_CASES, ids=[case.id for case in HTTP_CASES])
async def test_outros_tipos_de_formato_passam_como_vieram(make: Any) -> None:
    case = make()
    provider = case.ok()
    await provider.chat(MESSAGES, MODEL, response_format={"type": "json_object"})
    assert case.sent_response_format() == {"type": "json_object"}


def _rotas_com_streaming() -> dict[str, Handler]:
    def chat(request: httpx2.Request) -> httpx2.Response:
        if b'"stream":true' in request.content.replace(b" ", b""):
            return sse_route(sse(delta_chunk("{}"), final_chunk()))(request)
        return json_route(completion())(request)

    return {CHAT: chat, MODELS: models_route(MODEL)}


@pytest.mark.us4
@pytest.mark.parametrize("stream", [False, True], ids=["completa", "streaming"])
async def test_require_parameters_so_com_formato(stream: bool) -> None:
    openrouter, transporte = build(OpenRouterProvider, routes=_rotas_com_streaming())

    for response_format in (formato(), None):
        result = await openrouter.chat(MESSAGES, MODEL, response_format=response_format, stream=stream)
        if stream:
            async for _ in result:
                pass
    com, sem = transporte.bodies()
    assert com["provider"] == {"require_parameters": True}
    assert "provider" not in sem

    openai, transporte_openai = build(OpenAIProvider, routes=_rotas_com_streaming())
    result = await openai.chat(MESSAGES, MODEL, response_format=formato(), stream=stream)
    if stream:
        async for _ in result:
            pass
    assert "provider" not in transporte_openai.bodies()[-1]


@pytest.mark.us4
@pytest.mark.parametrize(
    ("cls", "status", "mensagem"),
    [
        (OpenAIProvider, 400, "Invalid schema for response_format 'acao': anyOf at root is not permitted"),
        (OpenRouterProvider, 404, "No endpoints found that can handle the requested parameters."),
    ],
    ids=["openai", "openrouter"],
)
async def test_recusa_da_restricao_sem_reenvio(cls: Any, status: int, mensagem: str) -> None:
    recusa = json_route({"error": {"message": mensagem, "code": status}}, status=status)
    provider, transporte = build(cls, routes={CHAT: recusa, MODELS: models_route(MODEL)})

    with pytest.raises(ModelCallFailed) as erro:
        await provider.chat(MESSAGES, MODEL, response_format=formato())

    assert erro.value.provider == cls.NAME
    assert erro.value.model == MODEL
    assert f"erro {status}" in erro.value.reason
    assert mensagem in erro.value.reason
    assert len(transporte.requests) == 1

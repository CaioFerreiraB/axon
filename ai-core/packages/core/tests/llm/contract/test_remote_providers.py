"""T032 e T045 — o que os providers remotos acrescentam à camada compatível (contracts/remote-adapters.md).

US3: credencial pela porta `SecretResolver` (FR-011, research R21), URL base fixa (R20), chave nunca em mensagem e
sondagem por variante e com lista truncada (R22). US4: a restrição de formato na forma mais rígida de cada provider
(R18) e a recusa dela como erro, sem reenvio (R19). Sem rede: o transporte HTTP falso do testkit (research R10).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

import httpx2
import jsonschema
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
from ai_core.llm.domain.names import function_name
from ai_core.llm.domain.strict import to_strict

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
    # Na OpenAI, o esquema vai no subconjunto estrito (ADR-023); nos demais, como veio.
    esperado = to_strict(ESQUEMA).wire if case.name == "openai" else ESQUEMA
    assert corpo["json_schema"]["schema"] == esperado
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


# --- subconjunto estrito da OpenAI (ADR-023; contracts/remote-adapters.md casos 8 a 11; T056) ------------------------

ACAO: dict[str, Any] = {
    "anyOf": [
        {"type": "object", "properties": {"action": {"const": "answer"}}, "required": ["action"]},
        {
            "type": "object",
            "properties": {
                "action": {"const": "tool"},
                "name": {"const": "clima.previsao"},
                "arguments": {
                    "type": "object",
                    "properties": {"cidade": {"type": "string"}, "dias": {"type": "integer"}},
                    "required": ["cidade"],
                },
            },
            "required": ["action", "name", "arguments"],
        },
    ]
}
FORMATO_ACAO: dict[str, Any] = {"type": "json_schema", "json_schema": {"name": "acao", "schema": ACAO}}
ESTRITO = '{"value": {"action": "tool", "name": "clima.previsao", "arguments": {"cidade": "Natal", "dias": null}}}'


def _rotas_estritas(content: str = ESTRITO) -> dict[str, Handler]:
    def chat(request: httpx2.Request) -> httpx2.Response:
        if b'"stream":true' in request.content.replace(b" ", b""):
            return sse_route(sse(delta_chunk(content[:20]), delta_chunk(content[20:]), final_chunk()))(request)
        return json_route(completion(content=content))(request)

    return {CHAT: chat, MODELS: models_route(MODEL)}


@pytest.mark.us4
@pytest.mark.parametrize(
    ("cls", "model"),
    [(OpenAIProvider, "gpt-4.1-nano"), (OpenRouterProvider, "openai/gpt-4.1-nano")],
    ids=["openai", "openrouter-openai"],
)
async def test_estrito_corpo_enviado_e_conteudo_desfeito(cls: Any, model: str) -> None:
    provider, transporte = build(cls, routes=_rotas_estritas())
    original = json.loads(json.dumps(FORMATO_ACAO))

    resposta = await provider.chat(MESSAGES, model, response_format=FORMATO_ACAO)

    enviado = transporte.bodies()[-1]["response_format"]["json_schema"]
    assert enviado["strict"] is True
    assert enviado["schema"]["type"] == "object"
    assert enviado["schema"]["required"] == ["value"]
    ramo_tool = enviado["schema"]["properties"]["value"]["anyOf"][1]
    assert ramo_tool["properties"]["arguments"]["required"] == ["cidade", "dias"]
    assert ramo_tool["properties"]["arguments"]["additionalProperties"] is False
    assert original == FORMATO_ACAO  # o response_format recebido não muda

    acao = json.loads(resposta["message"]["content"] or "")
    assert acao == {"action": "tool", "name": "clima.previsao", "arguments": {"cidade": "Natal"}}
    jsonschema.validate(acao, ACAO)


@pytest.mark.us4
async def test_estrito_com_streaming_entrega_o_conteudo_desfeito() -> None:
    provider, _ = build(OpenAIProvider, routes=_rotas_estritas())
    pedacos = [
        chunk
        async for chunk in await provider.chat(MESSAGES, "gpt-4.1-nano", response_format=FORMATO_ACAO, stream=True)
    ]
    texto = "".join(chunk["delta"] for chunk in pedacos)
    assert json.loads(texto) == {"action": "tool", "name": "clima.previsao", "arguments": {"cidade": "Natal"}}
    assert pedacos[-1].get("finish_reason") == "stop"


@pytest.mark.us4
@pytest.mark.parametrize("cls", [OpenAIProvider, OpenRouterProvider], ids=["openai", "openrouter"])
async def test_estrito_sem_equivalente_falha_antes_da_rede(cls: Any) -> None:
    provider, transporte = build(cls)
    livre = {
        "type": "json_schema",
        "json_schema": {"name": "x", "schema": {"type": "object", "properties": {"a": {"type": "object"}}}},
    }
    modelo = "openai/gpt-4.1-nano" if cls is OpenRouterProvider else "gpt-4.1-nano"
    with pytest.raises(ModelCallFailed) as erro:
        await provider.chat(MESSAGES, modelo, response_format=livre)
    assert "subconjunto estrito da OpenAI" in erro.value.reason
    assert "$.properties.a" in erro.value.reason
    assert transporte.requests == []


@pytest.mark.us4
async def test_openrouter_de_outro_autor_envia_o_esquema_como_veio() -> None:
    provider, transporte = build(OpenRouterProvider, routes=_rotas_estritas(content='{"action": "answer"}'))
    resposta = await provider.chat(MESSAGES, "z-ai/glm-5.3-flash", response_format=FORMATO_ACAO)
    enviado = transporte.bodies()[-1]["response_format"]["json_schema"]["schema"]
    assert "anyOf" in enviado and "value" not in json.dumps(enviado)
    assert resposta["message"]["content"] == '{"action": "answer"}'


@pytest.mark.us4
async def test_nomes_de_funcao_com_namespace_viram_apelido_e_voltam() -> None:
    apelido = function_name("demo.eco")
    resposta_com_tool = completion(
        tool_calls=[{"id": "c1", "type": "function", "function": {"name": apelido, "arguments": "{}"}}]
    )
    provider, transporte = build(
        OpenAIProvider, routes={CHAT: json_route(resposta_com_tool), MODELS: models_route(MODEL)}
    )
    transcricao: list[Any] = [
        {"role": "user", "content": "oi"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "c0", "name": "demo.eco", "arguments": "{}"}]},
        {"role": "tool", "content": "ok", "tool_call_id": "c0"},
    ]
    tools: list[Any] = [{"name": "demo.eco", "description": "eco", "parameters": {"type": "object", "properties": {}}}]

    resposta = await provider.chat(transcricao, "gpt-4.1-nano", tools=tools)

    corpo = transporte.bodies()[-1]
    assert corpo["messages"][1]["tool_calls"][0]["function"]["name"] == apelido
    assert corpo["tools"][0]["function"]["name"] == apelido
    assert re.match(r"^[a-zA-Z0-9_-]{1,64}$", apelido)
    assert [call["name"] for call in resposta["message"].get("tool_calls", ())] == ["demo.eco"]


# --- custo informado pelo provider (ADR-035) --------------------------------------------------------------------------

USAGE_WITH_COST: dict[str, object] = {
    "prompt_tokens": 12,
    "completion_tokens": 3,
    "total_tokens": 15,
    "cost": 0.0000425,
}


def _rotas_com_custo(usage: Mapping[str, object]) -> dict[str, Handler]:
    def chat(request: httpx2.Request) -> httpx2.Response:
        if b'"stream":true' in request.content.replace(b" ", b""):
            return sse_route(sse(delta_chunk("oi"), final_chunk(usage=usage)))(request)
        return json_route(completion(usage=usage))(request)

    return {CHAT: chat, MODELS: models_route(MODEL)}


async def _usage_of(provider: Any, *, stream: bool) -> Any:
    result = await provider.chat(MESSAGES, MODEL, stream=stream)
    if not stream:
        return result.get("usage")
    usage = None
    async for chunk in result:
        usage = chunk.get("usage", usage)
    return usage


@pytest.mark.parametrize("stream", [False, True], ids=["completa", "streaming"])
async def test_openrouter_pede_o_custo_em_todo_pedido(stream: bool) -> None:
    openrouter, transporte = build(OpenRouterProvider, routes=_rotas_com_streaming())

    for response_format in (formato(), None):
        result = await openrouter.chat(MESSAGES, MODEL, response_format=response_format, stream=stream)
        if stream:
            async for _ in result:
                pass
    com, sem = transporte.bodies()
    assert com["usage"] == {"include": True}
    assert com["provider"] == {"require_parameters": True}
    assert sem["usage"] == {"include": True}

    openai, transporte_openai = build(OpenAIProvider, routes=_rotas_com_streaming())
    await _usage_of(openai, stream=stream)
    assert "usage" not in transporte_openai.bodies()[-1]


@REMOTES
@pytest.mark.parametrize("stream", [False, True], ids=["completa", "streaming"])
async def test_custo_informado_chega_no_usage(cls: Any, variable: str, stream: bool) -> None:
    provider, _ = build(cls, routes=_rotas_com_custo(USAGE_WITH_COST))

    usage = await _usage_of(provider, stream=stream)

    assert usage == {"prompt_tokens": 12, "completion_tokens": 3, "cost": 0.0000425}


@pytest.mark.parametrize("stream", [False, True], ids=["completa", "streaming"])
async def test_sem_custo_informado_o_usage_so_tem_tokens(stream: bool) -> None:
    usage_sem_custo: dict[str, object] = {"prompt_tokens": 12, "completion_tokens": 3}
    provider, _ = build(OpenRouterProvider, routes=_rotas_com_custo(usage_sem_custo))

    assert await _usage_of(provider, stream=stream) == {"prompt_tokens": 12, "completion_tokens": 3}


@pytest.mark.parametrize(
    ("extra", "esperado"),
    [
        ({"is_byok": True, "cost": 0.001, "cost_details": {"upstream_inference_cost": 0.02}}, 0.021),
        ({"is_byok": False, "cost": 0.001, "cost_details": {"upstream_inference_cost": 0.02}}, 0.001),
        ({"cost": "0.001"}, None),
        ({"cost": -1}, None),
        ({"cost": True}, None),
    ],
    ids=["byok-soma-o-upstream", "sem-byok", "texto", "negativo", "booleano"],
)
async def test_custo_byok_e_valores_estranhos(extra: dict[str, object], esperado: float | None) -> None:
    provider, _ = build(
        OpenRouterProvider, routes=_rotas_com_custo({"prompt_tokens": 1, "completion_tokens": 1, **extra})
    )

    usage = await _usage_of(provider, stream=False)

    assert usage.get("cost") == (pytest.approx(esperado) if esperado is not None else None)


# --- prontidão (ADR-035) ----------------------------------------------------------------------------------------------


@REMOTES
async def test_ready_do_remoto_e_so_a_credencial_sem_rede(cls: Any, variable: str) -> None:
    com_chave, transporte = build(cls)
    sem_chave, transporte_sem = build(cls, values={})

    pronto = await com_chave.ready()
    faltando = await sem_chave.ready()

    assert pronto.available and pronto.detail is None
    assert not faltando.available and faltando.detail is not None and variable in faltando.detail
    assert transporte.requests == [] and transporte_sem.requests == []


def test_so_o_openrouter_informa_o_custo() -> None:
    """ADR-036: quem informa o custo de cada chamada não tem preço de tabela."""
    assert build(OpenRouterProvider)[0].reports_cost is True
    assert build(OpenAIProvider)[0].reports_cost is False

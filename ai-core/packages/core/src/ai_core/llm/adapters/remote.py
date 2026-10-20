"""Parte comum dos providers remotos — OpenAI e OpenRouter (contracts/remote-adapters.md; research R20, R21).

Sobre a camada compatível, um remoto acrescenta só a credencial: lida uma vez, na construção, pela porta
`SecretResolver`. Sem ela, o provider fica registrado e explica a falta — `chat` falha antes de qualquer requisição e
`probe` relata, sem rede (FR-011, ADR-020). O valor da chave nunca entra em mensagem.

Onde o provider segue as regras da API da OpenAI (`_follows_openai_rules`), o adapter as cumpre por quem chama
(ADR-023, research R29): o esquema de saída vai no subconjunto estrito e a conversão é desfeita no conteúdo da volta;
nomes de função com namespace (`demo.eco`) viram apelidos na ida e voltam ao nome original nas `tool_calls`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any, ClassVar, Final, Literal, overload

import httpx2
from openai import OpenAIError

from ai_core.llm.adapters.openai_compat import OpenAICompatProvider
from ai_core.llm.api import ModelCallFailed
from ai_core.llm.domain.names import function_name
from ai_core.llm.domain.strict import StrictPlan, StrictSchemaError, from_strict, to_strict
from ai_core.llm.ports import ProbeResult, SecretResolver
from ai_core_contracts import ChatChunk, ChatMessage, ChatResponse, ChatTool, ChatToolCall, JSONValue

MISSING_SENTINEL: Final = "sem-credencial"
"""O que vai ao SDK quando falta a credencial: o cliente nunca é usado nesse estado, e uma chave explícita impede o SDK
de procurar `OPENAI_API_KEY` no ambiente."""

MASK: Final = "***"


class RemoteProvider(OpenAICompatProvider):
    """`ModelProvider` de um endpoint remoto. As subclasses fixam nome, endereço e o nome da credencial."""

    NAME: ClassVar[str]
    DEFAULT_BASE_URL: ClassVar[str]
    CREDENTIAL: ClassVar[str]

    def __init__(
        self,
        *,
        secrets: SecretResolver,
        base_url: str | None = None,
        connect_seconds: float = 5.0,
        idle_seconds: float = 120.0,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._key = secrets.resolve(self.CREDENTIAL)
        self._missing = None if self._key is not None else f"sem credencial: defina {self.CREDENTIAL}"
        super().__init__(
            name=self.NAME,
            base_url=base_url or self.DEFAULT_BASE_URL,
            api_key=self._key or MISSING_SENTINEL,
            connect_seconds=connect_seconds,
            idle_seconds=idle_seconds,
            http_client=http_client,
        )

    @overload
    async def chat(
        self,
        messages: Sequence[ChatMessage],
        model: str,
        *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
        stream: Literal[False] = False,
    ) -> ChatResponse: ...

    @overload
    async def chat(
        self,
        messages: Sequence[ChatMessage],
        model: str,
        *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
        stream: Literal[True],
    ) -> AsyncIterator[ChatChunk]: ...

    async def chat(
        self,
        messages: Sequence[ChatMessage],
        model: str,
        *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
        stream: bool = False,
    ) -> ChatResponse | AsyncIterator[ChatChunk]:
        if self._missing is not None:
            raise ModelCallFailed(provider=self.name, model=model, reason=self._missing)
        if not self._follows_openai_rules(model):
            if stream:
                return await super().chat(messages, model, tools=tools, response_format=response_format, stream=True)
            return await super().chat(messages, model, tools=tools, response_format=response_format, stream=False)

        plan = self._strict_plan(model, response_format)
        if plan is not None and response_format is not None:
            response_format = _with_schema(response_format, plan.wire)
        originals: dict[str, str] = {}
        messages = [_aliased_message(message, originals) for message in messages]
        if tools is not None:
            tools = [_aliased_tool(tool, originals) for tool in tools]
        if stream:
            chunks = await super().chat(messages, model, tools=tools, response_format=response_format, stream=True)
            return _restored_stream(chunks, plan, originals)
        response = await super().chat(messages, model, tools=tools, response_format=response_format, stream=False)
        return _restored_response(response, plan, originals)

    def _follows_openai_rules(self, model: str) -> bool:
        """O provider aplica, para este modelo, as regras da API da OpenAI — subconjunto estrito do esquema e nomes de
        função `[a-zA-Z0-9_-]` (ADR-023). As subclasses decidem."""
        return False

    def _strict_plan(self, model: str, response_format: Mapping[str, JSONValue] | None) -> StrictPlan | None:
        """A conversão do esquema de saída, quando exigida; sem equivalente estrito, falha antes da rede (FR-005)."""
        if response_format is None or response_format.get("type") != "json_schema":
            return None
        body = response_format.get("json_schema")
        schema = body.get("schema") if isinstance(body, Mapping) else None
        if not isinstance(schema, Mapping):
            return None
        try:
            return to_strict(schema)
        except StrictSchemaError as error:
            reason = f"esquema fora do subconjunto estrito da OpenAI: {error}"
            raise ModelCallFailed(provider=self.name, model=model, reason=reason) from error

    async def probe(self, model: str) -> ProbeResult:
        if self._missing is not None:
            return ProbeResult(available=False, detail=self._missing)
        return await super().probe(model)

    async def ready(self) -> ProbeResult:
        """Só a credencial, sem rede: com ela, o remoto está pronto (ADR-035). A sondagem do modelo é o `probe`."""
        return ProbeResult(available=self._missing is None, detail=self._missing)

    def _reason(self, error: OpenAIError) -> str:
        """O motivo da camada compatível, com o valor da chave trocado — o 401 da OpenAI ecoa a chave mascarada, e um
        proxy poderia ecoá-la inteira (FR-011)."""
        reason = super()._reason(error)
        return reason.replace(self._key, MASK) if self._key else reason


def _with_schema(response_format: Mapping[str, JSONValue], schema: dict[str, Any]) -> dict[str, Any]:
    """Cópia do formato com o esquema convertido; o recebido não muda."""
    body = response_format.get("json_schema")
    converted = dict(body) if isinstance(body, Mapping) else {}
    converted["schema"] = schema
    return {**response_format, "json_schema": converted}


def _restored_content(content: str | None, plan: StrictPlan) -> str | None:
    """O conteúdo na forma do esquema original. O que não é JSON volta como veio (quem chama o lê como inválido)."""
    if content is None:
        return None
    try:
        value = json.loads(content)
    except ValueError:
        return content
    return json.dumps(from_strict(value, plan), ensure_ascii=False)


def _aliased_message(message: ChatMessage, originals: dict[str, str]) -> ChatMessage:
    calls = message.get("tool_calls")
    if not calls:
        return message
    aliased: ChatMessage = {**message, "tool_calls": [_aliased_call(call, originals) for call in calls]}
    return aliased


def _aliased_call(call: ChatToolCall, originals: dict[str, str]) -> ChatToolCall:
    alias = function_name(call["name"])
    originals[alias] = call["name"]
    return {**call, "name": alias}


def _aliased_tool(tool: ChatTool, originals: dict[str, str]) -> ChatTool:
    alias = function_name(tool["name"])
    originals[alias] = tool["name"]
    aliased: ChatTool = {**tool, "name": alias}
    return aliased


def _original_calls(calls: Sequence[ChatToolCall], originals: Mapping[str, str]) -> list[ChatToolCall]:
    return [{**call, "name": originals.get(call["name"], call["name"])} for call in calls]


def _restored_response(response: ChatResponse, plan: StrictPlan | None, originals: Mapping[str, str]) -> ChatResponse:
    message: ChatMessage = {**response["message"]}
    if plan is not None:
        message["content"] = _restored_content(message["content"], plan)
    if "tool_calls" in message:
        message["tool_calls"] = _original_calls(message["tool_calls"], originals)
    restored: ChatResponse = {**response, "message": message}
    return restored


async def _restored_stream(
    chunks: AsyncIterator[ChatChunk], plan: StrictPlan | None, originals: Mapping[str, str]
) -> AsyncIterator[ChatChunk]:
    """Sem conversão de esquema, os pedaços passam (com os nomes de volta). Com ela, o conteúdo é juntado, desfeito e
    entregue num pedaço só, antes do final (research R29)."""
    if plan is None:
        async for chunk in chunks:
            if "tool_calls" in chunk:
                chunk = {**chunk, "tool_calls": _original_calls(chunk["tool_calls"], originals)}
            yield chunk
        return
    parts: list[str] = []
    closing: ChatChunk = {"delta": ""}
    async for chunk in chunks:
        parts.append(chunk.get("delta", ""))
        if "finish_reason" in chunk:
            closing["finish_reason"] = chunk["finish_reason"]
        if "usage" in chunk:
            closing["usage"] = chunk["usage"]
    content = _restored_content("".join(parts), plan) or ""
    if content:
        yield {"delta": content}
    yield closing

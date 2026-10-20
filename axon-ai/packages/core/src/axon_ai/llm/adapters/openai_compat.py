"""Provider sobre qualquer endpoint compatível com a API da OpenAI (specs/006.../contracts/ollama-adapter.md).

É a parte comum dos três providers do `design.md`: o Ollama (Fase 1) fixa aqui os defaults da camada compatível em
`:11434/v1`, e OpenAI e OpenRouter (Fase 3, `remote.py`) só mudam endereço, credencial e um detalhe de corpo. O SDK e
o cliente HTTP só aparecem em `adapters/` (princípio XIII, research R4).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any, ClassVar, Final, Literal, overload

import httpx2
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI, OpenAIError

from axon_ai.llm.api import ModelCallFailed
from axon_ai.llm.ports import ProbeResult
from axon_ai_contracts import (
    ChatChunk,
    ChatMessage,
    ChatResponse,
    ChatTool,
    ChatToolCall,
    ChatUsage,
    JSONValue,
)

BODY_LIMIT = 500
"""Corpo de erro do provider entra truncado na mensagem: conteúdo externo é dado, e dado longo é cortado."""

LISTED_LIMIT: Final = 20
"""Ids de modelo citados quando a sondagem não acha o declarado (research R22): o OpenRouter lista centenas, e o item de
saúde precisa caber numa linha."""


class OpenAICompatProvider:
    """Cumpre `ModelProvider` falando com um endpoint compatível.

    Timeouts (FR-010, research R5): `connect_seconds` é o prazo para abrir a conexão — provider fora do ar falha em
    segundos — e `idle_seconds` é o prazo **sem pedaço novo** durante o streaming. Não há teto de tempo total, porque
    no hardware alvo (5 a 15 tok/s) uma resposta legítima leva minutos. `max_retries=0`: nenhuma repetição silenciosa.
    """

    REPORTS_COST: ClassVar[bool] = False
    """O endpoint informa o custo em `usage.cost` (ADR-036); a subclasse que o pede declara `True`."""

    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        api_key: str,
        connect_seconds: float = 5.0,
        idle_seconds: float = 120.0,
        default_headers: Mapping[str, str] | None = None,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self._name = name
        self._base_url = base_url
        self._idle_seconds = idle_seconds
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=0,
            timeout=httpx2.Timeout(
                connect=connect_seconds, read=idle_seconds, write=connect_seconds, pool=connect_seconds
            ),
            default_headers=dict(default_headers) if default_headers else None,
            http_client=http_client,
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def reports_cost(self) -> bool:
        return self.REPORTS_COST

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
        payload = self._payload(messages, model, tools=tools, response_format=response_format)
        if stream:
            return self._stream(payload, model)
        try:
            completion = await self._client.chat.completions.create(**payload)
        except OpenAIError as error:
            raise self._failure(model, error) from error
        return _to_response(completion)

    async def _stream(self, payload: dict[str, Any], model: str) -> AsyncIterator[ChatChunk]:
        try:
            events = await self._client.chat.completions.create(
                **payload, stream=True, stream_options={"include_usage": True}
            )
            async for event in events:
                yield _to_chunk(event)
        except OpenAIError as error:
            raise self._failure(model, error) from error

    async def probe(self, model: str) -> ProbeResult:
        """Lista os modelos do endpoint e confere se o declarado está lá. Nunca levanta, nunca gera tokens."""
        try:
            page = await self._client.models.list()
        except OpenAIError as error:
            return ProbeResult(available=False, detail=self._reason(error))
        available = [entry.id for entry in page.data]
        if self._has_model(model, available):
            return ProbeResult(available=True)
        return ProbeResult(
            available=False,
            detail=f"modelo {model} não encontrado em {self._base_url}; disponíveis: {_listed(available)}",
        )

    async def ready(self) -> ProbeResult:
        """O endpoint responde à lista de modelos. Nunca levanta, nunca gera tokens."""
        try:
            await self._client.models.list()
        except OpenAIError as error:
            return ProbeResult(available=False, detail=self._reason(error))
        return ProbeResult(available=True)

    def _has_model(self, model: str, ids: Sequence[str]) -> bool:
        """O modelo está na lista do endpoint. O OpenRouter sobrescreve para aceitar a base de uma variante (R22)."""
        return model in ids

    def _payload(
        self,
        messages: Sequence[ChatMessage],
        model: str,
        *,
        tools: Sequence[ChatTool] | None,
        response_format: Mapping[str, JSONValue] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": model, "messages": [_to_wire_message(m) for m in messages]}
        if tools is not None:
            payload["tools"] = [_to_wire_tool(tool) for tool in tools]
        if response_format is not None:
            payload["response_format"] = _strict(response_format)
        return payload

    def _failure(self, model: str, error: OpenAIError) -> ModelCallFailed:
        return ModelCallFailed(provider=self._name, model=model, reason=self._reason(error))

    def _reason(self, error: OpenAIError) -> str:
        if isinstance(error, APITimeoutError):
            return f"sem resposta por {self._idle_seconds:g}s"
        if isinstance(error, APIConnectionError):
            return f"provider inalcançável em {self._base_url}"
        if isinstance(error, APIStatusError):
            body = str(error.response.text)[:BODY_LIMIT]
            return f"erro {error.status_code} do provider: {body}"
        return f"{type(error).__name__}: {error}"


def _strict(response_format: Mapping[str, JSONValue]) -> dict[str, Any]:
    """Cópia do formato com `json_schema` sempre no modo estrito (FR-005 camada 2, research R18), mesmo que quem chama
    mande `strict: false`. A OpenAI só garante o esquema assim; o OpenRouter repassa ao upstream; o Ollama ignora o
    campo e restringe por gramática. Outros tipos passam como vieram."""
    wire = dict(response_format)
    body = wire.get("json_schema")
    if wire.get("type") == "json_schema" and isinstance(body, Mapping):
        wire["json_schema"] = {**body, "strict": True}
    return wire


def _listed(ids: Sequence[str]) -> str:
    """Os primeiros `LISTED_LIMIT` ids, em ordem, e quantos ficaram de fora."""
    ordered = sorted(ids)
    if not ordered:
        return "nenhum"
    shown = ", ".join(ordered[:LISTED_LIMIT])
    hidden = len(ordered) - LISTED_LIMIT
    return f"{shown} (+{hidden})" if hidden > 0 else shown


def _to_wire_message(message: ChatMessage) -> dict[str, Any]:
    """Traduz para o corpo da camada compatível. Chave ausente não vira `None`: só vai o que foi declarado."""
    wire: dict[str, Any] = {"role": message["role"], "content": message["content"]}
    if "name" in message:
        wire["name"] = message["name"]
    if "tool_call_id" in message:
        wire["tool_call_id"] = message["tool_call_id"]
    if "tool_calls" in message:
        wire["tool_calls"] = [
            {
                "id": call["id"],
                "type": "function",
                "function": {"name": call["name"], "arguments": call["arguments"]},
            }
            for call in message["tool_calls"]
        ]
    return wire


def _to_wire_tool(tool: ChatTool) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": dict(tool["parameters"]),
        },
    }


def _to_tool_calls(raw: Any) -> tuple[ChatToolCall, ...]:
    calls: list[ChatToolCall] = []
    for call in raw or ():
        function = getattr(call, "function", None)
        calls.append(
            ChatToolCall(
                id=getattr(call, "id", "") or "",
                name=getattr(function, "name", "") or "",
                arguments=getattr(function, "arguments", "") or "",
            )
        )
    return tuple(calls)


def _to_usage(raw: Any) -> ChatUsage | None:
    if raw is None:
        return None
    usage = ChatUsage(prompt_tokens=raw.prompt_tokens, completion_tokens=raw.completion_tokens)
    cost = _reported_cost(raw)
    if cost is not None:
        usage["cost"] = cost
    return usage


def _reported_cost(raw: Any) -> float | None:
    """O custo em USD que o endpoint informa em `usage.cost` — o OpenRouter informa; OpenAI e Ollama, não (ADR-035).

    São campos extras do modelo do SDK, lidos por `getattr`. Com chave própria no upstream (`is_byok`), `cost` é só a
    taxa do OpenRouter, e o custo do upstream vem em `cost_details.upstream_inference_cost`: os dois somam.
    """
    cost = _number(getattr(raw, "cost", None))
    if cost is None:
        return None
    if getattr(raw, "is_byok", False) is True:
        details = getattr(raw, "cost_details", None)
        upstream = details.get("upstream_inference_cost") if isinstance(details, dict) else None
        if upstream is None and details is not None and not isinstance(details, dict):
            upstream = getattr(details, "upstream_inference_cost", None)
        cost += _number(upstream) or 0.0
    return cost


def _number(value: Any) -> float | None:
    """Número finito e não negativo; qualquer outra coisa é "não informado"."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if number >= 0 and number != float("inf") else None


def _to_response(completion: Any) -> ChatResponse:
    choice = completion.choices[0]
    message: ChatMessage = {"role": choice.message.role, "content": choice.message.content}
    tool_calls = _to_tool_calls(choice.message.tool_calls)
    if tool_calls:
        message["tool_calls"] = tool_calls
    response: ChatResponse = {"message": message, "finish_reason": choice.finish_reason or "stop"}
    if completion.model:
        response["model"] = completion.model
    usage = _to_usage(completion.usage)
    if usage is not None:
        response["usage"] = usage
    return response


def _to_chunk(event: Any) -> ChatChunk:
    """`finish_reason` e `usage` aparecem só no último pedaço, como o contrato 001 exige."""
    choice = event.choices[0] if event.choices else None
    delta = "" if choice is None else (choice.delta.content or "")
    chunk: ChatChunk = {"delta": delta}
    if choice is not None:
        tool_calls = _to_tool_calls(choice.delta.tool_calls)
        if tool_calls:
            chunk["tool_calls"] = tool_calls
        if choice.finish_reason:
            chunk["finish_reason"] = choice.finish_reason
    usage = _to_usage(getattr(event, "usage", None))
    if usage is not None:
        chunk["usage"] = usage
    return chunk

"""Parte comum dos providers remotos — OpenAI e OpenRouter (contracts/remote-adapters.md; research R20, R21).

Sobre a camada compatível, um remoto acrescenta só a credencial: lida uma vez, na construção, pela porta
`SecretResolver`. Sem ela, o provider fica registrado e explica a falta — `chat` falha antes de qualquer requisição e
`probe` relata, sem rede (FR-011, ADR-020). O valor da chave nunca entra em mensagem.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import ClassVar, Final, Literal, overload

import httpx2
from openai import OpenAIError

from ai_core.llm.adapters.openai_compat import OpenAICompatProvider
from ai_core.llm.api import ModelCallFailed
from ai_core.llm.ports import ProbeResult, SecretResolver
from ai_core_contracts import ChatChunk, ChatMessage, ChatResponse, ChatTool, JSONValue

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
        if stream:
            return await super().chat(messages, model, tools=tools, response_format=response_format, stream=True)
        return await super().chat(messages, model, tools=tools, response_format=response_format, stream=False)

    async def probe(self, model: str) -> ProbeResult:
        if self._missing is not None:
            return ProbeResult(available=False, detail=self._missing)
        return await super().probe(model)

    def _reason(self, error: OpenAIError) -> str:
        """O motivo da camada compatível, com o valor da chave trocado — o 401 da OpenAI ecoa a chave mascarada, e um
        proxy poderia ecoá-la inteira (FR-011)."""
        reason = super()._reason(error)
        return reason.replace(self._key, MASK) if self._key else reason

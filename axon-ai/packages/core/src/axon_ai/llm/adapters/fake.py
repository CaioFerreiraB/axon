"""Provider simulado: o adapter em memória da porta `ModelProvider` (princípio XIII, research R11).

É também o provider do perfil de teste da composition root (011 US3): a suíte ponta a ponta sobe a plataforma inteira
sem rede. Nada aqui fala com o mundo — o roteiro é dado na construção.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any, Literal, overload

from axon_ai.llm.api import ModelCallFailed, ModelMessage
from axon_ai.llm.ports import ProbeResult
from axon_ai_contracts import ChatChunk, ChatMessage, ChatResponse, ChatTool, ChatUsage, JSONValue

DEFAULT_USAGE: Mapping[str, int] = {"prompt_tokens": 7, "completion_tokens": 2}


class ScriptedProvider:
    """Respostas, pedaços e falhas programados; guarda as chamadas recebidas em `calls`."""

    def __init__(
        self,
        *,
        name: str = "fake",
        content: str = "resposta",
        deltas: Sequence[str] = ("Oi", " mundo"),
        usage: Mapping[str, int] | None = DEFAULT_USAGE,
        finish_reason: str = "stop",
        error: ModelCallFailed | None = None,
        fail_after: int | None = None,
        known_models: Sequence[str] | None = None,
        cost: float | None = None,
        unready: str | None = None,
        reports_cost: bool = False,
    ) -> None:
        self._name = name
        self._reports_cost = reports_cost
        self._content = content
        self._deltas = tuple(deltas)
        self._usage: ChatUsage | None = (
            None
            if usage is None
            else ChatUsage(prompt_tokens=usage["prompt_tokens"], completion_tokens=usage["completion_tokens"])
        )
        if self._usage is not None and cost is not None:
            self._usage["cost"] = cost
        self._finish_reason = finish_reason
        self._error = error
        self._fail_after = fail_after
        self._known_models = None if known_models is None else tuple(known_models)
        self._unready = unready
        self.calls: list[dict[str, Any]] = []
        self.images: list[str] = []
        """Os data URIs que chegaram, na ordem: as suítes provam o que chegou ao modelo (ADR-044, item 12)."""

    @property
    def name(self) -> str:
        return self._name

    @property
    def reports_cost(self) -> bool:
        return self._reports_cost

    @overload
    async def chat(
        self,
        messages: Sequence[ModelMessage],
        model: str,
        *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
        stream: Literal[False] = False,
    ) -> ChatResponse: ...

    @overload
    async def chat(
        self,
        messages: Sequence[ModelMessage],
        model: str,
        *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
        stream: Literal[True],
    ) -> AsyncIterator[ChatChunk]: ...

    async def chat(
        self,
        messages: Sequence[ModelMessage],
        model: str,
        *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
        stream: bool = False,
    ) -> ChatResponse | AsyncIterator[ChatChunk]:
        self.calls.append(
            {
                "model": model,
                "messages": list(messages),
                "tools": None if tools is None else list(tools),
                "response_format": None if response_format is None else dict(response_format),
                "stream": stream,
            }
        )
        self.images.extend(
            part["image_url"]["url"]
            for message in messages
            if not isinstance(message["content"], str | None)
            for part in message["content"]
            if part["type"] == "image_url"
        )
        if stream:
            return self._stream()
        if self._error is not None:
            raise self._error
        message: ChatMessage = {"role": "assistant", "content": self._content}
        response: ChatResponse = {"message": message, "finish_reason": self._finish_reason, "model": model}
        if self._usage is not None:
            response["usage"] = self._usage
        return response

    async def _stream(self) -> AsyncIterator[ChatChunk]:
        if self._error is not None and self._fail_after is None:
            raise self._error
        for index, delta in enumerate(self._deltas):
            if self._fail_after is not None and index >= self._fail_after and self._error is not None:
                raise self._error
            yield {"delta": delta}
        final: ChatChunk = {"delta": "", "finish_reason": self._finish_reason}
        if self._usage is not None:
            final["usage"] = self._usage
        yield final

    async def probe(self, model: str) -> ProbeResult:
        """Sondagem programada: falha configurada vira indisponibilidade, como num provider real."""
        if self._error is not None:
            return ProbeResult(available=False, detail=self._error.reason)
        if self._known_models is not None and model not in self._known_models:
            disponiveis = ", ".join(self._known_models) or "nenhum"
            return ProbeResult(available=False, detail=f"modelo {model} não encontrado; disponíveis: {disponiveis}")
        return ProbeResult(available=True)

    async def ready(self) -> ProbeResult:
        """Pronto, salvo quando `unready` programa o motivo — como um remoto sem chave ou um local fora do ar."""
        return ProbeResult(available=self._unready is None, detail=self._unready)

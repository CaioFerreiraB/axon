"""Serviço do Model Router: implementa o seam da 006 (contracts/model-router.md).

Orquestra `domain/` e as portas. É aqui que a chamada de modelo vira dado de trace: quem instrumenta é o cliente
devolvido pelo roteador, para que SC-002 ("100% das chamadas rastreáveis") valha por construção, sem depender de
disciplina de quem consome (research R7). Não importa `adapters/`.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Final

from ai_core.llm.api import (
    ModelCallFailed,
    ModelHealth,
    ModelPolicy,
    ModelRef,
    ModelRole,
    ModelRouter,
    ProviderStatus,
    UnknownProvider,
)
from ai_core.llm.domain.output import constraint_problem
from ai_core.llm.domain.policy import ensure_allowed, resolve
from ai_core.llm.ports import Clock, ModelProvider
from ai_core.observability.api import ExchangeMessage, ModelCall, ModelExchange, TraceSink
from axon_ai_contracts import ChatChunk, ChatMessage, ChatResponse, ChatTool, ChatToolCall, ChatUsage, JSONValue

ERROR_FINISH_REASON = "error"
"""Desfecho registrado quando a chamada falha — o trace cobre sucesso e falha (SC-002)."""


class TracedModel:
    """Cliente ligado a um modelo, que mede a própria chamada e a registra no Trace Sink.

    Antes do provider, e dentro do bloco medido, aplica a restrição de formato do papel (FR-005, research R17): a
    chamada recusada também vira um `ModelCall`, com `finish_reason="error"`.
    """

    def __init__(
        self,
        *,
        role: ModelRole,
        ref: ModelRef,
        provider: ModelProvider,
        trace: TraceSink,
        clock: Clock,
        request_id: str,
    ) -> None:
        self._role = role
        self._ref = ref
        self._provider = provider
        self._trace = trace
        self._clock = clock
        self._request_id = request_id

    @property
    def role(self) -> ModelRole:
        return self._role

    @property
    def ref(self) -> ModelRef:
        return self._ref

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
    ) -> ChatResponse:
        started = self._clock.monotonic()
        try:
            self._ensure_constraint(response_format)
            response = await self._provider.chat(
                messages, self._ref.model, tools=tools, response_format=response_format, stream=False
            )
        except BaseException:
            self._emit(started, finish_reason=ERROR_FINISH_REASON, usage=None)
            raise
        self._emit(started, finish_reason=response.get("finish_reason"), usage=response.get("usage"))
        self._exchange(messages, _text_of(response["message"]))
        return response

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """Emite ao encerrar o iterador — no fim, por erro ou por abandono de quem consome."""
        started = self._clock.monotonic()
        finish_reason: str | None = None
        usage: ChatUsage | None = None
        failed = False
        output: list[str] = []
        try:
            self._ensure_constraint(response_format)
            chunks = await self._provider.chat(
                messages, self._ref.model, tools=tools, response_format=response_format, stream=True
            )
            async for chunk in chunks:
                finish_reason = chunk.get("finish_reason", finish_reason)
                usage = chunk.get("usage", usage)
                output.append(chunk.get("delta") or "")
                output.extend(_tool_call_text(call) for call in chunk.get("tool_calls") or ())
                yield chunk
        except BaseException:
            failed = True
            raise
        finally:
            self._emit(
                started,
                finish_reason=ERROR_FINISH_REASON if failed else finish_reason,
                usage=usage,
            )
            if not failed:
                self._exchange(messages, "".join(output))

    def _ensure_constraint(self, response_format: Mapping[str, JSONValue] | None) -> None:
        problem = constraint_problem(self._role, response_format)
        if problem is not None:
            raise ModelCallFailed(provider=self._ref.provider, model=self._ref.model, reason=problem)

    def _exchange(self, messages: Sequence[ChatMessage], output: str) -> None:
        """O texto da chamada (ADR-034, 009 R35): o `TraceService` o descarta com a captura desligada. Sem cabeçalho nem
        credencial — só as mensagens e a saída."""
        self._trace.emit(
            ModelExchange(
                request_id=self._request_id,
                role=self._role,
                provider=self._ref.provider,
                model=self._ref.model,
                messages=tuple(_exchange_message(message) for message in messages),
                output=output,
            )
        )

    def _emit(self, started: float, *, finish_reason: str | None, usage: ChatUsage | None) -> None:
        self._trace.emit(
            ModelCall(
                request_id=self._request_id,
                role=self._role,
                provider=self._ref.provider,
                model=self._ref.model,
                duration_ms=max(0.0, (self._clock.monotonic() - started) * 1000),
                input_tokens=None if usage is None else usage["prompt_tokens"],
                output_tokens=None if usage is None else usage["completion_tokens"],
                finish_reason=finish_reason,
                cost_usd=None if usage is None else usage.get("cost"),
            )
        )


_EXCHANGE_ROLES: Final[frozenset[str]] = frozenset({"system", "user", "assistant", "tool"})


def _tool_call_text(call: ChatToolCall) -> str:
    return f"[tool {call['name']}: {call['arguments']}]"


def _text_of(message: ChatMessage) -> str:
    """Texto da mensagem; chamadas de tool viram marcadores com nome e argumentos."""
    parts = [message.get("content") or ""]
    parts.extend(_tool_call_text(call) for call in message.get("tool_calls") or ())
    return "\n".join(part for part in parts if part)


def _exchange_message(message: ChatMessage) -> ExchangeMessage:
    role = message["role"] if message["role"] in _EXCHANGE_ROLES else "user"
    return ExchangeMessage(role=role, content=_text_of(message))  # type: ignore[arg-type]


class ExecutionRouter:
    """Roteador de uma execução: política e requisição já fixadas (implementa `ModelRouter`)."""

    def __init__(
        self,
        *,
        policy: ModelPolicy,
        request_id: str,
        providers: Mapping[str, ModelProvider],
        trace: TraceSink,
        clock: Clock,
    ) -> None:
        self._policy = policy
        self._request_id = request_id
        self._providers = providers
        self._trace = trace
        self._clock = clock

    def for_role(self, role: ModelRole) -> TracedModel:
        """Resolve, confere a allowlist e liga o provider. As três falhas acontecem antes de qualquer I/O."""
        ref = ensure_allowed(resolve(self._policy, role), self._policy.allow)
        return TracedModel(
            role=role,
            ref=ref,
            provider=_provider_for(self._providers, ref),
            trace=self._trace,
            clock=self._clock,
            request_id=self._request_id,
        )


class ModelRoutingService:
    """Seam Model Router. Um por processo, montado pela composition root (spec 011) com os adapters do perfil."""

    def __init__(
        self,
        *,
        providers: Mapping[str, ModelProvider],
        trace: TraceSink,
        clock: Clock,
    ) -> None:
        self._providers = dict(providers)
        self._trace = trace
        self._clock = clock

    def for_execution(self, *, policy: ModelPolicy, request_id: str) -> ModelRouter:
        """Liga política e requisição. Não faz I/O e não instancia adapter (011 US1 cenário 5)."""
        return ExecutionRouter(
            policy=policy,
            request_id=request_id,
            providers=self._providers,
            trace=self._trace,
            clock=self._clock,
        )

    async def check(self, policy: ModelPolicy) -> tuple[ModelHealth, ...]:
        """Sonda um provider por papel configurado. Indisponibilidade é resultado, não exceção (FR-009)."""
        results: list[ModelHealth] = []
        for role in policy.configured_roles():
            ref = policy.roles[role]
            try:
                provider = _provider_for(self._providers, ref)
            except UnknownProvider as error:
                results.append(ModelHealth(role=role, ref=ref, available=False, detail=str(error)))
                continue
            probe = await provider.probe(ref.model)
            results.append(ModelHealth(role=role, ref=ref, available=probe.available, detail=probe.detail))
        return tuple(results)

    async def providers(self) -> tuple[ProviderStatus, ...]:
        """Sonda os providers juntos: o local fora do ar não atrasa os outros (ADR-035)."""
        names = sorted(self._providers)
        results = await asyncio.gather(*(self._providers[name].ready() for name in names))
        return tuple(
            ProviderStatus(
                name=name,
                ready=result.available,
                detail=result.detail,
                reports_cost=self._providers[name].reports_cost,
            )
            for name, result in zip(names, results, strict=True)
        )


def _provider_for(providers: Mapping[str, ModelProvider], ref: ModelRef) -> ModelProvider:
    try:
        return providers[ref.provider]
    except KeyError:
        known = ", ".join(sorted(providers)) or "nenhum"
        raise UnknownProvider(f"provider '{ref.provider}' não registrado; providers conhecidos: {known}") from None

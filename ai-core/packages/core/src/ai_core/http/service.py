"""Serviço de chat: liga a requisição HTTP ao motor (005) e devolve respostas já no formato OpenAI.

Não conhece HTTP — nem status, nem cabeçalho, nem conexão. Isso é do adapter; aqui só existem a resolução do grant, a
execução e a construção das respostas por `domain/`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from ai_core.graph.api import (
    ExecutionEngine,
    ExecutionRequest,
    FinalEvent,
    ProgressEvent,
    TokenEvent,
)
from ai_core.http.domain.chat_request import ChatRequest
from ai_core.http.domain.openai_chunks import (
    completion,
    final_chunk,
    finish_reason,
    opening_chunk,
    progress_chunk,
    token_chunk,
)
from ai_core.http.ports import Clock, GrantResolver, Principal, RequestIds

FINISH_ERROR = "error"


@dataclass(frozen=True, slots=True, kw_only=True)
class CompletionResult:
    """Resposta sem streaming, com o desfecho separado para o adapter escolher o status."""

    body: dict[str, Any]
    request_id: str
    failed: bool


class ChatService:
    """Um serviço por processo, montado pela composition root (spec 011)."""

    def __init__(
        self,
        *,
        engine: ExecutionEngine,
        grants: GrantResolver,
        request_ids: RequestIds,
        clock: Clock,
    ) -> None:
        self._engine = engine
        self._grants = grants
        self._request_ids = request_ids
        self._clock = clock

    async def stream(self, request: ChatRequest, principal: Principal) -> AsyncIterator[dict[str, Any]]:
        """Chunks prontos, um por evento do motor, entregues no instante em que chegam."""
        grant = await self._grants.resolve(model=request.model, principal=principal)
        request_id = self._request_ids.next()
        created = self._clock.now()
        model = request.model

        events = self._engine.run(grant, self._execution_request(request, request_id))
        yield opening_chunk(request_id=request_id, model=model, created=created)
        async for event in events:
            match event:
                case TokenEvent():
                    yield token_chunk(event, request_id=request_id, model=model, created=created)
                case ProgressEvent():
                    yield progress_chunk(event, request_id=request_id, model=model, created=created)
                case FinalEvent():
                    yield final_chunk(event, request_id=request_id, model=model, created=created)

    async def complete(self, request: ChatRequest, principal: Principal) -> CompletionResult:
        """Resposta única. O desfecho volta separado porque uma execução que falhou não é 200 (princípio VII)."""
        grant = await self._grants.resolve(model=request.model, principal=principal)
        request_id = self._request_ids.next()
        created = self._clock.now()

        final: FinalEvent | None = None
        async for event in self._engine.run(grant, self._execution_request(request, request_id)):
            if isinstance(event, FinalEvent):
                final = event
        if final is None:  # pragma: no cover — o motor promete um evento final sempre
            final = FinalEvent(answer="")

        return CompletionResult(
            body=completion(final, request_id=request_id, model=request.model, created=created),
            request_id=request_id,
            failed=finish_reason(final) == FINISH_ERROR,
        )

    def new_request_id(self) -> str:
        """Identificador para respostas que nem chegam a executar (erro de requisição), mas precisam do cabeçalho."""
        return self._request_ids.next()

    @staticmethod
    def _execution_request(request: ChatRequest, request_id: str) -> ExecutionRequest:
        """A API **nunca** preenche a data de referência: avaliação fixa a data em processo (FR-012, ADR-013)."""
        return ExecutionRequest(request_id=request_id, messages=request.messages, stream=request.stream)

"""Serviços da API: liga a requisição HTTP ao motor (005) e às conversas, e devolve respostas no formato OpenAI.

Não conhece HTTP — nem status, nem cabeçalho, nem conexão. Isso é do adapter; aqui existem a resolução do grant (003),
o fluxo de conversa (research R21), a execução e a construção das respostas por `domain/`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final

from ai_core.assistants.api import GrantResolver, NotFound, Principal
from ai_core.graph.api import (
    ExecutionEngine,
    ExecutionGrant,
    ExecutionRequest,
    FinalEvent,
    ProgressEvent,
    TokenEvent,
)
from ai_core.http.domain.chat_request import ChatRequest
from ai_core.http.domain.conversations import exchange, execution_messages, last_user_message
from ai_core.http.domain.errors import NOT_FOUND, ConversationMismatch
from ai_core.http.domain.openai_chunks import (
    completion,
    final_chunk,
    finish_reason,
    opening_chunk,
    progress_chunk,
    token_chunk,
)
from ai_core.http.ports import Clock, Conversation, ConversationPage, ConversationStore, RequestIds, StoredMessage
from ai_core_contracts import Message

FINISH_ERROR: Final = "error"
CONVERSATION_PREFIX: Final = "conv_"
DEFAULT_RETENTION: Final = timedelta(days=180)
"""Prazo de retenção de conversas sem atividade (FR-019); configurável pelo operador (011)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class CompletionResult:
    """Resposta sem streaming, com o desfecho separado para o adapter escolher o status."""

    body: dict[str, Any]
    request_id: str
    conversation_id: str
    failed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class _Turn:
    grant: ExecutionGrant
    conversation: Conversation
    messages: tuple[Message, ...]
    user: Message


class ChatService:
    """Um serviço por processo, montado pela composition root (spec 011)."""

    def __init__(
        self,
        *,
        engine: ExecutionEngine,
        grants: GrantResolver,
        request_ids: RequestIds,
        clock: Clock,
        conversations: ConversationStore,
        conversation_ids: RequestIds,
    ) -> None:
        self._engine = engine
        self._grants = grants
        self._request_ids = request_ids
        self._clock = clock
        self._conversations = conversations
        self._conversation_ids = conversation_ids

    async def stream(self, request: ChatRequest, principal: Principal) -> AsyncIterator[dict[str, Any]]:
        """Chunks prontos, um por evento do motor, entregues no instante em que chegam."""
        turn = await self._open(request, principal)
        request_id = self._request_ids.next()
        created = self._clock.now()
        model = request.model

        events = self._engine.run(turn.grant, self._execution_request(turn, request, request_id))
        yield opening_chunk(request_id=request_id, model=model, created=created, conversation_id=turn.conversation.id)
        async for event in events:
            match event:
                case TokenEvent():
                    yield token_chunk(event, request_id=request_id, model=model, created=created)
                case ProgressEvent():
                    yield progress_chunk(event, request_id=request_id, model=model, created=created)
                case FinalEvent():
                    # Grava antes do último chunk: quando o cliente vê o fim, a troca já está no histórico.
                    await self._record(turn, event, request_id)
                    yield final_chunk(event, request_id=request_id, model=model, created=created)

    async def complete(self, request: ChatRequest, principal: Principal) -> CompletionResult:
        """Resposta única. O desfecho volta separado porque uma execução que falhou não é 200 (princípio VII)."""
        turn = await self._open(request, principal)
        request_id = self._request_ids.next()
        created = self._clock.now()

        final: FinalEvent | None = None
        async for event in self._engine.run(turn.grant, self._execution_request(turn, request, request_id)):
            if isinstance(event, FinalEvent):
                final = event
        if final is None:  # pragma: no cover — o motor promete um evento final sempre
            final = FinalEvent(answer="")
        await self._record(turn, final, request_id)

        return CompletionResult(
            body=completion(
                final,
                request_id=request_id,
                model=request.model,
                created=created,
                conversation_id=turn.conversation.id,
            ),
            request_id=request_id,
            conversation_id=turn.conversation.id,
            failed=finish_reason(final) == FINISH_ERROR,
        )

    async def _open(self, request: ChatRequest, principal: Principal) -> _Turn:
        """Conversa antes do grant: conversa alheia (404) e de outro Assistant (400) são recusadas sem consumir a cota
        do Assistant. Sem id, a conversa nasce antes da execução, para que o id saia no primeiro chunk (R21)."""
        user = last_user_message(request.messages)
        requested_assistant = request.model.partition("/")[0]
        existing: Conversation | None = None
        if request.conversation_id is not None:
            existing = await self._conversations.get(principal.subject, request.conversation_id)
            if existing is None:
                raise NotFound(NOT_FOUND)
            if existing.assistant != requested_assistant:
                raise ConversationMismatch(
                    f"a conversa '{existing.id}' é do Assistant '{existing.assistant}', não de '{requested_assistant}'"
                )

        grant = await self._grants.resolve(model=request.model, principal=principal)

        if existing is not None:
            history = await self._conversations.messages(principal.subject, existing.id) or ()
            return _Turn(
                grant=grant, conversation=existing, messages=execution_messages(history, request.messages), user=user
            )
        now = self._clock.now()
        conversation = Conversation(
            id=f"{CONVERSATION_PREFIX}{self._conversation_ids.next()}",
            owner=principal.subject,
            assistant=grant.assistant,
            model=request.model,
            created_at=now,
            last_activity_at=now,
        )
        await self._conversations.create(conversation)
        return _Turn(grant=grant, conversation=conversation, messages=tuple(request.messages), user=user)

    async def _record(self, turn: _Turn, final: FinalEvent, request_id: str) -> None:
        """Grava a troca se a execução não falhou. Conversa apagada no meio não recebe a troca (FR-018)."""
        now = self._clock.now()
        records = exchange(turn.user, final, request_id=request_id, at=now)
        if records:
            await self._conversations.append(turn.conversation.owner, turn.conversation.id, records, at=now)

    @staticmethod
    def _execution_request(turn: _Turn, request: ChatRequest, request_id: str) -> ExecutionRequest:
        """A API **nunca** preenche a data de referência: avaliação fixa a data em processo (FR-012, ADR-013)."""
        return ExecutionRequest(request_id=request_id, messages=turn.messages, stream=request.stream)


class ConversationService:
    """Listar, ler, apagar e expirar conversas — sempre no escopo do subject (clarificação 3)."""

    def __init__(self, *, store: ConversationStore, clock: Clock, retention: timedelta = DEFAULT_RETENTION) -> None:
        self._store = store
        self._clock = clock
        self._retention = retention

    async def page(self, principal: Principal, *, limit: int, cursor: str | None) -> ConversationPage:
        return await self._store.list(principal.subject, limit=limit, cursor=cursor)

    async def read(self, principal: Principal, conversation_id: str) -> tuple[Conversation, Sequence[StoredMessage]]:
        conversation = await self._store.get(principal.subject, conversation_id)
        messages = await self._store.messages(principal.subject, conversation_id)
        if conversation is None or messages is None:
            raise NotFound(NOT_FOUND)
        return conversation, messages

    async def delete(self, principal: Principal, conversation_id: str) -> None:
        if not await self._store.delete(principal.subject, conversation_id):
            raise NotFound(NOT_FOUND)

    async def expire(self) -> int:
        """Apaga as conversas sem atividade há mais que o prazo (FR-019). Quem agenda é a composition root (011)."""
        return await self._store.delete_inactive(before=self._clock.now() - self._retention)

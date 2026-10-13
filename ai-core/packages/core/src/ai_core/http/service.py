"""Serviços da API: liga a requisição HTTP ao motor (005) e às conversas, e devolve respostas no formato OpenAI.

Não conhece HTTP — nem status, nem cabeçalho, nem conexão. Isso é do adapter; aqui existem a resolução do grant (003),
o fluxo de conversa (research R21), a execução e a construção das respostas por `domain/`.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Final

from ai_core.assistants.api import GrantResolver, NotFound, Principal
from ai_core.graph.api import (
    ExecutionEngine,
    ExecutionGrant,
    ExecutionIssue,
    ExecutionRequest,
    FinalEvent,
    ProgressEvent,
    TokenEvent,
)
from ai_core.http.domain.admission import AdmissionLimits, decide, retry_after
from ai_core.http.domain.chat_request import ChatRequest
from ai_core.http.domain.conversations import exchange, execution_messages, last_user_message
from ai_core.http.domain.errors import (
    NOT_FOUND,
    QUEUE_TIMEOUT_KIND,
    QUEUE_TIMEOUT_STAGE,
    ConversationMismatch,
    Overloaded,
)
from ai_core.http.domain.openai_chunks import (
    completion,
    final_chunk,
    finish_reason,
    opening_chunk,
    progress_chunk,
    queue_chunk,
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
    conversation_id: str | None
    """`None` no pedido efêmero (FR-023)."""
    failed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class _Prepared:
    """O pedido depois das recusas da conversa e do grant, antes da admissão e de criar qualquer conversa."""

    grant: ExecutionGrant
    existing: Conversation | None
    messages: tuple[Message, ...]
    user: Message


@dataclass(frozen=True, slots=True, kw_only=True)
class _Turn:
    grant: ExecutionGrant
    conversation: Conversation | None
    """`None` no pedido efêmero (FR-023): nada a criar, gravar ou devolver."""
    messages: tuple[Message, ...]
    user: Message
    new: bool

    @property
    def conversation_id(self) -> str | None:
        return None if self.conversation is None else self.conversation.id


class Admission:
    """O lugar de um pedido na admissão: segurando uma vaga, ou esperando na fila (`position` a partir de 1)."""

    __slots__ = ("holding", "position", "released", "waiter")

    def __init__(self, *, waiter: asyncio.Future[None] | None = None, position: int = 0) -> None:
        self.waiter = waiter
        self.position = position
        self.holding = waiter is None
        self.released = False

    @property
    def queued(self) -> bool:
        return not self.holding


class ExecutionSlots:
    """Vagas de execução e a fila de espera, em memória e por processo (FR-016; design.md "Admissão e fila").

    A decisão é a pura de `domain/admission.py`; aqui só se guarda o estado. A vaga liberada passa direto ao primeiro da
    fila — a contagem de vagas ocupadas não cai —, e quem desiste ou esgota a espera sai da fila sem ocupar vaga.
    """

    def __init__(self, limits: AdmissionLimits) -> None:
        self.limits = limits
        self._running = 0
        self._queue: deque[asyncio.Future[None]] = deque()

    def admit(self) -> Admission:
        match decide(self._running, len(self._queue), self.limits):
            case "run":
                self._running += 1
                return Admission()
            case "queue":
                waiter: asyncio.Future[None] = asyncio.get_running_loop().create_future()
                self._queue.append(waiter)
                return Admission(waiter=waiter, position=len(self._queue))
            case _:
                raise Overloaded(retry_after(self.limits))

    async def wait(self, admission: Admission) -> bool:
        """Espera a vaga até o máximo do operador. Falso quando a espera esgota (e o pedido sai da fila)."""
        waiter = admission.waiter
        if admission.holding or waiter is None:
            return True
        await asyncio.wait({waiter}, timeout=self.limits.max_wait.total_seconds())
        if waiter.done() and not waiter.cancelled():
            admission.holding = True
            return True
        self._forget(waiter)
        return False

    def release(self, admission: Admission) -> None:
        """Libera o que o pedido tem — a vaga, ou o lugar na fila. Idempotente; chamado no `finally` da execução."""
        if admission.released:
            return
        admission.released = True
        waiter = admission.waiter
        if admission.holding or (waiter is not None and waiter.done() and not waiter.cancelled()):
            self._hand_over()
        elif waiter is not None:
            self._forget(waiter)

    def _hand_over(self) -> None:
        while self._queue:
            waiter = self._queue.popleft()
            if not waiter.done():
                waiter.set_result(None)
                return
        self._running -= 1

    def _forget(self, waiter: asyncio.Future[None]) -> None:
        if waiter in self._queue:
            self._queue.remove(waiter)
        if not waiter.done():
            waiter.cancel()


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
        admission: AdmissionLimits | None = None,
    ) -> None:
        self._engine = engine
        self._grants = grants
        self._request_ids = request_ids
        self._clock = clock
        self._conversations = conversations
        self._conversation_ids = conversation_ids
        self._slots = ExecutionSlots(admission) if admission is not None else None

    async def stream(self, request: ChatRequest, principal: Principal) -> AsyncIterator[dict[str, Any]]:
        """Chunks prontos, um por evento do motor, entregues no instante em que chegam.

        A recusa por sobrecarga sai antes do primeiro chunk — o adapter ainda escolhe o status (503). Quem espera na
        fila recebe a abertura e o aviso de fila na hora; esgotada a espera, o stream termina com o registro de erro
        (FR-017). O progresso vai como raciocínio só até o primeiro token (FR-005, R34).
        """
        prepared = await self._prepare(request, principal)
        admission = self._slots.admit() if self._slots is not None else None
        try:
            turn = await self._start(prepared, request, principal)
            request_id = self._request_ids.next()
            created = self._clock.now()
            model = request.model
            envelope: dict[str, Any] = {"request_id": request_id, "model": model, "created": created}

            events = self._engine.run(turn.grant, self._execution_request(turn, request, request_id))
            yield opening_chunk(**envelope, conversation_id=turn.conversation_id)
            if admission is not None and admission.queued:
                yield queue_chunk(position=admission.position, **envelope)
                assert self._slots is not None
                if not await self._slots.wait(admission):
                    await _close(events)
                    await self._discard(turn)
                    yield final_chunk(FinalEvent(answer="", errors=(_queue_timeout(),)), **envelope)
                    return
            reasoning = True
            async for event in events:
                match event:
                    case TokenEvent():
                        reasoning = False
                        yield token_chunk(event, **envelope)
                    case ProgressEvent():
                        yield progress_chunk(event, **envelope, reasoning=reasoning)
                    case FinalEvent():
                        # Grava antes do último chunk: quando o cliente vê o fim, a troca já está no histórico.
                        await self._record(turn, event, request_id)
                        yield final_chunk(event, **envelope)
        finally:
            if admission is not None and self._slots is not None:
                self._slots.release(admission)

    async def complete(self, request: ChatRequest, principal: Principal) -> CompletionResult:
        """Resposta única. O desfecho volta separado porque uma execução que falhou não é 200 (princípio VII)."""
        prepared = await self._prepare(request, principal)
        admission = self._slots.admit() if self._slots is not None else None
        try:
            if admission is not None and self._slots is not None and not await self._slots.wait(admission):
                raise Overloaded(retry_after(self._slots.limits))
            turn = await self._start(prepared, request, principal)
            request_id = self._request_ids.next()
            created = self._clock.now()

            final: FinalEvent | None = None
            async for event in self._engine.run(turn.grant, self._execution_request(turn, request, request_id)):
                if isinstance(event, FinalEvent):
                    final = event
        finally:
            if admission is not None and self._slots is not None:
                self._slots.release(admission)
        if final is None:  # pragma: no cover — o motor promete um evento final sempre
            final = FinalEvent(answer="")
        await self._record(turn, final, request_id)

        return CompletionResult(
            body=completion(
                final,
                request_id=request_id,
                model=request.model,
                created=created,
                conversation_id=turn.conversation_id,
            ),
            request_id=request_id,
            conversation_id=turn.conversation_id,
            failed=finish_reason(final) == FINISH_ERROR,
        )

    async def _prepare(self, request: ChatRequest, principal: Principal) -> _Prepared:
        """Conversa antes do grant: conversa alheia (404) e de outro Assistant (400) são recusadas sem consumir a cota
        do Assistant. Nada é criado aqui: a admissão vem depois, e a recusa por sobrecarga não deixa conversa vazia."""
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
            return _Prepared(
                grant=grant, existing=existing, messages=execution_messages(history, request.messages), user=user
            )
        return _Prepared(grant=grant, existing=None, messages=tuple(request.messages), user=user)

    async def _start(self, prepared: _Prepared, request: ChatRequest, principal: Principal) -> _Turn:
        """Admitido (ou na fila, em streaming): sem id, a conversa nasce agora, para que o id saia no primeiro chunk
        (R21) — exceto no pedido efêmero, que não tem conversa (FR-023)."""
        if prepared.existing is None and not request.store:
            return _Turn(
                grant=prepared.grant, conversation=None, messages=prepared.messages, user=prepared.user, new=False
            )
        if prepared.existing is not None:
            return _Turn(
                grant=prepared.grant,
                conversation=prepared.existing,
                messages=prepared.messages,
                user=prepared.user,
                new=False,
            )
        now = self._clock.now()
        conversation = Conversation(
            id=f"{CONVERSATION_PREFIX}{self._conversation_ids.next()}",
            owner=principal.subject,
            assistant=prepared.grant.assistant,
            model=request.model,
            created_at=now,
            last_activity_at=now,
        )
        await self._conversations.create(conversation)
        return _Turn(
            grant=prepared.grant, conversation=conversation, messages=prepared.messages, user=prepared.user, new=True
        )

    async def _discard(self, turn: _Turn) -> None:
        """A espera esgotou com o stream aberto: a conversa que nasceu para este pedido sai, vazia."""
        if turn.new and turn.conversation is not None:
            await self._conversations.delete(turn.conversation.owner, turn.conversation.id)

    async def _record(self, turn: _Turn, final: FinalEvent, request_id: str) -> None:
        """Grava a troca se a execução não falhou. Conversa apagada no meio não recebe a troca (FR-018); o pedido
        efêmero não grava nada (FR-023)."""
        if turn.conversation is None:
            return
        now = self._clock.now()
        records = exchange(turn.user, final, request_id=request_id, at=now)
        if records:
            await self._conversations.append(turn.conversation.owner, turn.conversation.id, records, at=now)

    @staticmethod
    def _execution_request(turn: _Turn, request: ChatRequest, request_id: str) -> ExecutionRequest:
        """A API **nunca** preenche a data de referência: avaliação fixa a data em processo (FR-012, ADR-013)."""
        return ExecutionRequest(request_id=request_id, messages=turn.messages, stream=request.stream)


def _queue_timeout() -> ExecutionIssue:
    return ExecutionIssue(
        stage=QUEUE_TIMEOUT_STAGE,
        kind=QUEUE_TIMEOUT_KIND,
        message="a espera por uma vaga de execução esgotou; nenhuma execução aconteceu — tente de novo",
    )


async def _close(events: AsyncIterator[Any]) -> None:
    """Fecha o iterador do motor que nunca chegou a rodar (espera esgotada)."""
    close = getattr(events, "aclose", None)
    if close is not None:
        await close()


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

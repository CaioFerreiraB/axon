"""Portas secundárias do motor (specs/005-core-execution-engine/contracts/ports.md).

Não são seams: são internas do módulo, e só a composition root (spec 011) escolhe o adapter de cada uma.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from ai_core.graph.api import ExecutionEvent
from ai_core.llm.api import ModelRouter
from ai_core.observability.api import TraceSink
from ai_core.packs.api import Composition, PackHooks
from ai_core_contracts import Message


class Clock(Protocol):
    """Tempo, por porta (ADR-013).

    Sem ela, `reference_time` viria do relógio do sistema dentro do serviço e o conjunto dourado da 105 deixaria de ser
    reproduzível — exatamente o problema que o ADR-013 resolve. A porta de outros módulos tem a mesma forma, então um
    único adapter serve aos três; quem injeta é a 011 (FR-008 da 011).
    """

    def now(self) -> datetime:
        """Instante atual, sempre com timezone. Fixa a data de referência da execução."""
        ...

    def monotonic(self) -> float:
        """Leitura de um relógio que nunca anda para trás, em segundos. Mede a duração da execução."""
        ...


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionPlan:
    """Tudo que o adapter de fluxo precisa para executar um turno. Interno: nenhum outro módulo o conhece.

    Os seams chegam aqui **já restritos** ao que a execução pode usar: o roteador já está ligado à política de modelos
    e ao identificador da requisição, e a composição já foi validada. O filtro por Assistant acontece antes, na
    construção do plano, nunca dentro de um nó.
    """

    flow: str
    request_id: str
    assistant: str
    reference_time: datetime
    question: str
    messages: Sequence[Message]
    composition: Composition
    hooks: PackHooks
    router: ModelRouter
    trace: TraceSink


class FlowRuntime(Protocol):
    """O framework de grafo, atrás de uma porta (ADR-011).

    É o que torna o SC-001 barato: trocar o framework é trocar o objeto injetado no serviço. O serviço não conhece
    estado, nós nem arestas — só pede os eventos de um plano.
    """

    def names(self) -> frozenset[str]:
        """Nomes de flow que este runtime sabe executar."""
        ...

    def events(self, plan: ExecutionPlan) -> AsyncIterator[ExecutionEvent]:
        """Executa o flow do plano. NUNCA levanta depois do primeiro evento: falha vira `FinalEvent` com erros."""
        ...

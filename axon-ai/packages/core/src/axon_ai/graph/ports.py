"""Portas secundárias do motor (specs/005-core-execution-engine/contracts/ports.md).

Não são seams: são internas do módulo, e só a composition root (spec 011) escolhe o adapter de cada uma.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo
from typing import Protocol

from axon_ai.capabilities.api import Capabilities
from axon_ai.graph.api import ExecutionEvent, ExecutionGrant, RagSettings
from axon_ai.llm.api import ModelRouter
from axon_ai.observability.api import TraceSink
from axon_ai.packs.api import Composition, PackHooks
from axon_ai_contracts import Message


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
    construção do plano, nunca dentro de um nó — e o catálogo de tools, na abertura da sessão pela 004, com o grant.

    `max_iterations` e `max_context_tokens` só são preenchidos nos flows de tool: o `chat` não lê limites (R22). `rag` e
    `escalate` só no `rag_first`: os números do operador e se o portão pode escalar para o loop (o grant declara
    `controller`; R40, R44).
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
    grant: ExecutionGrant | None = None
    capabilities: Capabilities | None = None
    max_iterations: int | None = None
    max_context_tokens: int | None = None
    rag: RagSettings | None = None
    escalate: bool = False
    timezone: tzinfo = UTC
    """O fuso da instalação: a data de referência vai ao controller e à geração do `agentic` nele (R50)."""


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

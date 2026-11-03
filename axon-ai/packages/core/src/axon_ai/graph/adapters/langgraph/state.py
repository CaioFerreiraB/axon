"""Estado e contexto internos de uma execução — PRIVADOS (ADR-011).

Nenhum outro módulo importa este arquivo, e nada daqui atravessa o seam: packs enxergam a Turn View (001) e a 008
enxerga os eventos do `api.py`. Trocar o framework de grafo é reescrever este arquivo junto com os outros do pacote.

```text
AgentState   → dados da execução
AgentContext → serviços e recursos disponíveis
```
"""

from __future__ import annotations

import operator
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, tzinfo
from typing import Annotated, Literal, TypedDict

from axon_ai.capabilities.api import Capabilities, DelegatedAuthorization, ToolCall, ToolSession
from axon_ai.graph.api import ExecutionGrant, ExecutionIssue, RagSettings
from axon_ai.graph.domain.gate import Passage
from axon_ai.graph.domain.images import ImagePlan
from axon_ai.graph.domain.transcript import Step
from axon_ai.llm.api import ModelRouter
from axon_ai.observability.api import TraceSink
from axon_ai.packs.api import Composition, PackHooks, StreamedValidation, ValidationOutcome
from axon_ai_contracts import Attachment, Chart, Citation, JSONValue, Message


class AgentState(TypedDict, total=False):
    """Dados que a execução carrega entre os passos.

    `errors`, `steps` e `decisions` acumulam com reducer: é o que impede perda entre as iterações do loop (FR-009,
    SC-005). `messages` é lista simples porque as mensagens deste projeto são as do contrato 001, não as do framework.
    Os campos do loop só existem no `agentic` (e no loop escalado do `rag_first`); o `chat` não os lê. `retrieved` e
    `reranked` só existem no `rag_first` (R43).
    """

    # identidade — escrita uma vez
    request_id: str
    assistant: str
    flow: str
    reference_time: datetime
    question: str

    # conversa
    messages: Sequence[Message]

    # fatias isoladas por pack
    packs: dict[str, dict[str, JSONValue]]

    # saída
    answer: str
    citations: Sequence[Citation]
    streamed: StreamedValidation | None
    validation: ValidationOutcome | None

    # controle do loop (agentic) — research R20, R22
    iteration: int
    limit: int | None
    ceiling: int | None
    route: Literal["controller", "execute_tool", "generate", "rerank", "image_gate", "end"]
    pending: ToolCall | None
    omitted: int

    # recuperação (rag_first) — research R37, R38, R43
    retrieved: tuple[Passage, ...]
    reranked: tuple[Passage, ...]

    # imagens (ADR-044) — research R51
    gate_images: bool

    # acumuladores (reducer obrigatório)
    errors: Annotated[list[ExecutionIssue], operator.add]
    steps: Annotated[list[Step], operator.add]
    decisions: Annotated[list[str], operator.add]
    viewed: Annotated[list[str], operator.add]
    """Ids das imagens da resposta anterior que vão à geração: as escolhidas pelo controller ou, sem ele, todas."""
    attachments: Annotated[list[Attachment], operator.add]
    """Imagens que as tools devolveram, na ordem em que saíram, uma vez por `id` — o que o usuário recebe."""
    charts: Annotated[list[Chart], operator.add]
    """Gráficos que as tools devolveram, do mesmo jeito (ADR-052)."""


class ToolSlot:
    """Compartimento da sessão de tools: a sessão só existe depois da preparação (precisa dos filtros das fatias), e
    é o passo `load_capabilities` que a abre e a guarda aqui para os passos seguintes da mesma execução."""

    def __init__(self) -> None:
        self.session: ToolSession | None = None

    def get(self) -> ToolSession:
        if self.session is None:
            raise RuntimeError("sessão de tools usada antes de ser aberta")
        return self.session


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Serviços de uma execução, já restritos. Chega pronto: nenhum nó resolve política nem filtra capacidade — o
    catálogo é o que a 004 monta com o grant."""

    composition: Composition
    hooks: PackHooks
    router: ModelRouter
    trace: TraceSink
    grant: ExecutionGrant | None = None
    capabilities: Capabilities | None = None
    mcp_delegation: DelegatedAuthorization | None = field(default=None, repr=False)
    tools: ToolSlot = field(default_factory=ToolSlot)
    rag: RagSettings | None = None
    escalate: bool = False
    timezone: tzinfo = UTC
    images: ImagePlan = field(default_factory=ImagePlan)

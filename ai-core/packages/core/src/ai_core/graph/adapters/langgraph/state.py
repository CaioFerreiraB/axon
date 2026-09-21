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
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, TypedDict

from ai_core.graph.api import ExecutionIssue
from ai_core.llm.api import ModelRouter
from ai_core.observability.api import TraceSink
from ai_core.packs.api import Composition, PackHooks, ValidationOutcome
from ai_core_contracts import Citation, JSONValue, Message


class AgentState(TypedDict, total=False):
    """Dados que a execução carrega entre os passos.

    `errors` acumula com reducer — não por necessidade do `chat`, que é linear, mas porque é o que impede perda quando
    o grafo ganhar loop e ramos na Fase 3 (FR-009, SC-005). Campos de retrieval, catálogo e loop entram nas fases
    deles; `messages` é lista simples porque as mensagens deste projeto são as do contrato 001, não as do framework.
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
    validation: ValidationOutcome | None

    # acumuladores (reducer obrigatório)
    errors: Annotated[list[ExecutionIssue], operator.add]


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Serviços de uma execução, já restritos. Chega pronto: nenhum nó resolve política nem filtra capacidade."""

    composition: Composition
    hooks: PackHooks
    router: ModelRouter
    trace: TraceSink

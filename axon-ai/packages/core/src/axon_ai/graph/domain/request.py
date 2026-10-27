"""Validação da requisição: pura, sem I/O e sem framework (FR-013).

Roda em `service.run()`, antes de qualquer evento e de qualquer chamada de modelo, para que a 008 responda 4xx sem
abrir o stream (research R5). Sobrevive a qualquer reescrita do grafo — é o que o SC-001 promete.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Final

from axon_ai.graph.api import (
    FLOW_AGENTIC,
    FLOW_CHAT,
    FLOW_RAG_FIRST,
    ExecutionGrant,
    ExecutionRequest,
    ExecutionRequestInvalid,
    UnknownFlow,
)
from axon_ai.graph.domain.images import sent_markers, user_images
from axon_ai.llm.api import ModelRole

USER_ROLE = "user"

REQUIRED_ROLES: Final[Mapping[str, tuple[ModelRole, ...]]] = {
    FLOW_CHAT: ("generation",),
    FLOW_AGENTIC: ("controller", "generation"),
    FLOW_RAG_FIRST: ("generation",),
}
"""Papéis que cada flow usa. `run()` os resolve antes do primeiro evento (FR-013, research R25): papel ausente ou fora
da allowlist é erro de requisição, não falha no meio do loop."""

OPTIONAL_ROLES: Final[Mapping[str, tuple[ModelRole, ...]]] = {
    FLOW_CHAT: ("controller",),
    FLOW_RAG_FIRST: ("controller",),
}
"""Papéis que o flow usa só quando o grant os declara: no `rag_first`, o `controller` decide se o portão escala para o
loop (FR-007a, research R40); no `chat` e no `rag_first` coberto, se uma imagem da resposta anterior vai à geração
(etapa `image_gate`, ADR-044). Declarado, é resolvido antes do primeiro evento, como os exigidos (FR-013)."""

TOOL_FLOWS: Final = frozenset({FLOW_AGENTIC, FLOW_RAG_FIRST})
"""Flows que só existem com o gateway de tools da 004 (research R16, R37)."""


def required_roles(flow: str) -> tuple[ModelRole, ...]:
    """Papéis exigidos pelo flow; nenhum para um flow sem entrada (um flow de teste, por exemplo)."""
    return REQUIRED_ROLES.get(flow, ())


def optional_roles(flow: str) -> tuple[ModelRole, ...]:
    """Papéis que o flow usa se o grant os declarar; nenhum para os outros flows."""
    return OPTIONAL_ROLES.get(flow, ())


def roles_to_resolve(flow: str, declared: Collection[ModelRole], *, image_gate: bool) -> tuple[ModelRole, ...]:
    """Os papéis que `run` resolve antes do primeiro evento: os exigidos e os opcionais declarados. No `chat`, o
    `controller` só quando a etapa `image_gate` vai rodar — sem imagem, o `chat` é o da Fase 1 (ADR-044, R51)."""
    optional = tuple(role for role in optional_roles(flow) if role in declared and (flow != FLOW_CHAT or image_gate))
    return (*required_roles(flow), *optional)


def offered(names: Collection[str], *, tools: bool) -> frozenset[str]:
    """Flows que o motor oferece: sem gateway de tools, os que dependem dele ficam de fora — falha fechada, e a
    validação de Assistants (003) os acusa."""
    return frozenset(name for name in names if tools or name not in TOOL_FLOWS)


def question_of(request: ExecutionRequest) -> str:
    """Pergunta da execução: a última mensagem de papel `user`.

    Regra mínima que serve ao `chat`; um flow futuro que precise de outra muda aqui, não nos packs (research R9). Só
    imagem vale como pergunta (ADR-044, item 5): a pergunta dos packs é a marca dela.
    """
    for message in reversed(tuple(request.messages)):
        if message["role"] == USER_ROLE:
            content = message["content"]
            if content.strip():
                return content
            images = tuple(message.get("attachments", ()))
            if images:
                return sent_markers(images)
    raise ExecutionRequestInvalid("a requisição precisa de uma mensagem de usuário com conteúdo")


def ensure_vision(request: ExecutionRequest, grant: ExecutionGrant) -> None:
    """Imagem na pergunta exige `vision` no papel `generation` (ADR-044, item 5). A 008 responde 400 antes; aqui é a
    mesma regra para quem chama o motor direto (o harness), antes de qualquer custo."""
    if user_images(request.messages) and "generation" not in grant.models.vision:
        raise ExecutionRequestInvalid(
            f"o Assistant '{grant.assistant}' não aceita imagem: o modelo do papel generation não declara vision"
        )


def validate(request: ExecutionRequest, grant: ExecutionGrant, available_flows: Collection[str]) -> str:
    """Confere requisição e flow e devolve a pergunta. Levanta antes de qualquer custo."""
    if grant.flow not in available_flows:
        known = ", ".join(sorted(available_flows)) or "nenhum"
        raise UnknownFlow(f"flow '{grant.flow}' não existe; disponíveis: {known}")
    ensure_vision(request, grant)
    return question_of(request)

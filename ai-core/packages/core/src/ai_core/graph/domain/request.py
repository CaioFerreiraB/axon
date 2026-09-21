"""Validação da requisição: pura, sem I/O e sem framework (FR-013).

Roda em `service.run()`, antes de qualquer evento e de qualquer chamada de modelo, para que a 008 responda 4xx sem
abrir o stream (research R5). Sobrevive a qualquer reescrita do grafo — é o que o SC-001 promete.
"""

from __future__ import annotations

from collections.abc import Collection

from ai_core.graph.api import ExecutionGrant, ExecutionRequest, ExecutionRequestInvalid, UnknownFlow

USER_ROLE = "user"


def question_of(request: ExecutionRequest) -> str:
    """Pergunta da execução: a última mensagem de papel `user`.

    Regra mínima que serve ao `chat`; um flow futuro que precise de outra muda aqui, não nos packs (research R9).
    """
    for message in reversed(tuple(request.messages)):
        if message["role"] == USER_ROLE:
            content = message["content"]
            if content.strip():
                return content
    raise ExecutionRequestInvalid("a requisição precisa de uma mensagem de usuário com conteúdo")


def validate(request: ExecutionRequest, grant: ExecutionGrant, available_flows: Collection[str]) -> str:
    """Confere requisição e flow e devolve a pergunta. Levanta antes de qualquer custo."""
    if grant.flow not in available_flows:
        known = ", ".join(sorted(available_flows)) or "nenhum"
        raise UnknownFlow(f"flow '{grant.flow}' não existe; disponíveis: {known}")
    return question_of(request)

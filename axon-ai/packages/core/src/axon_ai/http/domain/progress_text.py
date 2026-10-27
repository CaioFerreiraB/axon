"""Linhas de progresso para pessoas (FR-005; research R34): a etapa do motor como uma frase curta em português.

Indexada pelos estágios que a 005 **publica** no `ProgressEvent.stage` (data-model da 005), nunca por nomes internos do
grafo; estágio que não está aqui cai numa linha genérica — reescrever o motor não quebra a API, só deixa o texto menos
descritivo até a tabela ganhar a linha nova. A linha da fila é desta spec: a espera acontece antes do motor.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

QUEUE_STAGE: Final = "queue"
"""Estágio do progresso de espera na fila, emitido pela própria API (FR-017)."""

PROGRESS_LINES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "prepare_context": "Preparando o contexto da pergunta…",
        "load_capabilities": "Carregando as ferramentas…",
        "controller": "Decidindo o próximo passo ({detail})…",
        "execute_tool": "Usando a ferramenta {detail}…",
        "retrieve": "Consultando os documentos…",
        "rerank": "Ordenando os trechos encontrados…",
        "gate": "Conferindo se os trechos cobrem a pergunta…",
        "image_gate": "Conferindo se a pergunta é sobre as imagens anteriores…",
        "generate": "Escrevendo a resposta…",
        "validate_answer": "Conferindo a resposta…",
    }
)
"""Estágio publicado pela 005 → modelo da linha; `{detail}` recebe o complemento do evento."""

_WITHOUT_DETAIL: Final[Mapping[str, str]] = MappingProxyType(
    {
        "controller": "Decidindo o próximo passo…",
        "execute_tool": "Usando uma ferramenta…",
    }
)
"""As linhas que usam `{detail}`, para o evento que não o traz."""


def progress_line(stage: str, detail: str | None) -> str:
    template = PROGRESS_LINES.get(stage)
    if template is None:
        return f"Etapa {stage}…"
    if "{detail}" not in template:
        return template
    if not detail:
        return _WITHOUT_DETAIL[stage]
    return template.format(detail=detail)


def queue_line(position: int) -> str:
    return f"Aguardando uma vaga (posição {position} na fila)…"

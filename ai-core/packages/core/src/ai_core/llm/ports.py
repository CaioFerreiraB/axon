"""Portas secundárias da 006 (specs/006-core-llm-providers/contracts/ports.md).

Não são seams: são internas do módulo, e só a composition root (spec 011) escolhe o adapter de cada uma.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ai_core_contracts import LLMProvider


@dataclass(frozen=True, slots=True, kw_only=True)
class ProbeResult:
    """Resposta da sondagem de um modelo num provider. `detail` explica a indisponibilidade."""

    available: bool
    detail: str | None = None


class ModelProvider(LLMProvider, Protocol):
    """O contrato `LLMProvider` (001) mais a sondagem que a FR-009 exige (research R8).

    Estender aqui evita mudar um seam de outra spec para atender a esta. `name` é a chave pela qual a 011 registra o
    provider e o texto que aparece em `ModelRef.provider`, no trace e nas mensagens de erro.
    """

    @property
    def name(self) -> str:
        """Nome do provider no registro da composition root."""
        ...

    async def probe(self, model: str) -> ProbeResult:
        """Diz se o provider responde e conhece o modelo. NUNCA levanta e NUNCA gera tokens."""
        ...


class Clock(Protocol):
    """Tempo, por porta (ADR-013): sem ela a duração no trace seria intestável.

    Só mede intervalo — o instante de parede de cada registro é estampado pela 009.
    """

    def monotonic(self) -> float:
        """Leitura de um relógio que nunca anda para trás, em segundos."""
        ...

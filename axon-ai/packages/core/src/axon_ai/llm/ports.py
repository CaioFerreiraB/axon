"""Portas secundárias da 006 (specs/006-core-llm-providers/contracts/ports.md).

Não são seams: são internas do módulo, e só a composition root (spec 011) escolhe o adapter de cada uma.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, overload

from axon_ai.llm.api import ModelMessage
from axon_ai_contracts import ChatChunk, ChatResponse, ChatTool, JSONValue, LLMProvider


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

    # `chat` do `LLMProvider` com a mensagem da 006, que também leva imagem (ADR-044, research R32): o parâmetro só
    # alarga, então quem cumpre esta porta continua cumprindo o contrato 001.
    @overload
    async def chat(
        self,
        messages: Sequence[ModelMessage],
        model: str,
        *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
        stream: Literal[False] = False,
    ) -> ChatResponse: ...

    @overload
    async def chat(
        self,
        messages: Sequence[ModelMessage],
        model: str,
        *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
        stream: Literal[True],
    ) -> AsyncIterator[ChatChunk]: ...

    async def probe(self, model: str) -> ProbeResult:
        """Diz se o provider responde e conhece o modelo. NUNCA levanta e NUNCA gera tokens."""
        ...

    async def ready(self) -> ProbeResult:
        """Diz se o provider está pronto para uso, sem modelo nenhum (ADR-035): o remoto, pela credencial, sem rede; o
        local, se o endpoint responde. NUNCA levanta e NUNCA gera tokens."""
        ...

    @property
    def reports_cost(self) -> bool:
        """O provider informa o custo de cada chamada (ADR-036): nenhum preço de tabela se cadastra para ele."""
        ...


class SecretResolver(Protocol):
    """Credenciais dos providers remotos (Fase 3, research R21).

    Quem chama são os adapters remotos, uma vez, na construção, com um nome fixo deles — nenhum nome vem de entrada.
    A 011 escolhe o adapter (porta `llm_secrets`); a fonte é a mesma das outras portas de segredo do perfil (ADR-020).
    """

    def resolve(self, name: str) -> str | None:
        """Valor da credencial pelo nome, ou None quando ausente ou vazia. Nunca levanta."""
        ...


class Clock(Protocol):
    """Tempo, por porta (ADR-013): sem ela a duração no trace seria intestável.

    Só mede intervalo — o instante de parede de cada registro é estampado pela 009.
    """

    def monotonic(self) -> float:
        """Leitura de um relógio que nunca anda para trás, em segundos."""
        ...

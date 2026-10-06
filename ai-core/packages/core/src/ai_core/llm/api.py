"""Seam Model Router (spec 006): resolve papel → (provider, modelo) e entrega um cliente já ligado ao modelo.

Contrato em specs/006-core-llm-providers/contracts/model-router.md.

Único módulo da 006 que outros módulos importam. Depende só da stdlib e da API pública de `ai_core_contracts`: nenhum
tipo de SDK de provedor ou de cliente HTTP aparece aqui (princípio XIII, research R6). Não importa o resto do próprio
módulo — as implementações destes Protocols estão em `service.py` e em `adapters/`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Literal, Protocol

from ai_core_contracts import ChatChunk, ChatMessage, ChatResponse, ChatTool, JSONValue

type ModelRole = Literal["controller", "generation", "rerank"]
"""Papéis do ADR-008. Vocabulário fechado: o roteador nunca inventa papel nem escolhe modelo por conta própria."""

MODEL_ROLES: tuple[ModelRole, ...] = ("controller", "generation", "rerank")
"""Ordem canônica dos papéis — usada na verificação de saúde para que o relatório seja estável."""

AUTO_ROUTING_PROVIDER: Final = "openrouter"
"""O provider cujos roteadores escolhem o modelo sozinhos (FR-004, research R16). É também o nome com que o adapter do
OpenRouter se registra — o adapter importa esta constante, para os dois nunca divergirem."""


class ModelRoutingError(RuntimeError):
    """Base dos erros do módulo. Quem consome o seam trata esta hierarquia, nunca erros de SDK."""


class RoleNotConfigured(ModelRoutingError):
    """O papel pedido não está na política. O roteador informa em vez de escolher um modelo (FR-002)."""


class ModelNotAllowed(ModelRoutingError):
    """`provider/modelo` fora da allowlist da política (FR-003, elo 6 da cadeia de enforcement)."""


class UnknownProvider(ModelRoutingError):
    """O provider da referência não foi registrado pela composition root (spec 011)."""


class ModelCallFailed(ModelRoutingError):
    """Falha da chamada de modelo, sempre nomeando provider e modelo.

    Antes da rede: o papel `controller` sem restrição de formato (FR-005) ou o provider remoto sem credencial (FR-011).
    Ao falar com o provider: fora do ar, erro de status — inclusive a recusa da restrição —, stream interrompido ou
    inatividade (FR-010).
    """

    def __init__(self, *, provider: str, model: str, reason: str) -> None:
        super().__init__(f"{provider}/{model}: {reason}")
        self.provider = provider
        self.model = model
        self.reason = reason


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelRef:
    """Provider e modelo, sempre explícitos (princípio VIII). Não há default em lugar nenhum.

    Roteamento automático é recusado aqui (FR-004, research R16): toda referência a modelo — declaração do Assistant,
    escolha na requisição, saúde — passa por este construtor, então a allowlist nunca consegue liberá-lo.
    """

    provider: str
    model: str

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider não pode ser vazio")
        if "/" in self.provider:
            raise ValueError(f"provider não pode conter '/': {self.provider!r}")
        if not self.model.strip():
            raise ValueError("model não pode ser vazio")
        if _is_auto_routing(self.provider, self.model):
            raise ValueError(
                f"'{self.provider}/{self.model}' é roteamento automático, que escolhe o modelo sozinho: "
                "declare um modelo explícito (autor/modelo)"
            )

    @classmethod
    def parse(cls, text: str) -> ModelRef:
        """Lê `"provider/modelo"`, dividindo no primeiro `/` — modelos podem conter `/` e `:` (research R12)."""
        provider, separator, model = text.partition("/")
        if not separator:
            raise ValueError(f"referência de modelo precisa ser 'provider/modelo': {text!r}")
        return cls(provider=provider, model=model)

    def __str__(self) -> str:
        return f"{self.provider}/{self.model}"


def _is_auto_routing(provider: str, model: str) -> bool:
    """No OpenRouter, a forma curta `auto` e o namespace `openrouter/…` (o `openrouter/auto` e roteadores futuros).

    Compara a base do modelo — sem maiúsculas e antes do primeiro `:` —, então sufixos de variante do próprio modelo
    (`:free`, `:nitro`, `:floor`) não contam.
    """
    if provider != AUTO_ROUTING_PROVIDER:
        return False
    base = model.strip().casefold().partition(":")[0]
    return base == "auto" or base.startswith(f"{AUTO_ROUTING_PROVIDER}/")


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelPolicy:
    """Modelo por papel + allowlist. Montada pela 011 na Fase 1 e derivada do grant (003) a partir da Fase 2."""

    roles: Mapping[ModelRole, ModelRef]
    allow: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.roles:
            raise ValueError("a política precisa declarar ao menos um papel")
        unknown = sorted(str(role) for role in self.roles if role not in MODEL_ROLES)
        if unknown:
            raise ValueError(f"papéis desconhecidos: {', '.join(unknown)}")
        object.__setattr__(self, "roles", MappingProxyType(dict(self.roles)))

    def configured_roles(self) -> tuple[ModelRole, ...]:
        """Papéis declarados, na ordem canônica."""
        return tuple(role for role in MODEL_ROLES if role in self.roles)


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelHealth:
    """Resultado da verificação sob demanda de um papel (FR-009). Indisponibilidade é resultado, não exceção."""

    role: ModelRole
    ref: ModelRef
    available: bool
    detail: str | None = None


class BoundModel(Protocol):
    """Cliente já ligado a um modelo: quem chama não passa `model` — ele foi resolvido e conferido."""

    @property
    def role(self) -> ModelRole:
        """Papel que originou este cliente."""
        ...

    @property
    def ref(self) -> ModelRef:
        """Provider e modelo resolvidos."""
        ...

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
    ) -> ChatResponse:
        """Resposta completa. Emite um dado de chamada de modelo no trace ao terminar (FR-008)."""
        ...

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[ChatTool] | None = None,
        response_format: Mapping[str, JSONValue] | None = None,
    ) -> AsyncIterator[ChatChunk]:
        """Resposta em pedaços (princípio XI). Emite no trace ao encerrar o iterador, inclusive em falha."""
        ...


class ModelRouter(Protocol):
    """Roteador de uma execução: política e requisição já fixadas."""

    def for_role(self, role: ModelRole) -> BoundModel:
        """Resolve o papel, aplica a allowlist e devolve o cliente. Falha antes de qualquer I/O."""
        ...


class ModelRouting(Protocol):
    """Seam Model Router, montado uma vez no boot pela composition root (spec 011)."""

    def for_execution(self, *, policy: ModelPolicy, request_id: str) -> ModelRouter:
        """Liga política e requisição a um roteador. Não faz I/O."""
        ...

    async def check(self, policy: ModelPolicy) -> tuple[ModelHealth, ...]:
        """Verifica, sob demanda, provider e modelo de cada papel configurado (FR-009). Nunca levanta."""
        ...

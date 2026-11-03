"""Portas secundárias do trace (specs/009-core-observability-evaluation/contracts/ports.md).

Não são seams: são internas do módulo, e só a composition root (spec 011) escolhe o adapter de cada uma.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from axon_ai.observability.api import (
    ConnectionCheck,
    ImpactGrain,
    Price,
    TraceRecord,
    UsageGrouping,
    UsageOrigin,
)
from axon_ai.observability.domain.settings import DestinationSettings, LangfuseCredentials
from axon_ai.observability.domain.usage_records import (
    DailyRequests,
    DailyTokens,
    DayRequests,
    ExecutionRow,
    ImpactAggregate,
    ImpactCell,
    ImpactEstimate,
    KeyRequests,
    ModelCallRow,
    Origin,
    UnestimatedCall,
    UsageAggregate,
)

__all__ = [
    "DailyRequests",
    "DailyTokens",
    "DayRequests",
    "DestinationSettings",
    "ExecutionRow",
    "ImpactAggregate",
    "ImpactCell",
    "ImpactEstimate",
    "KeyRequests",
    "LangfuseCredentials",
    "ModelCallRow",
    "Origin",
    "UnestimatedCall",
    "UsageAggregate",
]


class TraceExporter(Protocol):
    """Escrita no backend de trace."""

    def export(self, record: TraceRecord) -> None:
        """Entrega um registro ao backend. PODE levantar — quem chama trata e nunca propaga (FR-011)."""
        ...


class TraceReader(Protocol):
    """Leitura do backend de trace. Opcional no perfil: um backend que só escreve não a fornece (research R5)."""

    def read(self, request_id: str) -> Sequence[TraceRecord]:
        """Registros da requisição, na ordem de emissão; vazio quando não há nenhum."""
        ...


class Clock(Protocol):
    """Tempo, por porta: `domain/` é puro e o serviço não lê o relógio do sistema (ADR-013)."""

    def now(self) -> datetime:
        """Instante atual, sempre com timezone."""
        ...


# ---------------------------------------------------------------------------------------------------------------------
# Fase 9 (contracts/ports.md, "Fase 9"): destinos, uso, preços, ajustes, cifra e transporte do Langfuse
# ---------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, kw_only=True)
class DestinationStats:
    """O que um destino conta de si: enfileirados, descartados (com os instantes) e o último erro."""

    queued: int = 0
    dropped: int = 0
    dropped_at: tuple[datetime, ...] = ()
    last_error: str | None = None
    last_sent_at: datetime | None = None
    impact_failed: int = 0
    """Estimativas de impacto que levantaram no destino de uso (research R46); as linhas gravaram sem impacto."""


class TraceDestination(Protocol):
    """Um destino além do primário (ADR-034): só enfileira — banco e rede ficam fora do caminho de quem emite."""

    @property
    def name(self) -> str: ...

    @property
    def accepts_content(self) -> bool:
        """Se recebe o `model_exchange` (texto de prompt e resposta) quando a captura está ligada."""
        ...

    def export(self, record: TraceRecord) -> None:
        """NÃO bloqueia. PODE levantar — o serviço conta e segue."""
        ...

    async def flush(self) -> None: ...

    def stats(self) -> DestinationStats: ...


class UsageStore(Protocol):
    async def append(self, calls: Sequence[ModelCallRow], executions: Sequence[ExecutionRow]) -> None:
        """Grava em lote; uma execução repetida (início, depois fim) atualiza a linha."""
        ...

    async def daily(
        self, *, start: datetime, end: datetime, tz: str, by: UsageGrouping, origin: UsageOrigin
    ) -> UsageAggregate:
        """Agregado por dia local no fuso `tz`, para chamadas em `[start, end)`."""
        ...

    async def purge(self, *, before: datetime) -> int: ...

    async def impact(
        self, *, start: datetime, end: datetime, tz: str, grain: ImpactGrain, by: UsageGrouping, origin: UsageOrigin
    ) -> ImpactAggregate:
        """Impacto por balde do grão, no dia local do fuso `tz`, para chamadas em `[start, end)` (research R49)."""
        ...

    async def unestimated(self, limit: int, *, after: int = -1) -> tuple[UnestimatedCall, ...]:
        """Chamadas elegíveis nunca estimadas (`impact_match` nulo) com `id` maior que `after`, pela ordem de gravação
        (research R50): o cursor deixa o preenchimento passar pelas que falharam sem voltar a elas."""
        ...

    async def set_impacts(self, items: Sequence[tuple[int, ImpactEstimate | None]]) -> None:
        """Grava a estimativa — ou o marcador de sem par, com `None` — só onde ainda não houve tentativa."""
        ...


class PriceStore(Protocol):
    async def all(self) -> Sequence[Price]: ...

    async def add(self, price: Price) -> Price:
        """Um preço por (provider, modelo, vigência): repetir a vigência substitui."""
        ...


class DestinationSettingsStore(Protocol):
    async def get(self) -> DestinationSettings: ...

    async def put(self, settings: DestinationSettings, *, expected_version: int) -> bool:
        """`False` se a versão guardada não é `expected_version`."""
        ...


class SealError(Exception):
    """Selo que não abre: chave mestra errada ou dado adulterado. A mensagem nunca traz o conteúdo."""


class SecretCipher(Protocol):
    def seal(self, plaintext: bytes) -> bytes: ...

    def open(self, sealed: bytes) -> bytes: ...


class LangfuseTransport(Protocol):
    """O envio ao Langfuse: aceita os registros já filtrados e não bloqueia; a fila e o lote são do transporte."""

    def send(self, record: TraceRecord) -> None: ...

    async def check(self, credentials: LangfuseCredentials) -> ConnectionCheck: ...

    def reconfigure(self, credentials: LangfuseCredentials | None) -> None:
        """Troca as credenciais (ou desliga com `None`) sem perder o que já estava na fila."""
        ...

    async def flush(self) -> None: ...

    def shutdown(self) -> None: ...


# ---------------------------------------------------------------------------------------------------------------------
# Incremento 9.6 (contracts/ports.md, "Passada de 2026-11-03"; ADR-056)
# ---------------------------------------------------------------------------------------------------------------------


class ImpactEstimator(Protocol):
    """Estimativa do impacto ambiental de uma chamada de modelo (research R44)."""

    @property
    def version(self) -> str:
        """Versão do método (a do EcoLogits), gravada com cada estimativa."""
        ...

    def estimate(self, provider: str, model: str, output_tokens: int, latency_s: float) -> ImpactEstimate | None:
        """`None` quando o modelo não tem par na base ou o método recusa a chamada. PODE levantar: quem chama conta e
        grava a linha sem impacto."""
        ...

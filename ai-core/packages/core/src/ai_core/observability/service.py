"""Serviços do trace (spec 009): os seams Trace Sink e Trace, e — Fase 9 (ADR-034) — o uso e custo, a tabela de preços
e os destinos (Langfuse e captura de conteúdo).

Orquestra `domain/` e as portas. Falha de backend ou de destino nunca chega a quem emite: é contada e registrada
(FR-011). O conteúdo de prompt e resposta (`ModelExchange`) só existe com a captura ligada, e só vai a destinos que o
aceitam — o primário nunca o recebe (SC-007).
"""

from __future__ import annotations

import dataclasses
import logging
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Final, Protocol

from ai_core.observability.api import (
    Conflict,
    ConnectionCheck,
    DestinationHealth,
    DestinationSettingsView,
    DestinationState,
    InstallationDefined,
    InvalidPrice,
    MasterKeyMissing,
    ModelExchange,
    Price,
    Trace,
    TraceEvent,
    TraceQueryUnavailable,
    TraceRecord,
    UsageQuery,
    UsageReport,
)
from ai_core.observability.domain.content import exchange_record
from ai_core.observability.domain.prices import check_amount, with_states
from ai_core.observability.domain.records import to_record
from ai_core.observability.domain.settings import (
    DestinationSettings,
    EffectiveDestinations,
    InstallationDestinations,
    LangfuseCredentials,
    check_host,
    effective,
)
from ai_core.observability.domain.usage import build_report, period_cost, previous, unpriced, window
from ai_core.observability.ports import (
    Clock,
    DestinationSettingsStore,
    DestinationStats,
    LangfuseTransport,
    PriceStore,
    SealError,
    SecretCipher,
    TraceDestination,
    TraceExporter,
    TraceReader,
    UsageStore,
)

logger: Final = logging.getLogger("ai_core.observability")

DEFAULT_TIMEZONE: Final = "UTC"
DEFAULT_RETENTION_DAYS: Final = 400


class TraceService:
    """Um serviço por processo, montado pela composition root (spec 011) com os adapters do perfil.

    `exporter` é o primário (memória ou JSONL), consultável e síncrono; `destinations` só enfileiram (uso, Langfuse).
    `capture` diz, a cada `ModelExchange`, se a captura de conteúdo está ligada (o `DestinationService` responde).
    """

    def __init__(
        self,
        *,
        exporter: TraceExporter,
        reader: TraceReader | None,
        clock: Clock,
        destinations: Sequence[TraceDestination] = (),
        capture: Callable[[], bool] | None = None,
    ) -> None:
        self._exporter = exporter
        self._reader = reader
        self._clock = clock
        self._destinations = tuple(destinations)
        self._capture = capture or (lambda: False)
        self._dropped = 0
        self._destination_failures: defaultdict[str, int] = defaultdict(int)

    def emit(self, event: TraceEvent) -> None:
        """Registra um dado de trace. Nunca levanta: trace é observação, não o trabalho (FR-011)."""
        try:
            now = self._clock.now()
            if isinstance(event, ModelExchange):
                self._exchange(event, now)
                return
            record = to_record(event, now)
        except Exception as error:
            self._dropped += 1
            logger.warning("evento de trace descartado na montagem (%s)", type(error).__name__)
            return
        try:
            self._exporter.export(record)
        except Exception as error:
            self._dropped += 1
            logger.warning(
                "evento de trace descartado (%s: %s); requisição %s, tipo %s",
                type(error).__name__,
                error,
                record.request_id,
                record.type,
            )
        for destination in self._destinations:
            self._deliver(destination, record)

    def _exchange(self, event: ModelExchange, now: datetime) -> None:
        """Conteúdo: descartado com a captura desligada; ligado, redigido e só para quem aceita (ADR-034, R29)."""
        try:
            capture = self._capture()
        except Exception:
            capture = False
        if not capture:
            return
        record = exchange_record(event, now)
        for destination in self._destinations:
            if destination.accepts_content:
                self._deliver(destination, record)

    def _deliver(self, destination: TraceDestination, record: TraceRecord) -> None:
        try:
            destination.export(record)
        except Exception as error:
            self._destination_failures[destination.name] += 1
            logger.debug("destino '%s' recusou um registro (%s)", destination.name, type(error).__name__)

    async def flush(self) -> None:
        """Esvazia as filas dos destinos — tarefa periódica da 011 e encerramento. Nunca levanta."""
        for destination in self._destinations:
            try:
                await destination.flush()
            except Exception as error:
                self._destination_failures[destination.name] += 1
                logger.warning("destino '%s' falhou ao esvaziar a fila (%s)", destination.name, type(error).__name__)

    @property
    def destinations(self) -> tuple[TraceDestination, ...]:
        return self._destinations

    def destination_failures(self, name: str) -> int:
        return self._destination_failures[name]

    def trace(self, request_id: str) -> Trace:
        """Eventos da requisição, na ordem de emissão."""
        if self._reader is None:
            raise TraceQueryUnavailable(
                f"o backend configurado ({type(self._exporter).__name__}) não oferece consulta de trace"
            )
        return Trace(request_id=request_id, records=tuple(self._reader.read(request_id)))

    def dropped_events(self) -> int:
        """Eventos perdidos por falha do backend desde o início do processo; a saúde agregada (011 US5) lê isto."""
        return self._dropped


# --- uso, custo e preços (US5) ----------------------------------------------------------------------------------------


class UsageService:
    """`UsageReportSeam` e `PriceBook` (contracts/usage-api.md)."""

    def __init__(
        self, *, store: UsageStore, prices: PriceStore, clock: Clock, default_timezone: str = DEFAULT_TIMEZONE
    ) -> None:
        self._store = store
        self._prices = prices
        self._clock = clock
        self._tz = default_timezone

    @property
    def default_timezone(self) -> str:
        return self._tz

    async def report(self, query: UsageQuery) -> UsageReport:
        start, end = window(query)
        aggregate_ = await self._store.daily(start=start, end=end, tz=query.tz, by=query.by, origin=query.origin)
        prices = tuple(await self._prices.all())
        before = previous(query)
        previous_start, previous_end = window(before)
        previous_aggregate = await self._store.daily(
            start=previous_start, end=previous_end, tz=query.tz, by=query.by, origin=query.origin
        )
        previous_cost, _ = period_cost(previous_aggregate, prices)
        return build_report(query, aggregate_, prices, previous_cost=previous_cost)

    async def prices(self) -> tuple[Price, ...]:
        return with_states(tuple(await self._prices.all()), today=self._clock.now().date())

    async def add_price(
        self,
        *,
        provider: str,
        model: str,
        usd_per_mtok_in: Decimal,
        usd_per_mtok_out: Decimal,
        effective_from: date,
        actor: str,
    ) -> Price:
        if not provider.strip() or "/" in provider:
            raise InvalidPrice("provider: obrigatório, sem barra", field="provider")
        if not model.strip():
            raise InvalidPrice("model: obrigatório", field="model")
        price = Price(
            provider=provider.strip(),
            model=model.strip(),
            usd_per_mtok_in=check_amount("input", usd_per_mtok_in),
            usd_per_mtok_out=check_amount("output", usd_per_mtok_out),
            effective_from=effective_from,
            created_by=actor,
            created_at=self._clock.now(),
        )
        await self._prices.add(price)
        states = with_states(tuple(await self._prices.all()), today=self._clock.now().date())
        return next(
            p
            for p in states
            if (p.provider, p.model, p.effective_from) == (price.provider, price.model, price.effective_from)
        )

    async def unpriced_models(self, *, start: date, end: date) -> tuple[str, ...]:
        query = UsageQuery(start=start, end=end, tz=self._tz, by="model", origin="all")
        window_start, window_end = window(query)
        aggregate_ = await self._store.daily(start=window_start, end=window_end, tz=self._tz, by="model", origin="all")
        return unpriced(aggregate_, tuple(await self._prices.all()))

    async def purge(self, *, retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
        """Retenção do uso (R34): tarefa diária da 011. Preços não expiram."""
        return await self._store.purge(before=self._clock.now() - timedelta(days=retention_days))


# --- destinos: Langfuse e captura de conteúdo (US6, US7) --------------------------------------------------------------


class ConfigurableDestination(Protocol):
    """O destino Langfuse como o `DestinationService` o enxerga: liga, desliga e troca as credenciais."""

    def configure(self, credentials: LangfuseCredentials | None) -> None: ...

    def stats(self) -> DestinationStats: ...


class DestinationService:
    """`TraceDestinations` (contracts/usage-api.md): ajustes com precedência instalação > runtime > padrão (ADR-033)."""

    def __init__(
        self,
        *,
        store: DestinationSettingsStore,
        cipher: SecretCipher | None,
        installation: InstallationDestinations,
        transport: LangfuseTransport,
        langfuse: ConfigurableDestination | None,
        usage: TraceDestination | None,
        clock: Clock,
    ) -> None:
        self._store = store
        self._cipher = cipher
        self._installation = installation
        self._transport = transport
        self._langfuse = langfuse
        self._usage = usage
        self._clock = clock
        self._effective = effective(installation, DestinationSettings(), secret=None)
        self._secret_error: str | None = None

    async def start(self) -> None:
        """Lê os ajustes e liga (ou não) o Langfuse. Chamada no boot e a cada gravação."""
        stored = await self._store.get()
        self._effective = effective(self._installation, stored, secret=self._open(stored))
        if self._langfuse is not None:
            self._langfuse.configure(self._effective.langfuse)

    def capture_enabled(self) -> bool:
        """Lido pelo `TraceService` a cada `ModelExchange` — sem I/O."""
        return self._effective.capture

    def _open(self, stored: DestinationSettings) -> str | None:
        if stored.langfuse_secret_sealed is None:
            return None
        if self._cipher is None:
            self._secret_error = "sem AI_CORE_MASTER_KEY, o segredo gravado não abre"
            return None
        try:
            secret = self._cipher.open(stored.langfuse_secret_sealed).decode("utf-8")
        except (SealError, UnicodeDecodeError):
            self._secret_error = "o segredo gravado não abre com esta chave mestra"
            return None
        self._secret_error = None
        return secret

    async def settings(self) -> DestinationSettingsView:
        return self._effective.view

    async def _check_version(self, version: int) -> DestinationSettings:
        stored = await self._store.get()
        if stored.version != version:
            raise Conflict("os ajustes mudaram desde a leitura", current_version=stored.version)
        return stored

    async def _write(self, stored: DestinationSettings, *, actor: str, **changes: Any) -> DestinationSettingsView:
        updated = dataclasses.replace(
            stored, version=stored.version + 1, updated_by=actor, updated_at=self._clock.now(), **changes
        )
        if not await self._store.put(updated, expected_version=stored.version):
            current = await self._store.get()
            raise Conflict("os ajustes mudaram desde a leitura", current_version=current.version)
        await self.start()
        return self._effective.view

    async def set_langfuse(
        self,
        *,
        enabled: bool | None = None,
        host: str | None = None,
        public_key: str | None = None,
        secret_key: str | None = None,
        actor: str,
        version: int,
    ) -> DestinationSettingsView:
        given = {
            "langfuse_enabled": enabled,
            "langfuse_host": host,
            "langfuse_public_key": public_key,
            "langfuse_secret": secret_key,
        }
        if self._installation.langfuse is not None:
            field = next((name for name, value in given.items() if value is not None), "langfuse_enabled")
            raise InstallationDefined(
                f"{field}: o Langfuse é definido pela instalação (AI_CORE_LANGFUSE_*)", field=field
            )
        stored = await self._check_version(version)
        changes: dict[str, Any] = {}
        if enabled is not None:
            changes["langfuse_enabled"] = enabled
        if host is not None:
            changes["langfuse_host"] = check_host(host)
        if public_key is not None:
            changes["langfuse_public_key"] = public_key.strip() or None
        if secret_key is not None:
            if self._cipher is None:
                raise MasterKeyMissing("defina AI_CORE_MASTER_KEY na instalação para gravar o segredo do Langfuse")
            changes["langfuse_secret_sealed"] = self._cipher.seal(secret_key.encode("utf-8")) if secret_key else None
        return await self._write(stored, actor=actor, **changes)

    async def set_capture(self, *, enabled: bool, actor: str, version: int) -> DestinationSettingsView:
        if self._installation.capture is not None:
            raise InstallationDefined(
                "capture_content: definido pela instalação (AI_CORE_LANGFUSE_CAPTURE_CONTENT)", field="capture_content"
            )
        stored = await self._check_version(version)
        return await self._write(stored, actor=actor, capture_content=enabled)

    async def test_langfuse(
        self, *, host: str | None = None, public_key: str | None = None, secret_key: str | None = None
    ) -> ConnectionCheck:
        """Com os argumentos (o que a pessoa está digitando) ou com os ajustes efetivos. Nunca devolve o segredo."""
        current = self._effective
        stored_secret = self._open(await self._store.get())
        if self._installation.langfuse is not None:
            stored_secret = self._installation.langfuse.secret_key
        resolved_host = check_host(host) if host is not None else current.view.langfuse_host
        resolved_public = public_key if public_key is not None else current.view.langfuse_public_key
        resolved_secret = secret_key if secret_key is not None else stored_secret
        missing = [
            name
            for name, value in (
                ("host", resolved_host),
                ("public_key", resolved_public),
                ("secret_key", resolved_secret),
            )
            if not value
        ]
        if missing:
            return ConnectionCheck(ok=False, detail=f"faltam: {', '.join(missing)}")
        credentials = LangfuseCredentials(host=resolved_host, public_key=resolved_public, secret_key=resolved_secret)  # type: ignore[arg-type]
        return await self._transport.check(credentials)

    def health(self) -> tuple[DestinationHealth, ...]:
        """Itens não críticos da saúde (R34): `usage` e `langfuse`, com descartes nas últimas 24 h e o último erro."""
        now = self._clock.now()
        result: list[DestinationHealth] = []
        if self._usage is not None:
            result.append(self._health("usage", self._usage.stats(), now=now, on=True))
        if self._langfuse is not None:
            result.append(
                self._health("langfuse", self._langfuse.stats(), now=now, on=self._effective.langfuse is not None)
            )
        return tuple(result)

    def _health(self, name: str, stats: DestinationStats, *, now: datetime, on: bool) -> DestinationHealth:
        recent = sum(1 for instant in stats.dropped_at if now - instant <= timedelta(hours=24))
        error = stats.last_error or (self._secret_error if name == "langfuse" else None)
        state: DestinationState = "off"
        if on:
            state = "degraded" if recent or stats.last_error else "ok"
        return DestinationHealth(
            name=name, state=state, dropped_24h=recent, last_error=error, last_sent_at=stats.last_sent_at
        )

    @property
    def effective_settings(self) -> EffectiveDestinations:
        return self._effective

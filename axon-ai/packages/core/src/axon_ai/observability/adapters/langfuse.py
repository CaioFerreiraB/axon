"""Destino Langfuse por OpenTelemetry (ADR-034; research R32). O único lugar do core com o SDK de OTel (import-linter).

O Langfuse recebe OTLP/HTTP em `{host}/api/public/otel/v1/traces`, com `Authorization: Basic base64(public:secret)`.
O `BatchSpanProcessor` dá fila limitada (cheia, descarta), lote e retentativa — `send` nunca espera a rede.

Mapeamento (R32): `execution_started` abre o span raiz (nome = Assistant); `model_call` vira span filho de geração
com início em `at` menos `duration_ms`, modelo e tokens; `model_exchange` (só com a captura ligada) preenche a entrada e
a saída da geração pendente da mesma requisição; `tool_call` vira span de tool; decisão do controller, portão,
validação, recuperação e erro viram eventos do raiz; `execution_finished` encerra o raiz. Spans abertos há mais de 1 h
são encerrados.
"""

from __future__ import annotations

import base64
import json
import logging
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Final

import httpx
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Span, Status, StatusCode

from axon_ai.observability.api import ConnectionCheck, TraceRecord
from axon_ai.observability.ports import DestinationStats, LangfuseCredentials, LangfuseTransport

logger: Final = logging.getLogger("axon_ai.observability")

OTLP_PATH: Final = "/api/public/otel/v1/traces"
CHECK_PATH: Final = "/api/public/projects"
QUEUE: Final = 2_048
BATCH: Final = 256
DELAY_MS: Final = 5_000
OPEN_TTL: Final = timedelta(hours=1)
ROOT_EVENTS: Final = frozenset(
    {"controller_decision", "coverage_gate", "validation_run", "retrieval", "execution_error"}
)

ExporterFactory = Callable[[LangfuseCredentials], SpanExporter]


def _ns(instant: datetime) -> int:
    return int(instant.timestamp() * 1_000_000_000)


def basic_auth(credentials: LangfuseCredentials) -> str:
    token = base64.b64encode(f"{credentials.public_key}:{credentials.secret_key}".encode()).decode("ascii")
    return f"Basic {token}"


def otlp_exporter(credentials: LangfuseCredentials) -> SpanExporter:
    return OTLPSpanExporter(
        endpoint=f"{credentials.host.rstrip('/')}{OTLP_PATH}",
        headers={"Authorization": basic_auth(credentials)},
        timeout=10,
    )


def _attribute(value: object) -> str | bool | int | float:
    if isinstance(value, bool | int | float | str):
        return value
    return json.dumps(value, ensure_ascii=False, default=str)


class _Watched(SpanExporter):
    """O exportador de verdade, observado: a exportação roda na thread do `BatchSpanProcessor`, e sem isto um Langfuse
    fora do ar nunca chegaria à saúde (011 US6 cenário 4). Sucesso limpa o erro; falha o registra."""

    def __init__(self, inner: SpanExporter, on_result: Callable[[str | None], None]) -> None:
        self._inner = inner
        self._on_result = on_result

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            result = self._inner.export(spans)
        except Exception as error:
            self._on_result(f"exportação falhou: {type(error).__name__}")
            return SpanExportResult.FAILURE
        self._on_result(None if result is SpanExportResult.SUCCESS else "o Langfuse não aceitou o lote (OTLP)")
        return result

    def shutdown(self) -> None:
        self._inner.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return self._inner.force_flush(timeout_millis)


@dataclass
class _Open:
    """O que está aberto de uma requisição: o raiz e a geração que espera o conteúdo."""

    root: Span
    started: datetime
    generation: Span | None = None
    generation_end: int | None = None
    children: list[Span] = field(default_factory=list)


class OtelLangfuseTransport:
    """`LangfuseTransport` real. `exporter_factory` troca o exportador OTLP nas suítes (coletor em memória)."""

    def __init__(
        self,
        *,
        exporter_factory: ExporterFactory = otlp_exporter,
        http: httpx.AsyncClient | None = None,
        queue: int = QUEUE,
        batch: int = BATCH,
        delay_ms: int = DELAY_MS,
    ) -> None:
        self._factory = exporter_factory
        self._http = http
        self._queue, self._batch, self._delay = queue, batch, delay_ms
        self._provider: TracerProvider | None = None
        self._tracer: trace.Tracer | None = None
        self._open: dict[str, _Open] = {}
        self._lock = threading.Lock()
        self.errors = 0
        self.last_error: str | None = None
        self.export_failures = 0

    # --- configuração ---------------------------------------------------------------------------------------------

    def reconfigure(self, credentials: LangfuseCredentials | None) -> None:
        """Novo exportador para as credenciais novas; o antigo esvazia a fila dele e desliga numa thread."""
        with self._lock:
            old = self._provider
            self._open.clear()
            if credentials is None:
                self._provider, self._tracer = None, None
            else:
                provider = TracerProvider(resource=Resource.create({"service.name": "ai-core"}), shutdown_on_exit=False)
                provider.add_span_processor(
                    BatchSpanProcessor(
                        _Watched(self._factory(credentials), self._exported),
                        max_queue_size=self._queue,
                        max_export_batch_size=self._batch,
                        schedule_delay_millis=self._delay,
                    )
                )
                self._provider, self._tracer = provider, provider.get_tracer("ai-core")
        if old is not None:
            threading.Thread(target=old.shutdown, name="langfuse-shutdown", daemon=True).start()

    @property
    def active(self) -> bool:
        return self._tracer is not None

    def _exported(self, failure: str | None) -> None:
        """Chamado da thread de exportação. Vale o último resultado: o Langfuse que volta deixa de aparecer
        degradado."""
        if failure is not None:
            self.export_failures += 1
        self.last_error = failure

    # --- envio ----------------------------------------------------------------------------------------------------

    def send(self, record: TraceRecord) -> None:
        with self._lock:
            if self._tracer is None:
                return
            try:
                self._map(self._tracer, record)
            except Exception as error:
                self.errors += 1
                self.last_error = f"{type(error).__name__}: {error}"[:300]
            self._expire(record.at)

    def _map(self, tracer: trace.Tracer, record: TraceRecord) -> None:
        attributes = record.attributes
        kind = record.type
        if kind == "execution_started":
            root = tracer.start_span(
                str(attributes.get("assistant", "execução")),
                start_time=_ns(record.at),
                attributes={
                    "langfuse.trace.name": str(attributes.get("assistant", "")),
                    "langfuse.trace.metadata.flow": str(attributes.get("flow", "")),
                    "langfuse.trace.metadata.packs": _attribute(attributes.get("packs", [])),
                    "langfuse.trace.metadata.request_id": record.request_id,
                },
            )
            self._open[record.request_id] = _Open(root=root, started=record.at)
            return
        opened = self._open.get(record.request_id)
        if opened is None:
            return
        if kind == "model_exchange":
            if opened.generation is not None:
                opened.generation.set_attribute("langfuse.observation.input", _attribute(attributes.get("messages")))
                opened.generation.set_attribute("langfuse.observation.output", _attribute(attributes.get("output")))
                self._end_generation(opened)
            return
        self._end_generation(opened)
        context = trace.set_span_in_context(opened.root)
        if kind == "model_call":
            duration = float(attributes.get("duration_ms") or 0)  # type: ignore[arg-type]
            start = record.at - timedelta(milliseconds=duration)
            span_attributes: dict[str, Any] = {
                "langfuse.observation.type": "generation",
                "gen_ai.request.model": f"{attributes.get('provider')}/{attributes.get('model')}",
                "gen_ai.system": str(attributes.get("provider", "")),
                "langfuse.observation.metadata.role": str(attributes.get("role", "")),
            }
            for source, target in (
                ("input_tokens", "gen_ai.usage.input_tokens"),
                ("output_tokens", "gen_ai.usage.output_tokens"),
            ):
                if isinstance(attributes.get(source), int):
                    span_attributes[target] = attributes[source]
            cost = attributes.get("cost_usd")
            if isinstance(cost, int | float) and not isinstance(cost, bool):
                # O custo informado pelo provider (ADR-035): sem ele, o Langfuse estima pela tabela dele.
                span_attributes["langfuse.observation.cost_details"] = _attribute({"total": cost})
            span = tracer.start_span(
                f"{attributes.get('role', 'modelo')}",
                context=context,
                start_time=_ns(start),
                attributes=span_attributes,
            )
            if attributes.get("finish_reason") == "error":
                span.set_attribute("langfuse.observation.level", "ERROR")
                span.set_status(Status(StatusCode.ERROR))
            opened.generation, opened.generation_end = span, _ns(record.at)
        elif kind == "tool_call":
            duration = float(attributes.get("duration_ms") or 0)  # type: ignore[arg-type]
            span = tracer.start_span(
                str(attributes.get("tool", "tool")),
                context=context,
                start_time=_ns(record.at - timedelta(milliseconds=duration)),
                attributes={
                    "langfuse.observation.type": "tool",
                    "langfuse.observation.metadata.status": str(attributes.get("status", "")),
                    "langfuse.observation.metadata.kind": str(attributes.get("kind") or ""),
                },
            )
            if attributes.get("status") not in (None, "ok"):
                span.set_attribute("langfuse.observation.level", "WARNING")
            span.end(end_time=_ns(record.at))
        elif kind in ROOT_EVENTS:
            opened.root.add_event(
                kind, {key: _attribute(value) for key, value in attributes.items()}, timestamp=_ns(record.at)
            )
            if kind == "execution_error":
                opened.root.set_attribute("langfuse.observation.level", "ERROR")
        elif kind == "execution_finished":
            if attributes.get("ok") is False:
                opened.root.set_status(Status(StatusCode.ERROR))
            opened.root.end(end_time=_ns(record.at))
            del self._open[record.request_id]

    @staticmethod
    def _end_generation(opened: _Open) -> None:
        if opened.generation is not None:
            opened.generation.end(end_time=opened.generation_end)
            opened.generation, opened.generation_end = None, None

    def _expire(self, now: datetime) -> None:
        for rid in [rid for rid, item in self._open.items() if now - item.started > OPEN_TTL]:
            item = self._open.pop(rid)
            self._end_generation(item)
            item.root.end(end_time=_ns(now))

    # --- conexão --------------------------------------------------------------------------------------------------

    async def check(self, credentials: LangfuseCredentials) -> ConnectionCheck:
        """ "Testar conexão": `GET /api/public/projects` com a mesma autenticação (R32). Nunca devolve o segredo."""
        client = self._http or httpx.AsyncClient(timeout=10.0)
        try:
            response = await client.get(
                f"{credentials.host.rstrip('/')}{CHECK_PATH}", headers={"Authorization": basic_auth(credentials)}
            )
        except httpx.HTTPError as error:
            return ConnectionCheck(ok=False, detail=f"endereço inalcançável ({type(error).__name__})")
        finally:
            if self._http is None:
                await client.aclose()
        if response.status_code in (401, 403):
            return ConnectionCheck(ok=False, detail="credencial recusada")
        if response.status_code != 200:
            return ConnectionCheck(ok=False, detail=f"o Langfuse respondeu {response.status_code}")
        try:
            data = response.json().get("data") or []
            name = data[0].get("name") if data and isinstance(data[0], Mapping) else None
        except (ValueError, AttributeError):
            name = None
        return ConnectionCheck(ok=True, detail=f"projeto {name}" if name else "credencial aceita")

    async def flush(self) -> None:
        provider = self._provider
        if provider is not None:
            import asyncio

            await asyncio.to_thread(provider.force_flush, 10_000)

    def shutdown(self) -> None:
        self.reconfigure(None)


class LangfuseDestination:
    """O destino que o `TraceService` enxerga: aceita conteúdo e repassa ao transporte, que nunca bloqueia."""

    def __init__(self, transport: LangfuseTransport, *, clock: Callable[[], datetime]) -> None:
        self._transport = transport
        self._now = clock
        self._sent_at: datetime | None = None
        self._failures: list[datetime] = []
        self._last_error: str | None = None
        self.enabled = False

    @property
    def name(self) -> str:
        return "langfuse"

    @property
    def accepts_content(self) -> bool:
        return True

    def configure(self, credentials: LangfuseCredentials | None) -> None:
        self.enabled = credentials is not None
        self._transport.reconfigure(credentials)

    def export(self, record: TraceRecord) -> None:
        if not self.enabled:
            return
        try:
            self._transport.send(record)
            self._sent_at = record.at
        except Exception as error:
            self._failures.append(self._now())
            self._last_error = f"{type(error).__name__}: {error}"[:300]

    async def flush(self) -> None:
        try:
            await self._transport.flush()
        except Exception as error:
            self._failures.append(self._now())
            self._last_error = f"{type(error).__name__}: {error}"[:300]

    def stats(self) -> DestinationStats:
        transport_error = getattr(self._transport, "last_error", None)
        return DestinationStats(
            dropped=len(self._failures),
            dropped_at=tuple(self._failures[-1_000:]),
            last_error=self._last_error or transport_error,
            last_sent_at=self._sent_at,
        )

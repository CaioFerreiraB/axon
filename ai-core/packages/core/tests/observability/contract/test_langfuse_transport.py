"""T062 — o transporte do Langfuse por OpenTelemetry (research R32): mapeamento para spans, envio OTLP com Basic auth
contra um coletor local, fila sem bloquear e o "testar conexão"."""

from __future__ import annotations

import base64
import threading
import time
from collections.abc import Iterator
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import httpx
import pytest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
from trace_testkit import AT, exchange, finished, model_call, started

from ai_core.observability.adapters.langfuse import LangfuseDestination, OtelLangfuseTransport
from ai_core.observability.api import ToolCall
from ai_core.observability.domain.content import exchange_record
from ai_core.observability.domain.records import to_record
from ai_core.observability.ports import LangfuseCredentials

pytestmark = pytest.mark.us6

CREDENTIALS = LangfuseCredentials(host="https://cloud.langfuse.test", public_key="pk-lf-1", secret_key="sk-lf-segredo")


def _memory() -> tuple[OtelLangfuseTransport, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    transport = OtelLangfuseTransport(exporter_factory=lambda _c: exporter, delay_ms=10)
    transport.reconfigure(CREDENTIALS)
    return transport, exporter


def _flush(transport: OtelLangfuseTransport) -> None:
    assert transport._provider is not None
    transport._provider.force_flush()


def test_raiz_por_requisicao_geracao_com_inicio_e_tokens() -> None:
    transport, exporter = _memory()
    transport.send(to_record(started(), AT))
    transport.send(to_record(model_call(duration_ms=2_000.0), AT + timedelta(seconds=3)))
    transport.send(
        to_record(
            ToolCall(
                request_id="req-7f3a",
                tool="generic.calculate",
                kind="native",
                status="ok",
                duration_ms=5.0,
                size_bytes=10,
            ),
            AT + timedelta(seconds=4),
        )
    )
    transport.send(to_record(finished(), AT + timedelta(seconds=5)))
    _flush(transport)
    spans = {span.name: span for span in exporter.get_finished_spans()}
    root, generation, tool = spans["geral"], spans["generation"], spans["generic.calculate"]
    assert (
        root.attributes["langfuse.trace.name"] == "geral" and root.attributes["langfuse.trace.metadata.flow"] == "chat"
    )
    assert generation.parent is not None and generation.parent.span_id == root.context.span_id
    assert generation.attributes["langfuse.observation.type"] == "generation"
    assert generation.attributes["gen_ai.request.model"] == "ollama/qwen3:1.7b"
    assert generation.attributes["gen_ai.usage.input_tokens"] == 412
    assert generation.end_time - generation.start_time == 2_000_000_000
    assert tool.attributes["langfuse.observation.type"] == "tool"
    assert root.end_time - root.start_time == 5_000_000_000


def test_conteudo_preenche_a_geracao_pendente() -> None:
    transport, exporter = _memory()
    transport.send(to_record(started(), AT))
    transport.send(to_record(model_call(), AT + timedelta(seconds=1)))
    transport.send(exchange_record(exchange(), AT + timedelta(seconds=1)))
    transport.send(to_record(finished(), AT + timedelta(seconds=2)))
    _flush(transport)
    generation = next(span for span in exporter.get_finished_spans() if span.name == "generation")
    assert "Você é útil." in str(generation.attributes["langfuse.observation.input"])
    assert "sk-segredo-123" not in str(generation.attributes["langfuse.observation.input"])
    assert generation.attributes["langfuse.observation.output"] == "Brasília."


def test_erro_marca_a_geracao_e_eventos_vao_ao_raiz() -> None:
    from ai_core.observability.api import ExecutionError

    transport, exporter = _memory()
    transport.send(to_record(started(), AT))
    transport.send(to_record(model_call(finish_reason="error"), AT))
    transport.send(
        to_record(
            ExecutionError(request_id="req-7f3a", stage="generate", kind="ModelCallFailed", message="timeout"), AT
        )
    )
    transport.send(to_record(finished(ok=False), AT))
    _flush(transport)
    spans = {span.name: span for span in exporter.get_finished_spans()}
    assert spans["generation"].attributes["langfuse.observation.level"] == "ERROR"
    assert spans["generation"].status.status_code is StatusCode.ERROR
    assert [event.name for event in spans["geral"].events] == ["execution_error"]


def test_sem_credenciais_nada_sai_e_reconfigurar_desliga() -> None:
    exporter = InMemorySpanExporter()
    transport = OtelLangfuseTransport(exporter_factory=lambda _c: exporter)
    transport.send(to_record(started(), AT))
    assert not transport.active
    transport.reconfigure(CREDENTIALS)
    transport.reconfigure(None)
    transport.send(to_record(started(), AT))
    assert exporter.get_finished_spans() == ()


class _Collector(BaseHTTPRequestHandler):
    received: ClassVar[list[tuple[str, str, bytes]]] = []

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        _Collector.received.append((self.path, self.headers.get("authorization", ""), self.rfile.read(length)))
        self.send_response(200)
        self.send_header("content-type", "application/x-protobuf")
        self.end_headers()

    def log_message(self, *_args: object) -> None:
        return None


@pytest.fixture
def collector() -> Iterator[str]:
    _Collector.received = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Collector)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()


def test_otlp_http_de_verdade_com_basic_auth(collector: str) -> None:
    credentials = LangfuseCredentials(host=collector, public_key="pk-lf-1", secret_key="sk-lf-segredo")
    transport = OtelLangfuseTransport(delay_ms=10)
    transport.reconfigure(credentials)
    transport.send(to_record(started(), AT))
    transport.send(to_record(model_call(), AT))
    transport.send(to_record(finished(), AT))
    _flush(transport)
    deadline = time.time() + 5
    while not _Collector.received and time.time() < deadline:
        time.sleep(0.05)
    path, authorization, body = _Collector.received[0]
    assert path == "/api/public/otel/v1/traces"
    assert authorization == "Basic " + base64.b64encode(b"pk-lf-1:sk-lf-segredo").decode()
    request = ExportTraceServiceRequest.FromString(body)
    names = {span.name for resource in request.resource_spans for scope in resource.scope_spans for span in scope.spans}
    assert names == {"geral", "generation"}
    transport.shutdown()


def test_fila_cheia_descarta_sem_bloquear() -> None:
    class Slow(InMemorySpanExporter):
        def export(self, spans: object) -> object:  # type: ignore[override]
            time.sleep(1)
            return super().export(spans)  # type: ignore[arg-type]

    transport = OtelLangfuseTransport(exporter_factory=lambda _c: Slow(), queue=4, batch=2, delay_ms=1)
    transport.reconfigure(CREDENTIALS)
    start = time.perf_counter()
    for index in range(200):
        transport.send(to_record(started(request_id=f"r{index}"), AT))
        transport.send(to_record(finished(request_id=f"r{index}"), AT))
    assert time.perf_counter() - start < 0.5
    transport.reconfigure(None)


async def test_testar_conexao() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/public/projects"
        if request.headers["authorization"] != "Basic " + base64.b64encode(b"pk-lf-1:sk-lf-segredo").decode():
            return httpx.Response(401)
        return httpx.Response(200, json={"data": [{"id": "p1", "name": "agentic"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        transport = OtelLangfuseTransport(http=http)
        ok = await transport.check(CREDENTIALS)
        assert ok.ok and ok.detail == "projeto agentic"
        refused = await transport.check(
            LangfuseCredentials(host=CREDENTIALS.host, public_key="pk", secret_key="errado")
        )
        assert not refused.ok and refused.detail == "credencial recusada" and "errado" not in refused.detail

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sem rota", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(down)) as http:
        unreachable = await OtelLangfuseTransport(http=http).check(CREDENTIALS)
        assert not unreachable.ok and unreachable.detail.startswith("endereço inalcançável")


def test_destino_desligado_nao_envia_e_aceita_conteudo() -> None:
    exporters: list[InMemorySpanExporter] = []

    def factory(_credentials: LangfuseCredentials) -> InMemorySpanExporter:
        exporters.append(InMemorySpanExporter())
        return exporters[-1]

    transport = OtelLangfuseTransport(exporter_factory=factory, delay_ms=10)
    destination = LangfuseDestination(transport, clock=lambda: AT)
    assert destination.accepts_content and destination.name == "langfuse"
    destination.export(to_record(started(), AT))
    assert not destination.enabled and not transport.active and exporters == []
    destination.configure(CREDENTIALS)
    destination.export(to_record(started(), AT))
    destination.export(to_record(finished(), AT))
    _flush(transport)
    assert [span.name for span in exporters[-1].get_finished_spans()] == ["geral"]
    assert destination.stats().last_sent_at == AT
    destination.configure(None)
    assert not transport.active


def test_exportacao_que_falha_aparece_e_a_que_volta_limpa() -> None:
    """Langfuse fora do ar chega à saúde pelo transporte (011 US6 cenário 4), e o erro some quando ele volta."""
    from opentelemetry.sdk.trace.export import SpanExportResult

    class Flaky(InMemorySpanExporter):
        down = True

        def export(self, spans: object) -> SpanExportResult:  # type: ignore[override]
            return SpanExportResult.FAILURE if self.down else super().export(spans)  # type: ignore[arg-type]

    exporter = Flaky()
    transport = OtelLangfuseTransport(exporter_factory=lambda _c: exporter, delay_ms=10)
    destination = LangfuseDestination(transport, clock=lambda: AT)
    destination.configure(CREDENTIALS)
    destination.export(to_record(started(), AT))
    destination.export(to_record(finished(), AT))
    _flush(transport)
    assert destination.stats().last_error == "o Langfuse não aceitou o lote (OTLP)" and transport.export_failures == 1
    exporter.down = False
    destination.export(to_record(started(request_id="r2"), AT))
    destination.export(to_record(finished(request_id="r2"), AT))
    _flush(transport)
    assert destination.stats().last_error is None

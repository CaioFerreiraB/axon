"""Fábricas dos testes da 006 (T007): políticas, trace de memória e transportes HTTP falsos.

O relógio programado **não** mora aqui: é adapter (`axon_ai.llm.adapters.clock.ScriptedClock`), porque a 011 precisa
dele no perfil de teste (princípio XIII).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any, Final

import httpx2

from axon_ai.llm.adapters.fake import ScriptedProvider
from axon_ai.llm.adapters.ollama import OllamaProvider
from axon_ai.llm.adapters.openai import OpenAIProvider
from axon_ai.llm.adapters.openrouter import OpenRouterProvider
from axon_ai.llm.adapters.secrets import InMemorySecretResolver
from axon_ai.llm.api import ModelCallFailed, ModelPolicy, ModelRef
from axon_ai.llm.ports import ModelProvider
from axon_ai.observability.api import ModelExchange, TraceEvent

REQUEST_ID: Final = "req-006-1"
"""Identificador de requisição dos testes; o mesmo que aparece nos `ModelCall` emitidos."""

MODEL: Final = "qwen3:1.7b"
BASE_URL: Final = "http://ollama.test/v1"

SECRET: Final = "sk-teste-0123456789"
"""Credencial dos remotos nos testes: nunca pode aparecer em mensagem (FR-011)."""
REMOTE_BASE_URL: Final = "http://remoto.test/v1"

Handler = Callable[[httpx2.Request], httpx2.Response]


class RecordingTraceSink:
    """Trace Sink (seam da 009) que acumula o que foi emitido, para os testes de instrumentação.

    `events` são os `ModelCall` (o que a instrumentação da Fase 1 prova); `exchanges`, os `ModelExchange` da Fase 9
    (ADR-034), que o `TraceService` descarta com a captura desligada.
    """

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []
        self.exchanges: list[ModelExchange] = []

    def emit(self, event: TraceEvent) -> None:
        if isinstance(event, ModelExchange):
            self.exchanges.append(event)
        else:
            self.events.append(event)


def policy(
    *,
    generation: str = f"ollama/{MODEL}",
    controller: str | None = None,
    allow: tuple[str, ...] = (),
    vision: frozenset[str] = frozenset(),
) -> ModelPolicy:
    """Política de exemplo: sempre com `generation`, opcionalmente com `controller` e papéis com `vision`."""
    roles = {"generation": ModelRef.parse(generation)}
    if controller is not None:
        roles["controller"] = ModelRef.parse(controller)
    return ModelPolicy(roles=roles, allow=allow, vision=vision)  # type: ignore[arg-type]


def sse(*chunks: Mapping[str, object]) -> bytes:
    """Corpo de streaming no formato que a camada compatível com OpenAI usa."""
    lines = [f"data: {json.dumps(chunk)}\n\n" for chunk in chunks]
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


def delta_chunk(content: str) -> dict[str, object]:
    return {
        "id": "c1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": MODEL,
        "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
    }


def final_chunk(*, finish_reason: str = "stop", usage: Mapping[str, object] | None = None) -> dict[str, object]:
    chunk: dict[str, object] = {
        "id": "c1",
        "object": "chat.completion.chunk",
        "created": 1,
        "model": MODEL,
        "choices": [{"index": 0, "delta": {}, "finish_reason": finish_reason}],
    }
    if usage is not None:
        chunk["usage"] = dict(usage)
    return chunk


def completion(
    *,
    content: str = "resposta",
    finish_reason: str = "stop",
    usage: Mapping[str, object] | None = None,
    tool_calls: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Corpo de uma resposta única da camada compatível."""
    message: dict[str, object] = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    body: dict[str, object] = {
        "id": "r1",
        "object": "chat.completion",
        "created": 1,
        "model": MODEL,
        "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
    }
    if usage is not None:
        body["usage"] = dict(usage)
    return body


class RecordingTransport:
    """Transporte falso que guarda os corpos enviados e responde pelo que o roteiro disser.

    `routes` mapeia sufixo de caminho (`/chat/completions`, `/models`) para um handler.
    """

    def __init__(self, routes: Mapping[str, Handler]) -> None:
        self._routes = dict(routes)
        self.requests: list[httpx2.Request] = []

    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self._handle)

    def bodies(self) -> list[dict[str, object]]:
        """Corpos JSON enviados, na ordem."""
        return [json.loads(request.content) for request in self.requests if request.content]

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        for suffix, handler in self._routes.items():
            if request.url.path.endswith(suffix):
                return handler(request)
        raise AssertionError(f"caminho inesperado no transporte falso: {request.url.path}")


def json_route(body: Mapping[str, object], *, status: int = 200) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(status, json=dict(body))

    return handler


def sse_route(payload: bytes) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=payload)

    return handler


def raising_route(error: Exception) -> Handler:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise error

    return handler


CHAT: Final = "/chat/completions"
MODELS: Final = "/models"


def models_route(*model_ids: str) -> Handler:
    entries = [{"id": name, "object": "model", "created": 1, "owned_by": "t"} for name in model_ids]
    return json_route({"object": "list", "data": entries})


USAGE: Final = {"prompt_tokens": 7, "completion_tokens": 2}
"""Uso de tokens das respostas de exemplo."""

FAILURES: Final = ("inalcançável", "sem resposta", "429")
"""Motivos de falha que os dois adapters sabem reproduzir."""


class ScriptedCase:
    """Caso montado sobre o adapter em memória da porta `ModelProvider`."""

    id = "scripted"
    name = "ollama"

    def ok(self, *, usage: Mapping[str, int] | None = USAGE, models: tuple[str, ...] = (MODEL,)) -> ModelProvider:
        self.provider = ScriptedProvider(
            name="ollama", content="resposta", deltas=("Oi", " mundo"), usage=usage, known_models=models
        )
        return self.provider

    def failing(self, reason: str) -> ModelProvider:
        self.provider = ScriptedProvider(
            name="ollama", error=ModelCallFailed(provider="ollama", model=MODEL, reason=reason)
        )
        return self.provider

    def sent_model(self) -> str:
        return str(self.provider.calls[-1]["model"])

    def sent_tool_names(self) -> list[str]:
        tools = self.provider.calls[-1]["tools"] or []
        return [tool["name"] for tool in tools]

    def sent_response_format(self) -> Mapping[str, object] | None:
        return self.provider.calls[-1]["response_format"]

    def sent_messages(self) -> list[Any]:
        return [dict(message) for message in self.provider.calls[-1]["messages"]]

    def call_count(self) -> int:
        return len(self.provider.calls)


class HttpCase:
    """Caso montado sobre um adapter real da camada compatível, contra um transporte HTTP falso (research R10)."""

    id = "http"
    name = "ollama"

    def _provider(self, http_client: httpx2.AsyncClient) -> ModelProvider:
        raise NotImplementedError

    def _build(self, chat_handler: Handler, models_handler: Handler) -> ModelProvider:
        self.transport = RecordingTransport({CHAT: chat_handler, MODELS: models_handler})
        return self._provider(httpx2.AsyncClient(transport=self.transport.transport()))

    def ok(self, *, usage: Mapping[str, int] | None = USAGE, models: tuple[str, ...] = (MODEL,)) -> ModelProvider:
        def handler(request: httpx2.Request) -> httpx2.Response:
            if b'"stream": true' in request.content or b'"stream":true' in request.content:
                return sse_route(sse(delta_chunk("Oi"), delta_chunk(" mundo"), final_chunk(usage=usage)))(request)
            return json_route(completion(usage=usage))(request)

        return self._build(handler, models_route(*models))

    def failing(self, reason: str) -> ModelProvider:
        errors: dict[str, Handler] = {
            "inalcançável": raising_route(httpx2.ConnectError("connection refused")),
            "sem resposta": raising_route(httpx2.ReadTimeout("read timeout")),
            "429": json_route({"error": {"message": "rate limit"}}, status=429),
        }
        # A sondagem usa o mesmo transporte: provider fora do ar também responde indisponível em `probe`.
        return self._build(errors[reason], errors[reason])

    def sent_model(self) -> str:
        return str(self.transport.bodies()[-1]["model"])

    def sent_tool_names(self) -> list[str]:
        tools = self.transport.bodies()[-1].get("tools") or []
        return [tool["function"]["name"] for tool in tools]

    def sent_response_format(self) -> Mapping[str, object] | None:
        value = self.transport.bodies()[-1].get("response_format")
        return value if value is None else dict(value)

    def sent_messages(self) -> list[Any]:
        return list(self.transport.bodies()[-1]["messages"])  # type: ignore[call-overload]

    def call_count(self) -> int:
        return len(self.transport.requests)


class OllamaCase(HttpCase):
    id = "ollama"
    name = "ollama"

    def _provider(self, http_client: httpx2.AsyncClient) -> ModelProvider:
        return OllamaProvider(base_url=BASE_URL, http_client=http_client)


class OpenAICase(HttpCase):
    """Fase 3: o remoto da OpenAI com credencial, contra o transporte falso (T031)."""

    id = "openai"
    name = "openai"

    def _provider(self, http_client: httpx2.AsyncClient) -> ModelProvider:
        secrets = InMemorySecretResolver({OpenAIProvider.CREDENTIAL: SECRET})
        return OpenAIProvider(secrets=secrets, base_url=REMOTE_BASE_URL, http_client=http_client)


class OpenRouterCase(HttpCase):
    """Fase 3: o remoto do OpenRouter com credencial, contra o transporte falso (T031)."""

    id = "openrouter"
    name = "openrouter"

    def _provider(self, http_client: httpx2.AsyncClient) -> ModelProvider:
        secrets = InMemorySecretResolver({OpenRouterProvider.CREDENTIAL: SECRET})
        return OpenRouterProvider(secrets=secrets, base_url=REMOTE_BASE_URL, http_client=http_client)


PROVIDER_CASES: Final = (ScriptedCase, OllamaCase)
"""Os dois adapters da Fase 1: a conformidade do seam roda contra ambos (princípio XIII)."""

PORT_CASES: Final = (*PROVIDER_CASES, OpenAICase, OpenRouterCase)
"""Todos os adapters da porta `ModelProvider`, inclusive os remotos da Fase 3 (T031)."""

HTTP_CASES: Final = (OllamaCase, OpenAICase, OpenRouterCase)
"""Os adapters da camada compatível — os que montam um corpo HTTP de verdade."""

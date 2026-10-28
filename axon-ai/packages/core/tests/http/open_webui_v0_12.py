"""O pedido que o Open WebUI v0.12.0 manda a uma conexão compatível com OpenAI (contracts/open-webui.md; research R38).

Montado a partir do código da versão (backend/open_webui): `routers/openai.py` (`generate_chat_completion`: o corpo do
formulário sem `metadata`, `model` sem prefixo, `max_completion_tokens` → `max_tokens` fora da OpenAI),
`utils/payload.py` (`apply_model_params_to_body_openai`: `temperature`, `top_p`, `max_tokens`, `seed`, `stop`…) e
`utils/headers.py` (`get_headers_and_cookies`: `Content-Type`, `Authorization: Bearer` do `system_oauth` e os
`headers` da conexão — na instalação, `x-axon-store: false`, `x-axon-progress: status` e
`x-axon-citations: sources`). O histórico vai inteiro, porque o Open WebUI não envia id de conversa; o raciocínio das
respostas anteriores não volta (`reasoning_format=None`). Mudou a versão do Open WebUI: refazer a partir do código novo.
"""

from __future__ import annotations

from typing import Any, Final

VERSION: Final = "v0.12.0"


def body(model: str = "geral", **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Responda em português."},
            {"role": "user", "content": "Qual é a capital do Brasil?"},
            {"role": "assistant", "content": "Brasília."},
            {"role": "user", "content": "E a do Paraná?"},
        ],
        "stream": True,
        "stream_options": {"include_usage": True},
        "temperature": 0.8,
        "top_p": 0.9,
        "max_tokens": 1024,
        "seed": 42,
    }
    return base | overrides


def headers(access_token: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "x-axon-store": "false",
        "x-axon-progress": "status",
        "x-axon-citations": "sources",
    }

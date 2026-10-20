"""Provider local: Ollama pela camada compatível com OpenAI em `:11434/v1` (design.md, research R4).

O `design.md` escolheu essa camada — e não a API nativa em `/api` — para que os três providers fiquem quase idênticos.
Aqui só ficam os defaults do Ollama; todo o comportamento está em `openai_compat.py`.
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx2

from axon_ai.llm.adapters.openai_compat import OpenAICompatProvider

DEFAULT_BASE_URL = "http://localhost:11434/v1"
"""Camada compatível do Ollama. A composition root (011) lê o endereço real da configuração do operador."""

CREDENTIAL_SENTINEL = "ollama"
"""O Ollama exige o cabeçalho de credencial e ignora o valor: não há segredo a resolver nesta fase."""


class OllamaProvider(OpenAICompatProvider):
    """`ModelProvider` do provider local."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_BASE_URL,
        connect_seconds: float = 5.0,
        idle_seconds: float = 120.0,
        default_headers: Mapping[str, str] | None = None,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            name="ollama",
            base_url=base_url,
            api_key=CREDENTIAL_SENTINEL,
            connect_seconds=connect_seconds,
            idle_seconds=idle_seconds,
            default_headers=default_headers,
            http_client=http_client,
        )

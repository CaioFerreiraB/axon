"""`SecretResolver` pelo ambiente (research R7): a referência `financeiro_token` lê
`AXON_MCP_SECRET_FINANCEIRO_TOKEN` e nada mais.

O prefixo fixo é o controle: um MCP global — ou quem tem uma chave de administração — não consegue apontar uma
referência para `AXON_DATABASE_URL` nem para outra variável do processo e mandá-la para um endpoint externo.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Final

from axon_ai.mcp.api import CREDENTIAL_REF_PATTERN

PREFIX: Final = "AXON_MCP_SECRET_"


class EnvSecretResolver:
    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = environ if environ is not None else os.environ

    def resolve(self, ref: str) -> str | None:
        if not CREDENTIAL_REF_PATTERN.fullmatch(ref):
            return None
        value = self._environ.get(f"{PREFIX}{ref.upper()}")
        return value or None

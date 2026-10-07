"""Provider remoto da OpenAI (contracts/remote-adapters.md; research R20).

Só os dados do endpoint: o comportamento é o da camada compatível, e a credencial, o de `remote.py`.
"""

from __future__ import annotations

from ai_core.llm.adapters.remote import RemoteProvider


class OpenAIProvider(RemoteProvider):
    NAME = "openai"
    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    CREDENTIAL = "AI_CORE_OPENAI_API_KEY"

    def _follows_openai_rules(self, model: str) -> bool:
        """É a própria API da OpenAI (ADR-023)."""
        return True

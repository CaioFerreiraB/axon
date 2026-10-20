"""Provider remoto do OpenRouter (contracts/remote-adapters.md; research R18, R20, R22).

Além dos dados do endpoint, três particularidades: a sondagem aceita a base de uma variante — `:nitro` e `:floor`
escolhem o upstream do mesmo modelo e não aparecem como id na lista —, as chamadas com restrição de formato pedem ao
OpenRouter que só encaminhe a upstream que a cumpra, e todo pedido pede o custo na resposta (ADR-035).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ai_core.llm.adapters.remote import RemoteProvider
from ai_core.llm.api import AUTO_ROUTING_PROVIDER
from ai_core_contracts import ChatMessage, ChatTool, JSONValue


class OpenRouterProvider(RemoteProvider):
    NAME = AUTO_ROUTING_PROVIDER
    """O mesmo nome que a regra de roteamento automático do `ModelRef` usa (research R16)."""
    DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
    CREDENTIAL = "AI_CORE_OPENROUTER_API_KEY"
    REPORTS_COST = True

    def _has_model(self, model: str, ids: Sequence[str]) -> bool:
        if model in ids:
            return True
        base, separator, _variant = model.rpartition(":")
        return bool(separator) and base in ids

    def _follows_openai_rules(self, model: str) -> bool:
        """Modelos da OpenAI pelo OpenRouter vão a upstream com as regras da API da OpenAI (ADR-023)."""
        return model.casefold().startswith("openai/")

    def _payload(
        self,
        messages: Sequence[ChatMessage],
        model: str,
        *,
        tools: Sequence[ChatTool] | None,
        response_format: Mapping[str, JSONValue] | None,
    ) -> dict[str, Any]:
        """Com restrição de formato, só upstream que a suporte (research R18). Sem ela, o pedido não restringe: o
        `require_parameters` excluiria também quem não declara parâmetros acessórios, como `stream_options`.

        Todo pedido leva `usage.include`, para o custo vir em `usage.cost` — também no último pedaço do streaming
        (ADR-035)."""
        payload = super()._payload(messages, model, tools=tools, response_format=response_format)
        extra: dict[str, Any] = {"usage": {"include": True}}
        if response_format is not None:
            extra["provider"] = {"require_parameters": True}
        payload["extra_body"] = extra
        return payload

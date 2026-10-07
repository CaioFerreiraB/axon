"""JSON ⇄ servidor MCP da 007 (contracts/mcp-routes.md; research R26). Só o mapeamento: as regras são da 007.

O corpo segue a forma do `mcp.yaml` — `auth: {type, credential}` e `policy: {…}` aninhados —, para que operador e
usuário escrevam o mesmo formato. Tipo errado e chave desconhecida são recusados aqui, nomeando o campo; o que a 007
decide (escopo, `https`, `stdio`, faixas) ela recusa com `McpRejected`. A resposta nunca traz valor de credencial: só
o nome da referência (007 FR-004).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Final, Literal

from ai_core.http.domain.errors import InvalidRequest
from ai_core.mcp.api import McpServer, McpServerDraft, McpSummary, SecurityPolicy, ServerHealth

type Scope = Literal["global", "user"]

USER_PREFIX: Final = "~"
FIELDS: Final = frozenset({"alias", "transport", "endpoint", "description", "auth", "enabled", "user_access", "policy"})
AUTH_FIELDS: Final = frozenset({"type", "credential"})
POLICY_FIELDS: Final = frozenset({"allowed_tools", "write_tools", "timeout_ms", "max_response_bytes"})


def draft_from_json(body: Mapping[str, Any], *, scope: Scope, alias: str | None = None) -> McpServerDraft:
    """Rascunho a partir do corpo. `alias` (o do caminho) prevalece; no escopo `user`, ganha `~` se vier sem."""
    _known(body, FIELDS, prefix="")
    raw_alias = alias if alias is not None else body.get("alias")
    if not isinstance(raw_alias, str) or not raw_alias.strip():
        raise InvalidRequest("campo 'alias' é obrigatório", field="alias")
    if scope == "user" and not raw_alias.startswith(USER_PREFIX):
        raw_alias = f"{USER_PREFIX}{raw_alias}"

    auth = _mapping(body, "auth", required=False)
    _known(auth, AUTH_FIELDS, prefix="auth.")
    policy = _mapping(body, "policy", required=True)
    _known(policy, POLICY_FIELDS, prefix="policy.")

    return McpServerDraft(
        alias=raw_alias,
        transport=_text(body, "transport", required=True),
        endpoint=_optional_text(body, "endpoint"),
        description=_optional_text(body, "description"),
        auth_type=_optional_text(auth, "type", prefix="auth.") or "none",
        credential_ref=_optional_text(auth, "credential", prefix="auth."),
        enabled=_flag(body, "enabled", default=True),
        user_access=_flag(body, "user_access", default=False),
        policy=_policy(policy),
    )


def server_json(server: McpServer) -> dict[str, Any]:
    """A visão publicada de um servidor, com a referência de credencial pelo **nome**."""
    return {
        "alias": server.alias,
        "scope": server.scope,
        "owner": server.owner,
        "transport": server.transport,
        "endpoint": server.endpoint,
        "command": server.command,
        "description": server.description,
        "auth": {"type": server.auth_type, "credential": server.credential_ref},
        "enabled": server.enabled,
        "user_access": server.user_access,
        "policy": None if server.policy is None else _policy_json(server.policy),
        "origin": server.origin,
        "available": server.available,
        "reason": server.reason,
        "created_at": _moment(server.created_at),
        "updated_at": _moment(server.updated_at),
    }


def summary_json(summary: McpSummary) -> dict[str, Any]:
    """O que o Principal pode referenciar: sem endpoint, credencial nem política."""
    return {"alias": summary.alias, "scope": summary.scope, "description": summary.description}


def health_json(health: ServerHealth) -> dict[str, Any]:
    return {
        "alias": health.alias,
        "ok": health.ok,
        "detail": health.detail,
        "tools": list(health.tools),
        "missing": list(health.missing),
    }


# --- leitura ------------------------------------------------------------------------------------------------------


def _known(body: Mapping[str, Any], fields: frozenset[str], *, prefix: str) -> None:
    for key in sorted(str(k) for k in body if k not in fields):
        raise InvalidRequest(f"campo '{prefix}{key}' não é aceito num servidor MCP", field=f"{prefix}{key}")


def _mapping(body: Mapping[str, Any], name: str, *, required: bool) -> Mapping[str, Any]:
    value = body.get(name)
    if value is None:
        if required:
            raise InvalidRequest(f"campo '{name}' é obrigatório", field=name)
        return {}
    if not isinstance(value, Mapping):
        raise InvalidRequest(f"campo '{name}' precisa ser um objeto", field=name)
    return value


def _text(body: Mapping[str, Any], name: str, *, required: bool, prefix: str = "") -> str:
    value = body.get(name)
    if not isinstance(value, str) or not value.strip():
        raise InvalidRequest(f"campo '{prefix}{name}' precisa ser um texto não vazio", field=f"{prefix}{name}")
    return value


def _optional_text(body: Mapping[str, Any], name: str, *, prefix: str = "") -> str | None:
    if body.get(name) is None:
        return None
    return _text(body, name, required=True, prefix=prefix)


def _flag(body: Mapping[str, Any], name: str, *, default: bool) -> bool:
    value = body.get(name, default)
    if not isinstance(value, bool):
        raise InvalidRequest(f"campo '{name}' precisa ser verdadeiro ou falso", field=name)
    return value


def _names(policy: Mapping[str, Any], name: str) -> tuple[str, ...]:
    value = policy.get(name, [])
    if not isinstance(value, list):
        raise InvalidRequest(f"campo 'policy.{name}' precisa ser uma lista de nomes", field=f"policy.{name}")
    return tuple(value)


def _integer(policy: Mapping[str, Any], name: str) -> dict[str, int]:
    if name not in policy:
        return {}
    value = policy[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidRequest(f"campo 'policy.{name}' precisa ser um número inteiro", field=f"policy.{name}")
    return {name: value}


def _policy(policy: Mapping[str, Any]) -> SecurityPolicy:
    """As faixas e a allowlist obrigatória são da 007: `SecurityPolicy` as recusa com `McpRejected` nomeando o campo."""
    return SecurityPolicy(
        allowed_tools=_names(policy, "allowed_tools"),
        write_tools=_names(policy, "write_tools"),
        **_integer(policy, "timeout_ms"),
        **_integer(policy, "max_response_bytes"),
    )


def _policy_json(policy: SecurityPolicy) -> dict[str, Any]:
    return {
        "allowed_tools": list(policy.allowed_tools),
        "write_tools": list(policy.write_tools),
        "timeout_ms": policy.timeout_ms,
        "max_response_bytes": policy.max_response_bytes,
    }


def _moment(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()

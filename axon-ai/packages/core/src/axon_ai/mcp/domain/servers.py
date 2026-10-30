"""Validação do registro e do arquivo do operador (research R4, R10, R11; FR-012 a FR-015). Puro: nada de I/O.

As mesmas regras valem para o rascunho que vem da API e para a entrada do `mcp.yaml`; o que muda é a origem — só o
arquivo pode declarar `stdio` (clarificação 1) — e o escopo.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Final, cast
from urllib.parse import urlsplit

from axon_ai.mcp.api import (
    ALIAS_PATTERN,
    AUTH_TYPES,
    CREDENTIAL_REF_PATTERN,
    DESCRIPTION_MAX,
    TRANSPORTS,
    USER_PREFIX,
    AuthType,
    McpConfigError,
    McpRejected,
    McpServer,
    McpServerDraft,
    Origin,
    Scope,
    SecurityPolicy,
    Transport,
)
from axon_ai.mcp.domain.records import ConfigEntry, McpConfig, StdioCommand

ENV_NAME: Final = re.compile(r"[A-Z_][A-Z0-9_]*")
HOSTNAME: Final = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*")

_TOP_KEYS: Final = frozenset({"servers", "network"})
_NETWORK_KEYS: Final = frozenset({"internal_hosts", "allowed_hosts"})
_ENTRY_KEYS: Final = frozenset(
    {"transport", "endpoint", "command", "args", "env", "secrets", "description", "auth", "user_access", "enabled"}
    | {"policy"}
)
_STDIO_ONLY: Final = ("command", "args", "env", "secrets")
_POLICY_KEYS: Final = frozenset({"allowed_tools", "write_tools", "timeout_ms", "max_response_bytes"})


def _reject(field: str, message: str) -> McpRejected:
    return McpRejected(f"{field}: {message}", field=field)


# ---------------------------------------------------------------------------------------------------------------------
# Rascunho (API e arquivo)
# ---------------------------------------------------------------------------------------------------------------------


def check_alias(alias: object, scope: Scope) -> str:
    """Global: `ALIAS_PATTERN`, sem `~`; usuário: `~` + a mesma gramática (FR-015)."""
    if not isinstance(alias, str):
        raise _reject("alias", "precisa ser um texto")
    if scope == "user":
        if not alias.startswith(USER_PREFIX) or not ALIAS_PATTERN.fullmatch(alias.removeprefix(USER_PREFIX)):
            raise _reject("alias", f"MCP de usuário precisa de alias '~' + {ALIAS_PATTERN.pattern}: {alias!r}")
    elif not ALIAS_PATTERN.fullmatch(alias):
        raise _reject("alias", f"MCP global precisa de alias {ALIAS_PATTERN.pattern} (sem '~'): {alias!r}")
    return alias


def validate_draft(draft: McpServerDraft, *, scope: Scope, origin: Origin) -> McpServerDraft:
    """O rascunho, se cumpre as regras do escopo e da origem; senão `McpRejected` nomeando o campo."""
    check_alias(draft.alias, scope)
    transport = _transport(draft.transport, scope=scope, origin=origin)
    if transport == "stdio":
        if draft.endpoint is not None:
            raise _reject("endpoint", "servidor stdio não tem endpoint; o comando vem do arquivo do operador")
    else:
        _endpoint(draft.endpoint, scope=scope)
    _description(draft.description)
    _auth(draft.auth_type, draft.credential_ref, scope=scope, transport=transport)
    if not isinstance(draft.enabled, bool):
        raise _reject("enabled", "precisa ser verdadeiro ou falso")
    if not isinstance(draft.user_access, bool):
        raise _reject("user_access", "precisa ser verdadeiro ou falso")
    if scope == "user" and draft.user_access:
        raise _reject("user_access", "só um MCP global pode ser liberado a usuários")
    if draft.auth_type == "delegated" and (
        scope != "global"
        or transport != "http"
        or draft.user_access
        or not (draft.endpoint or "").startswith("https://")
    ):
        raise _reject("auth_type", "delegated exige MCP global HTTP HTTPS sem user_access")
    if not isinstance(draft.policy, SecurityPolicy):
        raise _reject("policy", "obrigatória")
    return draft


def _transport(value: object, *, scope: Scope, origin: Origin) -> Transport:
    if value not in TRANSPORTS:
        raise _reject("transport", f"precisa ser http, sse ou stdio: {value!r}")
    if value == "stdio" and (scope == "user" or origin != "file"):
        # Comando no host é nível de operador (ADR-003): nem a API nem um usuário o registram (FR-012, FR-013).
        raise _reject("transport", "stdio só pelo arquivo do operador — pela API seria execução de comando no host")
    return value


def _endpoint(value: object, *, scope: Scope) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _reject("endpoint", "obrigatório para http e sse")
    try:
        parts = urlsplit(value)
        _ = parts.port  # porta fora da faixa ou não numérica levanta aqui
    except ValueError as error:
        raise _reject("endpoint", f"URL inválida: {error}") from None
    allowed = ("https",) if scope == "user" else ("http", "https")
    if parts.scheme not in allowed:
        raise _reject("endpoint", f"esquema precisa ser {' ou '.join(allowed)}")
    if not parts.hostname:
        raise _reject("endpoint", "URL sem host")
    if parts.username is not None or parts.password is not None:
        raise _reject("endpoint", "credencial embutida na URL não é aceita — use a referência de credencial")
    if parts.fragment:
        raise _reject("endpoint", "URL com fragmento")
    return value


def _description(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise _reject("description", "precisa ser um texto")
    if len(value) > DESCRIPTION_MAX:
        raise _reject("description", f"passa de {DESCRIPTION_MAX} caracteres")


def _auth(auth_type: object, ref: object, *, scope: Scope, transport: Transport) -> None:
    if auth_type not in AUTH_TYPES:
        raise _reject("auth_type", f"precisa ser none, bearer ou delegated: {auth_type!r}")
    if scope == "user":
        if auth_type != "none":
            raise _reject("auth_type", "MCP de usuário não tem autenticação nesta fase")
        if ref is not None:
            raise _reject("credential_ref", "MCP de usuário não referencia credencial do servidor")
        return
    if transport == "stdio" and auth_type != "none":
        raise _reject("auth_type", "servidor stdio recebe segredos pelo ambiente (`secrets`), não por cabeçalho")
    if auth_type == "bearer":
        if not isinstance(ref, str) or not CREDENTIAL_REF_PATTERN.fullmatch(ref):
            raise _reject("credential_ref", f"bearer exige referência {CREDENTIAL_REF_PATTERN.pattern}")
    elif ref is not None:
        raise _reject("credential_ref", "só com auth_type bearer")


# ---------------------------------------------------------------------------------------------------------------------
# Visão publicada
# ---------------------------------------------------------------------------------------------------------------------


def to_view(
    draft: McpServerDraft,
    *,
    scope: Scope,
    owner: str | None,
    origin: Origin,
    stdio: StdioCommand | None = None,
    available: bool = True,
    reason: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> McpServer:
    return McpServer(
        alias=draft.alias,
        scope=scope,
        owner=owner,
        transport=cast("Transport", draft.transport),
        endpoint=draft.endpoint,
        command=stdio.command if stdio is not None else None,
        description=draft.description,
        auth_type=cast("AuthType", draft.auth_type),
        credential_ref=draft.credential_ref,
        enabled=draft.enabled,
        user_access=draft.user_access,
        policy=draft.policy,
        origin=origin,
        available=available,
        reason=reason,
        created_at=created_at,
        updated_at=updated_at,
    )


def broken_view(entry: ConfigEntry) -> McpServer:
    """Entrada do arquivo com erro: aparece indisponível, com o motivo, e nada mais."""
    return McpServer(
        alias=entry.alias,
        scope="global",
        owner=None,
        transport=None,
        endpoint=None,
        policy=None,
        origin="file",
        available=False,
        reason=entry.problem,
    )


# ---------------------------------------------------------------------------------------------------------------------
# Arquivo do operador (contracts/mcp-yaml.md)
# ---------------------------------------------------------------------------------------------------------------------


def read_config(data: object, *, origin: str) -> McpConfig:
    """Erro de arquivo levanta `McpConfigError` nomeando o caminho; erro de um servidor só o deixa indisponível."""
    if data is None:
        return McpConfig()
    if not isinstance(data, Mapping):
        raise McpConfigError(f"{origin}: a raiz precisa ser um mapeamento")
    unknown = sorted(str(key) for key in data if key not in _TOP_KEYS)
    if unknown:
        raise McpConfigError(f"{origin}: chave desconhecida na raiz: {', '.join(unknown)}")

    servers = data.get("servers") or {}
    if not isinstance(servers, Mapping):
        raise McpConfigError(f"{origin}: servers precisa ser um mapeamento alias → servidor")
    network = data.get("network") or {}
    if not isinstance(network, Mapping):
        raise McpConfigError(f"{origin}: network precisa ser um mapeamento")
    unknown = sorted(str(key) for key in network if key not in _NETWORK_KEYS)
    if unknown:
        raise McpConfigError(f"{origin}: chave desconhecida em network: {', '.join(unknown)}")

    internal = _hosts(network.get("internal_hosts"), f"{origin}: network.internal_hosts", wildcard=False)
    allowed = None
    if "allowed_hosts" in network:
        allowed = _hosts(network.get("allowed_hosts"), f"{origin}: network.allowed_hosts", wildcard=True)
        if not allowed:
            raise McpConfigError(f"{origin}: network.allowed_hosts vazia bloquearia todo destino — remova a chave")
    entries = tuple(parse_entry(str(alias), raw) for alias, raw in servers.items())
    return McpConfig(entries=entries, internal_hosts=internal, allowed_hosts=allowed)


def _hosts(raw: object, path: str, *, wildcard: bool) -> frozenset[str]:
    if raw is None:
        return frozenset()
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        raise McpConfigError(f"{path} precisa ser uma lista de textos")
    hosts = [item.strip().lower().rstrip(".") for item in raw]
    for host in hosts:
        if not _valid_host_pattern(host, wildcard=wildcard):
            accepted = "nome de host, *.domínio ou IP" if wildcard else "nome de host ou IP"
            raise McpConfigError(f"{path}: '{host}' não é {accepted}")
    return frozenset(hosts)


def _valid_host_pattern(host: str, *, wildcard: bool) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return True
    if wildcard and host.startswith("*."):
        host = host[2:]
    return bool(host) and HOSTNAME.fullmatch(host) is not None


def parse_entry(alias: str, raw: object) -> ConfigEntry:
    """Uma entrada do arquivo, sempre global. Qualquer erro vira o problema da entrada, nomeando o campo."""
    try:
        return _parse_entry(alias, raw)
    except McpRejected as error:
        return ConfigEntry(alias=alias, problem=str(error))
    except (TypeError, ValueError) as error:
        return ConfigEntry(alias=alias, problem=f"entrada inválida: {error}")


def _parse_entry(alias: str, raw: object) -> ConfigEntry:
    if not isinstance(raw, Mapping):
        raise _reject("servidor", "precisa ser um mapeamento")
    unknown = sorted(str(key) for key in raw if key not in _ENTRY_KEYS)
    if unknown:
        raise _reject(unknown[0], "chave desconhecida")
    transport = raw.get("transport")
    stdio: StdioCommand | None = None
    if transport == "stdio":
        if "endpoint" in raw:
            raise _reject("endpoint", "servidor stdio não tem endpoint")
        if "auth" in raw:
            raise _reject("auth", "servidor stdio recebe segredos por `secrets`")
        stdio = _stdio(raw)
    else:
        for key in _STDIO_ONLY:
            if key in raw:
                raise _reject(key, "só em servidor stdio")
    auth_type, ref = _auth_block(raw.get("auth"))
    draft = McpServerDraft(
        alias=alias,
        transport=cast("str", transport),
        endpoint=cast("str | None", raw.get("endpoint")),
        description=cast("str | None", raw.get("description")),
        auth_type=auth_type,
        credential_ref=ref,
        enabled=cast("bool", raw.get("enabled", True)),
        user_access=cast("bool", raw.get("user_access", False)),
        policy=_policy(raw.get("policy")),
    )
    validate_draft(draft, scope="global", origin="file")
    return ConfigEntry(alias=alias, draft=draft, stdio=stdio)


def _stdio(raw: Mapping[str, Any]) -> StdioCommand:
    command = raw.get("command")
    if not isinstance(command, str) or not command.strip():
        raise _reject("command", "obrigatório em servidor stdio")
    args = raw.get("args", [])
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise _reject("args", "precisa ser uma lista de textos")
    env = _env_mapping("env", raw.get("env", {}), value_pattern=None)
    secrets = _env_mapping("secrets", raw.get("secrets", {}), value_pattern=CREDENTIAL_REF_PATTERN)
    return StdioCommand(command=command, args=tuple(args), env=env, secrets=secrets)


def _env_mapping(field: str, raw: object, *, value_pattern: re.Pattern[str] | None) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        raise _reject(field, "precisa ser um mapeamento variável → valor")
    result: dict[str, str] = {}
    for name, value in raw.items():
        if not isinstance(name, str) or not ENV_NAME.fullmatch(name):
            raise _reject(field, f"nome de variável inválido: {name!r}")
        if not isinstance(value, str) or (value_pattern is not None and not value_pattern.fullmatch(value)):
            raise _reject(field, f"valor inválido para {name}")
        result[name] = value
    return result


def _auth_block(raw: object) -> tuple[str, str | None]:
    if raw is None:
        return "none", None
    if not isinstance(raw, Mapping):
        raise _reject("auth", "precisa ser um mapeamento {type, credential}")
    unknown = sorted(str(key) for key in raw if key not in {"type", "credential"})
    if unknown:
        raise _reject("auth", f"chave desconhecida: {', '.join(unknown)}")
    return cast("str", raw.get("type", "none")), cast("str | None", raw.get("credential"))


def _policy(raw: object) -> SecurityPolicy:
    if not isinstance(raw, Mapping):
        raise _reject("policy", "obrigatória, com ao menos allowed_tools")
    unknown = sorted(str(key) for key in raw if key not in _POLICY_KEYS)
    if unknown:
        raise _reject(f"policy.{unknown[0]}", "chave desconhecida")
    values: dict[str, Any] = {key: raw[key] for key in _POLICY_KEYS if key in raw}
    for key in ("allowed_tools", "write_tools"):
        if key in values:
            if not isinstance(values[key], list):
                raise _reject(f"policy.{key}", "precisa ser uma lista de nomes")
            values[key] = tuple(cast("Sequence[str]", values[key]))
    if "allowed_tools" not in values:
        raise _reject("policy.allowed_tools", "obrigatória e não pode ser vazia")
    return SecurityPolicy(**values)

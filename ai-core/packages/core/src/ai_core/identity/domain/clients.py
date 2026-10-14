"""Leitura do `identity.yaml` do operador (FR-005; contracts/identity-yaml.md).

Recebe o mapeamento já carregado (o adapter lê o arquivo); erro de formato levanta `ClientsFileError` nomeando o campo.
Nenhum valor de segredo passa por aqui: `secret` é só a referência para `AI_CORE_IDENTITY_SECRET_<REF>`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Final
from urllib.parse import urlsplit

from ai_core.identity.api import ClientType
from ai_core.identity.domain.records import Client

CLIENT_ID_PATTERN: Final = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")
SECRET_REF_PATTERN: Final = re.compile(r"[a-z0-9_]{1,64}")
_CLIENT_TYPES: Final = ("confidential", "public")
_KEYS: Final = frozenset({"type", "secret", "audience", "redirect_uris", "post_logout_redirect_uris"})
_LOCAL_HOSTS: Final = frozenset({"localhost", "127.0.0.1", "[::1]", "::1"})


class ClientsFileError(ValueError):
    """`identity.yaml` inválido; a mensagem nomeia o campo (FR-005)."""


def secret_variable(ref: str) -> str:
    return f"AI_CORE_IDENTITY_SECRET_{ref.upper()}"


def read_clients(data: object, *, origin: str = "identity.yaml") -> tuple[Client, ...]:
    if not isinstance(data, Mapping):
        raise ClientsFileError(f"{origin}: o arquivo precisa ser um mapeamento com 'version' e 'clients'")
    unknown = sorted(set(map(str, data)) - {"version", "clients"})
    if unknown:
        raise ClientsFileError(f"{origin}: chave desconhecida: {unknown[0]}")
    if data.get("version") != 1:
        raise ClientsFileError(f"{origin}: version: só a versão 1 existe")
    entries = data.get("clients")
    if not isinstance(entries, Mapping) or not entries:
        raise ClientsFileError(f"{origin}: clients: declare ao menos um cliente")
    clients = tuple(_client(str(key), value, origin=origin) for key, value in entries.items())
    ids = {client.id for client in clients}
    for client in clients:
        if client.audience in ids:
            # Sem isso, um token de identidade (aud = client_id) se passaria por token de acesso.
            raise ClientsFileError(f"{origin}: clients.{client.id}.audience: não pode ser o id de um cliente")
    return clients


def redirect_origins(clients: Sequence[Client]) -> tuple[str, ...]:
    """Origens dos endereços de retorno, para o `form-action` da CSP das páginas (research R5)."""
    seen: dict[str, None] = {}
    for client in clients:
        for uri in client.redirect_uris:
            parts = urlsplit(uri)
            seen.setdefault(f"{parts.scheme}://{parts.netloc}", None)
    return tuple(seen)


def _client(client_id: str, value: object, *, origin: str) -> Client:
    where = f"{origin}: clients.{client_id}"
    if not CLIENT_ID_PATTERN.fullmatch(client_id):
        raise ClientsFileError(f"{where}: o id precisa casar com [a-z0-9][a-z0-9_-]{{0,63}}")
    if not isinstance(value, Mapping):
        raise ClientsFileError(f"{where}: precisa ser um mapeamento")
    unknown = sorted(set(map(str, value)) - _KEYS)
    if unknown:
        raise ClientsFileError(f"{where}.{unknown[0]}: chave desconhecida")
    kind = value.get("type")
    if kind not in _CLIENT_TYPES:
        raise ClientsFileError(f"{where}.type: obrigatório, 'confidential' ou 'public'")
    client_type: ClientType = "confidential" if kind == "confidential" else "public"
    secret = value.get("secret")
    if client_type == "confidential":
        if not isinstance(secret, str) or not SECRET_REF_PATTERN.fullmatch(secret):
            raise ClientsFileError(f"{where}.secret: obrigatório em cliente confidencial, no formato [a-z0-9_]{{1,64}}")
    elif secret is not None:
        raise ClientsFileError(f"{where}.secret: proibido em cliente público (PKCE no lugar do segredo)")
    audience = value.get("audience")
    if not isinstance(audience, str) or not audience.strip():
        raise ClientsFileError(f"{where}.audience: obrigatório")
    redirect_uris = _uris(value.get("redirect_uris"), field=f"{where}.redirect_uris", required=True)
    post_logout = _uris(value.get("post_logout_redirect_uris"), field=f"{where}.post_logout_redirect_uris")
    return Client(
        id=client_id,
        type=client_type,
        audience=audience,
        redirect_uris=redirect_uris,
        post_logout_redirect_uris=post_logout,
        secret_ref=secret if isinstance(secret, str) else None,
    )


def _uris(value: object, *, field: str, required: bool = False) -> tuple[str, ...]:
    if value is None:
        if required:
            raise ClientsFileError(f"{field}: declare ao menos um endereço")
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str) or (required and not value):
        raise ClientsFileError(f"{field}: precisa ser uma lista{' não vazia' if required else ''} de URIs")
    uris: list[str] = []
    for index, uri in enumerate(value):
        problem = _uri_problem(uri)
        if problem is not None:
            raise ClientsFileError(f"{field}[{index}]: {problem}")
        uris.append(uri)
    return tuple(uris)


def _uri_problem(uri: object) -> str | None:
    if not isinstance(uri, str):
        return "precisa ser texto"
    parts = urlsplit(uri)
    if parts.scheme not in ("https", "http") or not parts.hostname:
        return "precisa ser uma URI absoluta http(s)"
    if parts.fragment:
        return "não pode ter fragmento (#)"
    if parts.username or parts.password:
        return "não pode ter usuário nem senha"
    if parts.scheme == "http":
        host = parts.hostname
        if host not in _LOCAL_HOSTS and "." in host:
            return "http só para localhost, 127.0.0.1 ou nome sem ponto (rede interna)"
    return None

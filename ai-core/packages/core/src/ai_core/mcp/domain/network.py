"""A decisão de rede (contracts/network-policy.md; FR-009; research R5). Pura: recebe os IPs já resolvidos.

Quem a aplica é o transporte HTTP, a cada conexão, conectando no endereço que ela devolve — nunca deixando a biblioteca
resolver de novo. O critério é `is_global` (a definição da IANA de "alcançável na internet"), depois de extrair o IPv4
embutido em IPv4 mapeado, 6to4, Teredo e NAT64: uma lista de faixas mantida à mão esquece algum.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv6Address, IPv6Network, ip_address
from typing import Final

from ai_core.mcp.api import Scope

type IPAddress = IPv4Address | IPv6Address

NAT64: Final = IPv6Network("64:ff9b::/96")
"""Prefixo bem conhecido do NAT64: `is_global` o considera público, mas ele carrega um IPv4 nos últimos 32 bits."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Admission:
    """Permitido com o endereço a conectar, ou bloqueado com o motivo."""

    allowed: bool
    address: IPAddress | None = None
    reason: str | None = None


def normalize_host(host: str) -> str:
    return host.strip().strip("[]").lower().rstrip(".")


def admit(
    host: str,
    addresses: Sequence[IPAddress],
    *,
    scope: Scope,
    internal_hosts: frozenset[str],
    allowed_hosts: frozenset[str] | None,
) -> Admission:
    name = normalize_host(host)
    if scope == "global" and name in internal_hosts:
        # Exceção do operador (clarificação 2): o host é de confiança, resolva para onde resolver.
        if not addresses:
            return _blocked(f"destino bloqueado: '{name}' não resolveu")
        return Admission(allowed=True, address=addresses[0])
    if name == "localhost" or name.endswith(".localhost"):
        return _blocked(f"destino bloqueado: '{name}' é localhost")
    if allowed_hosts is not None and not host_matches(name, allowed_hosts):
        return _blocked(f"destino bloqueado: '{name}' está fora da allowlist de hosts do operador")
    if not addresses:
        return _blocked(f"destino bloqueado: '{name}' não resolveu")
    for address in addresses:
        problem = classify(address)
        if problem is not None:
            return _blocked(f"destino bloqueado: '{name}' resolve para {address} ({problem})")
    return Admission(allowed=True, address=addresses[0])


def host_matches(name: str, patterns: Iterable[str]) -> bool:
    """Nome exato, IP literal exato, ou `*.domínio` — os subdomínios, não o próprio domínio."""
    for pattern in patterns:
        if pattern.startswith("*."):
            if name.endswith(pattern[1:]) and name != pattern[2:]:
                return True
        elif name == pattern:
            return True
    return False


def classify(address: IPAddress) -> str | None:
    """`None` se o endereço é alcançável na internet; senão a classe que o bloqueia."""
    for candidate in _embedded(address):
        problem = _class_of(candidate)
        if problem is not None:
            return problem
    return None


def _embedded(address: IPAddress) -> list[IPAddress]:
    """O endereço e os IPv4 que ele carrega (mapeado, 6to4, Teredo, NAT64)."""
    found: list[IPAddress] = [address]
    if isinstance(address, IPv6Address):
        if address.ipv4_mapped is not None:
            found.append(address.ipv4_mapped)
        if address.sixtofour is not None:
            found.append(address.sixtofour)
        if address.teredo is not None:
            found.extend(address.teredo)
        if address in NAT64:
            found.append(ip_address(int(address) & 0xFFFFFFFF))
    return found


def _class_of(address: IPAddress) -> str | None:
    if address.is_multicast:
        # `is_global` aceita multicast; destino TCP de MCP nunca é.
        return "multicast"
    if address.is_global:
        return None
    if address.is_unspecified:
        return "não especificado"
    if address.is_loopback:
        return "loopback"
    if address.is_link_local:
        return "link-local"
    if address.is_private:
        return "privado"
    if address.is_reserved:
        return "reservado"
    return "não global"


def _blocked(reason: str) -> Admission:
    return Admission(allowed=False, reason=reason)

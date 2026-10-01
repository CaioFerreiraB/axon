"""`DnsResolver` pelo resolvedor do sistema (`getaddrinfo` do laço de eventos)."""

from __future__ import annotations

import asyncio
import socket
from collections.abc import Sequence
from ipaddress import IPv4Address, IPv6Address, ip_address


class SystemDnsResolver:
    async def resolve(self, host: str, port: int) -> Sequence[IPv4Address | IPv6Address]:
        try:
            return (ip_address(host.strip("[]")),)
        except ValueError:
            pass
        try:
            infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except (socket.gaierror, UnicodeError):
            return ()
        addresses: list[IPv4Address | IPv6Address] = []
        for _family, _type, _proto, _canon, sockaddr in infos:
            address = ip_address(str(sockaddr[0]).split("%", 1)[0])
            if address not in addresses:
                addresses.append(address)
        return tuple(addresses)

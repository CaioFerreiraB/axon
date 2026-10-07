"""T040 — a decisão de rede (contracts/network-policy.md; FR-009; SC-002), função pura, com a tabela de vetores."""

from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address, ip_address

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ai_core.mcp.domain.network import admit

pytestmark = pytest.mark.us6

PUBLICO = "93.184.216.34"
INTERNOS = frozenset({"mcp-financeiro", "10.0.5.20"})


def decide(host: str, *ips: str, scope: str = "user", allowed: frozenset[str] | None = None) -> tuple[bool, str | None]:
    admission = admit(
        host,
        [ip_address(ip) for ip in ips],
        scope=scope,  # type: ignore[arg-type]
        internal_hosts=INTERNOS,
        allowed_hosts=allowed,
    )
    return admission.allowed, admission.reason


VETORES = [
    ("loopback IPv4", "a.example", "127.0.0.1", "loopback"),
    ("loopback IPv4 outro", "a.example", "127.1.2.3", "loopback"),
    ("loopback IPv6", "a.example", "::1", "loopback"),
    ("privada 10/8", "a.example", "10.0.0.5", "privad"),
    ("privada 172.16/12", "a.example", "172.16.0.1", "privad"),
    ("privada 192.168/16", "a.example", "192.168.1.1", "privad"),
    ("metadados", "a.example", "169.254.169.254", "link-local"),
    ("link-local IPv6", "a.example", "fe80::1", "link-local"),
    ("CGNAT", "a.example", "100.64.0.1", "não global"),
    ("ULA / metadados IPv6", "a.example", "fd00:ec2::254", "privad"),
    ("não especificado v4", "a.example", "0.0.0.0", "não especificad"),
    ("não especificado v6", "a.example", "::", "não especificad"),
    ("IPv4 mapeado loopback", "a.example", "::ffff:127.0.0.1", "loopback"),
    ("IPv4 mapeado privado", "a.example", "::ffff:10.0.0.1", "privad"),
    ("6to4 com privada", "a.example", "2002:0a00:0001::", "privad"),
    ("NAT64 com loopback", "a.example", "64:ff9b::7f00:1", "loopback"),
    ("multicast", "a.example", "224.0.0.1", "multicast"),
    ("decimal na URL", "2130706433", "127.0.0.1", "loopback"),
    ("DNS para privada", "interno.exemplo.test", "10.0.0.7", "privad"),
]


@pytest.mark.parametrize(("nome", "host", "ip", "classe"), VETORES, ids=[v[0] for v in VETORES])
@pytest.mark.parametrize("scope", ["user", "global"])
def test_vetores_bloqueados_para_usuario_e_para_global_fora_dos_internos(
    nome: str, host: str, ip: str, classe: str, scope: str
) -> None:
    allowed, reason = decide(host, ip, scope=scope)
    assert not allowed, nome
    assert reason is not None and classe in reason and host in reason


@pytest.mark.parametrize("host", ["localhost", "LOCALHOST", "api.localhost", "localhost."])
def test_localhost_por_nome_e_bloqueado_antes_de_resolver(host: str) -> None:
    allowed, reason = decide(host, PUBLICO)
    assert not allowed and reason is not None and "localhost" in reason


def test_resposta_mista_e_bloqueada() -> None:
    allowed, reason = decide("misto.exemplo.test", PUBLICO, "10.0.0.7")
    assert not allowed and reason is not None and "10.0.0.7" in reason


def test_nome_que_nao_resolve_e_bloqueado() -> None:
    allowed, reason = decide("nada.exemplo.test")
    assert not allowed and reason is not None and "não resolveu" in reason


def test_publico_passa_nos_dois_escopos_e_devolve_o_endereco() -> None:
    for scope in ("user", "global"):
        admission = admit(
            "mcp.example",
            [ip_address(PUBLICO)],
            scope=scope,
            internal_hosts=INTERNOS,
            allowed_hosts=None,  # type: ignore[arg-type]
        )
        assert admission.allowed and admission.address == IPv4Address(PUBLICO)


def test_host_interno_so_para_global() -> None:
    """US6 cen. 3."""
    assert decide("mcp-financeiro", "10.0.5.20", scope="global")[0]
    assert decide("MCP-Financeiro.", "10.0.5.20", scope="global")[0], "comparação normalizada"
    assert decide("10.0.5.20", "10.0.5.20", scope="global")[0], "IP literal listado"
    assert not decide("mcp-financeiro", "10.0.5.20", scope="user")[0]


def test_interno_compara_o_host_e_nao_o_ip_resolvido() -> None:
    assert not decide("outro-nome", "10.0.5.20", scope="global")[0]


def test_metadados_por_global_sem_excecao() -> None:
    """US6 cen. 4."""
    allowed, reason = decide("169.254.169.254", "169.254.169.254", scope="global")
    assert not allowed and reason is not None and "link-local" in reason


# --- allowlist de hosts de destino (US6 cen. 5) -----------------------------------------------------------------------

EMPRESA = frozenset({"*.empresa.example", "mcp.parceiro.example", "93.184.216.34"})


@pytest.mark.parametrize("scope", ["user", "global"])
def test_allowlist_de_destino_vale_para_os_dois_escopos(scope: str) -> None:
    assert decide("mcp.empresa.example", PUBLICO, scope=scope, allowed=EMPRESA)[0]
    assert decide("a.b.empresa.example", PUBLICO, scope=scope, allowed=EMPRESA)[0]
    assert decide("mcp.parceiro.example", PUBLICO, scope=scope, allowed=EMPRESA)[0]
    for host in ("empresa.example", "outro.example", "xempresa.example", "parceiro.example"):
        allowed, reason = decide(host, PUBLICO, scope=scope, allowed=EMPRESA)
        assert not allowed and reason is not None and "allowlist" in reason, host


def test_ip_literal_na_allowlist_casa_so_ele_mesmo() -> None:
    assert decide("93.184.216.34", PUBLICO, allowed=EMPRESA)[0]
    assert not decide("93.184.216.35", "93.184.216.35", allowed=EMPRESA)[0]


def test_host_interno_de_global_passa_antes_da_allowlist() -> None:
    assert decide("mcp-financeiro", "10.0.5.20", scope="global", allowed=EMPRESA)[0]


def test_allowlist_nao_libera_faixa_privada() -> None:
    assert not decide("mcp.empresa.example", "10.0.0.7", allowed=EMPRESA)[0]


def test_sem_allowlist_nao_ha_restricao_por_nome() -> None:
    assert decide("qualquer.example", PUBLICO, allowed=None)[0]


# --- propriedade (hypothesis) -----------------------------------------------------------------------------------------


@given(st.ip_addresses(v=4))
def test_todo_ipv4_nao_global_e_bloqueado_para_usuario(address: IPv4Address) -> None:
    if not address.is_global:
        assert not admit("a.example", [address], scope="user", internal_hosts=INTERNOS, allowed_hosts=None).allowed


@given(st.ip_addresses(v=6))
def test_todo_ipv6_nao_global_e_bloqueado_para_usuario(address: IPv6Address) -> None:
    if not address.is_global:
        assert not admit("a.example", [address], scope="user", internal_hosts=INTERNOS, allowed_hosts=None).allowed

"""T010 — o arquivo do operador `mcp.yaml` (contracts/mcp-yaml.md), contra o adapter em memória e o YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import pytest
import yaml

from axon_ai.mcp.adapters.config_yaml import YamlMcpConfigSource
from axon_ai.mcp.api import McpConfigError
from axon_ai.mcp.domain.servers import read_config
from axon_ai.mcp.ports import McpConfig

pytestmark = pytest.mark.us1

EXEMPLO: Final = """
servers:
  financeiro:
    transport: http
    endpoint: http://mcp-financeiro:8080/mcp
    description: Saldos e extratos
    auth: { type: bearer, credential: financeiro_token }
    user_access: false
    enabled: true
    policy:
      timeout_ms: 10000
      max_response_bytes: 65536
      allowed_tools: [saldo, extrato]
      write_tools: []
  arquivos:
    transport: stdio
    command: /usr/local/bin/mcp-arquivos
    args: ["--raiz", "/dados"]
    env: { LOG_LEVEL: info }
    secrets: { TOKEN: arquivos_token }
    policy:
      allowed_tools: [ler, listar]
network:
  internal_hosts:
    - MCP-Financeiro
    - 10.0.5.20
  allowed_hosts:
    - "*.empresa.example"
    - mcp.parceiro.example
"""


def from_yaml(tmp_path: Path, text: str) -> McpConfig:
    path = tmp_path / "mcp.yaml"
    path.write_text(text, encoding="utf-8")
    return YamlMcpConfigSource(path).load()


def from_mapping(_tmp_path: Path, text: str) -> McpConfig:
    return read_config(yaml.safe_load(text), origin="configuração em memória")


SOURCES = pytest.mark.parametrize("load", [from_yaml, from_mapping], ids=["yaml", "memoria"])


@SOURCES
def test_o_exemplo_do_contrato_carrega(load: Any, tmp_path: Path) -> None:
    config = load(tmp_path, EXEMPLO)

    entries = {entry.alias: entry for entry in config.entries}
    assert set(entries) == {"financeiro", "arquivos"}
    financeiro = entries["financeiro"]
    assert financeiro.problem is None and financeiro.draft is not None
    assert financeiro.draft.auth_type == "bearer" and financeiro.draft.credential_ref == "financeiro_token"
    assert financeiro.draft.policy.allowed_tools == ("saldo", "extrato")
    arquivos = entries["arquivos"]
    assert arquivos.draft is not None and arquivos.draft.transport == "stdio" and arquivos.draft.endpoint is None
    assert arquivos.stdio is not None and arquivos.stdio.command == "/usr/local/bin/mcp-arquivos"
    assert arquivos.stdio.args == ("--raiz", "/dados")
    assert dict(arquivos.stdio.env) == {"LOG_LEVEL": "info"}
    assert dict(arquivos.stdio.secrets) == {"TOKEN": "arquivos_token"}
    assert config.internal_hosts == frozenset({"mcp-financeiro", "10.0.5.20"}), "normalizados em minúsculas"
    assert config.allowed_hosts == frozenset({"*.empresa.example", "mcp.parceiro.example"})


@SOURCES
def test_sem_network_nao_ha_excecoes_nem_allowlist(load: Any, tmp_path: Path) -> None:
    config = load(tmp_path, "servers: {}\n")
    assert config.internal_hosts == frozenset()
    assert config.allowed_hosts is None


@SOURCES
@pytest.mark.parametrize(
    ("texto", "trecho"),
    [
        ("- uma\n- lista\n", "raiz"),
        ("servidores: {}\n", "servidores"),
        ("servers: [a]\n", "servers"),
        ("network: [a]\n", "network"),
        ("network: { internal_hosts: x }\n", "internal_hosts"),
        ("network: { allowed_hosts: [] }\n", "allowed_hosts"),
        ("network: { allowed_hosts: ['http://x'] }\n", "allowed_hosts"),
        ("network: { allowed_hosts: ['*.'] }\n", "allowed_hosts"),
        ("network: { proxy: x }\n", "proxy"),
    ],
)
def test_erro_de_arquivo_levanta_nomeando_o_caminho(load: Any, tmp_path: Path, texto: str, trecho: str) -> None:
    with pytest.raises(McpConfigError, match=trecho):
        load(tmp_path, texto)


def test_yaml_invalido_e_arquivo_ausente(tmp_path: Path) -> None:
    with pytest.raises(McpConfigError):
        from_yaml(tmp_path, "servers: [\n")
    with pytest.raises(McpConfigError, match="não encontrado"):
        YamlMcpConfigSource(tmp_path / "nao-existe.yaml").load()


@SOURCES
@pytest.mark.parametrize(
    ("servidor", "trecho"),
    [
        ("{ transport: http, policy: { allowed_tools: [a] } }", "endpoint"),
        ("{ transport: stdio, policy: { allowed_tools: [a] } }", "command"),
        ("{ transport: stdio, command: x, endpoint: 'http://a', policy: { allowed_tools: [a] } }", "endpoint"),
        ("{ transport: http, endpoint: 'http://a', command: x, policy: { allowed_tools: [a] } }", "command"),
        ("{ transport: http, endpoint: 'http://a', policy: { allowed_tools: [] } }", "allowed_tools"),
        ("{ transport: http, endpoint: 'http://a', policy: { allowed_tools: [a] }, cor: azul }", "cor"),
        ("{ transport: http, endpoint: 'http://a' }", "policy"),
        ("{ transport: ws, endpoint: 'http://a', policy: { allowed_tools: [a] } }", "transport"),
        ("[nao, e, mapeamento]", "mapeamento"),
    ],
)
def test_erro_de_um_servidor_so_o_deixa_indisponivel(load: Any, tmp_path: Path, servidor: str, trecho: str) -> None:
    texto = (
        f"servers:\n  ruim: {servidor}\n"
        "  bom: { transport: http, endpoint: 'https://b.example/mcp', policy: { allowed_tools: [a] } }\n"
    )
    config = load(tmp_path, texto)

    entries = {entry.alias: entry for entry in config.entries}
    assert entries["bom"].problem is None
    assert entries["ruim"].draft is None and entries["ruim"].problem is not None
    assert trecho in entries["ruim"].problem


@SOURCES
def test_alias_invalido_no_arquivo_fica_indisponivel(load: Any, tmp_path: Path) -> None:
    texto = "servers:\n  '~meu': { transport: http, endpoint: 'https://b', policy: { allowed_tools: [a] } }\n"
    config = load(tmp_path, texto)
    (entry,) = config.entries
    assert entry.problem is not None and "alias" in entry.problem

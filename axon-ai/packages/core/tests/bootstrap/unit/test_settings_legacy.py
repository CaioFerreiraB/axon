"""T070 — a recusa dos nomes antigos do ambiente (research R48; contracts/configuration.md, incremento 9.5; US7).

Corte seco com diagnóstico (ADR-037, item 3): qualquer `AI_CORE_*` recusa a configuração antes da primeira etapa,
nomeando a variável nova e nunca o valor.
"""

from __future__ import annotations

import pytest

from axon_ai.bootstrap.settings import ConfigurationError, EnvConfigSource


def _recusa(environ: dict[str, str]) -> str:
    with pytest.raises(ConfigurationError) as erro:
        EnvConfigSource(environ).load()
    return str(erro.value)


def test_variavel_conhecida_com_o_nome_antigo_e_recusada_com_o_nome_novo() -> None:
    """US7 cen. 3."""
    mensagem = _recusa({"AI_CORE_PROFILE": "memory"})
    assert "AI_CORE_PROFILE → AXON_PROFILE" in mensagem and "ADR-037" in mensagem


def test_variavel_que_nunca_existiu_tambem_e_recusada() -> None:
    """A regra é pelo prefixo, não por uma lista."""
    assert "AI_CORE_FOO → AXON_FOO" in _recusa({"AI_CORE_FOO": "x"})


def test_variavel_vazia_tambem_e_recusada() -> None:
    assert "AI_CORE_PROFILE → AXON_PROFILE" in _recusa({"AI_CORE_PROFILE": ""})


def test_o_nome_antigo_e_recusado_mesmo_com_o_novo_definido() -> None:
    """US7 cen. 4: o nome antigo nunca é ignorado."""
    assert "AI_CORE_PROFILE → AXON_PROFILE" in _recusa({"AI_CORE_PROFILE": "memory", "AXON_PROFILE": "memory"})


def test_uma_linha_por_variavel_em_ordem_e_sem_os_valores() -> None:
    mensagem = _recusa(
        {
            "AI_CORE_PROFILE": "valor-do-perfil",
            "AI_CORE_MCP_SECRET_FINANCEIRO_TOKEN": "segredo-do-mcp",
            "AXON_PORT": "8000",
        }
    )
    linhas = [linha.strip() for linha in mensagem.splitlines()[1:]]
    assert linhas == [
        "AI_CORE_MCP_SECRET_FINANCEIRO_TOKEN → AXON_MCP_SECRET_FINANCEIRO_TOKEN",
        "AI_CORE_PROFILE → AXON_PROFILE",
    ]
    assert "segredo-do-mcp" not in mensagem and "valor-do-perfil" not in mensagem


@pytest.mark.parametrize("nome", ["AI_COREX", "MY_AI_CORE_URL", "AI_SCOUTING_INDEX"])
def test_nomes_parecidos_nao_sao_do_core(nome: str) -> None:
    """Casos de borda: só o prefixo `AI_CORE_` é recusado; `AI_SCOUTING_*` é do pack (101)."""
    assert EnvConfigSource({nome: "x"}).load().profile == "memory"
